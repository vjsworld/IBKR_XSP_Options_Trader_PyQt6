"""
SPX 0DTE Options Trading Application - PyQt6 Edition
Professional Bloomberg-style GUI for Interactive Brokers API
Author: VJS World
Date: October 24, 2025

Technology Stack:
- PyQt6: Modern GUI framework with native performance
- lightweight-charts: TradingView charting library for real-time candlesticks
- IBKR API: Real-time market data and order execution
- Black-Scholes: Greeks calculations for options analysis
"""

import sys
import json
import math
import threading
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum
from collections import defaultdict


# ============================================================================
# LOGGING SYSTEM - Setup FIRST before any other imports
# ============================================================================

def setup_logging():
    """
    Setup comprehensive logging system with daily log files
    
    Creates logs in ./logs/ directory with format: YYYY-MM-DD.log
    Configures both file and console logging with different levels
    """
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Log filename: today's date
    log_filename = datetime.now().strftime("%Y-%m-%d.log")
    log_path = log_dir / log_filename
    
    # Create logger
    logger = logging.getLogger("SPXTrader")
    logger.setLevel(logging.DEBUG)  # Capture everything
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # File handler - DEBUG level (everything)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10*1024*1024,  # 10MB per file
        backupCount=30,  # Keep 30 days of logs
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler - INFO level (less verbose)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Log startup
    logger.info("="*70)
    logger.info("SPX 0DTE Options Trading Application - PyQt6 Edition")
    logger.info("="*70)
    logger.info(f"Log file: {log_path}")
    logger.info(f"Python version: {sys.version}")
    
    return logger


# Initialize logger (will be used throughout the app)
logger = setup_logging()

# PyQt6 imports - with error handling
logger.info("Loading PyQt6 modules...")
try:
    from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QTextEdit, QSplitter, QFrame, QGridLayout,
    QHeaderView, QMessageBox, QDialog, QFormLayout, QDialogButtonBox,
    QStatusBar, QGroupBox
)
    from PyQt6.QtCore import (  # type: ignore[import-untyped]
        Qt, QTimer, pyqtSignal, QObject, QThread, pyqtSlot
    )
    from PyQt6.QtGui import QColor, QFont, QPalette  # type: ignore[import-untyped]
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore[import-untyped]
    logger.info("PyQt6 loaded successfully")
    PYQT6_AVAILABLE = True
except ImportError as e:
    PYQT6_AVAILABLE = False
    logger.critical(f"PyQt6 import failed: {e}", exc_info=True)
    print("="*70)
    print("ERROR: PyQt6 is not installed!")
    print("="*70)
    print(f"Import error: {e}")
    print("\nTo install dependencies, run:")
    print("  .\\setup.ps1")
    print("\nOr manually:")
    print("  .venv\\Scripts\\Activate.ps1")
    print("  pip install -r requirements.txt")
    print("="*70)
    sys.exit(1)

# Data processing
logger.info("Loading data processing libraries (pandas, numpy)...")
import pandas as pd  # type: ignore[import-untyped]
import numpy as np  # type: ignore[import-untyped]
logger.info("Data processing libraries loaded successfully")

# Interactive Brokers API
logger.info("Loading IBKR API modules...")
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.common import TickerId, TickAttrib
from ibapi.ticktype import TickType
logger.info("IBKR API loaded successfully")

# lightweight-charts (will be integrated in chart widgets)
logger.info("Loading lightweight-charts...")
try:
    from lightweight_charts import Chart  # type: ignore[import-untyped]
    CHARTS_AVAILABLE = True
except ImportError:
    Chart = None  # Define as None when not available
    CHARTS_AVAILABLE = False
    logger.warning("lightweight-charts not installed. Charts will be disabled.")


# ============================================================================
# INSTRUMENT CONFIGURATION - Dual-Instrument Support
# ============================================================================

INSTRUMENT_CONFIG = {
    'SPX': {
        'name': 'SPX',
        'underlying_symbol': 'SPX',          # Index symbol
        'options_symbol': 'SPX',             # Options symbol  
        'options_trading_class': 'SPXW',    # Weekly options
        'underlying_type': 'IND',            # Index
        'underlying_exchange': 'CBOE',
        'multiplier': '100',
        'strike_increment': 5.0,             # $5 increments
        'tick_size_above_3': 0.10,           # >= $3.00: $0.10 tick
        'tick_size_below_3': 0.05,           # < $3.00: $0.05 tick
        'description': 'S&P 500 Index Options (Full size, $100 multiplier)'
    },
    'XSP': {
        'name': 'XSP',
        'underlying_symbol': 'XSP',          # Mini-SPX symbol
        'options_symbol': 'XSP',
        'options_trading_class': 'XSP',
        'underlying_type': 'STK',            # Stock/ETF type
        'underlying_exchange': 'ARCA',
        'multiplier': '100',
        'strike_increment': 1.0,             # $1 increments (1/10 of SPX)
        'tick_size_above_3': 0.05,
        'tick_size_below_3': 0.05,
        'description': 'Mini-SPX Options (1/10 size of SPX, $100 multiplier)'
    }
}


# ============================================================================
# CONNECTION STATE MACHINE
# ============================================================================
# Note: Greeks (delta, gamma, theta, vega, IV) are calculated by IBKR
# and received via tickOptionComputation callback using mid-price model.
# No local Black-Scholes calculation needed.
# ============================================================================

class ConnectionState(Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"


# ============================================================================
# IBKR API WRAPPER WITH PYQT SIGNALS
# ============================================================================

class IBKRSignals(QObject):
    """Signal emitter for thread-safe GUI updates"""
    # Connection signals
    connection_status = pyqtSignal(str)  # "CONNECTED", "DISCONNECTED", "CONNECTING"
    connection_message = pyqtSignal(str, str)  # message, level
    
    # Market data signals
    spx_price_updated = pyqtSignal(float)
    market_data_tick = pyqtSignal(str, str, float)  # contract_key, tick_type, value
    greeks_updated = pyqtSignal(str, dict)  # contract_key, greeks_dict
    
    # Position and order signals
    position_update = pyqtSignal(str, dict)  # contract_key, position_data
    order_status_update = pyqtSignal(int, dict)  # order_id, status_data
    
    # Historical data signals
    historical_bar = pyqtSignal(str, dict)  # contract_key, bar_data
    historical_complete = pyqtSignal(str)  # contract_key
    
    # Account signals
    next_order_id = pyqtSignal(int)
    managed_accounts = pyqtSignal(str)


class IBKRWrapper(EWrapper):
    """Wrapper to handle all incoming messages from IBKR"""
    
    def __init__(self, signals: IBKRSignals, app_state):
        EWrapper.__init__(self)
        self.signals = signals
        self.app = app_state
    
    def error(self, reqId: TickerId, errorCode: int, errorString: str):
        """Handle error messages from IBKR API"""
        error_msg = f"Error {errorCode}: {errorString}"
        logger.debug(f"IBKR error callback: reqId={reqId}, code={errorCode}, msg={errorString}")
        
        # Benign errors - suppress
        if errorCode == 10268:  # EtradeOnly attribute warning
            return
        
        # Data server connection confirmed
        if errorCode in [2104, 2106]:
            self.signals.connection_message.emit("✓ Data server connection confirmed - ready for trading", "SUCCESS")
            self.app['data_server_ok'] = True
            return
        
        # Security definition server OK
        if errorCode == 2158:
            self.signals.connection_message.emit("✓ Security definition server OK", "INFO")
            return
        
        if errorCode == 10147:  # Order already filled/cancelled
            self.signals.connection_message.emit(f"Order {reqId} already processed", "INFO")
            return
        
        # Log all other errors
        level = "ERROR" if errorCode not in [354, 162, 165, 321] else "WARNING"
        self.signals.connection_message.emit(error_msg, level)
        
        # Connection-related errors
        if errorCode in [502, 503, 504, 1100, 2110]:
            self.signals.connection_status.emit("DISCONNECTED")
    
    def connectAck(self):
        """Called when connection is acknowledged"""
        logger.info("IBKR connection acknowledged")
        self.signals.connection_message.emit("Connection acknowledged", "INFO")
    
    def nextValidId(self, orderId: int):
        """Receives next valid order ID - signals successful connection"""
        logger.info(f"IBKR connected successfully! Next order ID: {orderId}")
        self.app['next_order_id'] = orderId
        self.signals.next_order_id.emit(orderId)
        self.signals.connection_status.emit("CONNECTED")
        self.signals.connection_message.emit(f"✓ Connected to IBKR! Next Order ID: {orderId}", "SUCCESS")
    
    def managedAccounts(self, accountsList: str):
        """Receives the list of managed accounts"""
        accounts = accountsList.split(',')
        self.app['managed_accounts'] = accounts
        self.app['account'] = accounts[-1] if accounts else ""  # Use last account
        self.signals.managed_accounts.emit(accountsList)
        self.signals.connection_message.emit(f"✓ Using account: {self.app['account']}", "SUCCESS")
    
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float, attrib: TickAttrib):
        """Receives real-time price updates"""
        # SPX underlying price
        if reqId == self.app.get('spx_req_id'):
            if tickType == 4:  # LAST price
                self.app['spx_price'] = price
                self.signals.spx_price_updated.emit(price)
            return
        
        # Option contract prices
        if reqId in self.app.get('market_data_map', {}):
            contract_key = self.app['market_data_map'][reqId]
            tick_name = {1: 'bid', 2: 'ask', 4: 'last', 9: 'prev_close'}.get(tickType)
            if tick_name:
                self.signals.market_data_tick.emit(contract_key, tick_name, price)
    
    def tickSize(self, reqId: TickerId, tickType: TickType, size: int):
        """Receives real-time size updates"""
        if reqId in self.app.get('market_data_map', {}):
            contract_key = self.app['market_data_map'][reqId]
            if tickType == 8:  # VOLUME
                self.signals.market_data_tick.emit(contract_key, 'volume', float(size))
    
    def tickOptionComputation(self, reqId: TickerId, tickType: TickType,
                             tickAttrib: int, impliedVol: float,
                             delta: float, optPrice: float, pvDividend: float,
                             gamma: float, vega: float, theta: float, undPrice: float):
        """Receives option greeks"""
        if reqId in self.app.get('market_data_map', {}):
            contract_key = self.app['market_data_map'][reqId]
            greeks = {
                'delta': delta if delta not in [-2, -1] else 0,
                'gamma': gamma if gamma not in [-2, -1] else 0,
                'theta': theta if theta not in [-2, -1] else 0,
                'vega': vega if vega not in [-2, -1] else 0,
                'iv': impliedVol if impliedVol not in [-2, -1] else 0
            }
            self.signals.greeks_updated.emit(contract_key, greeks)
    
    def orderStatus(self, orderId: int, status: str, filled: float,
                   remaining: float, avgFillPrice: float, permId: int,
                   parentId: int, lastFillPrice: float, clientId: int,
                   whyHeld: str, mktCapPrice: float):
        """Receives order status updates"""
        status_data = {
            'status': status,
            'filled': filled,
            'remaining': remaining,
            'avgFillPrice': avgFillPrice,
            'lastFillPrice': lastFillPrice
        }
        self.signals.order_status_update.emit(orderId, status_data)
        self.signals.connection_message.emit(
            f"Order {orderId}: {status} - Filled: {filled} @ {avgFillPrice}",
            "INFO"
        )
    
    def openOrder(self, orderId: int, contract: Contract, order: Order, orderState):
        """Receives open order information"""
        contract_key = f"{contract.symbol}_{contract.strike}_{contract.right}_{contract.lastTradeDateOrContractMonth[:8]}"
        self.signals.connection_message.emit(
            f"✓ TWS received Order #{orderId}: {contract_key} {order.action} {order.totalQuantity}",
            "SUCCESS"
        )
    
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """Receives position updates from IBKR"""
        if position != 0:
            contract_key = f"{contract.symbol}_{contract.strike}_{contract.right}_{contract.lastTradeDateOrContractMonth[:8]}"
            per_option_cost = avgCost / 100 if contract.secType == "OPT" else avgCost
            
            position_data = {
                'contract': contract,
                'position': position,
                'avgCost': per_option_cost,
                'currentPrice': 0,
                'pnl': 0,
                'entryTime': datetime.now()
            }
            self.signals.position_update.emit(contract_key, position_data)
    
    def positionEnd(self):
        """Called when initial position data is complete"""
        self.signals.connection_message.emit("Position subscription complete", "INFO")
    
    def execDetails(self, reqId: int, contract: Contract, execution):
        """Receives execution details"""
        contract_key = f"{contract.symbol}_{contract.strike}_{contract.right}_{contract.lastTradeDateOrContractMonth[:8]}"
        self.signals.connection_message.emit(
            f"Execution: Order #{execution.orderId} - {contract_key} {execution.side} {execution.shares} @ ${execution.price:.2f}",
            "SUCCESS"
        )
    
    def historicalData(self, reqId: int, bar):
        """Receives historical bar data"""
        if reqId in self.app.get('historical_data_requests', {}):
            contract_key = self.app['historical_data_requests'][reqId]
            bar_data = {
                'date': bar.date,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            }
            self.signals.historical_bar.emit(contract_key, bar_data)
    
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Called when historical data request is complete"""
        if reqId in self.app.get('historical_data_requests', {}):
            contract_key = self.app['historical_data_requests'][reqId]
            self.signals.historical_complete.emit(contract_key)


class IBKRClient(EClient):
    """Client to send requests to IBKR"""
    
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)


class IBKRThread(QThread):
    """Thread to run IBKR API message loop"""
    
    def __init__(self, client):
        super().__init__()
        self.client = client
    
    def run(self):
        """Run the IBKR message loop in background thread"""
        try:
            self.client.run()
        except Exception as e:
            print(f"IBKR thread exception: {e}")


# ============================================================================
# CHART WIDGET WITH LIGHTWEIGHT-CHARTS
# ============================================================================

class ChartWidget(QWidget):
    """TradingView-style candlestick chart using lightweight-charts"""
    
    def __init__(self, title="Chart", parent=None):
        super().__init__(parent)
        self.title = title
        self.chart = None
        self.candlestick_series = None
        self.setup_ui()
    
    def setup_ui(self):
        """Setup chart UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QLabel(self.title)
        header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #e0e0e0; padding: 5px;")
        layout.addWidget(header)
        
        if CHARTS_AVAILABLE and Chart is not None:
            try:
                # Create lightweight-charts instance
                self.chart = Chart(width=600, height=400, title=self.title)  # type: ignore[misc]
                self.candlestick_series = self.chart.create_candlestick_series()  # type: ignore[attr-defined]
                
                # Get HTML for WebEngineView
                html = self.chart.get_webview_html()  # type: ignore[attr-defined]
                
                # Create WebEngineView
                self.web_view = QWebEngineView()
                self.web_view.setHtml(html)
                layout.addWidget(self.web_view)
            except Exception as e:
                # Fallback to label if chart creation fails
                fallback = QLabel(f"Chart unavailable: {str(e)}")
                fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
                fallback.setStyleSheet("color: #888888; font-style: italic;")
                layout.addWidget(fallback)
        else:
            # No charts library - show message
            placeholder = QLabel("lightweight-charts not installed\nInstall with: pip install lightweight-charts")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #888888; font-style: italic;")
            layout.addWidget(placeholder)
    
    def update_data(self, bars: list):
        """Update chart with historical data"""
        if self.candlestick_series and bars:
            try:
                # Format data for lightweight-charts
                formatted_bars = [
                    {
                        'time': bar['date'].split()[0] if ' ' in bar['date'] else bar['date'],
                        'open': float(bar['open']),
                        'high': float(bar['high']),
                        'low': float(bar['low']),
                        'close': float(bar['close'])
                    }
                    for bar in bars
                ]
                self.candlestick_series.set(formatted_bars)
            except Exception as e:
                print(f"Error updating chart: {e}")
    
    def add_bar(self, bar: dict):
        """Add single bar for real-time updates"""
        if self.candlestick_series:
            try:
                formatted_bar = {
                    'time': bar['date'].split()[0] if ' ' in bar['date'] else bar['date'],
                    'open': float(bar['open']),
                    'high': float(bar['high']),
                    'low': float(bar['low']),
                    'close': float(bar['close'])
                }
                self.candlestick_series.update(formatted_bar)
            except Exception as e:
                print(f"Error adding bar: {e}")


# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        logger.info("Initializing MainWindow")
        self.setWindowTitle("SPX 0DTE Options Trader - PyQt6 Professional Edition")
        self.setGeometry(100, 100, 1600, 900)
        
        # Application state (shared with IBKR wrapper)
        self.app_state = {
            'next_order_id': 1,
            'spx_price': 0.0,
            'spx_req_id': None,
            'data_server_ok': False,
            'managed_accounts': [],
            'account': '',
            'market_data_map': {},  # reqId -> contract_key
            'historical_data_requests': {},  # reqId -> contract_key
            'active_option_req_ids': [],  # Track active option chain request IDs
        }
        
        # Trading state
        self.positions = {}  # contract_key -> position_data
        self.market_data = {}  # contract_key -> market_data
        self.pending_orders = {}  # order_id -> (contract_key, action, quantity)
        self.manual_orders = {}  # order_id -> manual_order_info
        self.historical_data = {}  # contract_key -> bars
        
        # Connection settings
        self.host = "127.0.0.1"
        self.port = 7497  # Paper trading
        self.client_id = 1
        self.connection_state = ConnectionState.DISCONNECTED
        
        # Strategy parameters
        self.strikes_above = 20
        self.strikes_below = 20
        self.current_expiry = self.calculate_expiry_date(0)
        
        # IBKR API setup
        self.signals = IBKRSignals()
        self.ibkr_wrapper = IBKRWrapper(self.signals, self.app_state)
        self.ibkr_client = IBKRClient(self.ibkr_wrapper)
        self.ibkr_thread = None
        
        # Connect signals
        self.connect_signals()
        
        # Setup UI
        self.setup_ui()
        self.apply_dark_theme()
        
        # Load settings
        self.load_settings()
        
        # Auto-connect after 2 seconds
        QTimer.singleShot(2000, self.connect_to_ibkr)
    
    def connect_signals(self):
        """Connect IBKR signals to GUI slots"""
        self.signals.connection_status.connect(self.on_connection_status)
        self.signals.connection_message.connect(self.log_message)
        self.signals.spx_price_updated.connect(self.update_spx_display)
        self.signals.market_data_tick.connect(self.on_market_data_tick)
        self.signals.greeks_updated.connect(self.on_greeks_updated)
        self.signals.next_order_id.connect(self.on_next_order_id)
        self.signals.managed_accounts.connect(self.on_managed_accounts)
        self.signals.position_update.connect(self.on_position_update)
        self.signals.order_status_update.connect(self.on_order_status)
        self.signals.historical_bar.connect(self.on_historical_bar)
        self.signals.historical_complete.connect(self.on_historical_complete)
    
    def setup_ui(self):
        """Setup the user interface"""
        # Central widget with tab widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: Trading Dashboard
        self.trading_tab = self.create_trading_tab()
        self.tabs.addTab(self.trading_tab, "Trading Dashboard")
        
        # Tab 2: Settings
        self.settings_tab = self.create_settings_tab()
        self.tabs.addTab(self.settings_tab, "Settings")
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Status: Disconnected")
        self.status_bar.addWidget(self.status_label)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.status_bar.addWidget(self.connect_btn)
        
        self.pnl_label = QLabel("Total P&L: $0.00")
        self.pnl_label.setStyleSheet("font-weight: bold;")
        self.status_bar.addPermanentWidget(self.pnl_label)
    
    def create_trading_tab(self):
        """Create the main trading dashboard tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Header with SPX price
        header = QFrame()
        header_layout = QHBoxLayout(header)
        
        title_label = QLabel("SPX Option Chain")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        self.spx_price_label = QLabel("SPX: Loading...")
        self.spx_price_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #FF8C00;")
        header_layout.addWidget(self.spx_price_label)
        
        header_layout.addStretch()
        
        self.expiry_combo = QComboBox()
        self.expiry_combo.addItems(self.get_expiration_options())
        self.expiry_combo.currentTextChanged.connect(self.on_expiry_changed)
        header_layout.addWidget(QLabel("Expiration:"))
        header_layout.addWidget(self.expiry_combo)
        
        refresh_btn = QPushButton("Refresh Chain")
        refresh_btn.clicked.connect(self.refresh_option_chain)
        header_layout.addWidget(refresh_btn)
        
        layout.addWidget(header)
        
        # Option chain table
        self.option_table = QTableWidget()
        self.option_table.setColumnCount(21)
        headers = [
            "Imp Vol", "Delta", "Theta", "Vega", "Gamma", "Volume", "CHANGE %", "Last", "Ask", "Bid",
            "● STRIKE ●",
            "Bid", "Ask", "Last", "CHANGE %", "Volume", "Gamma", "Vega", "Theta", "Delta", "Imp Vol"
        ]
        self.option_table.setHorizontalHeaderLabels(headers)
        self.option_table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.option_table.setMinimumHeight(300)
        self.option_table.cellClicked.connect(self.on_option_cell_clicked)
        layout.addWidget(self.option_table)
        
        # Charts panel
        charts_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.call_chart = ChartWidget("Call Chart", self)
        self.put_chart = ChartWidget("Put Chart", self)
        
        charts_splitter.addWidget(self.call_chart)
        charts_splitter.addWidget(self.put_chart)
        charts_splitter.setSizes([400, 400])
        
        layout.addWidget(charts_splitter)
        
        # Positions and Orders panel
        pos_order_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Positions
        positions_group = QGroupBox("Open Positions")
        pos_layout = QVBoxLayout(positions_group)
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(7)
        self.positions_table.setHorizontalHeaderLabels([
            "Contract", "Qty", "Entry", "Current", "P&L", "P&L %", "Action"
        ])
        self.positions_table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.positions_table.setMaximumHeight(200)
        self.positions_table.cellClicked.connect(self.on_position_cell_clicked)
        pos_layout.addWidget(self.positions_table)
        
        # Orders
        orders_group = QGroupBox("Active Orders")
        orders_layout = QVBoxLayout(orders_group)
        
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(7)
        self.orders_table.setHorizontalHeaderLabels([
            "Order ID", "Contract", "Action", "Qty", "Price", "Status", "Action"
        ])
        self.orders_table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.orders_table.setMaximumHeight(200)
        self.orders_table.cellClicked.connect(self.on_order_cell_clicked)
        orders_layout.addWidget(self.orders_table)
        
        pos_order_splitter.addWidget(positions_group)
        pos_order_splitter.addWidget(orders_group)
        pos_order_splitter.setSizes([400, 400])
        
        layout.addWidget(pos_order_splitter)
        
        # Manual trading panel
        trading_panel = QFrame()
        trading_panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        trading_layout = QHBoxLayout(trading_panel)
        
        trading_label = QLabel("Manual Trading:")
        trading_label.setStyleSheet("font-weight: bold;")
        trading_layout.addWidget(trading_label)
        
        self.buy_call_btn = QPushButton("BUY CALL")
        self.buy_call_btn.setProperty("success", True)
        self.buy_call_btn.clicked.connect(self.manual_buy_call)
        trading_layout.addWidget(self.buy_call_btn)
        
        self.buy_put_btn = QPushButton("BUY PUT")
        self.buy_put_btn.setProperty("danger", True)
        self.buy_put_btn.clicked.connect(self.manual_buy_put)
        trading_layout.addWidget(self.buy_put_btn)
        
        trading_layout.addWidget(QLabel("Max Risk:"))
        self.max_risk_edit = QLineEdit("500")
        self.max_risk_edit.setMaximumWidth(100)
        trading_layout.addWidget(self.max_risk_edit)
        trading_layout.addWidget(QLabel("$ (per contract)"))
        
        trading_layout.addStretch()
        
        layout.addWidget(trading_panel)
        
        # Activity log
        log_label = QLabel("Activity Log")
        log_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        return tab
    
    def create_settings_tab(self):
        """Create the settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Connection settings
        conn_group = QGroupBox("Connection Settings")
        conn_layout = QFormLayout(conn_group)
        
        self.host_edit = QLineEdit(self.host)
        conn_layout.addRow("Host IP:", self.host_edit)
        
        self.port_edit = QLineEdit(str(self.port))
        conn_layout.addRow("Port:", self.port_edit)
        
        self.client_id_edit = QLineEdit(str(self.client_id))
        conn_layout.addRow("Client ID:", self.client_id_edit)
        
        layout.addWidget(conn_group)
        
        # Strategy settings
        strategy_group = QGroupBox("Strategy Parameters")
        strategy_layout = QFormLayout(strategy_group)
        
        self.strikes_above_edit = QLineEdit(str(self.strikes_above))
        strategy_layout.addRow("Strikes Above SPX:", self.strikes_above_edit)
        
        self.strikes_below_edit = QLineEdit(str(self.strikes_below))
        strategy_layout.addRow("Strikes Below SPX:", self.strikes_below_edit)
        
        layout.addWidget(strategy_group)
        
        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        
        return tab
    
    def apply_dark_theme(self):
        """Apply IBKR TWS dark color scheme"""
        stylesheet = """
        QMainWindow {
            background-color: #000000;
        }
        
        QWidget {
            background-color: #000000;
            color: #c8c8c8;
        }
        
        QTableWidget {
            background-color: #000000;
            color: #c8c8c8;
            gridline-color: #1a1a1a;
            selection-background-color: #1a2a3a;
            selection-color: #ffffff;
            border: 1px solid #1a1a1a;
        }
        
        QHeaderView::section {
            background-color: #1a3a5a;
            color: #ffffff;
            padding: 5px;
            border: 1px solid #1a1a1a;
            font-weight: bold;
        }
        
        QPushButton {
            background-color: #1a1a1a;
            color: #d0d0d0;
            border: 1px solid #3a3a3a;
            padding: 8px 16px;
            border-radius: 4px;
        }
        
        QPushButton:hover {
            background-color: #2a2a2a;
        }
        
        QPushButton[success="true"] {
            background-color: #1a3a1a;
            color: #44ff44;
            border: 1px solid #2a5a2a;
        }
        
        QPushButton[danger="true"] {
            background-color: #3a1a1a;
            color: #ff4444;
            border: 1px solid #5a2a2a;
        }
        
        QLineEdit, QComboBox {
            background-color: #0a0a0a;
            color: #c8c8c8;
            border: 1px solid #3a3a3a;
            padding: 5px;
        }
        
        QTextEdit {
            background-color: #0a0a0a;
            color: #c8c8c8;
            border: 1px solid #3a3a3a;
        }
        
        QGroupBox {
            border: 1px solid #3a3a3a;
            border-radius: 5px;
            margin-top: 10px;
            font-weight: bold;
        }
        
        QGroupBox::title {
            color: #e0e0e0;
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
        }
        
        QStatusBar {
            background-color: #1a1a1a;
            color: #c8c8c8;
        }
        
        QTabWidget::pane {
            border: 1px solid #3a3a3a;
        }
        
        QTabBar::tab {
            background-color: #1a1a1a;
            color: #c8c8c8;
            padding: 8px 16px;
            border: 1px solid #3a3a3a;
        }
        
        QTabBar::tab:selected {
            background-color: #2a4a6a;
            color: #ffffff;
        }
        """
        self.setStyleSheet(stylesheet)
    
    # ========================================================================
    # IBKR CONNECTION MANAGEMENT
    # ========================================================================
    
    def connect_to_ibkr(self):
        """Connect to Interactive Brokers"""
        if self.connection_state == ConnectionState.CONNECTED:
            logger.warning("Already connected to IBKR")
            return
        
        logger.info("Initiating IBKR connection...")
        self.connection_state = ConnectionState.CONNECTING
        self.status_label.setText("Status: Connecting...")
        self.connect_btn.setEnabled(False)
        
        try:
            # Update settings from UI
            self.host = self.host_edit.text()
            self.port = int(self.port_edit.text())
            self.client_id = int(self.client_id_edit.text())
            
            logger.info(f"Connecting to IBKR: {self.host}:{self.port} (Client ID: {self.client_id})")
            
            # Connect to IBKR
            self.ibkr_client.connect(self.host, self.port, self.client_id)
            
            # Start API thread
            self.ibkr_thread = IBKRThread(self.ibkr_client)
            self.ibkr_thread.start()
            
            self.log_message(f"Connecting to IBKR at {self.host}:{self.port}...", "INFO")
        except Exception as e:
            logger.error(f"IBKR connection error: {e}", exc_info=True)
            self.log_message(f"Connection error: {e}", "ERROR")
            self.connection_state = ConnectionState.DISCONNECTED
            self.status_label.setText("Status: Disconnected")
            self.connect_btn.setEnabled(True)
    
    def disconnect_from_ibkr(self):
        """Disconnect from Interactive Brokers"""
        logger.info("Disconnecting from IBKR...")
        try:
            self.ibkr_client.disconnect()
            if self.ibkr_thread:
                self.ibkr_thread.wait(2000)
            
            self.connection_state = ConnectionState.DISCONNECTED
            self.status_label.setText("Status: Disconnected")
            self.connect_btn.setText("Connect")
            self.connect_btn.setEnabled(True)
            
            self.log_message("Disconnected from IBKR", "INFO")
        except Exception as e:
            logger.error(f"Disconnect error: {e}", exc_info=True)
            self.log_message(f"Disconnect error: {e}", "ERROR")
    
    def toggle_connection(self):
        """Toggle connection to IBKR"""
        if self.connection_state == ConnectionState.CONNECTED:
            self.disconnect_from_ibkr()
        else:
            self.connect_to_ibkr()
    
    @pyqtSlot(str)
    def on_connection_status(self, status: str):
        """Handle connection status updates"""
        self.connection_state = ConnectionState[status]
        self.status_label.setText(f"Status: {status}")
        
        if status == "CONNECTED":
            self.connect_btn.setText("Disconnect")
            self.connect_btn.setEnabled(True)
            
            # Initialize after connection
            self.ibkr_client.reqAccountUpdates(True, "")
            self.ibkr_client.reqPositions()
            self.subscribe_spx_price()
            self.request_option_chain()
        elif status == "DISCONNECTED":
            self.connect_btn.setText("Connect")
            self.connect_btn.setEnabled(True)
    
    @pyqtSlot(int)
    def on_next_order_id(self, order_id: int):
        """Handle next valid order ID"""
        self.app_state['next_order_id'] = order_id
    
    @pyqtSlot(str)
    def on_managed_accounts(self, accounts: str):
        """Handle managed accounts list"""
        pass  # Already handled in wrapper
    
    # ========================================================================
    # MARKET DATA HANDLING
    # ========================================================================
    
    def subscribe_spx_price(self):
        """Subscribe to SPX underlying price"""
        spx_contract = Contract()
        spx_contract.symbol = "SPX"
        spx_contract.secType = "IND"
        spx_contract.currency = "USD"
        spx_contract.exchange = "CBOE"
        
        req_id = 1
        self.app_state['spx_req_id'] = req_id
        
        self.ibkr_client.reqMktData(req_id, spx_contract, "", False, False, [])
        self.log_message("Subscribed to SPX underlying price", "INFO")
    
    @pyqtSlot(float)
    def update_spx_display(self, price: float):
        """Update SPX price display"""
        self.app_state['spx_price'] = price
        self.spx_price_label.setText(f"SPX: {price:.2f}")
    
    @pyqtSlot(str, str, float)
    def on_market_data_tick(self, contract_key: str, tick_type: str, value: float):
        """Handle market data tick updates"""
        if contract_key not in self.market_data:
            self.market_data[contract_key] = {
                'bid': 0, 'ask': 0, 'last': 0, 'prev_close': 0, 'volume': 0,
                'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'iv': 0
            }
        
        self.market_data[contract_key][tick_type] = value
        
        # Update option chain display immediately
        self.update_option_chain_cell(contract_key)
    
    @pyqtSlot(str, dict)
    def on_greeks_updated(self, contract_key: str, greeks: dict):
        """Handle greeks updates"""
        if contract_key not in self.market_data:
            self.market_data[contract_key] = {
                'bid': 0, 'ask': 0, 'last': 0, 'prev_close': 0, 'volume': 0,
                'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'iv': 0
            }
        
        self.market_data[contract_key].update(greeks)
        
        # Update option chain display
        self.update_option_chain_cell(contract_key)
    
    @pyqtSlot(str, dict)
    def on_position_update(self, contract_key: str, position_data: dict):
        """Handle position updates"""
        self.positions[contract_key] = position_data
        self.update_positions_display()
    
    @pyqtSlot(int, dict)
    def on_order_status(self, order_id: int, status_data: dict):
        """Handle order status updates"""
        # TODO: Update orders table
        pass
    
    @pyqtSlot(str, dict)
    def on_historical_bar(self, contract_key: str, bar_data: dict):
        """Handle historical bar data"""
        if contract_key not in self.historical_data:
            self.historical_data[contract_key] = []
        
        self.historical_data[contract_key].append(bar_data)
    
    @pyqtSlot(str)
    def on_historical_complete(self, contract_key: str):
        """Handle historical data complete"""
        if contract_key in self.historical_data:
            bars = self.historical_data[contract_key]
            self.log_message(f"Historical data complete for {contract_key}: {len(bars)} bars", "SUCCESS")
            
            # Update appropriate chart
            # TODO: Determine if call or put and update chart
    
    # ========================================================================
    # OPTION CHAIN MANAGEMENT
    # ========================================================================
    
    def calculate_expiry_date(self, offset: int) -> str:
        """Calculate expiration date based on offset (0 = today, 1 = next, etc.)"""
        current_date = datetime.now()
        target_date = current_date
        expiry_days = [0, 2, 4]  # Mon, Wed, Fri
        
        expirations_found = 0
        days_checked = 0
        
        while expirations_found <= offset and days_checked < 60:
            if target_date.weekday() in expiry_days:
                if expirations_found == offset:
                    return target_date.strftime("%Y%m%d")
                expirations_found += 1
            target_date += timedelta(days=1)
            days_checked += 1
        
        return datetime.now().strftime("%Y%m%d")
    
    def get_expiration_options(self) -> list:
        """Get list of expiration options for dropdown"""
        options = []
        for i in range(10):
            expiry_date = self.calculate_expiry_date(i)
            date_obj = datetime.strptime(expiry_date, "%Y%m%d")
            
            if i == 0:
                label = f"0 DTE (Today - {date_obj.strftime('%m/%d/%Y')})"
            elif i == 1:
                label = f"1 DTE (Next - {date_obj.strftime('%m/%d/%Y')})"
            else:
                label = f"{i} DTE ({date_obj.strftime('%m/%d/%Y')})"
            
            options.append(label)
        
        return options
    
    def on_expiry_changed(self, text: str):
        """Handle expiration selection change"""
        offset = int(text.split()[0])
        self.current_expiry = self.calculate_expiry_date(offset)
        self.log_message(f"Expiration changed to: {self.current_expiry}", "INFO")
        self.refresh_option_chain()
    
    def refresh_option_chain(self):
        """Refresh option chain"""
        self.log_message("Refreshing option chain...", "INFO")
        self.request_option_chain()
    
    def request_option_chain(self):
        """Build and subscribe to option chain"""
        if self.connection_state != ConnectionState.CONNECTED:
            self.log_message("Cannot request option chain - not connected", "WARNING")
            return
        
        if self.app_state['spx_price'] == 0:
            self.log_message("Waiting for SPX price...", "INFO")
            QTimer.singleShot(2000, self.request_option_chain)
            return
        
        # Cancel existing option chain subscriptions to avoid duplicate ticker ID errors
        if self.app_state.get('active_option_req_ids'):
            self.log_message(f"Canceling {len(self.app_state['active_option_req_ids'])} existing subscriptions...", "INFO")
            for req_id in self.app_state['active_option_req_ids']:
                try:
                    self.ibkr_client.cancelMktData(req_id)
                except Exception as e:
                    logger.debug(f"Error canceling reqId {req_id}: {e}")
            self.app_state['active_option_req_ids'] = []
            # Clear market data map for old requests
            self.app_state['market_data_map'] = {k: v for k, v in self.app_state['market_data_map'].items() 
                                                  if not (isinstance(k, int) and 100 <= k <= 999)}
        
        spx_price = self.app_state['spx_price']
        center_strike = round(spx_price / 5) * 5
        
        strikes = []
        current_strike = center_strike - (self.strikes_below * 5)
        end_strike = center_strike + (self.strikes_above * 5)
        
        while current_strike <= end_strike:
            strikes.append(current_strike)
            current_strike += 5
        
        self.log_message(f"Creating option chain: {len(strikes)} strikes from {min(strikes)} to {max(strikes)}", "INFO")
        
        # Clear table
        self.option_table.setRowCount(0)
        self.option_table.setRowCount(len(strikes))
        
        # Subscribe to market data for each strike
        req_id = 100  # Start from 100 for option contracts
        new_req_ids = []  # Track new request IDs
        
        for row, strike in enumerate(strikes):
            # Create call contract
            call_contract = Contract()
            call_contract.symbol = "SPX"
            call_contract.secType = "OPT"
            call_contract.exchange = "SMART"
            call_contract.currency = "USD"
            call_contract.tradingClass = "SPXW"
            call_contract.strike = strike
            call_contract.right = "C"
            call_contract.lastTradeDateOrContractMonth = self.current_expiry
            call_contract.multiplier = "100"
            
            call_key = f"SPX_{strike}_C_{self.current_expiry}"
            self.app_state['market_data_map'][req_id] = call_key
            self.ibkr_client.reqMktData(req_id, call_contract, "", False, False, [])
            new_req_ids.append(req_id)
            req_id += 1
            
            # Create put contract
            put_contract = Contract()
            put_contract.symbol = "SPX"
            put_contract.secType = "OPT"
            put_contract.exchange = "SMART"
            put_contract.currency = "USD"
            put_contract.tradingClass = "SPXW"
            put_contract.strike = strike
            put_contract.right = "P"
            put_contract.lastTradeDateOrContractMonth = self.current_expiry
            put_contract.multiplier = "100"
            
            put_key = f"SPX_{strike}_P_{self.current_expiry}"
            self.app_state['market_data_map'][req_id] = put_key
            self.ibkr_client.reqMktData(req_id, put_contract, "", False, False, [])
            new_req_ids.append(req_id)
            req_id += 1
            
            # Set strike in table
            strike_item = QTableWidgetItem(f"{strike:.0f}")
            strike_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            strike_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            strike_item.setBackground(QColor("#2a4a6a"))
            self.option_table.setItem(row, 10, strike_item)
        
        # Store active request IDs for future cleanup
        self.app_state['active_option_req_ids'] = new_req_ids
        self.log_message(f"Subscribed to {len(strikes) * 2} option contracts", "SUCCESS")
    
    def update_option_chain_cell(self, contract_key: str):
        """Update a single option chain row with market data"""
        try:
            # Parse contract_key: "SPX_6740_C_20251024"
            parts = contract_key.split('_')
            if len(parts) != 4:
                return
            
            symbol, strike, right, expiry = parts
            strike = float(strike)
            
            # Find the row for this strike
            for row in range(self.option_table.rowCount()):
                strike_item = self.option_table.item(row, 10)  # Strike column
                if strike_item and float(strike_item.text()) == strike:
                    # Get market data
                    data = self.market_data.get(contract_key, {})
                    
                    if right == 'C':  # Call options (left side)
                        # Columns: Imp Vol, Delta, Theta, Vega, Gamma, Volume, CHANGE %, Last, Ask, Bid
                        self.option_table.setItem(row, 0, QTableWidgetItem(f"{data.get('iv', 0):.2f}"))
                        self.option_table.setItem(row, 1, QTableWidgetItem(f"{data.get('delta', 0):.3f}"))
                        self.option_table.setItem(row, 2, QTableWidgetItem(f"{data.get('theta', 0):.2f}"))
                        self.option_table.setItem(row, 3, QTableWidgetItem(f"{data.get('vega', 0):.2f}"))
                        self.option_table.setItem(row, 4, QTableWidgetItem(f"{data.get('gamma', 0):.4f}"))
                        self.option_table.setItem(row, 5, QTableWidgetItem(f"{int(data.get('volume', 0))}"))
                        
                        # Calculate change %
                        last = data.get('last', 0)
                        prev = data.get('prev_close', 0)
                        change_pct = ((last - prev) / prev * 100) if prev > 0 else 0
                        change_item = QTableWidgetItem(f"{change_pct:.1f}%")
                        change_item.setForeground(QColor("#00ff00" if change_pct >= 0 else "#ff0000"))
                        self.option_table.setItem(row, 6, change_item)
                        
                        self.option_table.setItem(row, 7, QTableWidgetItem(f"{last:.2f}"))
                        self.option_table.setItem(row, 8, QTableWidgetItem(f"{data.get('ask', 0):.2f}"))
                        self.option_table.setItem(row, 9, QTableWidgetItem(f"{data.get('bid', 0):.2f}"))
                    
                    elif right == 'P':  # Put options (right side)
                        # Columns: Bid, Ask, Last, CHANGE %, Volume, Gamma, Vega, Theta, Delta, Imp Vol
                        self.option_table.setItem(row, 11, QTableWidgetItem(f"{data.get('bid', 0):.2f}"))
                        self.option_table.setItem(row, 12, QTableWidgetItem(f"{data.get('ask', 0):.2f}"))
                        self.option_table.setItem(row, 13, QTableWidgetItem(f"{data.get('last', 0):.2f}"))
                        
                        # Calculate change %
                        last = data.get('last', 0)
                        prev = data.get('prev_close', 0)
                        change_pct = ((last - prev) / prev * 100) if prev > 0 else 0
                        change_item = QTableWidgetItem(f"{change_pct:.1f}%")
                        change_item.setForeground(QColor("#00ff00" if change_pct >= 0 else "#ff0000"))
                        self.option_table.setItem(row, 14, change_item)
                        
                        self.option_table.setItem(row, 15, QTableWidgetItem(f"{int(data.get('volume', 0))}"))
                        self.option_table.setItem(row, 16, QTableWidgetItem(f"{data.get('gamma', 0):.4f}"))
                        self.option_table.setItem(row, 17, QTableWidgetItem(f"{data.get('vega', 0):.2f}"))
                        self.option_table.setItem(row, 18, QTableWidgetItem(f"{data.get('theta', 0):.2f}"))
                        self.option_table.setItem(row, 19, QTableWidgetItem(f"{data.get('delta', 0):.3f}"))
                        self.option_table.setItem(row, 20, QTableWidgetItem(f"{data.get('iv', 0):.2f}"))
                    
                    break
        
        except Exception as e:
            logger.debug(f"Error updating option chain cell for {contract_key}: {e}")
    
    def on_option_cell_clicked(self, row: int, col: int):
        """Handle option chain cell click"""
        # Get strike from row
        strike_item = self.option_table.item(row, 10)
        if not strike_item:
            return
        
        strike = float(strike_item.text())
        
        # Determine if call or put was clicked
        if col < 10:  # Call side
            contract_key = f"SPX_{strike}_C_{self.current_expiry}"
            self.log_message(f"Selected CALL: Strike {strike}", "INFO")
            # TODO: Update call chart
        elif col > 10:  # Put side
            contract_key = f"SPX_{strike}_P_{self.current_expiry}"
            self.log_message(f"Selected PUT: Strike {strike}", "INFO")
            # TODO: Update put chart
    
    # ========================================================================
    # MANUAL TRADING
    # ========================================================================
    
    def manual_buy_call(self):
        """Manual buy call option"""
        self.log_message("Manual BUY CALL initiated", "INFO")
        # TODO: Implement manual trading logic
    
    def manual_buy_put(self):
        """Manual buy put option"""
        self.log_message("Manual BUY PUT initiated", "INFO")
        # TODO: Implement manual trading logic
    
    # ========================================================================
    # POSITIONS AND ORDERS
    # ========================================================================
    
    def update_positions_display(self):
        """Update positions table"""
        self.positions_table.setRowCount(0)
        total_pnl = 0
        
        for row, (contract_key, pos) in enumerate(self.positions.items()):
            self.positions_table.insertRow(row)
            
            # Update P&L
            if contract_key in self.market_data:
                md = self.market_data[contract_key]
                bid, ask = md.get('bid', 0), md.get('ask', 0)
                if bid > 0 and ask > 0:
                    current_price = (bid + ask) / 2
                    pos['currentPrice'] = current_price
                    pos['pnl'] = (current_price - pos['avgCost']) * pos['position'] * 100
            
            pnl = pos.get('pnl', 0)
            pnl_pct = (pos['currentPrice'] / pos['avgCost'] - 1) * 100 if pos['avgCost'] > 0 else 0
            total_pnl += pnl
            
            # Populate row
            items = [
                QTableWidgetItem(contract_key),
                QTableWidgetItem(f"{pos['position']:.0f}"),
                QTableWidgetItem(f"${pos['avgCost']:.2f}"),
                QTableWidgetItem(f"${pos['currentPrice']:.2f}"),
                QTableWidgetItem(f"${pnl:.2f}"),
                QTableWidgetItem(f"{pnl_pct:.2f}%"),
                QTableWidgetItem("Close")
            ]
            
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Color P&L cells
                if col == 4 or col == 5:
                    if pnl > 0:
                        item.setForeground(QColor("#00ff00"))
                    elif pnl < 0:
                        item.setForeground(QColor("#ff0000"))
                
                # Close button styling
                if col == 6:
                    item.setBackground(QColor("#cc0000"))
                    item.setForeground(QColor("#ffffff"))
                
                self.positions_table.setItem(row, col, item)
        
        # Update total P&L
        pnl_color = "#44ff44" if total_pnl >= 0 else "#ff4444"
        self.pnl_label.setText(f"Total P&L: ${total_pnl:.2f}")
        self.pnl_label.setStyleSheet(f"font-weight: bold; color: {pnl_color};")
    
    def on_position_cell_clicked(self, row: int, col: int):
        """Handle position table cell click"""
        if col == 6:  # Close button
            # TODO: Implement position close logic
            pass
    
    def on_order_cell_clicked(self, row: int, col: int):
        """Handle order table cell click"""
        if col == 6:  # Cancel button
            # TODO: Implement order cancel logic
            pass
    
    # ========================================================================
    # LOGGING
    # ========================================================================
    
    @pyqtSlot(str, str)
    def log_message(self, message: str, level: str = "INFO"):
        """Log a message to the activity log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        colors = {
            "ERROR": "#ff4444",
            "WARNING": "#ffa500",
            "SUCCESS": "#44ff44",
            "INFO": "#c8c8c8"
        }
        
        color = colors.get(level, "#c8c8c8")
        
        self.log_text.append(f'<span style="color: {color};">[{timestamp}] {message}</span>')
        
        # Console log
        print(f"[{timestamp}] [{level}] {message}")
    
    # ========================================================================
    # SETTINGS MANAGEMENT
    # ========================================================================
    
    def save_settings(self):
        """Save settings to JSON file"""
        try:
            settings = {
                'host': self.host_edit.text(),
                'port': int(self.port_edit.text()),
                'client_id': int(self.client_id_edit.text()),
                'strikes_above': int(self.strikes_above_edit.text()),
                'strikes_below': int(self.strikes_below_edit.text())
            }
            
            Path('settings.json').write_text(json.dumps(settings, indent=2))
            self.log_message("Settings saved successfully", "SUCCESS")
        except Exception as e:
            self.log_message(f"Error saving settings: {e}", "ERROR")
    
    def load_settings(self):
        """Load settings from JSON file"""
        try:
            if Path('settings.json').exists():
                settings = json.loads(Path('settings.json').read_text())
                
                self.host = settings.get('host', '127.0.0.1')
                self.port = settings.get('port', 7497)
                self.client_id = settings.get('client_id', 1)
                self.strikes_above = settings.get('strikes_above', 20)
                self.strikes_below = settings.get('strikes_below', 20)
                
                # Update UI
                self.host_edit.setText(self.host)
                self.port_edit.setText(str(self.port))
                self.client_id_edit.setText(str(self.client_id))
                self.strikes_above_edit.setText(str(self.strikes_above))
                self.strikes_below_edit.setText(str(self.strikes_below))
                
                self.log_message("Settings loaded successfully", "SUCCESS")
        except Exception as e:
            self.log_message(f"Error loading settings: {e}", "ERROR")
    
    # ========================================================================
    # WINDOW LIFECYCLE
    # ========================================================================
    
    def closeEvent(self, a0):  # type: ignore[override]
        """Handle window close event"""
        reply = QMessageBox.question(
            self,
            'Quit',
            'Do you want to quit?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Cleanup
            if self.connection_state == ConnectionState.CONNECTED:
                self.disconnect_from_ibkr()
            
            a0.accept()  # type: ignore[union-attr]
        else:
            a0.ignore()  # type: ignore[union-attr]


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Application entry point"""
    logger.info("Initializing PyQt6 application...")
    
    app = QApplication(sys.argv)
    app.setApplicationName("SPX 0DTE Trader")
    
    logger.info("Creating main window...")
    window = MainWindow()
    window.show()
    
    logger.info("Application ready!")
    logger.info("Auto-connect enabled - will connect to IBKR in 2 seconds...")
    logger.info("=" * 70)
    
    return_code = app.exec()
    logger.info(f"Application exiting with code: {return_code}")
    sys.exit(return_code)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user (Ctrl+C)")
        print("\n[SHUTDOWN] Application interrupted by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"FATAL ERROR: Application crashed: {e}", exc_info=True)
        print(f"[FATAL ERROR] Application crashed: {e}")
        import traceback
        traceback.print_exc()
        print(f"\nCheck log file for details: logs/{datetime.now().strftime('%Y-%m-%d.log')}")
        input("Press Enter to exit...")
        sys.exit(1)
