# main.py - Vega Delta Neutral Trading Platform
import sys
import threading
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
                             QPushButton, QLabel, QLineEdit, QComboBox, QSpinBox,
                             QDoubleSpinBox, QTextEdit, QSplitter, QHeaderView,
                             QGroupBox, QGridLayout, QMessageBox, QProgressBar)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QBrush
from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.contract import Contract, ContractDetails
from ibapi.order import Order
from ibapi.common import TickerId
from ibapi.ticktype import TickTypeEnum
import logging
from collections import deque
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VegaDeltaNeutralApp(EWrapper, EClient):
    """
    Vega Delta Neutral IB API Application
    """
    def __init__(self):
        EClient.__init__(self, self)
        self.nextOrderId = None
        self.contract_details = {}
        self.market_data = {}
        self.positions = {}
        self.orders = {}
        self.account_values = {}
        self.portfolio_items = {}
        self.greeks_data = {}
        self.volatility_data = {}
        self.current_reqId = 1
        
        # Strategy parameters
        self.target_vega = 0
        self.max_delta = 10  # Maximum allowed delta
        self.vega_target = 500  # Target vega exposure
        self.hedge_ratio = 1.0
        
    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.nextOrderId = orderId
        logger.info(f"NextValidId: {orderId}")

    def error(self, reqId: TickerId, errorCode: int, errorString: str):
        logger.error(f"Error {errorCode}: {errorString}")

    def tickPrice(self, reqId: TickerId, tickType: int, price: float, attrib):
        self.market_data[reqId] = self.market_data.get(reqId, {})
        field = TickTypeEnum.to_str(tickType)
        self.market_data[reqId][field] = price
        logger.debug(f"TickPrice. ReqId: {reqId}, Field: {field}, Price: {price}")

    def tickSize(self, reqId: TickerId, tickType: int, size: int):
        self.market_data[reqId] = self.market_data.get(reqId, {})
        field = TickTypeEnum.to_str(tickType)
        self.market_data[reqId][field] = size

    def tickOptionComputation(self, reqId: TickerId, tickType: int, 
                            impliedVol: float, delta: float, optPrice: float,
                            pvDividend: float, gamma: float, vega: float,
                            theta: float, undPrice: float):
        """Receive option Greeks"""
        self.greeks_data[reqId] = {
            'impliedVol': impliedVol,
            'delta': delta,
            'gamma': gamma,
            'vega': vega,
            'theta': theta,
            'undPrice': undPrice,
            'optPrice': optPrice
        }

    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        key = f"{contract.symbol}_{contract.secType}"
        self.positions[key] = {
            'account': account,
            'contract': contract,
            'position': position,
            'avgCost': avgCost,
            'marketValue': position * avgCost
        }

    def orderStatus(self, orderId: int, status: str, filled: float, remaining: float, 
                   avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float, 
                   clientId: int, whyHeld: str, mktCapPrice: float):
        self.orders[orderId] = {
            'status': status,
            'filled': filled,
            'remaining': remaining,
            'avgFillPrice': avgFillPrice,
            'lastFillPrice': lastFillPrice
        }
        logger.info(f"Order {orderId} status: {status}")

    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str):
        self.account_values[key] = val

    def updatePortfolio(self, contract: Contract, position: float, marketPrice: float, 
                       marketValue: float, averageCost: float, unrealizedPNL: float, 
                       realizedPNL: float, accountName: str):
        key = f"{contract.symbol}_{contract.secType}"
        self.portfolio_items[key] = {
            'contract': contract,
            'position': position,
            'marketPrice': marketPrice,
            'marketValue': marketValue,
            'averageCost': averageCost,
            'unrealizedPNL': unrealizedPNL,
            'realizedPNL': realizedPNL
        }

class VegaDeltaNeutralEngine:
    """
    Core engine for Vega Delta Neutral strategy
    """
    def __init__(self, ib_app):
        self.ib_app = ib_app
        self.active_positions = {}
        self.hedge_positions = {}
        self.portfolio_greeks = {
            'delta': 0,
            'gamma': 0,
            'vega': 0,
            'theta': 0
        }
        
    def calculate_strangle_position(self, symbol, expiration_days, target_vega=500):
        """
        Calculate strangle position size to achieve target vega
        """
        try:
            # Get ATM strikes
            atm_strike = self.get_atm_strike(symbol)
            call_strike = atm_strike * 1.02  # 2% OTM
            put_strike = atm_strike * 0.98   # 2% OTM
            
            # Get option Greeks
            call_vega = self.get_option_vega(symbol, expiration_days, call_strike, "C")
            put_vega = self.get_option_vega(symbol, expiration_days, put_strike, "P")
            
            if call_vega and put_vega:
                # Calculate position size to achieve target vega
                avg_vega = (call_vega + put_vega) / 2
                contracts_needed = int(target_vega / avg_vega)
                
                return {
                    'symbol': symbol,
                    'expiration_days': expiration_days,
                    'call_strike': call_strike,
                    'put_strike': put_strike,
                    'call_vega': call_vega,
                    'put_vega': put_vega,
                    'contracts_needed': contracts_needed,
                    'total_vega': contracts_needed * (call_vega + put_vega)
                }
            
        except Exception as e:
            logger.error(f"Error calculating strangle: {e}")
        return None

    def get_atm_strike(self, symbol):
        """Get ATM strike price based on current underlying price"""
        # This would use real market data - simplified for example
        if symbol == "SPY":
            return 450.0  # Example
        return 100.0

    def get_option_vega(self, symbol, expiration_days, strike, right):
        """Get vega for specific option - would use real market data"""
        # Simplified - in reality, you'd request real option Greeks from IB
        base_vega = 0.15  # Example base vega for ATM options
        return base_vega

    def calculate_delta_hedge(self, option_delta, contracts):
        """Calculate shares needed for delta hedge"""
        total_delta = option_delta * contracts * 100  # Option multiplier
        shares_needed = -total_delta  # Negative to hedge
        return shares_needed

    def execute_vega_delta_neutral_trade(self, trade_params):
        """
        Execute complete vega delta neutral trade
        """
        try:
            symbol = trade_params['symbol']
            contracts = trade_params['contracts_needed']
            call_strike = trade_params['call_strike']
            put_strike = trade_params['put_strike']
            expiration = trade_params['expiration_days']
            
            # 1. Buy strangle (long vega)
            call_contract = self.create_option_contract(symbol, expiration, call_strike, "C")
            put_contract = self.create_option_contract(symbol, expiration, put_strike, "P")
            
            # 2. Calculate initial delta hedge
            call_delta = 0.45  # Example - would be real data
            put_delta = -0.45  # Example - would be real data
            total_delta = (call_delta + put_delta) * contracts * 100
            hedge_shares = -total_delta
            
            # 3. Execute trades
            trade_id = f"VEGA_{symbol}_{int(time.time())}"
            
            self.active_positions[trade_id] = {
                'trade_id': trade_id,
                'symbol': symbol,
                'strangle_contracts': contracts,
                'call_strike': call_strike,
                'put_strike': put_strike,
                'current_delta': total_delta,
                'target_delta': 0,
                'hedge_shares': hedge_shares,
                'vega_exposure': trade_params['total_vega'],
                'status': 'active',
                'entry_time': datetime.now()
            }
            
            logger.info(f"Executed Vega Delta Neutral trade: {trade_id}")
            return trade_id
            
        except Exception as e:
            logger.error(f"Error executing vega trade: {e}")
            return None

    def monitor_and_hedge(self):
        """
        Monitor positions and adjust delta hedge
        """
        for trade_id, position in self.active_positions.items():
            if position['status'] == 'active':
                current_delta = position['current_delta']
                
                # Check if delta hedge needed
                if abs(current_delta) > self.ib_app.max_delta:
                    self.adjust_delta_hedge(trade_id, current_delta)

    def adjust_delta_hedge(self, trade_id, current_delta):
        """Adjust delta hedge to maintain neutrality"""
        try:
            position = self.active_positions[trade_id]
            symbol = position['symbol']
            
            # Calculate hedge adjustment
            hedge_adjustment = -current_delta  # Opposite sign to neutralize
            
            # Execute hedge trade
            logger.info(f"Adjusting delta hedge for {trade_id}: {hedge_adjustment} shares")
            
            # Update position
            position['current_delta'] += hedge_adjustment
            position['hedge_shares'] += hedge_adjustment
            
        except Exception as e:
            logger.error(f"Error adjusting delta hedge: {e}")

    def create_option_contract(self, symbol, expiration_days, strike, right):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "OPT"
        contract.exchange = "SMART"
        contract.currency = "USD"
        contract.lastTradeDateOrContractMonth = self.calculate_expiration(expiration_days)
        contract.strike = strike
        contract.right = right
        contract.multiplier = "100"
        return contract

    def create_stock_contract(self, symbol):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract

    def calculate_expiration(self, days_out):
        expiration = datetime.now() + timedelta(days=days_out)
        return expiration.strftime("%Y%m%d")

class VegaScannerThread(QThread):
    """
    Thread for scanning Vega Delta Neutral opportunities
    """
    scan_complete = pyqtSignal(dict)
    
    def __init__(self, ib_app, scanner_engine):
        super().__init__()
        self.ib_app = ib_app
        self.scanner_engine = scanner_engine
        
    def run(self):
        try:
            opportunities = self.scan_vega_opportunities()
            self.scan_complete.emit(opportunities)
        except Exception as e:
            logger.error(f"Scan error: {e}")

    def scan_vega_opportunities(self):
        """
        Scan for optimal Vega Delta Neutral opportunities
        """
        opportunities = {}
        
        # Focus on high liquidity underlyings
        symbols = ["SPY", "QQQ", "IWM", "DIA"]
        
        for symbol in symbols:
            # Look for 30-45 DTE for optimal vega exposure
            for dte in [30, 45, 60]:
                opportunity = self.analyze_vega_opportunity(symbol, dte)
                if opportunity and opportunity['score'] > 7:
                    opportunities[f"{symbol}_{dte}D"] = opportunity
        
        return opportunities

    def analyze_vega_opportunity(self, symbol, dte):
        """
        Analyze specific symbol/DTE for vega opportunity
        """
        try:
            # Calculate theoretical position
            position_data = self.scanner_engine.calculate_strangle_position(symbol, dte)
            
            if position_data:
                # Score opportunity based on multiple factors
                score = self.calculate_opportunity_score(symbol, dte, position_data)
                
                return {
                    'symbol': symbol,
                    'dte': dte,
                    'contracts_needed': position_data['contracts_needed'],
                    'estimated_vega': position_data['total_vega'],
                    'capital_required': position_data['contracts_needed'] * 2000,  # Approximate
                    'score': score,
                    'analysis_time': datetime.now()
                }
                
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
        
        return None

    def calculate_opportunity_score(self, symbol, dte, position_data):
        """
        Calculate opportunity score (1-10)
        """
        score = 5  # Base score
        
        # Factor 1: DTE optimality (30-45 DTE is ideal)
        if 30 <= dte <= 45:
            score += 2
        elif 20 <= dte <= 60:
            score += 1
            
        # Factor 2: Contract count (manageable size)
        contracts = position_data['contracts_needed']
        if 5 <= contracts <= 20:
            score += 2
        elif contracts <= 40:
            score += 1
            
        # Factor 3: Vega exposure (target ~500)
        vega = position_data['total_vega']
        if 400 <= vega <= 600:
            score += 2
        elif 300 <= vega <= 700:
            score += 1
            
        return min(score, 10)  # Cap at 10

class GreeksChart(FigureCanvas):
    """
    Real-time Greeks monitoring chart
    """
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        
        # Create subplots for different Greeks
        self.axes_delta = self.fig.add_subplot(221)
        self.axes_gamma = self.fig.add_subplot(222)
        self.axes_vega = self.fig.add_subplot(223)
        self.axes_theta = self.fig.add_subplot(224)
        
        self.setup_charts()
        self.greeks_history = {
            'delta': deque(maxlen=100),
            'gamma': deque(maxlen=100),
            'vega': deque(maxlen=100),
            'theta': deque(maxlen=100),
            'time': deque(maxlen=100)
        }
        
    def setup_charts(self):
        """Initialize chart formatting"""
        self.axes_delta.set_title('Portfolio Delta')
        self.axes_delta.set_ylabel('Delta')
        self.axes_delta.grid(True)
        
        self.axes_gamma.set_title('Portfolio Gamma')
        self.axes_gamma.set_ylabel('Gamma')
        self.axes_gamma.grid(True)
        
        self.axes_vega.set_title('Portfolio Vega')
        self.axes_vega.set_ylabel('Vega')
        self.axes_vega.grid(True)
        
        self.axes_theta.set_title('Portfolio Theta')
        self.axes_theta.set_ylabel('Theta')
        self.axes_theta.grid(True)
        
        self.fig.tight_layout()

    def update_greeks(self, greeks_data):
        """Update charts with new Greeks data"""
        current_time = datetime.now()
        
        self.greeks_history['time'].append(current_time)
        self.greeks_history['delta'].append(greeks_data.get('delta', 0))
        self.greeks_history['gamma'].append(greeks_data.get('gamma', 0))
        self.greeks_history['vega'].append(greeks_data.get('vega', 0))
        self.greeks_history['theta'].append(greeks_data.get('theta', 0))
        
        # Update plots
        times = list(self.greeks_history['time'])
        self.axes_delta.clear()
        self.axes_delta.plot(times, list(self.greeks_history['delta']), 'b-', linewidth=2)
        self.axes_delta.set_title('Portfolio Delta')
        self.axes_delta.grid(True)
        
        self.axes_gamma.clear()
        self.axes_gamma.plot(times, list(self.greeks_history['gamma']), 'g-', linewidth=2)
        self.axes_gamma.set_title('Portfolio Gamma')
        self.axes_gamma.grid(True)
        
        self.axes_vega.clear()
        self.axes_vega.plot(times, list(self.greeks_history['vega']), 'r-', linewidth=2)
        self.axes_vega.set_title('Portfolio Vega')
        self.axes_vega.grid(True)
        
        self.axes_theta.clear()
        self.axes_theta.plot(times, list(self.greeks_history['theta']), 'orange', linewidth=2)
        self.axes_theta.set_title('Portfolio Theta')
        self.axes_theta.grid(True)
        
        self.fig.tight_layout()
        self.draw()

class VegaDeltaNeutralWindow(QMainWindow):
    """
    Main Vega Delta Neutral Trading Window
    """
    def __init__(self):
        super().__init__()
        self.ib_app = VegaDeltaNeutralApp()
        self.trading_engine = VegaDeltaNeutralEngine(self.ib_app)
        self.scanner_thread = None
        self.init_ui()
        self.setup_connections()
        
    def init_ui(self):
        self.setWindowTitle("Vega Delta Neutral Trading Platform")
        self.setGeometry(100, 100, 1600, 1000)
        
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Initialize specialized tabs
        self.setup_vega_scanner_tab()
        self.setup_position_manager_tab()
        self.setup_greeks_monitor_tab()
        self.setup_hedge_control_tab()
        
        # Status bar
        self.statusBar().showMessage("Vega Delta Neutral Platform Ready")
        
        # Start monitoring timer
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.monitor_positions)
        self.monitor_timer.start(2000)  # Update every 2 seconds

    def setup_vega_scanner_tab(self):
        """Setup the Vega opportunity scanner tab"""
        scanner_widget = QWidget()
        layout = QVBoxLayout(scanner_widget)
        
        # Scanner controls
        controls_group = QGroupBox("Vega Scanner Controls")
        controls_layout = QGridLayout(controls_group)
        
        self.vega_target_input = QDoubleSpinBox()
        self.vega_target_input.setRange(100, 2000)
        self.vega_target_input.setValue(500)
        self.vega_target_input.setSuffix(" vega")
        
        self.max_delta_input = QDoubleSpinBox()
        self.max_delta_input.setRange(1, 50)
        self.max_delta_input.setValue(10)
        
        self.dte_range_input = QComboBox()
        self.dte_range_input.addItems(["30-45 DTE", "45-60 DTE", "30-60 DTE"])
        
        self.scan_button = QPushButton("Scan Vega Opportunities")
        self.scan_button.clicked.connect(self.run_vega_scan)
        
        controls_layout.addWidget(QLabel("Target Vega:"), 0, 0)
        controls_layout.addWidget(self.vega_target_input, 0, 1)
        controls_layout.addWidget(QLabel("Max Delta:"), 1, 0)
        controls_layout.addWidget(self.max_delta_input, 1, 1)
        controls_layout.addWidget(QLabel("DTE Range:"), 2, 0)
        controls_layout.addWidget(self.dte_range_input, 2, 1)
        controls_layout.addWidget(self.scan_button, 3, 0, 1, 2)
        
        # Opportunities table
        self.opportunities_table = QTableWidget()
        self.opportunities_table.setColumnCount(7)
        self.opportunities_table.setHorizontalHeaderLabels([
            "Symbol", "DTE", "Contracts", "Vega", "Capital", "Score", "Action"
        ])
        
        # Add to layout
        layout.addWidget(controls_group)
        layout.addWidget(QLabel("Vega Opportunities:"))
        layout.addWidget(self.opportunities_table)
        
        self.tabs.addTab(scanner_widget, "Vega Scanner")

    def setup_position_manager_tab(self):
        """Setup position management tab"""
        position_widget = QWidget()
        layout = QVBoxLayout(position_widget)
        
        # Active positions table
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(10)
        self.positions_table.setHorizontalHeaderLabels([
            "ID", "Symbol", "Contracts", "Call Strike", "Put Strike", 
            "Current Delta", "Hedge Shares", "Vega", "Status", "Actions"
        ])
        
        # Position controls
        controls_group = QGroupBox("Position Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        self.auto_hedge_check = QPushButton("Auto-Hedge: OFF")
        self.auto_hedge_check.setCheckable(True)
        self.auto_hedge_check.clicked.connect(self.toggle_auto_hedge)
        
        self.close_all_button = QPushButton("Close All Positions")
        self.close_all_button.clicked.connect(self.close_all_positions)
        
        self.hedge_now_button = QPushButton("Hedge Now")
        self.hedge_now_button.clicked.connect(self.manual_hedge)
        
        controls_layout.addWidget(self.auto_hedge_check)
        controls_layout.addWidget(self.hedge_now_button)
        controls_layout.addWidget(self.close_all_button)
        controls_layout.addStretch()
        
        layout.addWidget(controls_group)
        layout.addWidget(QLabel("Active Vega Positions:"))
        layout.addWidget(self.positions_table)
        
        self.tabs.addTab(position_widget, "Position Manager")

    def setup_greeks_monitor_tab(self):
        """Setup real-time Greeks monitoring tab"""
        greeks_widget = QWidget()
        layout = QVBoxLayout(greeks_widget)
        
        # Greeks chart
        self.greeks_chart = GreeksChart(self, width=10, height=8, dpi=100)
        
        # Greeks summary
        summary_group = QGroupBox("Portfolio Greeks Summary")
        summary_layout = QGridLayout(summary_group)
        
        self.delta_label = QLabel("Delta: 0")
        self.gamma_label = QLabel("Gamma: 0")
        self.vega_label = QLabel("Vega: 0")
        self.theta_label = QLabel("Theta: 0")
        
        summary_layout.addWidget(self.delta_label, 0, 0)
        summary_layout.addWidget(self.gamma_label, 0, 1)
        summary_layout.addWidget(self.vega_label, 1, 0)
        summary_layout.addWidget(self.theta_label, 1, 1)
        
        layout.addWidget(summary_group)
        layout.addWidget(self.greeks_chart)
        
        self.tabs.addTab(greeks_widget, "Greeks Monitor")

    def setup_hedge_control_tab(self):
        """Setup advanced hedge controls"""
        hedge_widget = QWidget()
        layout = QVBoxLayout(hedge_widget)
        
        # Hedge parameters
        params_group = QGroupBox("Hedge Parameters")
        params_layout = QGridLayout(params_group)
        
        self.hedge_threshold_input = QDoubleSpinBox()
        self.hedge_threshold_input.setRange(1, 20)
        self.hedge_threshold_input.setValue(5)
        self.hedge_threshold_input.setSuffix(" delta")
        
        self.hedge_frequency_input = QSpinBox()
        self.hedge_frequency_input.setRange(1, 60)
        self.hedge_frequency_input.setValue(5)
        self.hedge_frequency_input.setSuffix(" min")
        
        self.volatility_alert_input = QDoubleSpinBox()
        self.volatility_alert_input.setRange(5, 50)
        self.volatility_alert_input.setValue(20)
        self.volatility_alert_input.setSuffix("% IV change")
        
        params_layout.addWidget(QLabel("Hedge Threshold:"), 0, 0)
        params_layout.addWidget(self.hedge_threshold_input, 0, 1)
        params_layout.addWidget(QLabel("Hedge Frequency:"), 1, 0)
        params_layout.addWidget(self.hedge_frequency_input, 1, 1)
        params_layout.addWidget(QLabel("Volatility Alert:"), 2, 0)
        params_layout.addWidget(self.volatility_alert_input, 2, 1)
        
        # Hedge log
        self.hedge_log = QTextEdit()
        self.hedge_log.setMaximumHeight(200)
        
        layout.addWidget(params_group)
        layout.addWidget(QLabel("Hedge Activity Log:"))
        layout.addWidget(self.hedge_log)
        
        self.tabs.addTab(hedge_widget, "Hedge Control")

    def setup_connections(self):
        """Setup signal connections"""
        # Scanner thread connection
        self.scanner_thread = VegaScannerThread(self.ib_app, self.trading_engine)
        self.scanner_thread.scan_complete.connect(self.display_vega_opportunities)

    def run_vega_scan(self):
        """Run Vega opportunity scan"""
        self.statusBar().showMessage("Scanning for Vega opportunities...")
        self.ib_app.vega_target = self.vega_target_input.value()
        self.ib_app.max_delta = self.max_delta_input.value()
        
        if not self.scanner_thread.isRunning():
            self.scanner_thread.start()

    def display_vega_opportunities(self, opportunities):
        """Display scanned Vega opportunities"""
        self.opportunities_table.setRowCount(0)
        
        for row, (key, opp) in enumerate(opportunities.items()):
            self.opportunities_table.insertRow(row)
            
            self.opportunities_table.setItem(row, 0, QTableWidgetItem(opp['symbol']))
            self.opportunities_table.setItem(row, 1, QTableWidgetItem(str(opp['dte'])))
            self.opportunities_table.setItem(row, 2, QTableWidgetItem(str(opp['contracts_needed'])))
            self.opportunities_table.setItem(row, 3, QTableWidgetItem(f"{opp['estimated_vega']:.0f}"))
            self.opportunities_table.setItem(row, 4, QTableWidgetItem(f"${opp['capital_required']:,.0f}"))
            self.opportunities_table.setItem(row, 5, QTableWidgetItem(f"{opp['score']}/10"))
            
            # Add execute button
            execute_btn = QPushButton("Execute")
            execute_btn.clicked.connect(lambda checked, opp=opp: self.execute_vega_trade(opp))
            self.opportunities_table.setCellWidget(row, 6, execute_btn)
        
        self.statusBar().showMessage(f"Found {len(opportunities)} Vega opportunities")

    def execute_vega_trade(self, opportunity):
        """Execute Vega Delta Neutral trade"""
        try:
            # Calculate precise position
            position_data = self.trading_engine.calculate_strangle_position(
                opportunity['symbol'], 
                opportunity['dte'],
                self.ib_app.vega_target
            )
            
            if position_data:
                trade_id = self.trading_engine.execute_vega_delta_neutral_trade(position_data)
                if trade_id:
                    QMessageBox.information(self, "Trade Executed", 
                                          f"Vega Delta Neutral trade executed: {trade_id}")
                    self.log_hedge_activity(f"EXECUTED: {trade_id}")
                else:
                    QMessageBox.warning(self, "Execution Failed", "Failed to execute trade")
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Trade execution error: {str(e)}")

    def monitor_positions(self):
        """Monitor and update positions display"""
        self.update_positions_table()
        self.update_greeks_display()
        self.trading_engine.monitor_and_hedge()

    def update_positions_table(self):
        """Update positions table with current data"""
        self.positions_table.setRowCount(0)
        
        for row, (trade_id, position) in enumerate(self.trading_engine.active_positions.items()):
            self.positions_table.insertRow(row)
            
            self.positions_table.setItem(row, 0, QTableWidgetItem(trade_id))
            self.positions_table.setItem(row, 1, QTableWidgetItem(position['symbol']))
            self.positions_table.setItem(row, 2, QTableWidgetItem(str(position['strangle_contracts'])))
            self.positions_table.setItem(row, 3, QTableWidgetItem(f"{position['call_strike']:.2f}"))
            self.positions_table.setItem(row, 4, QTableWidgetItem(f"{position['put_strike']:.2f}"))
            self.positions_table.setItem(row, 5, QTableWidgetItem(f"{position['current_delta']:.1f}"))
            self.positions_table.setItem(row, 6, QTableWidgetItem(f"{position['hedge_shares']:.0f}"))
            self.positions_table.setItem(row, 7, QTableWidgetItem(f"{position['vega_exposure']:.0f}"))
            self.positions_table.setItem(row, 8, QTableWidgetItem(position['status']))
            
            # Add close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(lambda checked, tid=trade_id: self.close_position(tid))
            self.positions_table.setCellWidget(row, 9, close_btn)

    def update_greeks_display(self):
        """Update Greeks display and chart"""
        # Calculate portfolio Greeks (simplified)
        portfolio_greeks = {
            'delta': sum(pos['current_delta'] for pos in self.trading_engine.active_positions.values()),
            'vega': sum(pos['vega_exposure'] for pos in self.trading_engine.active_positions.values()),
            'gamma': 0,  # Would need real gamma calculation
            'theta': 0   # Would need real theta calculation
        }
        
        # Update labels
        self.delta_label.setText(f"Delta: {portfolio_greeks['delta']:.1f}")
        self.gamma_label.setText(f"Gamma: {portfolio_greeks['gamma']:.1f}")
        self.vega_label.setText(f"Vega: {portfolio_greeks['vega']:.0f}")
        self.theta_label.setText(f"Theta: {portfolio_greeks['theta']:.1f}")
        
        # Update chart
        self.greeks_chart.update_greeks(portfolio_greeks)

    def toggle_auto_hedge(self, checked):
        """Toggle auto-hedging"""
        if checked:
            self.auto_hedge_check.setText("Auto-Hedge: ON")
            self.auto_hedge_check.setStyleSheet("background-color: green; color: white;")
        else:
            self.auto_hedge_check.setText("Auto-Hedge: OFF")
            self.auto_hedge_check.setStyleSheet("")

    def manual_hedge(self):
        """Manual hedge all positions"""
        for trade_id in self.trading_engine.active_positions.keys():
            position = self.trading_engine.active_positions[trade_id]
            if abs(position['current_delta']) > self.ib_app.max_delta:
                self.trading_engine.adjust_delta_hedge(trade_id, position['current_delta'])
                self.log_hedge_activity(f"MANUAL HEDGE: {trade_id}")

    def close_position(self, trade_id):
        """Close specific position"""
        try:
            if trade_id in self.trading_engine.active_positions:
                del self.trading_engine.active_positions[trade_id]
                self.log_hedge_activity(f"CLOSED: {trade_id}")
                QMessageBox.information(self, "Position Closed", f"Closed position: {trade_id}")
        except Exception as e:
            QMessageBox.warning(self, "Close Error", f"Error closing position: {str(e)}")

    def close_all_positions(self):
        """Close all active positions"""
        reply = QMessageBox.question(self, "Close All", 
                                   "Close all Vega Delta Neutral positions?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.trading_engine.active_positions.clear()
            self.log_hedge_activity("CLOSED ALL POSITIONS")

    def log_hedge_activity(self, message):
        """Log hedge activity"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.hedge_log.append(f"[{timestamp}] {message}")

    def connect_ib(self):
        """Connect to Interactive Brokers"""
        try:
            # Run IB client in separate thread
            def run_ib():
                self.ib_app.connect("127.0.0.1", 7497, clientId=1)  # TWS port
                self.ib_app.run()
            
            ib_thread = threading.Thread(target=run_ib, daemon=True)
            ib_thread.start()
            
            self.statusBar().showMessage("Connecting to IB...")
            
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to IB: {str(e)}")

def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = VegaDeltaNeutralWindow()
    window.show()
    
    # Connect to IB after window is shown
    QTimer.singleShot(1000, window.connect_ib)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()