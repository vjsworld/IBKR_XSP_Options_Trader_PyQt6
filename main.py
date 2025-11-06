"""
SPX 0DTE Options Trading Application - PyQt6 Edition
Professional Bloomberg-style GUI for Interactive Brokers API
Author: Van Gothreaux
Copyright Date: January 2025

Technology Stack:
- PyQt6: Modern GUI framework with native performance
- PyQt6-Charts: Native Qt candlestick charting for real-time visualization
- IBKR API: Real-time market data, order execution, and model-based greeks
- Dual-instrument support: SPX and XSP with symbol-agnostic architecture

CRITICAL TIMEZONE CONFIGURATION:
═══════════════════════════════════════════════════════════════════════════
🕐 ALL TIMES IN THIS APPLICATION USE CENTRAL TIME (America/Chicago) 🕐
═══════════════════════════════════════════════════════════════════════════
- Market hours: 8:30 AM - 3:00 PM CT
- After-hours: 7:15 PM - 7:25 AM CT (for 0DTE overnight trading)
- Regular trading restarts after a five minute break when stocks to dat 8:30 AM CT
- All charts display Central Time
- All positions show entry/exit times in Central Time
- All orders timestamped in Central Time
- TradeStation signals processed in Central Time
- ES, NQ, MES, MNQ Futures use Central Time market close (4:00 PM CT)
- SPX and XSP indexes and stocks use Central Time market close (3:00 PM CT)
- Option expiry calculations based on Central Time
═══════════════════════════════════════════════════════════════════════════
"""

# ============================================================================
# ⚙️ TRADING INSTRUMENT SELECTION - CHANGE THIS TO SWITCH INSTRUMENTS
# ============================================================================
# Set this to either 'SPX' (full-size S&P 500) or 'XSP' (mini 1/10 size)
# This controls which instrument the application will trade
SELECTED_INSTRUMENT = 'XSP'  # Change to 'XSP' for mini-SPX trading
# ============================================================================

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
import pytz  # For timezone-aware datetime (CENTRAL TIME - America/Chicago ONLY)


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
    QStatusBar, QGroupBox, QSpinBox, QDoubleSpinBox, QRadioButton, QButtonGroup, QScrollArea, QCheckBox,
    QSizePolicy
)
    from PyQt6.QtCore import (  # type: ignore[import-untyped]
        Qt, QTimer, pyqtSignal, QObject, QThread, pyqtSlot, QMargins, QMetaObject, Q_ARG
    )
    from PyQt6.QtGui import QColor, QFont, QPalette, QPainter  # type: ignore[import-untyped]
    logger.info("PyQt6 loaded successfully")
    PYQT6_AVAILABLE = True

    # Matplotlib imports for charting
    logger.info("Loading matplotlib modules...")
    import matplotlib
    matplotlib.use('Qt5Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    logger.info("Matplotlib loaded successfully")
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

# Matplotlib for charting
logger.info("Loading matplotlib/mplfinance for professional charts...")
import mplfinance as mpf
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.patches import Rectangle
import matplotlib.dates as mdates
logger.info("Chart libraries loaded successfully")

# Interactive Brokers API
logger.info("Loading IBKR API modules...")
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.common import TickerId, TickAttrib
from ibapi.ticktype import TickType
logger.info("IBKR API loaded successfully")

# TradeStation GlobalDictionary Integration
logger.info("Loading TradeStation integration...")
try:
    import GlobalDictionary
    import pythoncom
    TRADESTATION_AVAILABLE = True
    logger.info("TradeStation GlobalDictionary loaded successfully")
except ImportError as e:
    TRADESTATION_AVAILABLE = False
    logger.warning(f"TradeStation GlobalDictionary not available: {e}")
    logger.warning("TradeStation integration will be disabled")

# Charts are now handled by matplotlib/mplfinance
CHARTS_AVAILABLE = True  # Always available with matplotlib
logger.info("Using matplotlib/mplfinance for professional charts")


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
        'description': 'S&P 500 Index Options (Full size, $100 multiplier)',
        'hedge_instrument': 'ES',            # Hedge with E-mini S&P 500 futures
        'hedge_symbol': 'ES',
        'hedge_exchange': 'CME',
        'hedge_sec_type': 'FUT',
        'hedge_multiplier': 50,              # $50 per point
        'hedge_ratio': 2.0                   # 1 SPX option delta ~= 2 ES contracts
    },
    'XSP': {
        'name': 'XSP',
        'underlying_symbol': 'XSP',          # Mini-SPX Index symbol
        'options_symbol': 'XSP',
        'options_trading_class': 'XSP',
        'underlying_type': 'IND',            # Index (NOT stock)
        'underlying_exchange': 'CBOE',       # CBOE exchange like SPX
        'multiplier': '100',
        'strike_increment': 1.0,             # $1 increments (1/10 of SPX)
        'tick_size_above_3': 0.01,           # XSP trades in $0.01 increments (all prices)
        'tick_size_below_3': 0.01,           # XSP trades in $0.01 increments (all prices)
        'description': 'Mini-SPX Index Options (1/10 size of SPX, $100 multiplier)',
        'hedge_instrument': 'MES',           # Hedge with Micro E-mini S&P 500 futures
        'hedge_symbol': 'MES',
        'hedge_exchange': 'CME',
        'hedge_sec_type': 'FUT',
        'hedge_multiplier': 5,               # $5 per point (1/10 of ES)
        'hedge_ratio': 20.0                  # 1 XSP option delta (100 shares) ~= 20 MES contracts (5 per point * 20 = 100)
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

class IBKRSignals(QObject):  # type: ignore[misc]
    """Signal emitter for thread-safe GUI updates"""
    # Connection signals
    connection_status = pyqtSignal(str)  # type: ignore[possibly-unbound]  # "CONNECTED", "DISCONNECTED", "CONNECTING"
    connection_message = pyqtSignal(str, str)  # type: ignore[possibly-unbound]  # message, level
    
    # Market data signals
    underlying_price_updated = pyqtSignal(float)  # type: ignore[possibly-unbound]  # Underlying instrument price (SPX, XSP, etc.)
    es_price_updated = pyqtSignal(float)  # type: ignore[possibly-unbound]  # ES futures price (23/6 trading)
    market_data_tick = pyqtSignal(str, str, float)  # type: ignore[possibly-unbound]  # contract_key, tick_type, value
    greeks_updated = pyqtSignal(str, dict)  # type: ignore[possibly-unbound]  # contract_key, greeks_dict
    
    # Position and order signals
    position_update = pyqtSignal(str, dict)  # type: ignore[possibly-unbound]  # contract_key, position_data
    position_closed = pyqtSignal(str)  # type: ignore[possibly-unbound]  # contract_key - position quantity = 0
    order_status_update = pyqtSignal(int, dict)  # type: ignore[possibly-unbound]  # order_id, status_data
    
    # Historical data signals
    historical_bar = pyqtSignal(str, dict)  # type: ignore[possibly-unbound]  # contract_key, bar_data
    historical_complete = pyqtSignal(str)  # type: ignore[possibly-unbound]  # contract_key
    historical_bar_update = pyqtSignal(str, dict)  # type: ignore[possibly-unbound]  # contract_key, bar_data (real-time updates)
    
    # Account signals
    next_order_id = pyqtSignal(int)  # type: ignore[possibly-unbound]
    managed_accounts = pyqtSignal(str)  # type: ignore[possibly-unbound]


class IBKRWrapper(EWrapper):
    """Wrapper to handle all incoming messages from IBKR"""
    
    def __init__(self, signals: IBKRSignals, app_state, main_window=None):
        EWrapper.__init__(self)
        self.signals = signals
        self.app = app_state
        self._main_window = main_window  # Reference for error handling callbacks
        self._client = None  # Will be set after IBKRClient is created
    
    def set_client(self, client):
        """Set the client reference after IBKRClient is created"""
        self._client = client
    
    def error(self, reqId: TickerId, errorCode: int, errorString: str):
        """Handle error messages from IBKR API"""
        error_msg = f"Error {errorCode}: {errorString}"
        logger.debug(f"IBKR error callback: reqId={reqId}, code={errorCode}, msg={errorString}")
        
        # Special handling for Error 200 (No security definition) - ENHANCED
        if errorCode == 200:
            # Try to find which contract failed - check both market data and historical requests
            contract_key = "Unknown"
            request_type = "Unknown"
            
            # Check market data map
            if reqId in self.app.get('market_data_map', {}):
                contract_key = self.app['market_data_map'][reqId]
                request_type = "Market Data"
            
            # Check historical data requests
            elif reqId in self.app.get('historical_data_requests', {}):
                contract_key = self.app['historical_data_requests'][reqId]
                request_type = "Historical Data"
            
            # Enhanced error logging with diagnostics
            error_details = (
                f"\n{'='*70}\n"
                f"🚨 ERROR 200 - No Security Definition Found!\n"
                f"{'='*70}\n"
                f"Request ID: {reqId}\n"
                f"Request Type: {request_type}\n"
                f"Contract Key: {contract_key}\n"
                f"\n"
                f"LIKELY CAUSES:\n"
                f"  1. Wrong tradingClass (should be 'SPXW' for SPX weeklies)\n"
                f"  2. Wrong exchange (should be 'SMART' with tradingClass)\n"
                f"  3. Expiration date format issue (must be YYYYMMDD)\n"
                f"  4. Strike price not available for that expiration\n"
                f"  5. Wrong underlying symbol\n"
                f"\n"
                f"DEBUGGING STEPS:\n"
                f"  - Check contract creation in logs\n"
                f"  - Verify tradingClass is set correctly\n"
                f"  - Confirm expiration date is valid SPX expiry\n"
                f"  - Verify strike is in valid range\n"
                f"{'='*70}\n"
            )
            logger.error(error_details)
            
            self.signals.connection_message.emit(
                f"🚨 Contract error for {contract_key} (reqId={reqId}) - Check logs for details", 
                "ERROR"
            )
            return
        
        # Client ID already in use - try next client ID
        if errorCode == 326:
            if not self._main_window:
                self.signals.connection_message.emit("Client ID already in use but no main window reference", "ERROR")
                return
                
            logger.info(f"ERROR 326: Current client_id={self._main_window.client_id}, iterator={self._main_window.client_id_iterator}, max={self._main_window.max_client_id}")
            self.signals.connection_message.emit(f"Client ID {self._main_window.client_id} already in use", "WARNING")
            
            if self._main_window.client_id_iterator < self._main_window.max_client_id:
                self._main_window.client_id_iterator += 1
                self._main_window.client_id = self._main_window.client_id_iterator
                logger.info(f"ERROR 326: Incremented to client_id={self._main_window.client_id}, iterator={self._main_window.client_id_iterator}")
                self.signals.connection_message.emit(f"Retrying with Client ID {self._main_window.client_id}...", "INFO")
                # Mark that we're handling this error specially
                self._main_window.handling_client_id_error = True
                # Update connection state
                self.signals.connection_status.emit("DISCONNECTED")
                # Schedule reconnect with new client ID (disconnect will happen automatically)
                QTimer.singleShot(2000, self._main_window.retry_connection_with_new_client_id)
            else:
                self.signals.connection_message.emit(
                    f"Exhausted all client IDs (1-{self._main_window.max_client_id}). Please close other connections.", 
                    "ERROR"
                )
                self.signals.connection_status.emit("DISCONNECTED")
            return
        
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
        
        # Order modification errors (filled orders) - STOP CHASING
        if errorCode in [103, 104]:  # 103=Duplicate order id, 104=Cannot modify filled order
            logger.warning(f"Order #{reqId} cannot be modified (code {errorCode}) - likely filled/cancelled")
            # Signal to remove from chasing_orders
            if hasattr(self, '_main_window'):
                QMetaObject.invokeMethod(
                    self._main_window, 
                    "remove_from_chasing_orders",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(int, reqId)
                )
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
        # Reset client ID iterator for next connection
        if self._main_window:
            self._main_window.client_id_iterator = 1
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
    
    def tickSnapshotEnd(self, reqId: int):
        """Called when snapshot market data is complete"""
        if reqId == self.app.get('es_req_id'):
            logger.info("ES futures snapshot data complete")
            self.signals.connection_message.emit("ES futures snapshot received", "INFO")
        elif reqId == self.app.get('underlying_req_id'):
            logger.info("Underlying snapshot data complete")
            self.signals.connection_message.emit("Underlying snapshot received", "INFO")
    
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float, attrib: TickAttrib):
        """Receives real-time price updates"""
        # Underlying instrument price (SPX, XSP, etc.) for display
        if reqId == self.app.get('underlying_req_id'):
            # Accept LAST (4), CLOSE (9), DELAYED_LAST (68) for snapshot/delayed data
            if tickType in [4, 9, 68]:
                logger.debug(f"Underlying price tick: type={tickType}, price={price}")  # Suppressed - too verbose
                self.app['underlying_price'] = price
                self.signals.underlying_price_updated.emit(price)
            return
        
        # ES futures price (for strike calculations - always available)
        if reqId == self.app.get('es_req_id'):
            # Accept LAST (4), CLOSE (9), DELAYED_LAST (68) for snapshot/delayed data
            if tickType in [4, 9, 68]:
                logger.debug(f"ES futures price tick: type={tickType}, price={price}")  # Suppressed - too verbose
                self.app['es_price'] = price
                self.signals.es_price_updated.emit(price)
            else:
                # Log other tick types to help debug what we're receiving
                logger.debug(f"ES futures tick (ignored): reqId={reqId}, type={tickType}, price={price}")
            return
        
        # MES futures price (for delta hedging)
        if self._main_window and reqId == self._main_window.mes_req_id:
            # Accept LAST (4), CLOSE (9), DELAYED_LAST (68)
            if tickType in [4, 9, 68]:
                logger.debug(f"MES futures price tick: type={tickType}, price={price}")
                self._main_window.update_mes_price(price)
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
        logger.info(f"✓ openOrder callback received for order #{orderId}")
        logger.info(f"   Contract: {contract_key}")
        logger.info(f"   Action: {order.action} {order.totalQuantity}")
        logger.info(f"   OrderState status: {orderState.status}")
        self.signals.connection_message.emit(
            f"✓ TWS received Order #{orderId}: {contract_key} {order.action} {order.totalQuantity} (Status: {orderState.status})",
            "SUCCESS"
        )
    
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """
        Receives position updates from IBKR.
        Automatically subscribes to market data for each position to enable:
        - Real-time P&L updates
        - Bid/ask availability for close order mid-price chasing
        """
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
            
            # Subscribe to market data for this position if not already subscribed
            # Check if we have an active subscription (not just market_data entry)
            is_subscribed = any(contract_key == v for v in self.app.get('market_data_map', {}).values())
            
            if not is_subscribed and self._client and self._main_window:
                logger.info(f"Subscribing to market data for position: {contract_key}")
                self.signals.connection_message.emit(f"Subscribing to market data for position: {contract_key}", "INFO")
                
                # Create market data entry and subscribe
                req_id = self.app['next_req_id']
                self.app['next_req_id'] += 1
                
                # Ensure contract has required fields for market data subscription
                # IBKR position callback may not include exchange, so set it explicitly
                if not contract.exchange:
                    contract.exchange = "SMART"
                if not contract.tradingClass:
                    # Use the trading class from instrument config
                    contract.tradingClass = self._main_window.instrument['options_trading_class']
                if not contract.currency:
                    contract.currency = "USD"
                
                self.app['market_data_map'][req_id] = contract_key
                
                # Create market_data entry if it doesn't exist
                if contract_key not in self._main_window.market_data:
                    self._main_window.market_data[contract_key] = {
                        'contract': contract,
                        'right': contract.right,
                        'strike': contract.strike,
                        'bid': 0, 'ask': 0, 'last': 0, 'volume': 0,
                        'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'iv': 0
                    }
                    logger.info(f"Created market_data entry for {contract_key}")
                
                self._client.reqMktData(req_id, contract, "", False, False, [])
                logger.info(f"Requested market data (reqId={req_id}) for {contract_key}")
            else:
                logger.info(f"Position {contract_key} already has active market data subscription")
        else:
            # Position closed (quantity = 0) - signal to remove from tracking and unsubscribe
            contract_key = f"{contract.symbol}_{contract.strike}_{contract.right}_{contract.lastTradeDateOrContractMonth[:8]}"
            logger.info(f"Position closed: {contract_key}")
            self.signals.position_closed.emit(contract_key)
            self.signals.connection_message.emit(f"Position closed: {contract_key}", "INFO")
    
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
        # Check for historical close offset calculation requests
        if reqId == self.app.get('historical_close_spx_req_id'):
            contract_key = 'HISTORICAL_CLOSE_SPX'
        elif reqId == self.app.get('historical_close_es_req_id'):
            contract_key = 'HISTORICAL_CLOSE_ES'
        # Check both old and new request mapping systems
        elif reqId in self.app.get('historical_data_requests', {}):
            contract_key = self.app['historical_data_requests'][reqId]
        elif self._main_window and hasattr(self._main_window, 'request_id_map') and reqId in self._main_window.request_id_map:
            contract_key = self._main_window.request_id_map[reqId]
        else:
            contract_key = None
            
        if contract_key:
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
        # Check for historical close offset calculation requests
        if reqId == self.app.get('historical_close_spx_req_id'):
            contract_key = 'HISTORICAL_CLOSE_SPX'
        elif reqId == self.app.get('historical_close_es_req_id'):
            contract_key = 'HISTORICAL_CLOSE_ES'
        # Check both old and new request mapping systems
        elif reqId in self.app.get('historical_data_requests', {}):
            contract_key = self.app['historical_data_requests'][reqId]
        elif self._main_window and hasattr(self._main_window, 'request_id_map') and reqId in self._main_window.request_id_map:
            contract_key = self._main_window.request_id_map[reqId]
        else:
            contract_key = None
            
        if contract_key:
            self.signals.historical_complete.emit(contract_key)
    
    def historicalDataUpdate(self, reqId: int, bar):
        """
        Called when keepUpToDate=True and new bar data arrives in real-time.
        This is the proper IBAPI way to get real-time bar updates.
        
        NOTE: Real-time bar.date is Unix epoch timestamp (int), not formatted string!
        """
        # Check both old and new request mapping systems
        contract_key = None
        if reqId in self.app.get('historical_data_requests', {}):
            contract_key = self.app['historical_data_requests'][reqId]
        elif self._main_window and hasattr(self._main_window, 'request_id_map') and reqId in self._main_window.request_id_map:
            contract_key = self._main_window.request_id_map[reqId]
            
        if contract_key:
            # CRITICAL: Convert epoch timestamp to datetime string format
            # Real-time updates use epoch int, historical uses formatted string
            from datetime import datetime
            
            date_value = bar.date
            # Check if it's an epoch timestamp (integer) or formatted string
            if isinstance(date_value, (int, float)):
                # Unix epoch timestamp - convert to datetime string
                dt = datetime.fromtimestamp(date_value)
                formatted_date = dt.strftime('%Y%m%d %H:%M:%S')
            else:
                # Already a string, use as-is
                formatted_date = str(date_value)
            
            bar_data = {
                'date': formatted_date,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            }
            # Emit on a special real-time update signal
            self.signals.historical_bar_update.emit(contract_key, bar_data)


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
# TRADESTATION INTEGRATION - GLOBALDICTIONARY COM INTERFACE
# ============================================================================

class TradeStationSignals(QObject):  # type: ignore[misc]
    """PyQt signals for thread-safe communication from TradeStation COM to GUI"""
    ts_connected = pyqtSignal(bool)  # type: ignore[possibly-unbound]
    ts_message = pyqtSignal(str)  # type: ignore[possibly-unbound]
    ts_activity = pyqtSignal(str)  # type: ignore[possibly-unbound]  # NEW: For Activity Log
    entry_signal = pyqtSignal(dict)  # type: ignore[possibly-unbound]
    exit_signal = pyqtSignal(dict)  # type: ignore[possibly-unbound]
    signal_update = pyqtSignal(dict)  # type: ignore[possibly-unbound]
    strategy_state_changed = pyqtSignal(str)  # type: ignore[possibly-unbound]


class TradeStationManager(QObject):
    """TradeStation GlobalDictionary COM interface - NO THREADING (based on working Demo.py)
    
    Uses QTimer to pump COM messages in the main thread - this avoids COM apartment threading issues.
    The working Demo.py doesn't use threads, it just calls pythoncom.PumpWaitingMessages() in a loop.
    """
    
    def __init__(self, signals):
        super().__init__()
        self.signals = signals
        self.running = False
        self.gd = None
        self.dict_name = "IBKR-TRADER"  # Match TradeStation's dictionary name (with hyphen)
        self.processed_signals = set()
        self.timer = None  # QTimer for message pump
        
    def start(self):
        """Initialize COM and start message pump (NO THREADING - based on working Demo.py)"""
        if not TRADESTATION_AVAILABLE:
            self.signals.ts_message.emit("TradeStation GlobalDictionary not available")
            return
            
        try:
            # Initialize COM in main thread (like Demo.py)
            pythoncom.CoInitialize()  # type: ignore[possibly-unbound]
            
            # Create GlobalDictionary with callbacks (exactly like working Demo.py)
            self.gd = GlobalDictionary.create(  # type: ignore[possibly-unbound]
                name=self.dict_name,
                add=self.on_signal_add,
                remove=self.on_signal_remove,
                change=self.on_signal_change,
                clear=self.on_signal_clear
            )
            
            self.running = True
            self.signals.ts_connected.emit(True)
            
            # Prominent connection message
            logger.info("═══════════════════════════════════════════════════════")
            logger.info(f"✅ TRADESTATION CONNECTED: GlobalDictionary '{self.dict_name}'")
            logger.info("📡 Listening for TradeStation signals...")
            logger.info("═══════════════════════════════════════════════════════")
            self.signals.ts_message.emit(f"Connected to TradeStation GlobalDictionary: {self.dict_name}")
            
            # Send initial status to TradeStation
            try:
                self.gd.set("PYTHON_STATUS", "CONNECTED")
                self.gd.set("LAST_UPDATE", datetime.now().strftime("%H:%M:%S"))
            except Exception as e:
                logger.error(f"Error setting initial status: {e}")
            
            # Start QTimer to pump COM messages (like Demo.py's while loop but non-blocking)
            self.timer = QTimer()
            self.timer.timeout.connect(self.pump_messages)
            self.timer.start(10)  # Pump every 10ms (like Demo.py's 0.01s sleep)
                
        except Exception as e:
            logger.error(f"TradeStation COM error: {e}", exc_info=True)
            self.signals.ts_message.emit(f"TradeStation error: {e}")
            self.running = False
            self.signals.ts_connected.emit(False)
    
    def pump_messages(self):
        """Pump COM messages (called by QTimer) - exactly like Demo.py's loop"""
        try:
            if self.running:
                pythoncom.PumpWaitingMessages()  # type: ignore[possibly-unbound]
        except Exception as e:
            logger.error(f"Error pumping messages: {e}")
            self.stop()
    
    def on_signal_add(self, gd, key, value, size):
        """Called when a new key is added to GlobalDictionary
        Based on working Demo.py pattern.
        
        Parameters (from GlobalDictionary callback):
            gd: The GlobalDictionary instance (like 'self' in Demo.py)
            key: The dictionary key that was added
            value: The value (already decoded by GlobalDictionary)
            size: Current size of the dictionary
        """
        if not self.running:
            return
            
        try:
            # LOG ALL INCOMING DATA FROM TRADESTATION (to file only, not Activity Log)
            value_str = str(value)[:200] if value else "None"
            logger.info(f"[TS→PYTHON] NEW KEY: '{key}' = {value_str} (dict size: {size})")
            self.signals.ts_message.emit(f"TS ADD: {key} = {value_str}")
            # Show ADD events in Activity Log
            self.signals.ts_activity.emit(f"[ADD] {key} = {value_str}")
            
            if key.startswith("ENTRY_"):
                signal_id = key[6:]
                if signal_id not in self.processed_signals:
                    self.processed_signals.add(signal_id)
                    if isinstance(value, dict):
                        value_copy = value.copy()  # Make a copy for thread safety
                        value_copy['signal_id'] = signal_id
                        self.signals.entry_signal.emit(value_copy)
                        # Send ACK using the GlobalDictionary instance (like Demo.py: GD["key"] = value)
                        try:
                            gd.set(f"ACK_ENTRY_{signal_id}", True)
                            logger.info(f"[PYTHON→TS] Sent acknowledgment: ACK_ENTRY_{signal_id}")
                            self.signals.ts_activity.emit(f"[SENT] ACK_ENTRY_{signal_id} = True")
                        except Exception as ack_err:
                            logger.error(f"Error sending ACK_ENTRY: {ack_err}")
            
            elif key.startswith("EXIT_"):
                signal_id = key[5:]
                if signal_id not in self.processed_signals:
                    self.processed_signals.add(signal_id)
                    if isinstance(value, dict):
                        value_copy = value.copy()  # Make a copy for thread safety
                        value_copy['signal_id'] = signal_id
                        self.signals.exit_signal.emit(value_copy)
                        # Send ACK using the GlobalDictionary instance
                        try:
                            gd.set(f"ACK_EXIT_{signal_id}", True)
                            logger.info(f"[PYTHON→TS] Sent acknowledgment: ACK_EXIT_{signal_id}")
                            self.signals.ts_activity.emit(f"[SENT] ACK_EXIT_{signal_id} = True")
                        except Exception as ack_err:
                            logger.error(f"Error sending ACK_EXIT: {ack_err}")
            
            elif key == "TS_STRATEGY_STATE":
                self.signals.strategy_state_changed.emit(str(value))
                logger.info(f"[TS→PYTHON] Strategy state changed to: {value}")
                self.signals.ts_activity.emit(f"[STATE] Strategy: {value}")  # Keep this one
                
        except Exception as e:
            logger.error(f"Error processing signal add: {e}", exc_info=True)
    
    def on_signal_change(self, gd, key, value, size):
        """Called when a key is changed in GlobalDictionary
        Based on working Demo.py pattern.
        
        Parameters (from GlobalDictionary callback):
            gd: The GlobalDictionary instance
            key: The dictionary key that was changed
            value: The new value (already decoded)
            size: Current size of the dictionary
        """
        if not self.running:
            return
            
        try:
            # LOG ALL CHANGES FROM TRADESTATION (to file only, not Activity Log)
            value_str = str(value)[:200] if value else "None"
            logger.info(f"[TS→PYTHON] CHANGED KEY: '{key}' = {value_str} (dict size: {size})")
            self.signals.ts_message.emit(f"TS CHANGE: {key} = {value_str}")
            # Activity Log: Only log important events (muted routine GD messages)
            # self.signals.ts_activity.emit(f"[CHANGE] {key} = {value_str}")
            
            if key == "TS_STRATEGY_STATE":
                self.signals.strategy_state_changed.emit(str(value))
                logger.info(f"[TS→PYTHON] Strategy state updated to: {value}")
                self.signals.ts_activity.emit(f"[STATE] Strategy: {value}")  # Keep this one
        except Exception as e:
            logger.error(f"Error processing signal change: {e}", exc_info=True)
    
    def on_signal_remove(self, gd, key, size):
        """Called when a key is removed from GlobalDictionary
        Based on working Demo.py pattern.
        
        Parameters (from GlobalDictionary callback):
            gd: The GlobalDictionary instance
            key: The dictionary key that was removed
            size: Current size of the dictionary after removal
        """
        if not self.running:
            return
            
        try:
            # LOG ALL REMOVALS FROM TRADESTATION
            logger.info(f"[TS→PYTHON] REMOVED KEY: '{key}' (dict size: {size})")
            self.signals.ts_message.emit(f"TS REMOVE: {key}")
            # Show REMOVE events in Activity Log
            self.signals.ts_activity.emit(f"[REMOVE] Key: {key}")
        except Exception as e:
            logger.error(f"Error processing signal remove: {e}", exc_info=True)
    
    def on_signal_clear(self, gd):
        """Called when the GlobalDictionary is cleared
        Based on working Demo.py pattern.
        
        Parameters (from GlobalDictionary callback):
            gd: The GlobalDictionary instance
        """
        if not self.running:
            return
            
        try:
            # LOG CLEAR EVENT FROM TRADESTATION
            logger.info(f"[TS→PYTHON] DICTIONARY CLEARED")
            self.signals.ts_message.emit(f"TS CLEAR: Dictionary cleared")
            # Show CLEAR events in Activity Log
            self.signals.ts_activity.emit(f"[CLEAR] GlobalDictionary cleared")
        except Exception as e:
            logger.error(f"Error processing clear event: {e}", exc_info=True)
    
    def update_status(self, status):
        """Update Python status in GlobalDictionary
        NOTE: Cannot be called from main thread - COM marshaling issue.
        Status updates should be sent via the callback thread."""
        logger.warning("update_status() called - this method is deprecated due to COM threading")
    
    def send_trade_confirmation(self, signal_id, result):
        """Send trade result back to TradeStation
        NOTE: Cannot be called from main thread - COM marshaling issue.
        Confirmations are sent directly in the callbacks."""
        logger.warning("send_trade_confirmation() called - this method is deprecated due to COM threading")
    
    def stop(self):
        """Stop the COM message pump and cleanup"""
        self.running = False
        
        # Stop the timer
        if self.timer:
            self.timer.stop()
            self.timer = None
        
        # Cleanup COM
        if self.gd:
            try:
                self.gd.set("PYTHON_STATUS", "DISCONNECTED")
            except:
                pass


# ============================================================================
# PROFESSIONAL CHART WIDGETS - LINE CHARTS FOR OPTIONS & CANDLESTICKS FOR UNDERLYING
# ============================================================================

class ProfessionalChart(QWidget):
    """
    Professional line chart for options (mid-price data)
    Features:
    - Line chart for mid-price display
    - Right-aligned price axis
    - Time labels on bottom
    - Dark theme matching TradeStation
    - Real-time updates with blitting for high-frequency trading
    """
    
    def __init__(self, title: str, border_color: str = "#FF8C00", parent=None):
        super().__init__(parent)
        self.title = title
        self.border_color = border_color
        self.chart_data = []
        
        # Blitting optimization attributes
        self.background = None  # Cached background for blitting
        self.line_artist = None  # Main line object for fast updates
        self.price_line_artist = None  # Current price line
        self.price_text_artist = None  # Current price text
        self.animated_artists = []  # List of all animated artists
        self.needs_full_redraw = True  # Flag to force full redraw
        self.is_first_draw = True  # Track first draw for initialization
        
        # Throttling attributes
        self.last_update_time = 0  # Track last update timestamp
        self.update_interval = 0.25  # Minimum 250ms between updates (4 FPS) for trading
        self.pending_update = None  # QTimer for pending update
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Top toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(5, 2, 5, 2)
        toolbar_layout.setSpacing(10)
        
        # Title label
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {border_color};
                font-weight: bold;
                font-size: 11pt;
                border: none;
            }}
        """)
        toolbar_layout.addWidget(self.title_label)
        
        toolbar_layout.addStretch()
        
        # Interval selector
        toolbar_layout.addWidget(QLabel("Interval:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["15 secs", "30 secs", "1 min", "5 min", "15 min", "30 min", "1 hour"])
        self.interval_combo.setCurrentText("1 min")
        self.interval_combo.setFixedWidth(80)
        self.interval_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a2a;
                border: 1px solid {border_color};
                padding: 2px 5px;
                color: white;
                border-radius: 2px;
            }}
        """)
        toolbar_layout.addWidget(self.interval_combo)
        
        # Days selector (Note: Always loads 12 hours initially to prevent freezing)
        toolbar_layout.addWidget(QLabel("Days:"))
        self.days_combo = QComboBox()
        self.days_combo.addItems(["1", "2", "3", "5"])
        self.days_combo.setCurrentText("2")
        self.days_combo.setFixedWidth(50)
        self.days_combo.setToolTip("Display setting only - data loads 12 hours at a time")
        self.days_combo.setStyleSheet(self.interval_combo.styleSheet())
        toolbar_layout.addWidget(self.days_combo)
        
        # Refresh button
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFixedSize(24, 24)
        self.refresh_btn.setToolTip("Refresh Chart")
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                border: 1px solid {border_color};
                color: {border_color};
                font-weight: bold;
                font-size: 14pt;
                border-radius: 2px;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
            QPushButton:pressed {{
                background-color: #1a1a1a;
            }}
        """)
        toolbar_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(toolbar)
        
        # Create figure and canvas - use constrained_layout
        self.figure = Figure(figsize=(8, 5), dpi=100, facecolor='#0a0a0a', constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"border: 2px solid {border_color};")
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Enable mouse wheel zoom
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        
        # Connect to resize event to invalidate background cache for blitting
        self.canvas.mpl_connect('resize_event', self.on_resize)
        
        # Connect to draw_event to recapture background after navigation toolbar actions
        self.canvas.mpl_connect('draw_event', self.on_draw)
        
        # Add navigation toolbar for pan/zoom
        self.nav_toolbar = NavigationToolbar(self.canvas, self)
        self.nav_toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: #1a1a1a;
                border: 1px solid {border_color};
                spacing: 3px;
            }}
            QToolButton {{
                background-color: #2a2a2a;
                border: 1px solid {border_color};
                color: white;
                padding: 3px;
            }}
            QToolButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        layout.addWidget(self.nav_toolbar)
        
        layout.addWidget(self.canvas)
        
        # Set widget size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Initialize empty chart
        self.ax = None
        self.draw_empty_chart()
        
        # Apply dark theme
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #0a0a0a;
                color: white;
            }}
            QLabel {{
                color: white;
                border: none;
            }}
            QComboBox {{
                background-color: #2a2a2a;
                border: 1px solid {border_color};
                padding: 2px 5px;
                color: white;
                border-radius: 2px;
            }}
            QComboBox:hover {{
                background-color: #3a3a3a;
                border: 1px solid {border_color};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid white;
                width: 0px;
                height: 0px;
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                color: white;
                selection-background-color: {border_color};
                border: 1px solid {border_color};
            }}
        """)
    
    def draw_empty_chart(self):
        """Draw empty chart with 'No Data' message"""
        self.figure.clear()
        ax = self.figure.add_subplot(111, facecolor='#0a0a0a')
        ax.text(0.5, 0.5, 'No Data Available',
                ha='center', va='center',
                color='#808080',
                fontsize=14,
                transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        self.canvas.draw()
    
    def on_draw(self, event):
        """Handle draw events - recapture background and redraw animated artists after toolbar operations"""
        try:
            # Only handle if we have an axis and animated artists
            if not hasattr(self, 'ax') or self.ax is None:
                return
            if not hasattr(self, 'animated_artists') or len(self.animated_artists) == 0:
                return
            if self.is_first_draw:
                return
            
            # After matplotlib does a full draw (from zoom/pan/home), 
            # the animated artists are NOT drawn, so we need to:
            # 1. Recapture the clean background (without animated artists)
            self.background = self.canvas.copy_from_bbox(self.ax.bbox)
            
            # 2. Redraw the animated artists on top
            for artist in self.animated_artists:
                if artist in self.ax.lines or artist in self.ax.texts or artist in self.ax.artists:
                    self.ax.draw_artist(artist)
            
            # 3. Blit to show them
            self.canvas.blit(self.ax.bbox)
        except Exception as e:
            # Don't let draw callback errors propagate - just log them
            logger.debug(f"Error in on_draw callback: {e}")
    
    def on_resize(self, event):
        """Handle canvas resize - invalidate background cache for blitting"""
        # When canvas size changes, background becomes invalid
        self.background = None
        # Don't set needs_full_redraw here - let the on_draw callback handle it
        # This prevents clearing the chart when there's no data to redraw with
    
    def on_scroll(self, event):
        """Handle mouse wheel scroll for zoom in/out on x-axis"""
        if event.inaxes is None or not hasattr(self, 'ax') or self.ax is None:
            return
        
        if event.xdata is None:
            return
            
        # Get current x-axis limits
        cur_xlim = self.ax.get_xlim()
        xdata = event.xdata  # Mouse x position in data coordinates
        
        # Zoom factor
        base_scale = 1.2
        if event.button == 'up':
            # Zoom in (show less data, bars appear wider)
            scale_factor = 1 / base_scale
        elif event.button == 'down':
            # Zoom out (show more data, bars appear narrower)
            scale_factor = base_scale
        else:
            return
        
        # Calculate new limits centered on mouse position
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        
        new_left = xdata - new_width * (1 - relx)
        new_right = xdata + new_width * relx
        
        # Apply new limits
        self.ax.set_xlim(new_left, new_right)
        
        # NOTE: Don't force full redraw for zoom - let matplotlib handle it efficiently
        # The background cache remains valid, only the view changes
        self.canvas.draw_idle()
    
    def update_chart_throttled(self, price_data, contract_description: str = ""):
        """Throttled chart update - limits update frequency to prevent UI freezing"""
        import time
        current_time = time.time()
        
        # Check if enough time has passed since last update
        if current_time - self.last_update_time >= self.update_interval:
            # Update immediately
            self.last_update_time = current_time
            self.update_chart(price_data, contract_description)
        else:
            # Schedule update for later if not already scheduled
            if self.pending_update is None:
                remaining_time = self.update_interval - (current_time - self.last_update_time)
                delay_ms = int(remaining_time * 1000)
                self.pending_update = QTimer.singleShot(
                    delay_ms, 
                    lambda: self._execute_pending_update(price_data, contract_description)
                )
    
    def _execute_pending_update(self, price_data, contract_description: str = ""):
        """Execute the pending chart update"""
        import time
        self.pending_update = None
        self.last_update_time = time.time()
        self.update_chart(price_data, contract_description)
    
    def update_chart(self, price_data, contract_description: str = ""):
        """Update chart with price data (line chart for mid-price) - optimized with blitting"""
        if not price_data or len(price_data) < 2:
            self.draw_empty_chart()
            return
        
        try:
            # PERFORMANCE: Limit maximum bars to prevent UI freezing
            MAX_BARS = 2000  # Reasonable limit for smooth rendering
            original_len = len(price_data)
            if original_len > MAX_BARS:
                # Downsample: keep every Nth bar to reduce to MAX_BARS
                step = original_len // MAX_BARS
                price_data = price_data[::step]
                logger.info(f"Downsampled chart data from {original_len} to {len(price_data)} bars")
            
            # Convert to DataFrame
            df = pd.DataFrame(price_data)
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            
            # Ensure numeric columns
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna()
            
            # Sort by time to ensure proper chronological order
            df = df.sort_index()
            
            # Remove duplicate timestamps (keep last)
            df = df[~df.index.duplicated(keep='last')]
            
            if len(df) < 2:
                self.draw_empty_chart()
                return
            
            # Convert timestamps to matplotlib date numbers for proper spacing
            from matplotlib.dates import date2num
            import numpy as np
            x_dates = np.asarray(date2num(df.index))
            y_data = np.asarray(df['close'].values)
            current_price = float(y_data[-1])
            
            # Determine if we need a full redraw or can use blitting
            needs_full_redraw = (self.is_first_draw or 
                                self.ax is None or 
                                self.line_artist is None or
                                self.needs_full_redraw)
            
            if needs_full_redraw:
                # === FULL REDRAW - First time or after significant changes ===
                
                # Save current view limits before clearing
                saved_xlim = None
                if hasattr(self, 'ax') and self.ax is not None:
                    try:
                        saved_xlim = self.ax.get_xlim()
                    except:
                        pass
                
                # Clear figure
                self.figure.clear()
                self.ax = self.figure.add_subplot(111)
                
                # Plot ANIMATED line chart (will be updated via blitting)
                self.line_artist, = self.ax.plot(x_dates, y_data, 
                                                 color=self.border_color, 
                                                 linewidth=2, alpha=0.9, 
                                                 label='Mid Price',
                                                 animated=True)  # KEY: Enable blitting
                
                # Plot ANIMATED current price line
                self.price_line_artist = self.ax.axhline(y=current_price, 
                                                        color=self.border_color, 
                                                        linestyle='--', linewidth=1, 
                                                        alpha=0.5, animated=True)
                
                # Plot ANIMATED price text (will update with price changes)
                self.price_text_artist = self.ax.text(1.01, current_price, 
                                                      f'${current_price:.2f}', 
                                                      transform=self.ax.get_yaxis_transform(),
                                                      color=self.border_color, fontsize=10, 
                                                      fontweight='bold',
                                                      va='center', ha='left',
                                                      bbox=dict(boxstyle='round,pad=0.3', 
                                                               facecolor='#0a0a0a', 
                                                               edgecolor=self.border_color, 
                                                               linewidth=1),
                                                      animated=True)
                
                # Store all animated artists for blitting
                self.animated_artists = [self.line_artist, self.price_line_artist, 
                                        self.price_text_artist]
                
                # Format x-axis as datetime
                self.ax.xaxis_date()
                
                # Style the chart (STATIC elements - drawn once)
                self.ax.set_facecolor('#0a0a0a')
                self.ax.grid(True, color='#1a1a1a', linestyle='-', linewidth=0.5, alpha=0.5)
                self.ax.tick_params(colors='#e0e0e0', labelsize=9)
                self.ax.set_ylabel('Price', color='#e0e0e0', fontsize=9)
                self.ax.set_xlabel('Time', color='#e0e0e0', fontsize=9)
                self.ax.yaxis.tick_right()
                self.ax.yaxis.set_label_position("right")
                
                # Format x-axis with time labels
                self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                self.ax.tick_params(axis='x', rotation=0, colors='#e0e0e0')
                
                # Style spines
                for spine in self.ax.spines.values():
                    spine.set_color(self.border_color)
                    spine.set_linewidth(1.5)
                
                # Set title
                title_text = f"{self.title}"
                if contract_description:
                    title_text += f" - {contract_description}"
                self.title_label.setText(title_text)
                
                # Preserve zoom/pan or set default view
                if saved_xlim is not None:
                    self.ax.set_xlim(saved_xlim)
                    self.ax.autoscale(enable=False, axis='x')
                else:
                    # Default view: last 12 hours (720 bars at 1-min intervals)
                    visible_bars = min(720, len(x_dates))
                    if len(x_dates) > visible_bars:
                        x_range = x_dates[-1] - x_dates[-visible_bars]
                        padding = x_range * 0.02
                        self.ax.set_xlim(x_dates[-visible_bars], x_dates[-1] + padding)
                    else:
                        x_range = x_dates[-1] - x_dates[0]
                        padding = x_range * 0.02
                        self.ax.set_xlim(x_dates[0], x_dates[-1] + padding)
                    self.ax.autoscale(enable=False, axis='x')
                
                # Draw everything (static + animated) to create the background
                self.canvas.draw()
                
                # Cache the background for blitting (excluding animated artists)
                self.background = self.canvas.copy_from_bbox(self.ax.bbox)
                
                # Mark as drawn
                self.is_first_draw = False
                self.needs_full_redraw = False
                
                # Update navigation toolbar
                if hasattr(self, 'nav_toolbar'):
                    self.nav_toolbar.push_current()
                
            else:
                # === FAST UPDATE with BLITTING - Only update animated elements ===
                
                if self.background is None:
                    # Safety: if background was lost, force full redraw
                    self.needs_full_redraw = True
                    self.update_chart(price_data, contract_description)
                    return
                
                # Safety check: ensure all artist attributes exist
                if (self.line_artist is None or self.price_line_artist is None or 
                    self.price_text_artist is None or self.ax is None):
                    # Fall back to full redraw if any artist is missing
                    self.needs_full_redraw = True
                    self.update_chart(price_data, contract_description)
                    return
                
                # Restore the clean background
                self.canvas.restore_region(self.background)
                
                # Update the line data
                self.line_artist.set_data(x_dates, y_data)
                
                # Update current price line position
                self.price_line_artist.set_ydata([current_price, current_price])
                
                # Update price text position and value
                self.price_text_artist.set_position((1.01, current_price))
                self.price_text_artist.set_text(f'${current_price:.2f}')
                
                # Redraw only the animated artists
                for artist in self.animated_artists:
                    self.ax.draw_artist(artist)
                
                # Blit the updated artists onto the canvas
                self.canvas.blit(self.ax.bbox)
                
                # Flush events to update the display
                self.canvas.flush_events()
            
        except Exception as e:
            logger.error(f"Error updating chart {self.title}: {e}", exc_info=True)
            self.needs_full_redraw = True  # Force redraw on next update
            self.draw_empty_chart()


class ProfessionalUnderlyingChart(QWidget):
    """
    Professional candlestick chart for underlying (SPX/XSP) with Z-Score subplot
    Similar to TradeStation multi-panel charts with throttled updates for trading
    """
    
    def __init__(self, title: str, border_color: str = "#FF8C00", parent=None, main_window=None):
        super().__init__(parent)
        self.title = title
        self.border_color = border_color
        self.chart_data = []
        
        # Blitting optimization attributes
        self.background = None
        self.needs_full_redraw = True
        self.is_first_draw = True
        
        # Throttling attributes
        self.last_update_time = 0  # Throttle updates
        self.update_interval = 0.25  # Minimum 250ms between updates (4 FPS)
        self.pending_update = None  # QTimer for pending update
        self.main_window = main_window  # Reference to main window for offset access
        
        # Auto-fetch attributes for loading more historical data
        self.contract_key = None  # Will be set when data is first loaded
        self.is_fetching_more_data = False  # Flag to prevent multiple simultaneous requests
        self.earliest_data_timestamp = None  # Track earliest data point
        self.backfill_req_id = None  # Track request ID for backfill requests
        self.backfill_data = []  # Temporary storage for backfill data before prepending
        self.auto_fetch_timer = None  # Timer for debouncing auto-fetch on scroll
        self.auto_fetch_delay = 500  # Wait 500ms after last scroll before checking
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Top toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(5, 2, 5, 2)
        toolbar_layout.setSpacing(10)
        
        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {border_color};
                font-weight: bold;
                font-size: 11pt;
                border: none;
            }}
        """)
        toolbar_layout.addWidget(self.title_label)
        
        toolbar_layout.addStretch()
        
        # Interval selector
        toolbar_layout.addWidget(QLabel("Interval:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["15 secs", "30 secs", "1 min", "5 min", "15 min", "30 min", "1 hour"])
        self.interval_combo.setCurrentText("1 min")
        self.interval_combo.setFixedWidth(80)
        toolbar_layout.addWidget(self.interval_combo)
        
        # Days to load selector
        toolbar_layout.addWidget(QLabel("Days:"))
        self.days_combo = QComboBox()
        self.days_combo.addItems(["1", "2", "3", "5"])
        self.days_combo.setCurrentText("2")
        self.days_combo.setFixedWidth(50)
        toolbar_layout.addWidget(self.days_combo)
        
        # EMA period selector
        toolbar_layout.addWidget(QLabel("EMA:"))
        self.ema_input = QComboBox()
        self.ema_input.addItems(["9", "20", "50", "200"])
        self.ema_input.setCurrentText("9")
        self.ema_input.setFixedWidth(50)
        self.ema_input.setEditable(True)
        toolbar_layout.addWidget(self.ema_input)
        
        layout.addWidget(toolbar)
        
        # Create figure with subplots - use constrained_layout instead of tight_layout
        self.figure = Figure(figsize=(10, 7), dpi=100, facecolor='#0a0a0a', constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"border: 2px solid {border_color};")
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumSize(400, 300)
        
        # Enable mouse wheel zoom
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        
        # Add navigation toolbar for pan/zoom
        self.nav_toolbar = NavigationToolbar(self.canvas, self)
        self.nav_toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: #1a1a1a;
                border: 1px solid {border_color};
                spacing: 3px;
            }}
            QToolButton {{
                background-color: #2a2a2a;
                border: 1px solid {border_color};
                color: white;
                padding: 3px;
            }}
            QToolButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        layout.addWidget(self.nav_toolbar)
        
        # Ensure the widget itself also expands
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout.addWidget(self.canvas)
        
        # Set widget size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Initialize empty chart
        self.price_ax = None
        self.zscore_ax = None
        self.draw_empty_chart()
        
        # Apply styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #0a0a0a;
                color: white;
            }}
            QLabel {{
                color: white;
                border: none;
            }}
            QComboBox {{
                background-color: #2a2a2a;
                border: 1px solid {border_color};
                padding: 2px 5px;
                color: white;
                border-radius: 2px;
            }}
            QComboBox:hover {{
                background-color: #3a3a3a;
                border: 1px solid {border_color};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid white;
                width: 0px;
                height: 0px;
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                color: white;
                selection-background-color: {border_color};
                border: 1px solid {border_color};
            }}
        """)
    
    def on_scroll(self, event):
        """Handle mouse wheel scroll for zoom in/out on x-axis"""
        if event.inaxes is None or not hasattr(self, 'price_ax') or self.price_ax is None:
            return
        
        if event.xdata is None:
            return
            
        # Get current x-axis limits (shared between price and zscore)
        cur_xlim = self.price_ax.get_xlim()
        xdata = event.xdata  # Mouse x position in data coordinates
        
        # Zoom factor
        base_scale = 1.2
        if event.button == 'up':
            # Zoom in (show less data, bars appear wider)
            scale_factor = 1 / base_scale
        elif event.button == 'down':
            # Zoom out (show more data, bars appear narrower)
            scale_factor = base_scale
        else:
            return
        
        # Calculate new limits centered on mouse position
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        
        new_left = xdata - new_width * (1 - relx)
        new_right = xdata + new_width * relx
        
        # Apply new limits (will affect both subplots due to sharex)
        self.price_ax.set_xlim(new_left, new_right)
        self.canvas.draw_idle()
        
        # Debounced auto-fetch: Reset timer on each scroll, check after 500ms of no scrolling
        if event.button == 'down':  # Only when zooming out
            self.schedule_auto_fetch_check()
    
    def draw_empty_chart(self):
        """Draw empty chart"""
        self.figure.clear()
        ax = self.figure.add_subplot(111, facecolor='#0a0a0a')
        ax.text(0.5, 0.5, 'No Data Available',
                ha='center', va='center',
                color='#808080',
                fontsize=14,
                transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        self.canvas.draw()
    
    def schedule_auto_fetch_check(self):
        """Schedule a check for auto-fetching more data after scroll stops"""
        # Cancel existing timer if any
        if self.auto_fetch_timer is not None:
            self.auto_fetch_timer.stop()
            self.auto_fetch_timer = None
        
        # Create new timer - will fire after 500ms of no scrolling
        from PyQt6.QtCore import QTimer
        self.auto_fetch_timer = QTimer()
        self.auto_fetch_timer.setSingleShot(True)
        self.auto_fetch_timer.timeout.connect(self.check_and_fetch_more_data)
        self.auto_fetch_timer.start(self.auto_fetch_delay)
    
    def check_and_fetch_more_data(self):
        """Check if we need more data based on current view and fetch if needed"""
        if not hasattr(self, 'chart_data') or len(self.chart_data) == 0:
            return
        
        if not hasattr(self, 'price_ax') or self.price_ax is None:
            return
        
        try:
            from matplotlib.dates import date2num, num2date
            import pandas as pd
            
            # Get current visible range
            xlim = self.price_ax.get_xlim()
            visible_start_num = xlim[0]
            visible_end_num = xlim[1]
            
            # Get data range
            df = pd.DataFrame(self.chart_data)
            if df.empty or 'time' not in df.columns:
                return
            
            df['time'] = pd.to_datetime(df['time'])
            earliest_data_num = date2num(df['time'].min())
            latest_data_num = date2num(df['time'].max())
            
            # Check if view extends significantly beyond our data on the left
            data_range = latest_data_num - earliest_data_num
            margin = data_range * 0.15  # 15% margin
            
            if visible_start_num < (earliest_data_num + margin):
                logger.info(f"Auto-fetch triggered: visible start {num2date(visible_start_num)} < earliest data {num2date(earliest_data_num)} + margin")
                self.request_more_historical_data()
        except Exception as e:
            logger.error(f"Error checking for auto-fetch: {e}", exc_info=True)
    
    def request_more_historical_data(self):
        """Request more historical data when zooming out past existing data"""
        if self.is_fetching_more_data or not self.main_window or not self.contract_key:
            return
        
        # Prevent multiple simultaneous requests
        self.is_fetching_more_data = True
        
        try:
            # Get earliest timestamp from current data
            if not self.chart_data or len(self.chart_data) == 0:
                return
            
            import pandas as pd
            from datetime import timedelta
            from matplotlib.dates import date2num
            
            df = pd.DataFrame(self.chart_data)
            df['time'] = pd.to_datetime(df['time'])
            earliest_time = df['time'].min()
            latest_time = df['time'].max()
            
            # Calculate how much data we need based on the GAP between visible start and earliest data
            if hasattr(self, 'price_ax') and self.price_ax is not None:
                xlim = self.price_ax.get_xlim()
                # Convert matplotlib date numbers to datetime
                from matplotlib.dates import num2date
                visible_start = num2date(xlim[0])
                visible_end = num2date(xlim[1])
                earliest_data = num2date(date2num(earliest_time))
                
                # Calculate the gap: from visible start to earliest data
                gap = earliest_data - visible_start
                
                # Request 1.5x the gap to have some buffer
                buffer_multiplier = 1.5
                total_seconds = gap.total_seconds() * buffer_multiplier
                
                # Ensure minimum request size (at least 1 hour of data)
                min_seconds = 3600
                total_seconds = max(total_seconds, min_seconds)
                
                # Calculate duration using IBAPI valid units: S, D, W, M, Y (no H for hours!)
                if total_seconds < 86400:  # Less than 1 day
                    # Use seconds for intraday ranges
                    duration = f"{int(total_seconds)} S"
                elif total_seconds < 604800:  # Less than 1 week
                    # Use days (round up)
                    days = int(total_seconds / 86400) + 1
                    duration = f"{days} D"
                else:
                    # Use weeks (round up)
                    weeks = int(total_seconds / 604800) + 1
                    duration = f"{weeks} W"
                
                logger.info(f"Auto-fetch: Gap is {gap.total_seconds()/3600:.1f} hours, requesting {duration}")
            else:
                # Fallback: request 1 day
                duration = "1 D"
            
            # Format the end time for the request (request data BEFORE the earliest we have)
            # IBAPI format: yyyyMMdd-HH:mm:ss (note the dash, not space)
            end_time_str = earliest_time.strftime("%Y%m%d-%H:%M:%S")
            
            # Get current bar size and duration settings
            interval_text = self.interval_combo.currentText()
            # Map display text to IBAPI bar size format
            bar_size_map = {
                "15 secs": "15 secs",
                "30 secs": "30 secs",
                "1 min": "1 min",
                "5 min": "5 mins",
                "15 min": "15 mins",
                "30 min": "30 mins",
                "1 hour": "1 hour"
            }
            bar_size = bar_size_map.get(interval_text, "1 min")  # Default to 1 min if not found
            
            # Determine the contract based on contract_key
            if self.contract_key == "ES_FUTURES_CONFIRM":
                # ES Futures contract
                from ibapi.contract import Contract
                contract = Contract()
                contract.symbol = "ES"
                contract.secType = "FUT"
                contract.exchange = "CME"
                contract.currency = "USD"
                # Get front month
                from datetime import datetime
                today = datetime.now()
                month_code = {12: 'Z', 3: 'H', 6: 'M', 9: 'U'}
                current_month = today.month
                current_year = today.year % 100
                # Determine which quarter we're in and get next contract
                if current_month <= 3:
                    contract.lastTradeDateOrContractMonth = f"{current_year}03"
                elif current_month <= 6:
                    contract.lastTradeDateOrContractMonth = f"{current_year}06"
                elif current_month <= 9:
                    contract.lastTradeDateOrContractMonth = f"{current_year}09"
                else:
                    contract.lastTradeDateOrContractMonth = f"{current_year}12"
                    
            elif self.contract_key.startswith("UNDERLYING_"):
                # SPX/XSP underlying contract
                from ibapi.contract import Contract
                contract = Contract()
                symbol = self.contract_key.replace("UNDERLYING_", "").split("_")[0]
                contract.symbol = symbol
                contract.secType = "IND"
                contract.exchange = "CBOE"
                contract.currency = "USD"
            else:
                logger.warning(f"Unknown contract_key: {self.contract_key}")
                self.is_fetching_more_data = False
                return
            
            # Get next request ID
            req_id = self.main_window.app_state.get('next_order_id', 1)
            self.main_window.app_state['next_order_id'] = req_id + 1
            
            # Track this request and mark it as a backfill
            self.main_window.app_state['historical_data_requests'][req_id] = self.contract_key
            self.backfill_req_id = req_id  # Remember this is a backfill request
            
            # Request historical data ending at our earliest point
            self.main_window.ibkr_client.reqHistoricalData(
                req_id,
                contract,
                end_time_str,  # End at our earliest existing data point
                duration,  # Get 1 more day
                bar_size,  # Use current chart interval
                "TRADES",
                0,  # Include after-hours
                1,  # Format date
                False,  # Don't keep up to date for historical backfill
                []
            )
            
            logger.info(f"Requested more historical data for {self.contract_key} ending at {end_time_str} (req_id={req_id})")
            
        except Exception as e:
            logger.error(f"Error requesting more historical data: {e}", exc_info=True)
            self.is_fetching_more_data = False
    
    def update_chart_throttled(self, price_data, ema_period=9, z_period=30, z_threshold=1.5, is_es_futures=False):
        """Throttled chart update - limits update frequency to prevent UI freezing"""
        import time
        current_time = time.time()
        
        # Check if enough time has passed since last update
        if current_time - self.last_update_time >= self.update_interval:
            # Update immediately
            self.last_update_time = current_time
            self.update_chart(price_data, ema_period, z_period, z_threshold, is_es_futures)
        else:
            # Schedule update for later if not already scheduled
            if self.pending_update is None:
                remaining_time = self.update_interval - (current_time - self.last_update_time)
                delay_ms = int(remaining_time * 1000)
                self.pending_update = QTimer.singleShot(
                    delay_ms,
                    lambda: self._execute_pending_update(price_data, ema_period, z_period, z_threshold, is_es_futures)
                )
    
    def _execute_pending_update(self, price_data, ema_period=9, z_period=30, z_threshold=1.5, is_es_futures=False):
        """Execute the pending chart update"""
        import time
        self.pending_update = None
        self.last_update_time = time.time()
        self.update_chart(price_data, ema_period, z_period, z_threshold, is_es_futures)
    
    def update_chart(self, price_data, ema_period=9, z_period=30, z_threshold=1.5, is_es_futures=False):
        """Update chart with price data, EMA, and Z-Score - optimized with downsampling"""
        if not price_data or len(price_data) < max(ema_period, z_period):
            self.draw_empty_chart()
            return
        
        try:
            # Store the chart data for auto-fetch feature
            self.chart_data = price_data.copy() if isinstance(price_data, list) else list(price_data)
            
            # Set contract_key based on chart title if not already set
            if self.contract_key is None:
                if "Confirmation" in self.title:
                    self.contract_key = "ES_FUTURES_CONFIRM"
                elif "Trade" in self.title:
                    # Will be set by main window based on selected underlying
                    self.contract_key = "UNDERLYING_SPX_TRADE"  # Default
            
            # PERFORMANCE: Limit maximum bars to prevent UI freezing
            MAX_BARS = 2000  # Reasonable limit for smooth candlestick rendering
            original_len = len(price_data)
            if original_len > MAX_BARS:
                # Downsample: keep every Nth bar to reduce to MAX_BARS
                step = original_len // MAX_BARS
                price_data = price_data[::step]
                logger.info(f"Downsampled candlestick chart from {original_len} to {len(price_data)} bars")
            
            # Save current view limits BEFORE clearing figure
            # BUT: Don't save xlim if this is a full redraw after backfill
            # (the xlim date numbers won't match the new data after prepending)
            saved_xlim = None
            if hasattr(self, 'price_ax') and self.price_ax is not None and not self.needs_full_redraw:
                try:
                    saved_xlim = self.price_ax.get_xlim()
                    logger.debug(f"Saved xlim: {saved_xlim}")
                except:
                    pass
            elif self.needs_full_redraw:
                logger.debug("Skipping xlim save due to full redraw flag")
            
            # Convert to DataFrame
            df = pd.DataFrame(price_data)
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna()
            
            # Sort by time to ensure proper chronological order
            df = df.sort_index()
            
            # Remove duplicate timestamps (keep last)
            df = df[~df.index.duplicated(keep='last')]
            
            if len(df) < 2:
                self.draw_empty_chart()
                return
            
            # Calculate EMA
            df['ema'] = df['close'].ewm(span=ema_period, adjust=False).mean()
            
            # Calculate offset-adjusted price if this is ES futures data
            if is_es_futures and self.main_window is not None:
                offset = self.main_window.es_to_cash_offset
                # For XSP: (ES/10) - offset, For SPX: ES - offset
                if self.main_window.instrument['underlying_symbol'] == 'XSP':
                    df['offset_adjusted'] = (df['close'] / 10.0) - offset
                else:
                    df['offset_adjusted'] = df['close'] - offset
            
            # Calculate Z-Score
            df['z_score'] = (df['close'] - df['close'].rolling(z_period).mean()) / df['close'].rolling(z_period).std()
            
            # Clear figure and create subplots
            self.figure.clear()
            gs = self.figure.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
            
            # Price chart (top) - optimized candlestick rendering with LineCollection
            self.price_ax = self.figure.add_subplot(gs[0])
            
            # Convert timestamps to matplotlib date numbers for proper spacing
            from matplotlib.dates import date2num
            from matplotlib.collections import LineCollection, PatchCollection
            x_dates = date2num(df.index)
            
            # Calculate bar width based on time interval (in days)
            if len(x_dates) > 1:
                bar_width = (x_dates[1] - x_dates[0]) * 0.6  # 60% of interval
            else:
                bar_width = 0.0003  # ~30 seconds for single bar
            
            # OPTIMIZED: Use collections instead of individual plots for better performance
            wick_segments = []  # High-low lines
            wick_colors = []
            body_patches = []  # Open-close rectangles
            body_colors = []
            
            for i, (timestamp, row) in enumerate(df.iterrows()):
                x = x_dates[i]
                is_bullish = row['close'] >= row['open']
                color = '#00ff00' if is_bullish else '#ff0000'
                
                # Collect wick data (high-low line)
                wick_segments.append([(x, row['low']), (x, row['high'])])
                wick_colors.append(color)
                
                # Collect body data (open-close rectangle)
                body_height = abs(row['close'] - row['open'])
                body_bottom = min(row['open'], row['close'])
                rect = Rectangle(
                    (x - bar_width/2, body_bottom), 
                    bar_width, 
                    body_height if body_height > 0 else 0.01,
                    facecolor=color,
                    edgecolor=color,
                    alpha=0.9
                )
                body_patches.append(rect)
                body_colors.append(color)
            
            # Draw all wicks as a single LineCollection (much faster than individual plots)
            if wick_segments:
                wick_collection = LineCollection(wick_segments, colors=wick_colors, 
                                                linewidths=1, alpha=0.8)
                self.price_ax.add_collection(wick_collection)
            
            # Draw all bodies as a PatchCollection (faster than individual patches)
            if body_patches:
                body_collection = PatchCollection(body_patches, match_original=True)
                self.price_ax.add_collection(body_collection)
            
            # Add EMA overlay using datetime x-axis
            self.price_ax.plot(x_dates, df['ema'].values.tolist(), color=self.border_color, 
                             linewidth=1.5, label=f'EMA({ema_period})', alpha=0.8)
            
            # Add offset-adjusted line if ES futures data
            if is_es_futures and 'offset_adjusted' in df.columns:
                self.price_ax.plot(x_dates, df['offset_adjusted'].values.tolist(), color='#FFFF00', 
                                 linewidth=1.5, label='Offset', alpha=0.8)
            
            # Set axis limits to include all data
            if len(x_dates) > 0:
                self.price_ax.set_xlim(x_dates[0] - bar_width, x_dates[-1] + bar_width)
                y_min = df[['low']].min().min()
                y_max = df[['high']].max().max()
                y_range = y_max - y_min
                self.price_ax.set_ylim(y_min - y_range * 0.05, y_max + y_range * 0.05)
            
            # Style price chart
            self.price_ax.set_facecolor('#0a0a0a')
            self.price_ax.grid(True, color='#1a1a1a', linestyle='-', linewidth=0.5, alpha=0.5)
            self.price_ax.tick_params(colors='#e0e0e0', labelsize=9, labelbottom=False)
            self.price_ax.set_ylabel('Price', color='#e0e0e0', fontsize=9)
            self.price_ax.yaxis.tick_right()
            self.price_ax.yaxis.set_label_position("right")
            self.price_ax.legend(loc='upper left', facecolor='#0a0a0a', 
                               edgecolor=self.border_color, labelcolor='#e0e0e0', 
                               fontsize=8, framealpha=0.8)
            
            # Add current price horizontal line (green dotted)
            current_price = float(df['close'].iloc[-1])
            self.price_ax.axhline(y=current_price, color='#00ff00', 
                                 linestyle=':', linewidth=2, alpha=0.7)
            
            # Add current price text label on right y-axis
            self.price_ax.text(1.01, current_price, f'${current_price:.2f}', 
                              transform=self.price_ax.get_yaxis_transform(),
                              color='#00ff00', fontsize=10, fontweight='bold',
                              va='center', ha='left',
                              bbox=dict(boxstyle='round,pad=0.3', facecolor='#0a0a0a', 
                                       edgecolor='#00ff00', linewidth=1))
            
            # Format x-axis as time
            self.price_ax.xaxis_date()
            
            for spine in self.price_ax.spines.values():
                spine.set_color(self.border_color)
                spine.set_linewidth(1.5)
            
            # Z-Score chart (bottom)
            self.zscore_ax = self.figure.add_subplot(gs[1], sharex=self.price_ax)
            
            # Plot Z-Score line
            self.zscore_ax.plot(df.index, df['z_score'], color='#4a9eff', linewidth=1.5)
            
            # Fill between zero line (convert to numpy arrays for type compatibility)
            z_values = df['z_score'].values
            self.zscore_ax.fill_between(df.index, 0, df['z_score'], 
                                       where=(z_values >= 0),  # type: ignore[arg-type]
                                       color='#00ff00', alpha=0.2, interpolate=True)
            self.zscore_ax.fill_between(df.index, 0, df['z_score'], 
                                       where=(z_values < 0),  # type: ignore[arg-type]
                                       color='#ff0000', alpha=0.2, interpolate=True)
            
            # Z-Score threshold lines
            self.zscore_ax.axhline(y=0, color='#808080', linestyle='-', linewidth=1, alpha=0.5)
            self.zscore_ax.axhline(y=z_threshold, color='#00ff00', linestyle='--', linewidth=1, alpha=0.5)
            self.zscore_ax.axhline(y=-z_threshold, color='#ff0000', linestyle='--', linewidth=1, alpha=0.5)
            
            # Style Z-Score chart
            self.zscore_ax.set_facecolor('#0a0a0a')
            self.zscore_ax.grid(True, color='#1a1a1a', linestyle='-', linewidth=0.5, alpha=0.5)
            self.zscore_ax.tick_params(colors='#e0e0e0', labelsize=8)
            self.zscore_ax.set_ylabel('Z-Score', color='#e0e0e0', fontsize=9)
            self.zscore_ax.set_ylim(-3, 3)
            self.zscore_ax.yaxis.tick_right()
            self.zscore_ax.yaxis.set_label_position("right")
            self.zscore_ax.set_xlabel('Time', color='#e0e0e0', fontsize=9)
            
            for spine in self.zscore_ax.spines.values():
                spine.set_color(self.border_color)
                spine.set_linewidth(1.5)
            
            # Format x-axis with better time labels
            self.zscore_ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            self.zscore_ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            self.zscore_ax.tick_params(axis='x', rotation=0, colors='#e0e0e0', labelsize=9)
            
            # Preserve current zoom/pan state if we saved it, otherwise set default view
            if saved_xlim is not None:
                # Restore the user's view from before figure was cleared (applies to both subplots due to sharex)
                self.price_ax.set_xlim(saved_xlim)
                self.price_ax.autoscale(enable=False, axis='x')
            else:
                # First time drawing - set default view to show last 12 hours (720 bars at 1-min intervals)
                visible_bars = min(720, len(x_dates))  # 12 hours = 720 minutes
                if len(x_dates) > visible_bars:
                    x_range = x_dates[-1] - x_dates[-visible_bars]
                    padding = x_range * 0.02
                    self.price_ax.set_xlim(x_dates[-visible_bars], x_dates[-1] + padding)
                else:
                    # Show all data if less than 12 hours available
                    x_range = x_dates[-1] - x_dates[0]
                    padding = x_range * 0.02
                    self.price_ax.set_xlim(x_dates[0], x_dates[-1] + padding)
                self.price_ax.autoscale(enable=False, axis='x')
            
            # Update title (price shown on chart now)
            self.title_label.setText(self.title)
            
            # No need to call tight_layout - using constrained_layout in Figure constructor
            # Use draw_idle() to avoid blocking UI thread
            self.canvas.draw_idle()
            
            # Reset the full redraw flag after completing the redraw
            if self.needs_full_redraw:
                self.needs_full_redraw = False
                logger.debug("Reset needs_full_redraw flag after completing full redraw")
            
            # Update navigation toolbar to reflect current view
            if hasattr(self, 'nav_toolbar'):
                self.nav_toolbar.push_current()
            
        except Exception as e:
            logger.error(f"Error updating underlying chart {self.title}: {e}", exc_info=True)
            self.draw_empty_chart()


# ============================================================================
# CHART WINDOW - POPUP WINDOW FOR CHARTS
# ============================================================================

class ChartWindow(QMainWindow):
    """Popup window for displaying all four charts"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Charts - 0DTE Options Trader")
        self.setGeometry(150, 150, 1400, 800)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        
        # Create 2x2 grid for charts with equal spacing
        self.charts_widget = QWidget()
        self.charts_layout = QGridLayout(self.charts_widget)
        self.charts_layout.setSpacing(5)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        
        # Set equal row and column stretch factors for uniform expansion
        self.charts_layout.setRowStretch(0, 1)
        self.charts_layout.setRowStretch(1, 1)
        self.charts_layout.setColumnStretch(0, 1)
        self.charts_layout.setColumnStretch(1, 1)
        
        layout.addWidget(self.charts_widget)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QWidget {
                background-color: #1a1a1a;
                color: white;
            }
        """)
        
        logger.info("ChartWindow initialized")


# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        logger.info("Initializing MainWindow")
        
        # Application state (shared with IBKR wrapper)
        self.app_state = {
            'next_order_id': 1,
            'next_req_id': 1000,  # For market data requests
            'underlying_price': 0.0,  # Current underlying price (SPX, XSP, etc.)
            'es_price': 0.0,  # ES futures price (23/6 trading for strike calculations)
            'underlying_req_id': None,  # Request ID for underlying price subscription
            'es_req_id': None,  # ES futures request ID
            'data_server_ok': False,
            'managed_accounts': [],
            'account': '',
            'market_data_map': {},  # reqId -> contract_key
            'historical_data_requests': {},  # reqId -> contract_key
            'active_option_req_ids': [],  # Track active option chain request IDs
        }
        
        # ES to cash offset tracking
        self.es_to_cash_offset = 0.0  # ES futures premium/discount to cash index (persistent)
        self.last_underlying_price = 0.0  # Last seen underlying price for offset calculation
        self.last_offset_update_time = 0  # Timestamp of last offset update
        self.offset_update_enabled = True  # True during market hours, False overnight
        self.es_futures_was_closed = None  # Track previous ES futures market state for transition detection
        
        # Trading state
        self.positions = {}  # contract_key -> position_data
        self.saved_positions = {}  # Loaded from positions.json for entryTime persistence
        self.market_data = {}  # contract_key -> market_data
        self.pending_orders = {}  # order_id -> (contract_key, action, quantity)
        self.chasing_orders = {}  # order_id -> chasing_order_info (for all orders with mid-price chasing enabled)
        self.historical_data = {}  # contract_key -> bars
        
        # Chart data storage - separate from general historical_data for chart-specific needs
        self.chart_data = {
            'underlying': [],  # SPX/XSP bars for confirmation chart
            'underlying_trade': [],  # SPX/XSP bars for trade chart
            'selected_call': [],  # Currently selected call option bars
            'selected_put': [],   # Currently selected put option bars
        }
        
        # Chart update tracking
        self.last_chart_update = 0
        self.chart_update_interval = 5000  # Update charts every 5 seconds max
        self.current_call_contract = None  # Currently displayed call contract
        self.current_put_contract = None   # Currently displayed put contract
        
        # Request tracking for charts
        self.request_id_map = {}  # Maps request IDs to contract keys for chart updates
        
        # Chart window (popup window for charts)
        self.chart_window = None
        
        # Connection settings
        self.host = "127.0.0.1"
        self.port = 7497  # Paper trading
        self.client_id = 1
        self.client_id_iterator = 1  # Current client ID being tried
        self.max_client_id = 10  # Maximum client ID to try
        self.handling_client_id_error = False  # Flag to prevent double reconnect
        self.connection_state = ConnectionState.DISCONNECTED
        
        # ========================================================================
        # INSTRUMENT SELECTION - Uses global variable from top of file
        # ========================================================================
        # The instrument is now controlled by SELECTED_INSTRUMENT at the top of this file
        self.trading_instrument = SELECTED_INSTRUMENT
        self.instrument = INSTRUMENT_CONFIG[self.trading_instrument]
        
        # Set convenient shortcuts to instrument properties
        self.strike_interval = self.instrument['strike_increment']
        
        # Set window title based on selected instrument
        self.setWindowTitle(f"{self.instrument['name']} 0DTE Options Trader - PyQt6 Professional Edition")
        self.setGeometry(100, 100, 1600, 900)
        
        logger.info(f"═══════════════════════════════════════════════════════")
        logger.info(f"TRADING INSTRUMENT: {self.instrument['name']}")
        logger.info(f"Description: {self.instrument['description']}")
        logger.info(f"Strike Increment: ${self.instrument['strike_increment']}")
        logger.info(f"Tick Sizes: ≥$3.00→${self.instrument['tick_size_above_3']}, <$3.00→${self.instrument['tick_size_below_3']}")
        logger.info(f"═══════════════════════════════════════════════════════")
        
        # Set timezone to Central Time (America/Chicago) - ALL TIMES IN THIS APP USE CT
        self.local_tz = pytz.timezone('America/Chicago')
        logger.info(f"Application timezone set to: {self.local_tz} (Central Time)")
        self.last_refresh_date = datetime.now(self.local_tz).date()
        
        # Strategy parameters
        self.strikes_above = 20
        self.strikes_below = 20
        self.current_expiry = self.calculate_expiry_date(0)
        self.chain_refresh_interval = 3600  # Auto-refresh chain every hour (in seconds)
        self.last_chain_center_strike = 0  # Track last center strike for drift detection
        self.chain_drift_threshold = 5  # Number of strikes to drift before auto-recentering (default: 5)
        self.is_recentering_chain = False  # Flag to prevent recentering loops
        self.last_recenter_time = 0  # Timestamp of last recenter to throttle rapid recenters
        self.delta_calibration_done = False  # Track if we've done initial delta-based recenter after chain load
        
        # TradeStation chain parameters (separate from main chain)
        self.ts_strikes_above = 6  # Fewer strikes for TS chains (default: 6)
        self.ts_strikes_below = 6
        self.ts_0dte_center_strike = 0  # Track center strike for drift detection
        self.ts_1dte_center_strike = 0
        self.ts_chain_drift_threshold = 3  # Drift threshold for TS chains (default: 3)
        
        # Auto-refresh timer for 4:00 PM ET expiration switch
        self.market_close_timer = QTimer()
        self.market_close_timer.timeout.connect(self.check_market_close_refresh)
        self.market_close_timer.start(60000)  # Check every 60 seconds
        
        # ES offset monitoring timer (check market hours and ES futures state every minute)
        self.offset_monitor_timer = QTimer()
        self.offset_monitor_timer.timeout.connect(self.check_offset_monitoring)
        self.offset_monitor_timer.start(60000)  # Check every minute for responsive market state detection
        
        # ES offset save timer (save offset every 1 minute during market hours)
        self.offset_save_timer = QTimer()
        self.offset_save_timer.timeout.connect(self.save_offset_to_settings)
        self.offset_save_timer.start(60000)  # Save every 60 seconds
        
        # Manual trading settings
        self.give_in_interval = 5.0  # Seconds between "give in" price adjustments (configurable)
        
        # Master Settings (Strategy Control Panel)
        self.strategy_enabled = False  # Strategy automation OFF by default
        self.vix_threshold = 20.0
        self.time_stop = 60  # minutes
        self.target_delta = 30  # Target delta for option selection (10, 20, 30, 40, 50)
        self.max_risk = 500  # Max risk in dollars
        self.trade_qty = 1  # Fixed trade quantity
        self.position_size_mode = "fixed"  # "fixed" or "calculated" (by risk)
        
        # Straddle Strategy Settings
        self.straddle_enabled = False  # Straddle automation OFF by default
        self.straddle_frequency = 60  # minutes
        self.straddle_next_entry = None  # Next scheduled entry time
        self.last_straddle_time = None  # Last straddle entry timestamp
        self.active_straddles = []  # List of active straddle positions for tracking
        self.straddle_timer = None  # QTimer for straddle checks
        
        # Vega Delta Neutral Strategy Settings
        self.vega_strategy_enabled = False  # Vega strategy OFF by default
        self.vega_target = 500  # Target vega exposure
        self.max_delta_threshold = 10  # Maximum allowed delta before rehedge
        self.auto_hedge_enabled = False  # Auto delta hedging OFF by default
        self.vega_positions = {}  # Track vega strategy positions: {trade_id: position_data}
        self.vega_scan_results = []  # Store scanner results
        self.last_vega_scan_time = None  # Last scan timestamp
        self.portfolio_greeks = {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0}  # Portfolio Greeks
        
        # MES Futures Hedging
        self.mes_contract = None  # MES futures contract (will be initialized when needed)
        self.mes_front_month = None  # Front month contract string (e.g., "202512")
        self.hedge_orders = {}  # Track hedge orders: {order_id: {'trade_id': ..., 'action': ..., 'quantity': ...}}
        self.mes_price = 0  # Current MES price
        self.mes_req_id = None  # Market data request ID for MES
        
        # Long Straddles Strategy Settings
        self.straddle_strategy_enabled = False  # Straddle strategy OFF by default
        self.straddle_otm_strikes = 1  # Number of strikes OTM (1 = first OTM, 2 = second OTM, etc.)
        self.straddle_positions = {}  # Track straddle positions: {trade_id: position_data}
        self.straddle_trade_counter = 1  # Counter for generating unique trade IDs
        
        # Chart Settings - Confirmation Chart
        self.confirm_ema_length = 9
        self.confirm_z_period = 30
        self.confirm_z_threshold = 1.5
        
        # Chart Settings - Trade Chart
        self.trade_ema_length = 9
        self.trade_z_period = 30
        self.trade_z_threshold = 1.5
        
        # IBKR API setup
        self.signals = IBKRSignals()
        self.ibkr_wrapper = IBKRWrapper(self.signals, self.app_state, self)
        self.ibkr_client = IBKRClient(self.ibkr_wrapper)
        self.ibkr_wrapper.set_client(self.ibkr_client)  # Set client reference for market data subscriptions
        self.ibkr_thread = None
        
        # TradeStation setup
        self.ts_signals = TradeStationSignals()
        self.ts_manager = None
        self.ts_enabled = False
        self.ts_strategy_state = "FLAT"
        self.ts_signal_log = []
        self.ts_0dte_chain_data = {}
        self.ts_1dte_chain_data = {}
        self.ts_0dte_expiry = None
        self.ts_1dte_expiry = None
        self.ts_active_contract_type = "0DTE"
        self.ts_last_signal_time = None
        self.ts_position_count = 0
        
        # TS chain drift tracking (same logic as main chain)
        self.ts_0dte_center_strike = 0  # Center strike when 0DTE chain was loaded
        self.ts_1dte_center_strike = 0  # Center strike when 1DTE chain was loaded
        self.ts_0dte_delta_calibration_done = False  # Flag: Has delta-based ATM been found for 0DTE?
        self.ts_1dte_delta_calibration_done = False  # Flag: Has delta-based ATM been found for 1DTE?
        self.ts_0dte_last_recenter_time = 0  # Timestamp of last 0DTE recenter
        self.ts_1dte_last_recenter_time = 0  # Timestamp of last 1DTE recenter
        self.ts_0dte_is_recentering = False  # Flag: Currently recentering 0DTE chain?
        self.ts_1dte_is_recentering = False  # Flag: Currently recentering 1DTE chain?
        
        # Connect signals
        self.connect_signals()
        
        # Setup UI
        self.setup_ui()
        self.apply_dark_theme()
        
        # Load settings
        self.load_settings()
        self.load_positions()  # Load saved positions to preserve entryTime
        
        # Log ES offset tracking status at startup
        if self.is_market_hours():
            logger.info("ES offset tracking: ACTIVE (market hours 8:30 AM - 3:00 PM CT)")
        else:
            logger.info("ES offset tracking: INACTIVE (outside market hours) - using saved offset from day session")
        
        # Start position auto-update timer (1-second updates for time tracking and P&L)
        self.position_update_timer = QTimer()
        self.position_update_timer.timeout.connect(self.update_positions_display)
        self.position_update_timer.timeout.connect(self.update_ts_positions_display)
        self.position_update_timer.start(1000)  # Update every 1000ms (1 second)
        
        # Start position auto-save timer (save every 60 seconds)
        self.position_save_timer = QTimer()
        self.position_save_timer.timeout.connect(self.save_positions)
        self.position_save_timer.start(60000)  # Save every 60 seconds
        
        # Auto-connect after 2 seconds
        QTimer.singleShot(2000, self.connect_to_ibkr)
        
        # Initialize real chart data after connection
        QTimer.singleShot(5000, self.request_chart_data)
    
    def connect_signals(self):
        """Connect IBKR signals to GUI slots"""
        self.signals.connection_status.connect(self.on_connection_status)
        self.signals.connection_message.connect(self.log_message)
        self.signals.underlying_price_updated.connect(self.update_underlying_display)
        self.signals.es_price_updated.connect(self.update_es_display)
        self.signals.market_data_tick.connect(self.on_market_data_tick)
        self.signals.greeks_updated.connect(self.on_greeks_updated)
        self.signals.next_order_id.connect(self.on_next_order_id)
        self.signals.managed_accounts.connect(self.on_managed_accounts)
        self.signals.position_update.connect(self.on_position_update)
        self.signals.position_closed.connect(self.on_position_closed)
        self.signals.order_status_update.connect(self.on_order_status)
        self.signals.historical_bar.connect(self.on_historical_bar)
        self.signals.historical_complete.connect(self.on_historical_complete)
        self.signals.historical_bar_update.connect(self.on_historical_bar_update)
        
        # Connect TradeStation signals
        if TRADESTATION_AVAILABLE:
            self.ts_signals.ts_connected.connect(self.on_ts_connected)
            self.ts_signals.ts_message.connect(self.on_ts_message)
            self.ts_signals.ts_activity.connect(self.on_ts_activity)  # NEW: Activity Log
            self.ts_signals.entry_signal.connect(self.on_ts_entry_signal)
            self.ts_signals.exit_signal.connect(self.on_ts_exit_signal)
            self.ts_signals.signal_update.connect(self.on_ts_signal_update)
            self.ts_signals.strategy_state_changed.connect(self.on_ts_strategy_state_changed)
    
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
        
        # Tab 2: Vega Strategy
        self.vega_tab = self.create_vega_strategy_tab()
        self.tabs.addTab(self.vega_tab, "Vega Strategy")
        
        # Tab 3: Long Straddles Strategy
        self.straddle_tab = self.create_straddle_strategy_tab()
        self.tabs.addTab(self.straddle_tab, "Long Straddles")
        
        # Tab 4: Settings
        self.settings_tab = self.create_settings_tab()
        self.tabs.addTab(self.settings_tab, "Settings")
        
        # Tab 5: TradeStation
        if TRADESTATION_AVAILABLE:
            self.tradestation_tab = self.create_tradestation_tab()
            self.tabs.addTab(self.tradestation_tab, "TradeStation")
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Status: Disconnected")
        self.status_bar.addWidget(self.status_label)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.status_bar.addWidget(self.connect_btn)
        
        self.pnl_label = QLabel("Total P&L: $0.00")
        self.pnl_label.setStyleSheet("font-weight: bold; padding: 2px 12px;")
        self.status_bar.addPermanentWidget(self.pnl_label)
        
        # Add spacer
        spacer1 = QLabel("  |  ")
        spacer1.setStyleSheet("color: #666666;")
        self.status_bar.addPermanentWidget(spacer1)
        
        self.cost_basis_label = QLabel("Total Cost Basis: $0.00")
        self.cost_basis_label.setStyleSheet("font-weight: bold; color: #aaaaaa; padding: 2px 12px;")
        self.status_bar.addPermanentWidget(self.cost_basis_label)
        
        # Add spacer
        spacer2 = QLabel("  |  ")
        spacer2.setStyleSheet("color: #666666;")
        self.status_bar.addPermanentWidget(spacer2)
        
        self.mkt_value_label = QLabel("Total Mkt Value: $0.00")
        self.mkt_value_label.setStyleSheet("font-weight: bold; color: #aaaaaa; padding: 2px 12px;")
        self.status_bar.addPermanentWidget(self.mkt_value_label)
    
    def create_option_chart(self, title: str, border_color: str):
        """Create a single option chart widget"""
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        chart_layout.setContentsMargins(2, 2, 2, 2)
        
        # Chart controls
        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(5, 2, 5, 2)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-weight: bold; color: {border_color}; font-size: 11pt;")
        controls_layout.addWidget(title_label)
        
        controls_layout.addStretch()
        
        # Timeframe selector
        timeframe_combo = QComboBox()
        timeframe_combo.addItems(["1 min", "5 min", "15 min", "30 min", "1 hour"])
        timeframe_combo.setCurrentText("1 min")
        timeframe_combo.setFixedWidth(80)
        controls_layout.addWidget(QLabel("Interval:"))
        controls_layout.addWidget(timeframe_combo)
        
        # Days selector
        days_combo = QComboBox()
        days_combo.addItems(["1", "2", "5", "10", "20"])
        days_combo.setCurrentText("1")
        days_combo.setFixedWidth(50)
        controls_layout.addWidget(QLabel("Days:"))
        controls_layout.addWidget(days_combo)
        
        chart_layout.addWidget(controls_frame)
        
        # Chart area
        figure = Figure(figsize=(6, 4), dpi=80, facecolor='#1a1a1a')
        figure.subplots_adjust(left=0.08, right=0.95, top=0.95, bottom=0.1)
        
        canvas = FigureCanvas(figure)
        chart_layout.addWidget(canvas)
        
        # Chart styling
        chart_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #1a1a1a;
                border: 2px solid {border_color};
                border-radius: 5px;
            }}
            QComboBox {{
                background-color: #2a2a2a;
                border: 1px solid {border_color};
                padding: 2px;
                color: white;
            }}
            QLabel {{
                color: white;
                border: none;
            }}
        """)
        
        # Initialize empty chart
        ax = figure.add_subplot(111, facecolor='#202020')
        ax.set_title(f"{title} - No Data", color='white', fontsize=10)
        ax.tick_params(colors='white', labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(border_color)
        ax.grid(True, color='#3a3a3a', alpha=0.3)
        canvas.draw()
        
        # Store references for updates using setattr to avoid type checker warnings
        setattr(chart_widget, 'figure', figure)
        setattr(chart_widget, 'canvas', canvas)
        setattr(chart_widget, 'ax', ax)
        setattr(chart_widget, 'timeframe_combo', timeframe_combo)
        setattr(chart_widget, 'days_combo', days_combo)
        
        return chart_widget
    
    def create_spx_chart(self, title: str, border_color: str, is_confirmation: bool):
        """Create an SPX chart with price and Z-Score subplots"""
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        chart_layout.setContentsMargins(2, 2, 2, 2)
        
        # Chart controls
        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(5, 2, 5, 2)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-weight: bold; color: {border_color}; font-size: 11pt;")
        controls_layout.addWidget(title_label)
        
        controls_layout.addStretch()
        
        # Interval selector
        interval_combo = QComboBox()
        if is_confirmation:
            interval_combo.addItems(["1 min", "5 min", "15 min", "30 min", "1 hour"])
            interval_combo.setCurrentText("1 min")
        else:
            interval_combo.addItems(["1 secs", "5 secs", "10 secs", "15 secs", "30 secs", "1 min"])
            interval_combo.setCurrentText("15 secs")
        interval_combo.setFixedWidth(80)
        controls_layout.addWidget(QLabel("Interval:"))
        controls_layout.addWidget(interval_combo)
        
        # Period selector
        period_combo = QComboBox()
        period_combo.addItems(["1 D", "2 D", "5 D"])
        period_combo.setCurrentText("1 D")
        period_combo.setFixedWidth(50)
        controls_layout.addWidget(QLabel("Period:"))
        controls_layout.addWidget(period_combo)
        
        # Chart settings
        controls_layout.addWidget(QLabel("EMA:"))
        ema_spinbox = QSpinBox()
        ema_spinbox.setRange(1, 200)
        ema_spinbox.setValue(20 if is_confirmation else 9)
        ema_spinbox.setFixedWidth(50)
        controls_layout.addWidget(ema_spinbox)
        
        controls_layout.addWidget(QLabel("Z Period:"))
        z_period_spinbox = QSpinBox()
        z_period_spinbox.setRange(5, 100)
        z_period_spinbox.setValue(30)
        z_period_spinbox.setFixedWidth(50)
        controls_layout.addWidget(z_period_spinbox)
        
        controls_layout.addWidget(QLabel("Z Threshold:"))
        z_threshold_spinbox = QDoubleSpinBox()
        z_threshold_spinbox.setRange(0.5, 5.0)
        z_threshold_spinbox.setValue(1.5)
        z_threshold_spinbox.setSingleStep(0.1)
        z_threshold_spinbox.setFixedWidth(60)
        controls_layout.addWidget(z_threshold_spinbox)
        
        chart_layout.addWidget(controls_frame)
        
        # Chart area with two subplots
        figure = Figure(figsize=(8, 5), dpi=80, facecolor='#1a1a1a')
        figure.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.08, hspace=0.05)
        
        canvas = FigureCanvas(figure)
        chart_layout.addWidget(canvas)
        
        # Navigation toolbar
        toolbar = NavigationToolbar(canvas, chart_widget)
        toolbar.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border: 1px solid {border_color};
                color: white;
            }}
        """)
        chart_layout.addWidget(toolbar)
        
        # Chart styling
        chart_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #1a1a1a;
                border: 2px solid {border_color};
                border-radius: 5px;
            }}
            QComboBox, QSpinBox, QDoubleSpinBox {{
                background-color: #2a2a2a;
                border: 1px solid {border_color};
                padding: 2px;
                color: white;
            }}
            QLabel {{
                color: white;
                border: none;
            }}
        """)
        
        # Create subplots
        gs = figure.add_gridspec(2, 1, height_ratios=[7, 3], hspace=0.05)
        price_ax = figure.add_subplot(gs[0])
        zscore_ax = figure.add_subplot(gs[1], sharex=price_ax)
        
        # Style price chart
        price_ax.set_facecolor('#000000')
        price_ax.tick_params(colors='white', labelsize=8, labelbottom=False)
        for spine in price_ax.spines.values():
            spine.set_color(border_color)
        price_ax.grid(True, color='#3a3a3a', alpha=0.3)
        price_ax.set_title(f"{title} - {self.instrument['underlying_symbol']} Price", color='white', fontsize=10)
        
        # Style Z-Score chart
        zscore_ax.set_facecolor('#000000')
        zscore_ax.tick_params(colors='white', labelsize=8)
        for spine in zscore_ax.spines.values():
            spine.set_color(border_color)
        zscore_ax.grid(True, color='#3a3a3a', alpha=0.3)
        zscore_ax.set_ylabel('Z-Score', color='white', fontsize=9)
        zscore_ax.axhline(y=0, color='#808080', linestyle='-', linewidth=1, alpha=0.5)
        zscore_ax.axhline(y=1.5, color='#44ff44', linestyle='--', linewidth=1, alpha=0.7)
        zscore_ax.axhline(y=-1.5, color='#ff4444', linestyle='--', linewidth=1, alpha=0.7)
        zscore_ax.set_ylim(-3, 3)
        
        canvas.draw()
        
        # Store references for updates using setattr to avoid type checker warnings
        setattr(chart_widget, 'figure', figure)
        setattr(chart_widget, 'canvas', canvas)
        setattr(chart_widget, 'price_ax', price_ax)
        setattr(chart_widget, 'zscore_ax', zscore_ax)
        setattr(chart_widget, 'interval_combo', interval_combo)
        setattr(chart_widget, 'period_combo', period_combo)
        setattr(chart_widget, 'ema_spinbox', ema_spinbox)
        setattr(chart_widget, 'z_period_spinbox', z_period_spinbox)
        setattr(chart_widget, 'z_threshold_spinbox', z_threshold_spinbox)
        setattr(chart_widget, 'is_confirmation', is_confirmation)
        
        return chart_widget
    
    def update_option_chart(self, chart_widget, price_data: List[Dict], contract_description: str = ""):
        """Update option chart with new price data"""
        if not price_data:
            return
            
        try:
            # Clear previous plot
            chart_widget.ax.clear()
            
            # Extract data
            times = [datetime.fromisoformat(bar['time']) for bar in price_data]
            highs = [bar['high'] for bar in price_data]
            lows = [bar['low'] for bar in price_data]
            opens = [bar['open'] for bar in price_data]
            closes = [bar['close'] for bar in price_data]
            volumes = [bar['volume'] for bar in price_data]
            
            # Create candlestick chart manually
            for i, (time, open_price, high, low, close) in enumerate(zip(times, opens, highs, lows, closes)):
                color = '#00FF00' if close >= open_price else '#FF0000'
                
                # Draw wick (high-low line)
                chart_widget.ax.plot([i, i], [low, high], color='white', linewidth=1)
                
                # Draw candle body
                body_height = abs(close - open_price)
                body_bottom = min(open_price, close)
                chart_widget.ax.bar(i, body_height, bottom=body_bottom, color=color, alpha=0.8, width=0.8)
            
            # Chart styling
            chart_widget.ax.set_facecolor('#202020')
            chart_widget.ax.tick_params(colors='white', labelsize=8)
            for spine in chart_widget.ax.spines.values():
                spine.set_color('#FF8C00')
            chart_widget.ax.grid(True, color='#3a3a3a', alpha=0.3)
            
            # Set title and labels
            last_price = closes[-1] if closes else 0
            title = f"Option Price: ${last_price:.2f}"
            if contract_description:
                title += f" - {contract_description}"
            chart_widget.ax.set_title(title, color='white', fontsize=10)
            
            # Set x-axis labels (show every 10th timestamp to avoid crowding)
            if len(times) > 1:
                step = max(1, len(times) // 10)
                x_ticks = range(0, len(times), step)
                x_labels = [times[i].strftime('%H:%M') for i in x_ticks]
                chart_widget.ax.set_xticks(x_ticks)
                chart_widget.ax.set_xticklabels(x_labels)
            
            chart_widget.canvas.draw()
            
        except Exception as e:
            logger.error(f"Error updating option chart: {e}")
    
    def update_spx_chart(self, chart_widget, price_data: List[Dict], trade_markers: Optional[List[Dict]] = None):
        """Update SPX chart with price data, EMA, Z-Score, and trade markers"""
        if not price_data:
            return
            
        try:
            # Convert to DataFrame for easier processing
            df = pd.DataFrame(price_data)
            df['time'] = pd.to_datetime(df['time'])
            df = df.sort_values('time')
            
            # Calculate EMA
            ema_length = chart_widget.ema_spinbox.value()
            df['ema'] = df['close'].ewm(span=ema_length, adjust=False).mean()
            
            # Calculate Z-Score
            z_period = chart_widget.z_period_spinbox.value()
            df['sma'] = df['close'].rolling(window=z_period).mean()
            df['std'] = df['close'].rolling(window=z_period).std()
            df['z_score'] = (df['close'] - df['sma']) / df['std']
            
            # Clear previous plots
            chart_widget.price_ax.clear()
            chart_widget.zscore_ax.clear()
            
            # Plot candlesticks manually
            for i, (idx, row) in enumerate(df.iterrows()):
                color = '#00FF00' if row['close'] >= row['open'] else '#FF0000'
                
                # Draw wick
                chart_widget.price_ax.plot([i, i], [row['low'], row['high']], 
                                         color='white', linewidth=1)
                
                # Draw candle body
                body_height = abs(row['close'] - row['open'])
                body_bottom = min(row['open'], row['close'])
                chart_widget.price_ax.bar(i, body_height, bottom=body_bottom, 
                                        color=color, alpha=0.8, width=0.8)
            
            # Plot EMA
            chart_widget.price_ax.plot(range(len(df)), df['ema'], 
                                     color='#FFA500', linewidth=2, label=f'EMA({ema_length})')
            
            # Add current price line
            if not df.empty:
                current_price = df['close'].iloc[-1]
                chart_widget.price_ax.axhline(y=current_price, color='#00FF00', 
                                            linestyle='--', linewidth=1, alpha=0.7)
                chart_widget.price_ax.text(len(df), current_price, 
                                         f' ${current_price:.2f}', 
                                         color='#00FF00', fontsize=9, 
                                         verticalalignment='center')
            
            # Plot trade markers if provided
            if trade_markers and chart_widget.is_confirmation == False:  # Only on trade chart
                for trade in trade_markers:
                    try:
                        trade_time = pd.to_datetime(trade['time'])
                        # Find closest data point
                        time_diffs = (df['time'] - trade_time).abs()
                        closest_idx = time_diffs.idxmin()
                        chart_idx = df.index.get_loc(closest_idx)
                        
                        entry_price = trade.get('entry_price', 0)
                        if entry_price > 0:
                            chart_widget.price_ax.scatter(chart_idx, entry_price, 
                                                        marker='v', s=100, 
                                                        color='#2196F3', zorder=5)
                            chart_widget.price_ax.text(chart_idx, entry_price, 
                                                      f" Entry ${entry_price:.2f}", 
                                                      color='#2196F3', fontsize=8)
                    except:
                        continue
            
            # Style price chart
            chart_widget.price_ax.set_facecolor('#000000')
            chart_widget.price_ax.tick_params(colors='white', labelsize=8, labelbottom=False)
            for spine in chart_widget.price_ax.spines.values():
                spine.set_color('#FF8C00' if chart_widget.is_confirmation else '#66BB6A')
            chart_widget.price_ax.grid(True, color='#3a3a3a', alpha=0.3)
            chart_widget.price_ax.set_title(
                f"{'Confirmation' if chart_widget.is_confirmation else 'Trade'} Chart - {self.instrument['underlying_symbol']} Price", 
                color='white', fontsize=10)
            
            # Plot Z-Score
            z_score_values = df['z_score'].fillna(0)
            chart_widget.zscore_ax.plot(range(len(df)), z_score_values, 
                                      color='#00BFFF', linewidth=2, label='Z-Score')
            
            # Fill Z-Score areas
            chart_widget.zscore_ax.fill_between(range(len(df)), 0, z_score_values, 
                                              where=(z_score_values > 0), 
                                              color='#44ff44', alpha=0.2)
            chart_widget.zscore_ax.fill_between(range(len(df)), 0, z_score_values, 
                                              where=(z_score_values < 0), 
                                              color='#ff4444', alpha=0.2)
            
            # Z-Score threshold lines
            z_threshold = chart_widget.z_threshold_spinbox.value()
            chart_widget.zscore_ax.axhline(y=0, color='#808080', linestyle='-', linewidth=1, alpha=0.5)
            chart_widget.zscore_ax.axhline(y=z_threshold, color='#44ff44', linestyle='--', 
                                         linewidth=1.5, alpha=0.8, label=f'Buy Signal (+{z_threshold})')
            chart_widget.zscore_ax.axhline(y=-z_threshold, color='#ff4444', linestyle='--', 
                                         linewidth=1.5, alpha=0.8, label=f'Sell Signal (-{z_threshold})')
            
            # Current Z-Score label
            if not df.empty and not pd.isna(z_score_values.iloc[-1]):
                current_zscore = z_score_values.iloc[-1]
                zscore_color = '#44ff44' if current_zscore > 0 else '#ff4444' if current_zscore < 0 else '#808080'
                chart_widget.zscore_ax.text(len(df), current_zscore, 
                                          f' {current_zscore:.2f}', 
                                          color=zscore_color, fontsize=9, 
                                          verticalalignment='center')
            
            # Style Z-Score chart
            chart_widget.zscore_ax.set_facecolor('#000000')
            chart_widget.zscore_ax.tick_params(colors='white', labelsize=8)
            for spine in chart_widget.zscore_ax.spines.values():
                spine.set_color('#FF8C00' if chart_widget.is_confirmation else '#66BB6A')
            chart_widget.zscore_ax.grid(True, color='#3a3a3a', alpha=0.3)
            chart_widget.zscore_ax.set_ylabel('Z-Score', color='white', fontsize=9)
            chart_widget.zscore_ax.set_ylim(-3, 3)
            
            # Set x-axis labels
            if len(df) > 1:
                step = max(1, len(df) // 10)
                x_ticks = range(0, len(df), step)
                x_labels = [df.iloc[i]['time'].strftime('%H:%M') for i in x_ticks]
                chart_widget.zscore_ax.set_xticks(x_ticks)
                chart_widget.zscore_ax.set_xticklabels(x_labels)
            
            chart_widget.canvas.draw()
            
        except Exception as e:
            logger.error(f"Error updating SPX chart: {e}")
    
    def generate_sample_data(self, base_price: float = 580.0, num_points: int = 50) -> List[Dict]:
        """Generate sample price data for testing charts"""
        data = []
        current_time = datetime.now()
        current_price = base_price
        
        for i in range(num_points):
            # Generate realistic price movement
            change = np.random.normal(0, 0.5)  # Small random changes
            current_price += change
            
            # Create OHLC data
            open_price = current_price
            high = current_price + abs(np.random.normal(0, 0.3))
            low = current_price - abs(np.random.normal(0, 0.3))
            close = open_price + np.random.normal(0, 0.2)
            volume = int(np.random.normal(1000, 300))
            
            data.append({
                'time': (current_time - timedelta(minutes=num_points-i-1)).isoformat(),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': max(volume, 100)
            })
            
            current_price = close
        
        return data
    
    def toggle_chart_window(self):
        """Toggle the chart popup window"""
        if self.chart_window is None or not self.chart_window.isVisible():
            # Create or show the chart window
            if self.chart_window is None:
                self.chart_window = ChartWindow(self)
                
                # Add the four charts to the popup window
                self.chart_window.charts_layout.addWidget(self.call_chart_widget, 0, 0)
                self.chart_window.charts_layout.addWidget(self.put_chart_widget, 0, 1)
                self.chart_window.charts_layout.addWidget(self.confirm_chart_widget, 1, 0)
                self.chart_window.charts_layout.addWidget(self.trade_chart_widget, 1, 1)
                
                logger.info("Chart window created and populated")
            
            self.chart_window.show()
            self.show_charts_btn.setText("Hide Charts")
            logger.info("Chart window shown")
        else:
            # Hide the chart window
            self.chart_window.hide()
            self.show_charts_btn.setText("Show Charts")
            logger.info("Chart window hidden")
    
    def on_underlying_settings_changed(self, chart_widget, is_trade_chart: bool):
        """Handle interval or days combo box changes for underlying charts"""
        if self.connection_state != ConnectionState.CONNECTED or not self.ibkr_client:
            logger.warning("Cannot reload chart - not connected to IBKR")
            return
        
        try:
            # Get settings from chart widget
            interval_text = chart_widget.interval_combo.currentText()
            days_text = chart_widget.days_combo.currentText()
            
            # Map interval to IBAPI bar size
            interval_map = {
                "15 secs": "15 secs",
                "30 secs": "30 secs",
                "1 min": "1 min",
                "5 min": "5 mins",
                "15 min": "15 mins",
                "30 min": "30 mins",
                "1 hour": "1 hour"
            }
            bar_size = interval_map.get(interval_text, "1 min")
            
            # SMART LOADING: Only fetch 12 hours of data initially (what's visible)
            # This prevents app freezing with small intervals (15sec, 30sec) over multiple days
            # User can zoom/pan and we'll fetch more data on-demand if needed
            hours_needed = 12  # Always fetch 12 hours initially (visible amount)
            duration = f"{hours_needed * 3600} S"  # Duration in seconds
            
            # Create contract - ES futures for confirmation chart, underlying for trade chart
            from ibapi.contract import Contract
            contract = Contract()
            
            if not is_trade_chart:  # Confirmation chart uses ES futures
                contract.symbol = "ES"
                contract.secType = "FUT"
                contract.exchange = "CME"
                contract.currency = "USD"
                contract.lastTradeDateOrContractMonth = self.get_es_front_month()
            else:  # Trade chart uses underlying
                contract.symbol = self.instrument['underlying_symbol']
                contract.secType = "IND" if self.instrument['underlying_symbol'] == "SPX" else "STK"
                contract.exchange = "CBOE" if self.instrument['underlying_symbol'] == "SPX" else "ARCA"
                contract.currency = "USD"
            
            req_id = self.app_state['next_req_id']
            self.app_state['next_req_id'] += 1
            
            # Determine contract key based on which chart
            if is_trade_chart:
                contract_key = f"UNDERLYING_{self.instrument['underlying_symbol']}_TRADE"
            else:
                contract_key = "ES_FUTURES_CONFIRM"  # Use ES futures for confirmation chart
            
            self.request_id_map[req_id] = contract_key
            
            # Clear existing data for this chart (both historical and chart data)
            if contract_key in self.historical_data:
                self.historical_data[contract_key] = []
            
            # Also clear chart_data to prevent rendering stale data
            if is_trade_chart:
                self.chart_data['underlying_trade'] = []
            else:
                self.chart_data['es_futures'] = []  # Clear ES futures data for confirmation chart
            
            # Request new data with updated settings
            self.ibkr_client.reqHistoricalData(
                req_id,
                contract,
                "",  # End time (empty = now)
                duration,
                bar_size,
                "TRADES",
                0,  # Include after-hours data
                1,  # Format date
                True,  # Keep up to date
                []
            )
            
            chart_name = "Trade" if is_trade_chart else "Confirmation"
            logger.info(f"Reloading {chart_name} chart with {interval_text} bars, 12 hours of data")
            self.log_message(f"Reloading {chart_name} chart: {interval_text}, 12 hours", "INFO")
            
        except Exception as e:
            logger.error(f"Error reloading underlying chart: {e}")
            self.log_message(f"Error reloading chart: {e}", "ERROR")
    
    def on_option_settings_changed(self, chart_widget, is_call: bool):
        """Handle interval or days combo box changes for option charts"""
        if self.connection_state != ConnectionState.CONNECTED or not self.ibkr_client:
            logger.warning("Cannot reload option chart - not connected to IBKR")
            return
        
        # Check if we have a contract selected
        contract_attr = 'current_call_contract' if is_call else 'current_put_contract'
        if not hasattr(self, contract_attr):
            self.log_message(f"No {'call' if is_call else 'put'} option selected", "WARNING")
            return
        
        try:
            # Get settings from chart widget
            interval_text = chart_widget.interval_combo.currentText()
            days_text = chart_widget.days_combo.currentText()
            
            # Map interval to IBAPI bar size
            interval_map = {
                "15 secs": "15 secs",
                "30 secs": "30 secs",
                "1 min": "1 min",
                "5 min": "5 mins",
                "15 min": "15 mins",
                "30 min": "30 mins",
                "1 hour": "1 hour"
            }
            bar_size = interval_map.get(interval_text, "1 min")
            
            # SMART LOADING: Only fetch 12 hours of data initially (what's visible)
            # This prevents app freezing with small intervals (15sec, 30sec) over multiple days
            hours_needed = 12  # Always fetch 12 hours initially (visible amount)
            duration = f"{hours_needed * 3600} S"  # Duration in seconds
            
            # Get the contract key for the current option
            contract_key = getattr(self, contract_attr)
            option_type = "call" if is_call else "put"
            
            # Parse contract key to get details and recreate request
            from ibapi.contract import Contract
            parts = contract_key.split('_')
            if len(parts) != 4:
                logger.error(f"Invalid contract key format: {contract_key}")
                return
                
            symbol, strike_str, right, expiry = parts
            strike = float(strike_str)
            
            # Create option contract
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "OPT"
            contract.exchange = "SMART"
            contract.currency = "USD"
            contract.lastTradeDateOrContractMonth = expiry
            contract.strike = strike
            contract.right = right
            contract.multiplier = "100"
            contract.tradingClass = "SPXW" if symbol == "SPX" else "XSP"
            
            # Get unique request ID
            req_id = self.app_state.get('next_order_id', 1)
            self.app_state['next_order_id'] = req_id + 1
            
            # Map this request to the appropriate chart data storage
            chart_key = f"CHART_{option_type}_{contract_key}"
            self.request_id_map[req_id] = chart_key
            
            # Clear existing data for this chart (both historical and chart data)
            if chart_key in self.historical_data:
                self.historical_data[chart_key] = []
            
            # Also clear chart_data to prevent rendering stale data
            if is_call:
                self.chart_data['selected_call'] = []
            else:
                self.chart_data['selected_put'] = []
            
            # Request historical data with new settings
            self.ibkr_client.reqHistoricalData(
                req_id,
                contract,
                "",  # End time (empty = now)
                duration,
                bar_size,
                "MIDPOINT",  # Use mid price (bid+ask)/2 for option charts
                0,  # Include after-hours data
                1,  # Format date
                True,  # Keep up to date
                []
            )
            
            chart_name = "Call" if is_call else "Put"
            logger.info(f"Reloading {chart_name} chart with {interval_text} bars, 12 hours of data")
            self.log_message(f"Reloading {chart_name} chart: {interval_text}, 12 hours", "INFO")
            
        except Exception as e:
            logger.error(f"Error reloading option chart: {e}")
            self.log_message(f"Error reloading option chart: {e}", "ERROR")
    
    def request_chart_data(self):
        """Request real historical data for charts"""
        if self.connection_state != ConnectionState.CONNECTED or not self.ibkr_client:
            logger.warning("Cannot request chart data - not connected to IBKR")
            return
            
        try:
            # Request underlying data for SPX/XSP charts
            self.request_underlying_historical_data()
            
            # Request data for currently selected options (if any)
            self.request_selected_option_data()
            
            logger.info("Chart data requests initiated")
            
        except Exception as e:
            logger.error(f"Error requesting chart data: {e}")
    
    def request_underlying_historical_data(self):
        """Request historical data for ES futures (confirmation chart) and underlying (trade chart)"""
        try:
            from ibapi.contract import Contract
            
            # Create ES futures contract for confirmation chart (24/6 trading)
            es_contract = Contract()
            es_contract.symbol = "ES"
            es_contract.secType = "FUT"
            es_contract.exchange = "CME"
            es_contract.currency = "USD"
            es_contract.lastTradeDateOrContractMonth = self.get_es_front_month()
            
            req_id = self.app_state['next_req_id']
            self.app_state['next_req_id'] += 1
            
            # Store request mapping for chart updates - use ES for confirmation chart
            contract_key = f"ES_FUTURES_CONFIRM"
            self.request_id_map[req_id] = contract_key
            
            # Request 1 day of 1-minute data for confirmation chart with real-time updates
            self.ibkr_client.reqHistoricalData(
                req_id,
                es_contract,
                "",  # End time (empty = now)
                "1 D",  # Duration
                "1 min",  # Bar size
                "TRADES",
                0,  # Include after-hours data
                1,  # Format date
                True,  # Keep up to date - enables real-time bar updates via historicalDataUpdate
                []
            )
            
            logger.info(f"Requested ES futures historical data for confirmation chart")
            
            # Request second dataset for trade chart - use underlying (SPX/XSP)
            underlying_contract = Contract()
            underlying_contract.symbol = self.instrument['underlying_symbol']
            underlying_contract.secType = "IND" if self.instrument['underlying_symbol'] == "SPX" else "STK"
            underlying_contract.exchange = "CBOE" if self.instrument['underlying_symbol'] == "SPX" else "ARCA"
            underlying_contract.currency = "USD"
            
            req_id_trade = self.app_state['next_req_id']
            self.app_state['next_req_id'] += 1
            
            contract_key_trade = f"UNDERLYING_{self.instrument['underlying_symbol']}_TRADE"
            self.request_id_map[req_id_trade] = contract_key_trade
            
            # Request 4 hours of 30-second data for trade chart with real-time updates
            self.ibkr_client.reqHistoricalData(
                req_id_trade,
                underlying_contract,
                "",  # End time (empty = now)
                "14400 S",  # 4 hours in seconds
                "30 secs",  # Bar size
                "TRADES",
                0,  # Include after-hours data
                1,  # Format date
                True,  # Keep up to date - enables real-time bar updates via historicalDataUpdate
                []
            )
            
            logger.info(f"Requested trade chart historical data for {contract_key_trade}")
            
        except Exception as e:
            logger.error(f"Error requesting underlying historical data: {e}")
    
    def request_selected_option_data(self):
        """Request historical data for currently selected options"""
        # For now, we'll select ATM call and put options automatically
        # In the future, this could be based on user selection in the option chain
        
        if not self.underlying_price or self.underlying_price <= 0:
            logger.warning("Cannot select options - no underlying price available")
            return
            
        try:
            # Find ATM options
            atm_strike = self.round_to_strike(self.underlying_price)
            
            # Create call contract
            symbol = self.instrument['options_symbol']
            call_contract_key = f"{symbol}_{atm_strike}_C_{self.current_expiry}"
            put_contract_key = f"{symbol}_{atm_strike}_P_{self.current_expiry}"
            
            # Request call option data
            if call_contract_key not in self.chart_data:
                self.request_option_historical_data(call_contract_key, 'C', atm_strike)
                self.current_call_contract = call_contract_key
            
            # Request put option data  
            if put_contract_key not in self.chart_data:
                self.request_option_historical_data(put_contract_key, 'P', atm_strike)
                self.current_put_contract = put_contract_key
                
        except Exception as e:
            logger.error(f"Error requesting selected option data: {e}")
    
    def request_option_historical_data(self, contract_key: str, right: str, strike: float):
        """Request historical data for a specific option"""
        try:
            from ibapi.contract import Contract
            
            contract = Contract()
            contract.symbol = self.instrument['options_symbol']
            contract.secType = "OPT"
            contract.exchange = "SMART"
            contract.currency = "USD"
            contract.lastTradeDateOrContractMonth = self.current_expiry
            contract.strike = strike
            contract.right = right
            contract.multiplier = str(self.instrument['multiplier'])
            contract.tradingClass = self.instrument['options_trading_class']
            
            req_id = self.app_state['next_req_id']
            self.app_state['next_req_id'] += 1
            
            self.request_id_map[req_id] = f"CHART_{contract_key}"
            
            # Request 1 day of 1-minute data for option charts using MIDPOINT with real-time updates
            self.ibkr_client.reqHistoricalData(
                req_id,
                contract,
                "",  # End time (empty = now)
                "1 D",  # Duration  
                "1 min",  # Bar size
                "MIDPOINT",  # Use mid price (bid+ask)/2 for option charts
                0,  # Include after-hours data
                1,  # Format date
                True,  # Keep up to date - enables real-time bar updates via historicalDataUpdate
                []
            )
            
            logger.info(f"Requested option historical data for {contract_key}")
            
        except Exception as e:
            logger.error(f"Error requesting option historical data for {contract_key}: {e}")
    
    def request_option_chart_data(self, contract_key: str, option_type: str):
        """Request historical data for option charts when user clicks on option chain"""
        try:
            if self.connection_state != ConnectionState.CONNECTED or not self.ibkr_client:
                logger.warning("Cannot request option chart data - not connected to IBKR")
                return
            
            # Parse contract key to get details
            parts = contract_key.split('_')
            if len(parts) != 4:
                logger.error(f"Invalid contract key format: {contract_key}")
                return
                
            symbol, strike_str, right, expiry = parts
            strike = float(strike_str)
            
            # Create option contract
            from ibapi.contract import Contract
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "OPT"
            contract.exchange = "SMART"
            contract.currency = "USD"
            contract.lastTradeDateOrContractMonth = expiry
            contract.strike = strike
            contract.right = right
            contract.multiplier = "100"
            contract.tradingClass = "SPXW" if symbol == "SPX" else "XSP"
            
            # Get unique request ID
            req_id = self.app_state.get('next_order_id', 1)
            self.app_state['next_order_id'] = req_id + 1
            
            # Map this request to the appropriate chart data storage
            chart_key = f"CHART_{option_type}_{contract_key}"
            self.request_id_map[req_id] = chart_key
            
            # Request historical data for charts using MIDPOINT with real-time updates
            self.ibkr_client.reqHistoricalData(
                req_id,
                contract,
                "",  # End time (empty = now)
                "1 D",  # Duration  
                "1 min",  # Bar size
                "MIDPOINT",  # Use mid price (bid+ask)/2 for option charts
                0,  # Include after-hours data
                1,  # Format date
                True,  # Keep up to date - enables real-time bar updates via historicalDataUpdate
                []
            )
            
            logger.info(f"Requested chart data for {option_type} option: {contract_key}")
            self.log_message(f"Requesting chart data for {contract_key}...", "INFO")
            
        except Exception as e:
            logger.error(f"Error requesting option chart data for {contract_key}: {e}")
    
    def create_trading_tab(self):
        """Create the main trading dashboard tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)  # This is the main layout for the tab
        
        # Header with underlying price and expiration selector
        header = QFrame()
        header_layout = QHBoxLayout(header)
        
        # Underlying price label (SPX, XSP, etc.)
        self.underlying_price_label = QLabel(f"{self.instrument['underlying_symbol']}: Loading...")
        self.underlying_price_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #FF8C00;")
        header_layout.addWidget(self.underlying_price_label)
        
        # Add 25-pixel spacing
        header_layout.addSpacing(25)
        
        # ES futures price (for strike calculations - trades 23/6)
        self.es_price_label = QLabel("ES: Loading...")
        self.es_price_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #00CED1;")
        self.es_price_label.setToolTip("ES front month futures (used for strike calculations - trades 23 hours/day)")
        header_layout.addWidget(self.es_price_label)
        
        # Add 25-pixel spacing
        header_layout.addSpacing(25)
        
        # ES to SPX offset display
        self.es_offset_label = QLabel("ES to SPX offset: N/A")
        self.es_offset_label.setStyleSheet("font-size: 12pt; color: #90EE90;")
        self.es_offset_label.setToolTip("ES futures premium/discount to cash index (persistent during overnight)")
        header_layout.addWidget(self.es_offset_label)
        
        # Add 25-pixel spacing
        header_layout.addSpacing(25)
        
        # ATM Strike display (based on 0.5 delta)
        self.atm_strike_label = QLabel("ATM: Calculating...")
        self.atm_strike_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #FFD700;")
        self.atm_strike_label.setToolTip("True ATM strike identified by options with delta closest to 0.5")
        header_layout.addWidget(self.atm_strike_label)
        
        header_layout.addStretch()
        
        # Show Charts button (before Expiration controls)
        self.show_charts_btn = QPushButton("Show Charts")
        self.show_charts_btn.clicked.connect(self.toggle_chart_window)
        self.show_charts_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 10pt;
                padding: 5px 15px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        header_layout.addWidget(self.show_charts_btn)
        
        # Add spacing before Expiration label
        header_layout.addSpacing(20)
        
        self.expiry_combo = QComboBox()
        self.expiry_combo.addItems(self.get_expiration_options())
        self.expiry_combo.currentTextChanged.connect(self.on_expiry_changed)
        header_layout.addWidget(QLabel("Expiration:"))
        header_layout.addWidget(self.expiry_combo)
        
        refresh_btn = QPushButton("Refresh Chain")
        refresh_btn.clicked.connect(self.refresh_option_chain)
        header_layout.addWidget(refresh_btn)
        
        recenter_btn = QPushButton("Recenter Chain")
        recenter_btn.clicked.connect(self.recenter_option_chain)
        recenter_btn.setToolTip("Center chain around current SPX price (ATM)")
        header_layout.addWidget(recenter_btn)
        
        main_layout.addWidget(header)

        # Main content area - split vertically: top for trading data, bottom for controls
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # ========================================================================
        # TOP SECTION: Trading Data (Option Chain, Charts, Positions)
        # ========================================================================
        trading_widget = QWidget()
        trading_layout = QVBoxLayout(trading_widget)
        trading_layout.setContentsMargins(0, 0, 0, 0)

        # Option chain table
        self.option_table = QTableWidget()
        self.option_table.setColumnCount(21)
        headers = [
            "Imp Vol", "Delta", "Theta", "Vega", "Gamma", "Volume", "CHANGE %", "Last", "Bid", "Ask",
            "● STRIKE ●",
            "Bid", "Ask", "Last", "CHANGE %", "Volume", "Gamma", "Vega", "Theta", "Delta", "Imp Vol"
        ]
        self.option_table.setHorizontalHeaderLabels(headers)
        self.option_table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.option_table.setMinimumHeight(225)  # Reduced by 25% (was 300)
        self.option_table.cellClicked.connect(self.on_option_cell_clicked)
        # Add orange border to option table and reduce row height by 25%
        self.option_table.setStyleSheet("""
            QTableWidget { 
                border: 1px solid #FF8C00; 
            }
            QTableWidget::item { 
                height: 18px; 
            }
            QHeaderView::section { 
                height: 18px; 
            }
        """)
        trading_layout.addWidget(self.option_table)

        # Charts are now in popup window - create professional chart widgets
        # Call Chart (Top Left) - Light blue for calls
        self.call_chart_widget = ProfessionalChart("Call Chart", "#4EC9FF")
        self.call_chart_widget.interval_combo.currentTextChanged.connect(
            lambda: self.on_option_settings_changed(self.call_chart_widget, is_call=True)
        )
        self.call_chart_widget.days_combo.currentTextChanged.connect(
            lambda: self.on_option_settings_changed(self.call_chart_widget, is_call=True)
        )
        
        # Put Chart (Top Right) - Pink for puts
        self.put_chart_widget = ProfessionalChart("Put Chart", "#FF69B4")
        self.put_chart_widget.interval_combo.currentTextChanged.connect(
            lambda: self.on_option_settings_changed(self.put_chart_widget, is_call=False)
        )
        self.put_chart_widget.days_combo.currentTextChanged.connect(
            lambda: self.on_option_settings_changed(self.put_chart_widget, is_call=False)
        )
        
        # Confirmation Chart (Bottom Left) - Professional underlying with Z-Score
        self.confirm_chart_widget = ProfessionalUnderlyingChart("Confirmation Chart", "#FFA726", main_window=self)
        self.confirm_chart_widget.interval_combo.currentTextChanged.connect(
            lambda: self.on_underlying_settings_changed(self.confirm_chart_widget, is_trade_chart=False)
        )
        self.confirm_chart_widget.days_combo.currentTextChanged.connect(
            lambda: self.on_underlying_settings_changed(self.confirm_chart_widget, is_trade_chart=False)
        )
        
        # Trade Chart (Bottom Right) - Professional underlying with Z-Score
        self.trade_chart_widget = ProfessionalUnderlyingChart("Trade Chart", "#66BB6A", main_window=self)
        self.trade_chart_widget.interval_combo.currentTextChanged.connect(
            lambda: self.on_underlying_settings_changed(self.trade_chart_widget, is_trade_chart=True)
        )
        self.trade_chart_widget.days_combo.currentTextChanged.connect(
            lambda: self.on_underlying_settings_changed(self.trade_chart_widget, is_trade_chart=True)
        )

        # Positions and Orders panel
        pos_order_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Positions
        positions_group = QGroupBox("Open Positions")
        pos_layout = QVBoxLayout(positions_group)
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(11)
        self.positions_table.setHorizontalHeaderLabels([
            "Contract", "Qty", "Entry", "Current", "P&L", "P&L %", "$ Cost Basis", "$ Mkt Value", "EntryTime", "TimeSpan", "Action"
        ])
        self.positions_table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.positions_table.setMaximumHeight(339)  # Increased by 3x (was 113)
        self.positions_table.cellClicked.connect(self.on_position_cell_clicked)
        # Set Contract column width (increased by 20px for full contract_key visibility)
        self.positions_table.setColumnWidth(0, 170)  # Contract column
        # Reduce row height by 25%
        self.positions_table.setStyleSheet("""
            QTableWidget::item { 
                height: 18px; 
            }
            QHeaderView::section { 
                height: 18px; 
            }
        """)
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
        self.orders_table.setMaximumHeight(339)  # Increased by 3x (was 113)
        self.orders_table.cellClicked.connect(self.on_order_cell_clicked)
        # Set Contract column width (increased by 20px for full contract_key visibility)
        self.orders_table.setColumnWidth(1, 170)  # Contract column
        # Reduce row height by 25%
        self.orders_table.setStyleSheet("""
            QTableWidget::item { 
                height: 18px; 
            }
            QHeaderView::section { 
                height: 18px; 
            }
        """)
        orders_layout.addWidget(self.orders_table)
        
        pos_order_splitter.addWidget(positions_group)
        pos_order_splitter.addWidget(orders_group)
        pos_order_splitter.setSizes([400, 400])
        
        trading_layout.addWidget(pos_order_splitter)
        
        main_splitter.addWidget(trading_widget)
        
        # ========================================================================
        # BOTTOM SECTION: Controls and Activity Log (Horizontal Layout)
        # ========================================================================
        bottom_widget = QWidget()
        bottom_widget.setMaximumHeight(200)  # Constrain bottom section height
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        
        # LEFT: Activity Log (Expanded)
        log_section = QWidget()
        log_section.setMinimumWidth(420)  # Increased from 250 to 420
        log_section.setMaximumWidth(450)  # Increased from 300 to 450
        log_layout = QVBoxLayout(log_section)
        log_layout.setContentsMargins(0, 0, 0, 0)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        # Add orange border to activity log
        self.log_text.setStyleSheet("QTextEdit { border: 1px solid #FF8C00; }")
        log_layout.addWidget(self.log_text)
        
        bottom_layout.addWidget(log_section)
        
        # RIGHT: Control Panels (6 compact panels horizontally)
        panels_scroll = QScrollArea()
        panels_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panels_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        panels_scroll.setWidgetResizable(True)
        
        panels_container = QWidget()
        panels_layout = QHBoxLayout(panels_container)
        panels_layout.setContentsMargins(0, 0, 0, 0)
        panels_layout.setSpacing(5)        # --- PANEL 1: Strategy Settings ---
        self.master_group = QGroupBox("Strategy Settings")
        self.master_group.setFixedWidth(280)
        master_layout = QFormLayout(self.master_group)
        master_layout.setVerticalSpacing(8)
        master_layout.setHorizontalSpacing(10)
        
        # Strategy ON/OFF buttons
        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)
        
        self.strategy_on_btn = QPushButton("ON")
        self.strategy_on_btn.setProperty("success", True)
        self.strategy_on_btn.clicked.connect(lambda: self.set_strategy_enabled(True))
        button_layout.addWidget(self.strategy_on_btn)
        
        self.strategy_off_btn = QPushButton("OFF")
        self.strategy_off_btn.setProperty("danger", True)
        self.strategy_off_btn.clicked.connect(lambda: self.set_strategy_enabled(False))
        button_layout.addWidget(self.strategy_off_btn)
        
        self.strategy_status_label = QLabel("OFF")
        self.strategy_status_label.setStyleSheet("font-weight: bold; color: #808080;")
        button_layout.addWidget(self.strategy_status_label)
        button_layout.addStretch()
        
        master_layout.addRow("<b>Auto Strategy:</b>", button_frame)
        
        # VIX Threshold
        self.vix_threshold_spin = QDoubleSpinBox()
        self.vix_threshold_spin.setRange(0, 100)
        self.vix_threshold_spin.setValue(self.vix_threshold)
        self.vix_threshold_spin.setDecimals(1)
        self.vix_threshold_spin.valueChanged.connect(self.on_master_settings_changed)
        master_layout.addRow("VIX Threshold:", self.vix_threshold_spin)
        
        # Time Stop
        self.time_stop_spin = QSpinBox()
        self.time_stop_spin.setRange(1, 300)
        self.time_stop_spin.setSingleStep(5)
        self.time_stop_spin.setValue(self.time_stop)
        self.time_stop_spin.setToolTip("Time stop in minutes")
        self.time_stop_spin.valueChanged.connect(self.on_master_settings_changed)
        master_layout.addRow("Time Stop (min):", self.time_stop_spin)
        
        panels_layout.addWidget(self.master_group)
        
        # --- PANEL 2: Confirmation Chart Settings ---
        confirm_group = QGroupBox("Confirmation Chart")
        confirm_group.setFixedWidth(280)
        confirm_layout = QFormLayout(confirm_group)
        confirm_layout.setVerticalSpacing(8)
        
        self.confirm_ema_spin = QSpinBox()
        self.confirm_ema_spin.setRange(1, 100)
        self.confirm_ema_spin.setValue(self.confirm_ema_length)
        self.confirm_ema_spin.valueChanged.connect(self.on_chart_settings_changed)
        confirm_layout.addRow("EMA Length:", self.confirm_ema_spin)
        
        self.confirm_z_period_spin = QSpinBox()
        self.confirm_z_period_spin.setRange(1, 100)
        self.confirm_z_period_spin.setValue(self.confirm_z_period)
        self.confirm_z_period_spin.valueChanged.connect(self.on_chart_settings_changed)
        confirm_layout.addRow("Z-Score Period:", self.confirm_z_period_spin)
        
        self.confirm_z_threshold_spin = QDoubleSpinBox()
        self.confirm_z_threshold_spin.setRange(0.1, 5.0)
        self.confirm_z_threshold_spin.setSingleStep(0.1)
        self.confirm_z_threshold_spin.setValue(self.confirm_z_threshold)
        self.confirm_z_threshold_spin.valueChanged.connect(self.on_chart_settings_changed)
        confirm_layout.addRow("Z-Score Threshold:", self.confirm_z_threshold_spin)
        
        self.confirm_refresh_btn = QPushButton("Refresh Chart")
        self.confirm_refresh_btn.clicked.connect(self.refresh_confirm_chart)
        confirm_layout.addRow("", self.confirm_refresh_btn)
        
        panels_layout.addWidget(confirm_group)
        
        # --- PANEL 3: Trade Chart Settings ---
        trade_chart_group = QGroupBox("Trade Chart")
        trade_chart_group.setFixedWidth(280)
        trade_layout = QFormLayout(trade_chart_group)
        trade_layout.setVerticalSpacing(8)
        
        self.trade_ema_spin = QSpinBox()
        self.trade_ema_spin.setRange(1, 100)
        self.trade_ema_spin.setValue(self.trade_ema_length)
        self.trade_ema_spin.valueChanged.connect(self.on_chart_settings_changed)
        trade_layout.addRow("EMA Length:", self.trade_ema_spin)
        
        self.trade_z_period_spin = QSpinBox()
        self.trade_z_period_spin.setRange(1, 100)
        self.trade_z_period_spin.setValue(self.trade_z_period)
        self.trade_z_period_spin.valueChanged.connect(self.on_chart_settings_changed)
        trade_layout.addRow("Z-Score Period:", self.trade_z_period_spin)
        
        self.trade_z_threshold_spin = QDoubleSpinBox()
        self.trade_z_threshold_spin.setRange(0.1, 5.0)
        self.trade_z_threshold_spin.setSingleStep(0.1)
        self.trade_z_threshold_spin.setValue(self.trade_z_threshold)
        self.trade_z_threshold_spin.valueChanged.connect(self.on_chart_settings_changed)
        trade_layout.addRow("Z-Score Threshold:", self.trade_z_threshold_spin)
        
        self.trade_refresh_btn = QPushButton("Refresh Chart")
        self.trade_refresh_btn.clicked.connect(self.refresh_trade_chart)
        trade_layout.addRow("", self.trade_refresh_btn)
        
        panels_layout.addWidget(trade_chart_group)
        
        # --- PANEL 4: Auto Entry (Straddle) ---
        straddle_group = QGroupBox("Auto Entry (Straddle)")
        straddle_group.setFixedWidth(280)
        straddle_layout = QFormLayout(straddle_group)
        straddle_layout.setVerticalSpacing(8)
        
        # Straddle ON/OFF buttons
        straddle_btn_frame = QWidget()
        straddle_btn_layout = QHBoxLayout(straddle_btn_frame)
        straddle_btn_layout.setContentsMargins(0, 0, 0, 0)
        straddle_btn_layout.setSpacing(5)
        
        self.straddle_on_btn = QPushButton("ON")
        self.straddle_on_btn.setProperty("success", True)
        self.straddle_on_btn.clicked.connect(lambda: self.set_straddle_enabled(True))
        straddle_btn_layout.addWidget(self.straddle_on_btn)
        
        self.straddle_off_btn = QPushButton("OFF")
        self.straddle_off_btn.setProperty("danger", True)
        self.straddle_off_btn.clicked.connect(lambda: self.set_straddle_enabled(False))
        straddle_btn_layout.addWidget(self.straddle_off_btn)
        
        self.straddle_status_label = QLabel("OFF")
        self.straddle_status_label.setStyleSheet("font-weight: bold; color: #808080;")
        straddle_btn_layout.addWidget(self.straddle_status_label)
        straddle_btn_layout.addStretch()
        
        straddle_layout.addRow("<b>Status:</b>", straddle_btn_frame)
        
        # Frequency
        freq_frame = QWidget()
        freq_layout = QHBoxLayout(freq_frame)
        freq_layout.setContentsMargins(0, 0, 0, 0)
        freq_layout.setSpacing(5)
        
        self.straddle_frequency_spin = QSpinBox()
        self.straddle_frequency_spin.setRange(1, 300)
        self.straddle_frequency_spin.setValue(self.straddle_frequency)
        self.straddle_frequency_spin.valueChanged.connect(self.on_straddle_settings_changed)
        freq_layout.addWidget(self.straddle_frequency_spin)
        freq_layout.addWidget(QLabel("minutes"))
        freq_layout.addStretch()
        
        straddle_layout.addRow("Frequency:", freq_frame)
        
        # Info label
        info_label = QLabel("Uses Master Settings for\nDelta & Position Size")
        info_label.setStyleSheet("color: #888888; font-size: 9pt;")
        straddle_layout.addRow("", info_label)
        
        # Next entry countdown
        self.straddle_next_label = QLabel("Next: --:--")
        self.straddle_next_label.setStyleSheet("color: #00BFFF;")
        straddle_layout.addRow("Next Entry:", self.straddle_next_label)
        
        panels_layout.addWidget(straddle_group)
        
        # --- PANEL 5: Quick Entry (Manual Mode) ---
        manual_group = QGroupBox("Quick Entry")
        manual_group.setFixedWidth(280)  # Expanded from 220 to 280
        manual_layout = QVBoxLayout(manual_group)
        
        self.buy_call_btn = QPushButton("BUY CALL")
        self.buy_call_btn.setProperty("success", True)
        self.buy_call_btn.clicked.connect(self.manual_buy_call)
        manual_layout.addWidget(self.buy_call_btn)
        
        self.buy_put_btn = QPushButton("BUY PUT")
        self.buy_put_btn.setProperty("danger", True)
        self.buy_put_btn.clicked.connect(self.manual_buy_put)
        manual_layout.addWidget(self.buy_put_btn)
        
        # Quick trade instructions
        quick_trade_info = QLabel(
            "💡 Quick Trade:\n"
            "• Ctrl + Click BID = BUY\n"
            "• Ctrl + Click ASK = SELL\n"
            "(Uses chase give-in)"
        )
        quick_trade_info.setStyleSheet("color: #00aaff; font-size: 8pt; padding: 5px;")
        quick_trade_info.setAlignment(Qt.AlignmentFlag.AlignLeft)
        manual_layout.addWidget(quick_trade_info)
        manual_layout.addStretch()
        
        panels_layout.addWidget(manual_group)
        
        # --- PANEL 6: Entry Settings ---
        entry_group = QGroupBox("Entry Settings")
        entry_group.setFixedWidth(280)
        entry_layout = QFormLayout(entry_group)
        entry_layout.setVerticalSpacing(8)
        
        # Target Delta
        self.target_delta_spin = QSpinBox()
        self.target_delta_spin.setRange(10, 50)
        self.target_delta_spin.setSingleStep(10)
        self.target_delta_spin.setValue(self.target_delta)
        self.target_delta_spin.valueChanged.connect(self.on_master_settings_changed)
        entry_layout.addRow("Target Delta:", self.target_delta_spin)
        
        # Max Risk
        self.max_risk_spin = QSpinBox()
        self.max_risk_spin.setRange(100, 10000)
        self.max_risk_spin.setSingleStep(50)
        self.max_risk_spin.setValue(self.max_risk)
        self.max_risk_spin.valueChanged.connect(self.on_master_settings_changed)
        entry_layout.addRow("Max Risk ($):", self.max_risk_spin)
        
        # Trade Quantity
        self.trade_qty_spin = QSpinBox()
        self.trade_qty_spin.setRange(1, 100)
        self.trade_qty_spin.setValue(self.trade_qty)
        self.trade_qty_spin.valueChanged.connect(self.on_master_settings_changed)
        entry_layout.addRow("Trade Quantity:", self.trade_qty_spin)
        
        # Position Size Mode
        radio_frame = QWidget()
        radio_layout = QHBoxLayout(radio_frame)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setSpacing(10)
        
        self.fixed_radio = QRadioButton("Fixed Qty")
        self.fixed_radio.setChecked(self.position_size_mode == "fixed")
        self.fixed_radio.toggled.connect(self.on_position_mode_changed)
        radio_layout.addWidget(self.fixed_radio)
        
        self.by_risk_radio = QRadioButton("By Risk")
        self.by_risk_radio.setChecked(self.position_size_mode == "calculated")
        self.by_risk_radio.toggled.connect(self.on_position_mode_changed)
        radio_layout.addWidget(self.by_risk_radio)
        radio_layout.addStretch()
        
        entry_layout.addRow("Position Sizing:", radio_frame)
        
        panels_layout.addWidget(entry_group)
        
        # Complete the scroll area setup
        panels_scroll.setWidget(panels_container)
        bottom_layout.addWidget(panels_scroll)
        
        # Initialize button states
        self.update_strategy_button_states()
        self.update_straddle_button_states()
        
        # Add the bottom widget to main splitter
        main_splitter.addWidget(bottom_widget)
        
        # Set splitter proportions (80% top, 20% bottom)
        main_splitter.setSizes([800, 200])
        
        # Add the main splitter to the main layout  
        main_layout.addWidget(main_splitter)
        
        return tab
    
    def create_vega_strategy_tab(self):
        """Create the Vega Delta Neutral Strategy tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Main splitter - vertical split
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # ===== TOP SECTION: Controls & Scanner =====
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        # Strategy Control Panel
        control_group = QGroupBox("Vega Strategy Control")
        control_layout = QGridLayout(control_group)
        
        # Row 0: Strategy Enable/Disable
        self.vega_strategy_enabled_cb = QCheckBox("Enable Vega Strategy")
        self.vega_strategy_enabled_cb.setChecked(self.vega_strategy_enabled)
        self.vega_strategy_enabled_cb.stateChanged.connect(self.on_vega_strategy_toggle)
        control_layout.addWidget(self.vega_strategy_enabled_cb, 0, 0, 1, 2)
        
        # Row 1: Auto Hedge Toggle
        self.auto_hedge_enabled_cb = QCheckBox("Enable Auto Delta Hedging")
        self.auto_hedge_enabled_cb.setChecked(self.auto_hedge_enabled)
        self.auto_hedge_enabled_cb.stateChanged.connect(self.on_auto_hedge_toggle)
        control_layout.addWidget(self.auto_hedge_enabled_cb, 1, 0, 1, 2)
        
        # Row 2: Target Vega
        control_layout.addWidget(QLabel("Target Vega:"), 2, 0)
        self.vega_target_spin = QSpinBox()
        self.vega_target_spin.setRange(0, 10000)
        self.vega_target_spin.setSingleStep(100)
        self.vega_target_spin.setValue(self.vega_target)
        self.vega_target_spin.setToolTip("Target portfolio vega exposure")
        control_layout.addWidget(self.vega_target_spin, 2, 1)
        
        # Row 3: Max Delta Threshold
        control_layout.addWidget(QLabel("Max Delta Threshold:"), 3, 0)
        self.max_delta_threshold_spin = QSpinBox()
        self.max_delta_threshold_spin.setRange(1, 100)
        self.max_delta_threshold_spin.setSingleStep(5)
        self.max_delta_threshold_spin.setValue(self.max_delta_threshold)
        self.max_delta_threshold_spin.setToolTip("Maximum allowed portfolio delta before auto-rehedge")
        control_layout.addWidget(self.max_delta_threshold_spin, 3, 1)
        
        # Row 4: Scan Button
        self.scan_vega_btn = QPushButton("🔍 Scan for Opportunities")
        self.scan_vega_btn.clicked.connect(self.scan_vega_opportunities)
        self.scan_vega_btn.setToolTip("Scan option chain for low IV rank opportunities")
        control_layout.addWidget(self.scan_vega_btn, 4, 0, 1, 2)
        
        # Row 5: Manual Hedge Button
        self.manual_hedge_btn = QPushButton("⚖️ Hedge Delta Now")
        self.manual_hedge_btn.clicked.connect(self.manual_delta_hedge)
        self.manual_hedge_btn.setToolTip("Manually execute delta hedge")
        control_layout.addWidget(self.manual_hedge_btn, 5, 0, 1, 2)
        
        top_layout.addWidget(control_group)
        
        # Portfolio Greeks Display
        greeks_group = QGroupBox("Portfolio Greeks")
        greeks_layout = QGridLayout(greeks_group)
        
        # Delta
        greeks_layout.addWidget(QLabel("Delta:"), 0, 0)
        self.portfolio_delta_label = QLabel("0.00")
        self.portfolio_delta_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        greeks_layout.addWidget(self.portfolio_delta_label, 0, 1)
        
        # Gamma
        greeks_layout.addWidget(QLabel("Gamma:"), 0, 2)
        self.portfolio_gamma_label = QLabel("0.00")
        self.portfolio_gamma_label.setStyleSheet("font-size: 14pt;")
        greeks_layout.addWidget(self.portfolio_gamma_label, 0, 3)
        
        # Vega
        greeks_layout.addWidget(QLabel("Vega:"), 1, 0)
        self.portfolio_vega_label = QLabel("0.00")
        self.portfolio_vega_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #ff8c00;")
        greeks_layout.addWidget(self.portfolio_vega_label, 1, 1)
        
        # Theta
        greeks_layout.addWidget(QLabel("Theta:"), 1, 2)
        self.portfolio_theta_label = QLabel("0.00")
        self.portfolio_theta_label.setStyleSheet("font-size: 14pt;")
        greeks_layout.addWidget(self.portfolio_theta_label, 1, 3)
        
        top_layout.addWidget(greeks_group)
        
        # Scanner Results Table
        scanner_group = QGroupBox("Vega Opportunity Scanner")
        scanner_layout = QVBoxLayout(scanner_group)
        
        self.vega_scanner_table = QTableWidget()
        self.vega_scanner_table.setColumnCount(8)
        self.vega_scanner_table.setHorizontalHeaderLabels([
            "Expiry", "IV Rank", "Put Strike", "Put IV", "Call Strike", "Call IV", "Total Cost", "Action"
        ])
        header = self.vega_scanner_table.horizontalHeader()
        if header:
            header.setStretchLastSection(False)
        self.vega_scanner_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        scanner_layout.addWidget(self.vega_scanner_table)
        
        top_layout.addWidget(scanner_group)
        
        main_splitter.addWidget(top_widget)
        
        # ===== BOTTOM SECTION: Active Vega Positions =====
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        positions_group = QGroupBox("Active Vega Positions")
        positions_layout = QVBoxLayout(positions_group)
        
        self.vega_positions_table = QTableWidget()
        self.vega_positions_table.setColumnCount(11)
        self.vega_positions_table.setHorizontalHeaderLabels([
            "Trade ID", "Entry Time", "Put", "Call", "Hedge MES", "Portfolio Δ", 
            "Portfolio Γ", "Portfolio V", "Portfolio Θ", "P&L", "Action"
        ])
        header = self.vega_positions_table.horizontalHeader()
        if header:
            header.setStretchLastSection(False)
        self.vega_positions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        positions_layout.addWidget(self.vega_positions_table)
        
        bottom_layout.addWidget(positions_group)
        
        main_splitter.addWidget(bottom_widget)
        
        # Set splitter proportions (50% top, 50% bottom)
        main_splitter.setSizes([500, 500])
        
        main_layout.addWidget(main_splitter)
        
        return tab
    
    def create_straddle_strategy_tab(self):
        """Create the Long Straddles Strategy tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Main splitter - vertical split
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # ===== TOP SECTION: Controls & Entry =====
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        # Strategy Control Panel
        control_group = QGroupBox("Long Straddles Control")
        control_layout = QGridLayout(control_group)
        
        # Row 0: Strategy Enable/Disable
        self.straddle_strategy_enabled_cb = QCheckBox("Enable Straddle Strategy")
        self.straddle_strategy_enabled_cb.setChecked(self.straddle_strategy_enabled)
        self.straddle_strategy_enabled_cb.stateChanged.connect(self.on_straddle_strategy_toggle)
        control_layout.addWidget(self.straddle_strategy_enabled_cb, 0, 0, 1, 2)
        
        # Row 1: OTM Strikes Selection
        control_layout.addWidget(QLabel("OTM Strikes Away:"), 1, 0)
        self.straddle_otm_spin = QSpinBox()
        self.straddle_otm_spin.setRange(1, 10)
        self.straddle_otm_spin.setSingleStep(1)
        self.straddle_otm_spin.setValue(self.straddle_otm_strikes)
        self.straddle_otm_spin.setToolTip("Number of strikes away from ATM (1 = first OTM, 2 = second OTM, etc.)")
        self.straddle_otm_spin.valueChanged.connect(self.on_straddle_otm_changed)
        control_layout.addWidget(self.straddle_otm_spin, 1, 1)
        
        # Row 2: Trade Quantity
        control_layout.addWidget(QLabel("Trade Quantity:"), 2, 0)
        self.straddle_qty_spin = QSpinBox()
        self.straddle_qty_spin.setRange(1, 100)
        self.straddle_qty_spin.setSingleStep(1)
        self.straddle_qty_spin.setValue(self.trade_qty)
        self.straddle_qty_spin.setToolTip("Number of contracts per leg")
        control_layout.addWidget(self.straddle_qty_spin, 2, 1)
        
        top_layout.addWidget(control_group)
        
        # Strike Selection Display
        strike_group = QGroupBox("Current Strike Selection")
        strike_layout = QGridLayout(strike_group)
        
        # ATM Strike Display
        strike_layout.addWidget(QLabel("Current ATM:"), 0, 0)
        self.straddle_atm_label = QLabel("--")
        self.straddle_atm_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #FFD700;")
        strike_layout.addWidget(self.straddle_atm_label, 0, 1)
        
        # Call Strike Display
        strike_layout.addWidget(QLabel("Call Strike:"), 1, 0)
        self.straddle_call_strike_label = QLabel("--")
        self.straddle_call_strike_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #00ff00;")
        strike_layout.addWidget(self.straddle_call_strike_label, 1, 1)
        
        # Call Greeks
        strike_layout.addWidget(QLabel("Call IV:"), 1, 2)
        self.straddle_call_iv_label = QLabel("--")
        strike_layout.addWidget(self.straddle_call_iv_label, 1, 3)
        
        strike_layout.addWidget(QLabel("Call Delta:"), 1, 4)
        self.straddle_call_delta_label = QLabel("--")
        strike_layout.addWidget(self.straddle_call_delta_label, 1, 5)
        
        strike_layout.addWidget(QLabel("Call Price:"), 1, 6)
        self.straddle_call_price_label = QLabel("--")
        strike_layout.addWidget(self.straddle_call_price_label, 1, 7)
        
        # Put Strike Display
        strike_layout.addWidget(QLabel("Put Strike:"), 2, 0)
        self.straddle_put_strike_label = QLabel("--")
        self.straddle_put_strike_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #ff4444;")
        strike_layout.addWidget(self.straddle_put_strike_label, 2, 1)
        
        # Put Greeks
        strike_layout.addWidget(QLabel("Put IV:"), 2, 2)
        self.straddle_put_iv_label = QLabel("--")
        strike_layout.addWidget(self.straddle_put_iv_label, 2, 3)
        
        strike_layout.addWidget(QLabel("Put Delta:"), 2, 4)
        self.straddle_put_delta_label = QLabel("--")
        strike_layout.addWidget(self.straddle_put_delta_label, 2, 5)
        
        strike_layout.addWidget(QLabel("Put Price:"), 2, 6)
        self.straddle_put_price_label = QLabel("--")
        strike_layout.addWidget(self.straddle_put_price_label, 2, 7)
        
        # Total Cost
        strike_layout.addWidget(QLabel("Total Cost:"), 3, 0)
        self.straddle_total_cost_label = QLabel("--")
        self.straddle_total_cost_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #ff8c00;")
        strike_layout.addWidget(self.straddle_total_cost_label, 3, 1, 1, 2)
        
        # Max Risk
        strike_layout.addWidget(QLabel("Max Risk:"), 3, 3)
        self.straddle_max_risk_label = QLabel("--")
        self.straddle_max_risk_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #ff4444;")
        strike_layout.addWidget(self.straddle_max_risk_label, 3, 4, 1, 2)
        
        top_layout.addWidget(strike_group)
        
        # Action Buttons
        button_layout = QHBoxLayout()
        
        self.enter_straddle_btn = QPushButton("🎯 Enter Straddle")
        self.enter_straddle_btn.setStyleSheet("font-size: 14pt; padding: 10px; background-color: #006400;")
        self.enter_straddle_btn.clicked.connect(self.enter_straddle_position)
        button_layout.addWidget(self.enter_straddle_btn)
        
        self.refresh_straddle_btn = QPushButton("🔄 Refresh Strikes")
        self.refresh_straddle_btn.clicked.connect(self.update_straddle_strike_display)
        button_layout.addWidget(self.refresh_straddle_btn)
        
        top_layout.addLayout(button_layout)
        
        main_splitter.addWidget(top_widget)
        
        # ===== BOTTOM SECTION: Active Straddle Positions =====
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        positions_group = QGroupBox("Active Straddle Positions")
        positions_layout = QVBoxLayout(positions_group)
        
        self.straddle_positions_table = QTableWidget()
        self.straddle_positions_table.setColumnCount(12)
        self.straddle_positions_table.setHorizontalHeaderLabels([
            "Trade ID", "Entry Time", "Call Strike", "Call Qty", "Put Strike", "Put Qty",
            "Entry Cost", "Current Value", "P&L", "P&L %", "Greeks", "Action"
        ])
        header = self.straddle_positions_table.horizontalHeader()
        if header:
            header.setStretchLastSection(False)
            for i in range(12):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.straddle_positions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        positions_layout.addWidget(self.straddle_positions_table)
        
        bottom_layout.addWidget(positions_group)
        
        main_splitter.addWidget(bottom_widget)
        
        # Set splitter proportions (40% top, 60% bottom)
        main_splitter.setSizes([400, 600])
        
        main_layout.addWidget(main_splitter)
        
        # Start update timer for strike display
        self.straddle_update_timer = QTimer()
        self.straddle_update_timer.timeout.connect(self.update_straddle_strike_display)
        self.straddle_update_timer.start(2000)  # Update every 2 seconds
        
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
        
        # Chain settings (moved from trading tab)
        chain_group = QGroupBox("Option Chain Settings")
        chain_layout = QFormLayout(chain_group)
        
        self.strikes_above_settings_spin = QSpinBox()
        self.strikes_above_settings_spin.setRange(5, 50)
        self.strikes_above_settings_spin.setValue(self.strikes_above)
        self.strikes_above_settings_spin.setToolTip("Number of strikes to display above ATM")
        chain_layout.addRow("Strikes Above ATM:", self.strikes_above_settings_spin)
        
        self.strikes_below_settings_spin = QSpinBox()
        self.strikes_below_settings_spin.setRange(5, 50)
        self.strikes_below_settings_spin.setValue(self.strikes_below)
        self.strikes_below_settings_spin.setToolTip("Number of strikes to display below ATM")
        chain_layout.addRow("Strikes Below ATM:", self.strikes_below_settings_spin)
        
        self.chain_refresh_settings_spin = QSpinBox()
        self.chain_refresh_settings_spin.setRange(0, 7200)
        self.chain_refresh_settings_spin.setSingleStep(60)
        self.chain_refresh_settings_spin.setValue(self.chain_refresh_interval)
        self.chain_refresh_settings_spin.setToolTip("Automatic chain refresh interval in seconds (0 = disabled)")
        chain_layout.addRow("Auto Refresh (seconds):", self.chain_refresh_settings_spin)
        
        self.chain_drift_settings_spin = QSpinBox()
        self.chain_drift_settings_spin.setRange(1, 20)
        self.chain_drift_settings_spin.setValue(self.chain_drift_threshold)
        self.chain_drift_settings_spin.setToolTip("How many strikes ATM can drift before auto-recentering")
        chain_layout.addRow("Drift Threshold (strikes):", self.chain_drift_settings_spin)
        
        layout.addWidget(chain_group)
        
        # TradeStation Chain Settings
        ts_chain_group = QGroupBox("TradeStation Chain Settings")
        ts_chain_layout = QFormLayout(ts_chain_group)
        
        self.ts_strikes_above_spin = QSpinBox()
        self.ts_strikes_above_spin.setRange(3, 20)
        self.ts_strikes_above_spin.setValue(self.ts_strikes_above)
        self.ts_strikes_above_spin.setToolTip("Number of strikes above ATM for TS chains")
        ts_chain_layout.addRow("TS Strikes Above ATM:", self.ts_strikes_above_spin)
        
        self.ts_strikes_below_spin = QSpinBox()
        self.ts_strikes_below_spin.setRange(3, 20)
        self.ts_strikes_below_spin.setValue(self.ts_strikes_below)
        self.ts_strikes_below_spin.setToolTip("Number of strikes below ATM for TS chains")
        ts_chain_layout.addRow("TS Strikes Below ATM:", self.ts_strikes_below_spin)
        
        self.ts_chain_drift_spin = QSpinBox()
        self.ts_chain_drift_spin.setRange(1, 10)
        self.ts_chain_drift_spin.setValue(self.ts_chain_drift_threshold)
        self.ts_chain_drift_spin.setToolTip("How many strikes ATM can drift in TS chains before auto-recentering")
        ts_chain_layout.addRow("TS Drift Threshold (strikes):", self.ts_chain_drift_spin)
        
        layout.addWidget(ts_chain_group)
        
        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        
        return tab
    
    def apply_dark_theme(self):
        """Apply IBKR TWS dark color scheme with minimal Bloomberg-style orange accents"""
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
            border: 1px solid #FF8C00;
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
        """
        Connect to Interactive Brokers.
        Will automatically try client IDs 1-10 if one is already in use.
        """
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
            # Use client_id_iterator for connection (allows auto-increment on error 326)
            self.client_id = self.client_id_iterator
            
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
    
    def retry_connection_with_new_client_id(self):
        """
        Retry connection with new client ID after error 326.
        Called via QTimer.singleShot after incrementing client_id_iterator.
        """
        logger.info(f"RETRY: Starting retry with client_id={self.client_id}, iterator={self.client_id_iterator}")
        self.handling_client_id_error = False
        logger.info(f"Retrying connection with client ID {self.client_id}")
        # Update the client ID in the UI
        self.client_id_edit.setText(str(self.client_id))
        # Don't reset client_id_iterator - it should keep the incremented value
        # Attempt reconnection
        self.connect_to_ibkr()
    
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
            self.ibkr_client.reqPositions()  # This will trigger position() callbacks, which auto-subscribe to market data
            self.subscribe_underlying_price()  # Subscribe to underlying instrument (SPX, XSP, etc.) for display
            self.subscribe_es_price()   # ES for strike calculations (23/6 trading)
            self.subscribe_mes_price()  # MES for vega strategy delta hedging
            self.request_option_chain()
            
            # Calculate offset from historical 3pm close if stale
            if self.is_offset_stale() and not self.is_market_hours():
                if self.es_to_cash_offset == 0:
                    self.log_message("No saved offset found and connected after market hours - calculating from historical 3pm close", "INFO")
                else:
                    from datetime import datetime
                    last_update = datetime.fromtimestamp(self.last_offset_update_time).strftime('%Y-%m-%d %H:%M:%S')
                    self.log_message(f"Saved offset is stale (last updated: {last_update}) - recalculating from historical 3pm close", "INFO")
                self.calculate_offset_from_historical_close()
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
    
    def subscribe_underlying_price(self):
        """Subscribe to underlying price (SPX or XSP based on SELECTED_INSTRUMENT)"""
        underlying_contract = Contract()
        underlying_contract.symbol = self.instrument['underlying_symbol']
        underlying_contract.secType = self.instrument['underlying_type']
        underlying_contract.currency = "USD"
        underlying_contract.exchange = self.instrument['underlying_exchange']
        
        req_id = 1
        self.app_state['underlying_req_id'] = req_id
        
        # Request LIVE market data (type 1 = live, never use delayed data)
        self.ibkr_client.reqMarketDataType(1)
        
        # Subscribe to market data (snapshot=False for streaming live data)
        self.ibkr_client.reqMktData(req_id, underlying_contract, "", False, False, [])
        self.log_message(f"Subscribed to {self.instrument['underlying_symbol']} underlying price (LIVE data)", "INFO")
    
    @pyqtSlot(float)
    def update_underlying_display(self, price: float):
        """Update underlying price display (SPX or XSP based on SELECTED_INSTRUMENT)"""
        self.app_state['underlying_price'] = price
        self.underlying_price = price  # Store for chart updates
        self.underlying_price_label.setText(f"{self.instrument['underlying_symbol']}: {price:.2f}")
        
        # Update ES-to-cash offset if conditions are met
        self.update_es_to_cash_offset(price, None)
        
        # Update charts with live data
        self.update_charts_with_live_data()
    
    def is_market_hours(self):
        """Check if it's during regular market hours (8:30 AM - 3:00 PM Central Time)"""
        import pytz
        ct_tz = pytz.timezone('US/Central')
        now_ct = datetime.now(ct_tz)
        
        # Market is open Monday-Friday, 8:30 AM - 3:00 PM CT (9:30 AM - 4:00 PM ET)
        if now_ct.weekday() >= 5:  # Weekend
            return False
        
        market_open = now_ct.replace(hour=8, minute=30, second=0, microsecond=0)
        market_close = now_ct.replace(hour=15, minute=0, second=0, microsecond=0)
        
        return market_open <= now_ct <= market_close
    
    def is_offset_stale(self):
        """
        Check if the ES-to-cash offset is stale and needs to be recalculated.
        Offset is considered stale if:
        - It's zero (never set)
        - It's older than the most recent 3pm market close
        """
        if self.es_to_cash_offset == 0:
            return True
        
        if self.last_offset_update_time == 0:
            return True
        
        import pytz
        ct_tz = pytz.timezone('US/Central')
        now_ct = datetime.now(ct_tz)
        last_update = datetime.fromtimestamp(self.last_offset_update_time, tz=ct_tz)
        
        # Find the most recent 3pm market close
        if now_ct.hour >= 15:  # After 3pm today
            latest_close = now_ct.replace(hour=15, minute=0, second=0, microsecond=0)
        else:  # Before 3pm today, use yesterday's close
            latest_close = now_ct.replace(hour=15, minute=0, second=0, microsecond=0) - timedelta(days=1)
        
        # Move back to Friday if latest_close is on weekend
        while latest_close.weekday() >= 5:  # Saturday or Sunday
            latest_close -= timedelta(days=1)
        
        # Offset is stale if it was updated before the most recent 3pm close
        return last_update < latest_close
    
    def is_futures_market_closed(self):
        """
        Check if ES futures market is closed (needs snapshot instead of streaming).
        ES futures are closed during: 4:00-5:00 PM CT (5:00-6:00 PM ET) weekdays and all weekend.
        Weekend starts Friday at 4:00 PM CT (5:00 PM ET) and ends Sunday at 5:00 PM CT (6:00 PM ET).
        """
        import pytz
        ct_tz = pytz.timezone('US/Central')
        now_ct = datetime.now(ct_tz)
        
        # Saturday or Sunday - definitely closed
        if now_ct.weekday() >= 5:  # Saturday or Sunday
            return True
        
        # Friday after 4:00 PM CT - weekend starts (market closed until Sunday 5pm)
        if now_ct.weekday() == 4:  # Friday
            friday_close = now_ct.replace(hour=16, minute=0, second=0, microsecond=0)
            if now_ct >= friday_close:
                return True
        
        # Weekdays (Mon-Fri): Check if in 4:00-5:00 PM CT window (ES futures settlement/closed period)
        settlement_start = now_ct.replace(hour=16, minute=0, second=0, microsecond=0)
        settlement_end = now_ct.replace(hour=17, minute=0, second=0, microsecond=0)
        
        return settlement_start <= now_ct < settlement_end
    
    def update_es_to_cash_offset(self, underlying_price=None, es_price=None):
        """
        Calculate and update ES-to-cash offset during market hours (8:30 AM - 3:00 PM CT).
        Offset is saved to settings every minute for use during after-hours trading.
        """
        # Use current prices if not provided
        if underlying_price is None:
            underlying_price = self.app_state['underlying_price']
        if es_price is None:
            es_price = self.app_state['es_price']
        
        # Need both prices to calculate offset
        if underlying_price <= 0 or es_price <= 0:
            return
        
        # Only update offset during market hours (8:30 AM - 3:00 PM Central Time)
        if not self.is_market_hours():
            self.offset_update_enabled = False
            return
        
        self.offset_update_enabled = True
        
        # For XSP, we need to scale ES to match XSP scale (ES/10)
        if self.instrument['underlying_symbol'] == 'XSP':
            # ES futures vs XSP cash: ES/10 - XSP
            scaled_es = es_price / 10.0
            offset = scaled_es - underlying_price
        else:
            # ES futures vs SPX cash: ES - SPX
            offset = es_price - underlying_price
        
        # Update offset and timestamp
        old_offset = self.es_to_cash_offset
        self.es_to_cash_offset = offset
        self.last_offset_update_time = time.time()
        
        # Update display
        self.update_offset_display()
        
        # Log significant offset changes (more than 1 point)
        if abs(offset - old_offset) > 1.0:
            symbol = self.instrument['underlying_symbol']
            logger.info(f"ES-to-{symbol} offset updated: {offset:.2f} points (was {old_offset:.2f}) [Market Hours Tracking]")
    
    def update_offset_display(self):
        """Update the ES offset display label"""
        symbol = self.instrument['underlying_symbol']
        if self.es_to_cash_offset == 0.0:
            self.es_offset_label.setText(f"ES to {symbol} offset: N/A")
        else:
            # Show different status based on whether we're in market hours
            if self.offset_update_enabled:
                status = "(live - tracking)"
            else:
                status = "(saved - from day session)"
            
            self.es_offset_label.setText(f"ES to {symbol} offset: {self.es_to_cash_offset:+.2f} {status}")
            
            # Color coding: green for premium, red for discount, yellow for saved/frozen
            if not self.offset_update_enabled:
                color = "#FFD700"  # Gold for saved offset (after-hours)
            elif self.es_to_cash_offset > 0:
                color = "#90EE90"  # Light green for premium (live)
            else:
                color = "#FFA07A"  # Light salmon for discount (live)
            
            self.es_offset_label.setStyleSheet(f"font-size: 12pt; color: {color};")
    
    def get_adjusted_es_price(self):
        """
        Get ES price adjusted for the cash offset for strike calculations.
        
        IMPORTANT: This should ONLY be used as a fallback when the actual underlying
        index (XSP/SPX) is not available. During regular market hours, always prefer
        the actual underlying price.
        
        The ES futures trade 23/6 but have a basis difference from the cash index.
        Using ES/10 for XSP will give incorrect ATM strikes that don't match TWS.
        """
        es_price = self.app_state['es_price']
        if es_price <= 0:
            return 0
        
        # Apply the offset to get a price closer to cash
        if self.instrument['underlying_symbol'] == 'XSP':
            # For XSP: (ES - offset*10) / 10
            adjusted_es = es_price - (self.es_to_cash_offset * 10.0)
            return adjusted_es / 10.0
        else:
            # For SPX: ES - offset
            return es_price - self.es_to_cash_offset
    
    def find_atm_strike_by_delta(self):
        """
        Find the TRUE ATM strike by identifying options with delta closest to 0.5.
        
        This is the industry-standard way to determine ATM:
        - ATM Call: Delta closest to +0.5
        - ATM Put: Delta closest to -0.5 (absolute value 0.5)
        
        Returns:
            float: The strike price closest to ATM, or 0 if no deltas available
        """
        min_call_diff = float('inf')
        min_put_diff = float('inf')
        atm_call_strike = 0
        atm_put_strike = 0
        
        # Search through all option market data for deltas
        for contract_key, data in self.market_data.items():
            if '_C_' not in contract_key and '_P_' not in contract_key:
                continue
            
            delta = data.get('delta', None)
            if delta is None or delta == 0:
                continue
            
            # Parse strike from contract_key: "XSP_589_C_20251029"
            try:
                parts = contract_key.split('_')
                if len(parts) != 4:
                    continue
                strike = float(parts[1])
                
                if '_C_' in contract_key:
                    # Call delta should be between 0 and 1, target 0.5
                    if 0 < delta < 1:
                        diff = abs(delta - 0.5)
                        if diff < min_call_diff:
                            min_call_diff = diff
                            atm_call_strike = strike
                
                elif '_P_' in contract_key:
                    # Put delta should be between -1 and 0, target -0.5
                    if -1 < delta < 0:
                        diff = abs(abs(delta) - 0.5)
                        if diff < min_put_diff:
                            min_put_diff = diff
                            atm_put_strike = strike
            
            except (ValueError, IndexError):
                continue
        
        # Prefer call-based ATM, fallback to put-based ATM
        if atm_call_strike > 0:
            logger.debug(f"ATM strike identified by CALL delta: {atm_call_strike} (delta diff: {min_call_diff:.4f})")
            return atm_call_strike
        elif atm_put_strike > 0:
            logger.debug(f"ATM strike identified by PUT delta: {atm_put_strike} (delta diff: {min_put_diff:.4f})")
            return atm_put_strike
        else:
            logger.debug("No ATM strike found by delta - waiting for greeks data")
            return 0
    
    def get_es_front_month(self):
        """
        Calculate ES futures front month contract based on CME rollover rules.
        
        ES futures expire on 3rd Friday of March, June, September, December (H, M, U, Z).
        Rollover typically occurs 8 days before expiration (2nd Thursday).
        
        Returns: str - Contract month code (e.g., "202503" for March 2025, "ESH5")
        """
        now = datetime.now(self.local_tz)
        year = now.year
        month = now.month
        day = now.day
        
        # Quarterly months: March(3), June(6), September(9), December(12)
        quarterly_months = [3, 6, 9, 12]
        
        # Find current or next quarterly month
        next_quarterly = None
        for qm in quarterly_months:
            if month <= qm:
                next_quarterly = qm
                break
        
        # If we're past December, roll to March of next year
        if next_quarterly is None:
            next_quarterly = 3
            year += 1
        
        # Calculate 3rd Friday of the contract month
        # Find first day of month and its weekday
        first_day = datetime(year, next_quarterly, 1)
        # Calculate days until first Friday (weekday 4 = Friday)
        days_until_friday = (4 - first_day.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 0  # First day is Friday
        first_friday = first_day + timedelta(days=days_until_friday)
        third_friday = first_friday + timedelta(days=14)  # Add 2 weeks
        
        # Rollover date: 8 days before expiration (2nd Thursday, week before 3rd Friday)
        rollover_date = third_friday - timedelta(days=8)
        
        # If we're past rollover date, move to next quarterly month
        if now.date() >= rollover_date.date():
            current_index = quarterly_months.index(next_quarterly)
            if current_index < len(quarterly_months) - 1:
                next_quarterly = quarterly_months[current_index + 1]
            else:
                next_quarterly = 3  # March of next year
                year += 1
        
        # ES month codes: H=Mar, M=Jun, U=Sep, Z=Dec
        month_codes = {3: 'H', 6: 'M', 9: 'U', 12: 'Z'}
        month_code = month_codes[next_quarterly]
        
        # Format: YYYYMM for contract (e.g., 202503)
        contract_month = f"{year}{next_quarterly:02d}"
        
        logger.info(f"ES front month: {month_code}{year%100} ({contract_month}), rollover: {rollover_date.strftime('%Y-%m-%d')}")
        
        return contract_month
    
    def subscribe_es_price(self):
        """Subscribe to ES futures front month for 23/6 price discovery"""
        es_contract = Contract()
        es_contract.symbol = "ES"
        es_contract.secType = "FUT"
        es_contract.currency = "USD"
        es_contract.exchange = "CME"
        es_contract.lastTradeDateOrContractMonth = self.get_es_front_month()
        
        req_id = 2
        self.app_state['es_req_id'] = req_id
        
        # Request LIVE market data (type 1 = live, never use delayed data)
        self.ibkr_client.reqMarketDataType(1)
        
        # Use snapshot mode during futures market closed hours (4-5pm CT weekdays, weekends)
        # to get last known price instead of waiting for streaming data
        use_snapshot = self.is_futures_market_closed()
        
        # Subscribe to market data
        self.ibkr_client.reqMktData(req_id, es_contract, "", use_snapshot, False, [])
        mode_str = "snapshot mode" if use_snapshot else "streaming mode"
        self.log_message(f"Subscribed to ES futures {es_contract.lastTradeDateOrContractMonth} ({mode_str}, LIVE data)", "INFO")
    
    def get_mes_front_month(self):
        """
        Get MES (Micro E-mini S&P 500) futures front month.
        MES has same expiration schedule as ES (quarterly: Mar, Jun, Sep, Dec).
        
        Returns: str - Contract month code (e.g., "202512" for December 2025)
        """
        # MES uses same rollover logic as ES
        return self.get_es_front_month()
    
    def subscribe_mes_price(self):
        """Subscribe to MES futures for delta hedging"""
        if self.connection_state != ConnectionState.CONNECTED:
            logger.warning("Cannot subscribe to MES: not connected")
            return
        
        # Get front month
        self.mes_front_month = self.get_mes_front_month()
        
        # Create MES contract
        self.mes_contract = Contract()
        self.mes_contract.symbol = self.instrument['hedge_symbol']  # "MES" for XSP
        self.mes_contract.secType = self.instrument['hedge_sec_type']  # "FUT"
        self.mes_contract.currency = "USD"
        self.mes_contract.exchange = self.instrument['hedge_exchange']  # "CME"
        self.mes_contract.lastTradeDateOrContractMonth = self.mes_front_month
        
        # Use a high request ID to avoid conflicts
        self.mes_req_id = 9001
        
        # Request LIVE market data
        self.ibkr_client.reqMarketDataType(1)
        
        # Use snapshot during market closed hours
        use_snapshot = self.is_futures_market_closed()
        
        # Subscribe to market data
        self.ibkr_client.reqMktData(self.mes_req_id, self.mes_contract, "", use_snapshot, False, [])
        mode_str = "snapshot mode" if use_snapshot else "streaming mode"
        self.log_message(f"✅ Subscribed to {self.mes_contract.symbol} futures {self.mes_front_month} ({mode_str}) for hedging", "SUCCESS")
        logger.info(f"MES subscription: {self.mes_contract.symbol} {self.mes_front_month}, reqId={self.mes_req_id}")
    
    def update_mes_price(self, price: float):
        """Update MES futures price (called from market data callback)"""
        self.mes_price = price
        logger.debug(f"MES price updated: {price:.2f}")
    
    @pyqtSlot(float)
    def update_es_display(self, price: float):
        """Update ES futures price display"""
        self.app_state['es_price'] = price
        self.es_price_label.setText(f"ES: {price:.2f}")
        
        # Update ES-to-cash offset if conditions are met
        self.update_es_to_cash_offset(None, price)
    
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
        
        # Also update TS chain tables if this contract belongs to a TS expiry
        self.update_ts_chain_cell(contract_key)
    
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
        
        # Also update TS chain tables if this contract belongs to a TS expiry
        self.update_ts_chain_cell(contract_key)
        
        # Update strike backgrounds based on delta-identified ATM
        # Throttle this to run at most once per second to avoid excessive recentering checks
        import time
        current_time = time.time()
        if not hasattr(self, '_last_atm_update_time'):
            self._last_atm_update_time = 0
        
        if current_time - self._last_atm_update_time >= 1.0:  # Update at most once per second
            self._last_atm_update_time = current_time
            self.update_strike_backgrounds_by_delta()
    
    @pyqtSlot(str, dict)
    def on_position_update(self, contract_key: str, position_data: dict):
        """Handle position updates"""
        # Add entryTime if this is a new position
        if contract_key not in self.positions:
            position_data['entryTime'] = datetime.now()
        else:
            # Preserve existing entryTime
            position_data['entryTime'] = self.positions[contract_key].get('entryTime', datetime.now())
        
        self.positions[contract_key] = position_data
        
        # Merge with saved positions to restore entryTime from previous session
        self.merge_saved_positions(contract_key)
        
        # Subscribe to market data for this position (if not already subscribed)
        # This ensures market data is available for P&L and close orders
        self.subscribe_position_market_data(contract_key, position_data.get('contract'))
        
        # No need to call update_positions_display() - timer does it automatically every second
    
    def subscribe_position_market_data(self, contract_key: str, contract: Optional[Contract] = None):
        """
        Subscribe to market data for a position.
        Called when position arrives from IBKR or when reconnecting with saved positions.
        Ensures bid/ask are available for real-time P&L and close order mid-price chasing.
        """
        if not contract:
            # If no contract provided, try to get from positions
            if contract_key in self.positions:
                contract = self.positions[contract_key].get('contract')
            if not contract:
                logger.warning(f"Cannot subscribe to market data for {contract_key} - no contract available")
                return
        
        # Check if already subscribed
        is_subscribed = any(contract_key == v for v in self.app_state.get('market_data_map', {}).values())
        
        if is_subscribed:
            logger.debug(f"Position {contract_key} already has active market data subscription")
            return
        
        logger.info(f"Subscribing to market data for position: {contract_key}")
        self.log_message(f"Subscribing to market data for position: {contract_key}", "INFO")
        
        # Generate new request ID
        req_id = self.app_state['next_req_id']
        self.app_state['next_req_id'] += 1
        
        # Ensure contract has required fields
        if not contract.exchange:
            contract.exchange = "SMART"
        if not contract.tradingClass:
            contract.tradingClass = self.instrument['options_trading_class']
        if not contract.currency:
            contract.currency = "USD"
        
        # Map request ID to contract key
        self.app_state['market_data_map'][req_id] = contract_key
        
        # Create market_data entry if it doesn't exist
        if contract_key not in self.market_data:
            self.market_data[contract_key] = {
                'contract': contract,
                'right': contract.right,
                'strike': contract.strike,
                'bid': 0, 'ask': 0, 'last': 0, 'volume': 0,
                'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'iv': 0
            }
            logger.debug(f"Created market_data entry for {contract_key}")
        
        # Subscribe to market data
        self.ibkr_client.reqMktData(req_id, contract, "", False, False, [])
        logger.info(f"Requested market data (reqId={req_id}) for {contract_key}")
    
    @pyqtSlot(int, dict)
    def on_order_status(self, order_id: int, status_data: dict):
        """Handle order status updates"""
        # Update pending order status
        if order_id in self.pending_orders:
            self.pending_orders[order_id]['status'] = status_data.get('status', 'Unknown')
            self.pending_orders[order_id]['filled'] = status_data.get('filled', 0)
            
            # Remove from pending if filled or cancelled
            status = status_data.get('status', '')
            if status in ['Filled', 'Cancelled', 'Inactive']:
                self.log_message(f"Order #{order_id} {status}", "SUCCESS")
                
                # CRITICAL: Remove from chasing_orders to stop chasing
                if order_id in self.chasing_orders:
                    logger.info(f"Removing order #{order_id} from chasing_orders (status: {status})")
                    del self.chasing_orders[order_id]
                
                # Keep in pending_orders for display but mark as complete
            
            # Update orders table
            self.update_orders_display()
            self.update_ts_orders_display()
        else:
            self.log_message(f"Received status for unknown order #{order_id}: {status_data.get('status')}", "INFO")
    
    @pyqtSlot(int)
    def remove_from_chasing_orders(self, order_id: int):
        """Remove order from chasing tracking (called when order is filled/cancelled)"""
        if order_id in self.chasing_orders:
            logger.info(f"Force-removing order #{order_id} from chasing_orders (order filled/cancelled)")
            del self.chasing_orders[order_id]
            self.update_orders_display()
            self.update_ts_orders_display()
    
    @pyqtSlot(str)
    def on_position_closed(self, contract_key: str):
        """
        Handle position closed (quantity = 0).
        Unsubscribes from market data and removes position from tracking.
        """
        logger.info(f"Handling position close for {contract_key}")
        
        # Unsubscribe from market data for this position
        self.unsubscribe_position_market_data(contract_key)
        
        # Remove from positions dict
        if contract_key in self.positions:
            del self.positions[contract_key]
            logger.info(f"Removed {contract_key} from positions tracking")
        
        # Remove from market_data dict
        if contract_key in self.market_data:
            del self.market_data[contract_key]
            logger.debug(f"Removed {contract_key} from market_data")
        
        # Update display (position will disappear from table)
        # No need to call update_positions_display() - timer does it automatically
    
    def unsubscribe_position_market_data(self, contract_key: str):
        """
        Unsubscribe from market data for a closed position.
        Cleans up resources by canceling the market data subscription.
        """
        # Find the req_id for this contract_key
        req_id_to_cancel = None
        for req_id, mapped_key in list(self.app_state.get('market_data_map', {}).items()):
            if mapped_key == contract_key:
                req_id_to_cancel = req_id
                break
        
        if req_id_to_cancel is not None:
            logger.info(f"Unsubscribing from market data for {contract_key} (reqId={req_id_to_cancel})")
            try:
                self.ibkr_client.cancelMktData(req_id_to_cancel)
                # Remove from map
                del self.app_state['market_data_map'][req_id_to_cancel]
                logger.info(f"Successfully unsubscribed market data (reqId={req_id_to_cancel})")
            except Exception as e:
                logger.error(f"Error unsubscribing market data for {contract_key}: {e}", exc_info=True)
        else:
            logger.debug(f"No active market data subscription found for {contract_key}")
    
    @pyqtSlot(str, dict)
    def on_historical_bar(self, contract_key: str, bar_data: dict):
        """Handle historical bar data"""
        # Check if this is for offset calculation from historical close
        if hasattr(self, 'historical_close_data') and self.historical_close_data:
            # This might be offset calculation data, handle separately
            if contract_key == 'HISTORICAL_CLOSE_SPX' or contract_key == 'HISTORICAL_CLOSE_ES':
                req_id = self.app_state.get('historical_close_spx_req_id') if 'SPX' in contract_key else self.app_state.get('historical_close_es_req_id')
                if req_id is not None:
                    self.on_historical_close_data_received(req_id, bar_data)
                return
        
        # Check if this is a backfill request for a chart
        is_backfill = False
        if contract_key == "ES_FUTURES_CONFIRM" and hasattr(self, 'confirm_chart_widget'):
            if self.confirm_chart_widget.backfill_req_id is not None:
                # Find the req_id for this bar
                for req_id, key in self.app_state.get('historical_data_requests', {}).items():
                    if key == contract_key and req_id == self.confirm_chart_widget.backfill_req_id:
                        is_backfill = True
                        self.confirm_chart_widget.backfill_data.append(bar_data)
                        return  # Don't append to main data yet
        elif contract_key.startswith("UNDERLYING_") and hasattr(self, 'trade_chart_widget'):
            if self.trade_chart_widget.backfill_req_id is not None:
                for req_id, key in self.app_state.get('historical_data_requests', {}).items():
                    if key == contract_key and req_id == self.trade_chart_widget.backfill_req_id:
                        is_backfill = True
                        self.trade_chart_widget.backfill_data.append(bar_data)
                        return  # Don't append to main data yet
        
        if not is_backfill:
            if contract_key not in self.historical_data:
                self.historical_data[contract_key] = []
            
            self.historical_data[contract_key].append(bar_data)
            
            # Update charts based on contract type
            if contract_key.startswith("UNDERLYING_") or contract_key == "ES_FUTURES_CONFIRM":
                self.update_underlying_chart_data(contract_key, bar_data)
            elif contract_key.startswith("CHART_"):
                self.update_option_chart_data(contract_key, bar_data)
    
    @pyqtSlot(str)
    def on_historical_complete(self, contract_key: str):
        """Handle historical data complete"""
        # Check if this is for offset calculation from historical close
        if hasattr(self, 'historical_close_data') and self.historical_close_data:
            if contract_key == 'HISTORICAL_CLOSE_SPX' or contract_key == 'HISTORICAL_CLOSE_ES':
                req_id = self.app_state.get('historical_close_spx_req_id') if 'SPX' in contract_key else self.app_state.get('historical_close_es_req_id')
                if req_id is not None:
                    self.on_historical_close_data_complete(req_id)
                return
        
        # Check if this is a backfill completion
        is_backfill = False
        if contract_key == "ES_FUTURES_CONFIRM" and hasattr(self, 'confirm_chart_widget'):
            if self.confirm_chart_widget.backfill_req_id is not None and len(self.confirm_chart_widget.backfill_data) > 0:
                # Prepend backfill data to existing data
                if contract_key not in self.historical_data:
                    self.historical_data[contract_key] = []
                self.historical_data[contract_key] = self.confirm_chart_widget.backfill_data + self.historical_data[contract_key]
                logger.info(f"Prepended {len(self.confirm_chart_widget.backfill_data)} backfill bars to {contract_key}")
                logger.info(f"Total bars after prepend: {len(self.historical_data[contract_key])}")
                # Clear backfill state
                self.confirm_chart_widget.backfill_data = []
                self.confirm_chart_widget.backfill_req_id = None
                self.confirm_chart_widget.is_fetching_more_data = False
                # Force full redraw of chart
                self.confirm_chart_widget.needs_full_redraw = True
                is_backfill = True
                # Force chart refresh with new data immediately (not throttled)
                self.update_underlying_charts_complete(contract_key, immediate=True)
                return
        elif contract_key.startswith("UNDERLYING_") and hasattr(self, 'trade_chart_widget'):
            if self.trade_chart_widget.backfill_req_id is not None and len(self.trade_chart_widget.backfill_data) > 0:
                # Prepend backfill data to existing data
                if contract_key not in self.historical_data:
                    self.historical_data[contract_key] = []
                self.historical_data[contract_key] = self.trade_chart_widget.backfill_data + self.historical_data[contract_key]
                logger.info(f"Prepended {len(self.trade_chart_widget.backfill_data)} backfill bars to {contract_key}")
                logger.info(f"Total bars after prepend: {len(self.historical_data[contract_key])}")
                # Clear backfill state
                self.trade_chart_widget.backfill_data = []
                self.trade_chart_widget.backfill_req_id = None
                self.trade_chart_widget.is_fetching_more_data = False
                # Force full redraw of chart
                self.trade_chart_widget.needs_full_redraw = True
                is_backfill = True
                # Force chart refresh with new data immediately (not throttled)
                self.update_underlying_charts_complete(contract_key, immediate=True)
                return
        
        if contract_key in self.historical_data:
            bars = self.historical_data[contract_key]
            self.log_message(f"Historical data complete for {contract_key}: {len(bars)} bars", "SUCCESS")
            
            # Update appropriate charts with complete data
            if contract_key.startswith("UNDERLYING_") or contract_key == "ES_FUTURES_CONFIRM":
                self.update_underlying_charts_complete(contract_key)
            elif contract_key.startswith("CHART_"):
                self.update_option_charts_complete(contract_key)
            else:
                # Legacy handling for direct contract keys
                if '_C_' in contract_key:
                    logger.info(f"CALL historical data ready: {len(bars)} bars")
                elif '_P_' in contract_key:
                    logger.info(f"PUT historical data ready: {len(bars)} bars")
    
    @pyqtSlot(str, dict)
    def on_historical_bar_update(self, contract_key: str, bar_data: dict):
        """Handle real-time bar updates from IBAPI's historicalDataUpdate callback"""
        try:
            # Add or update the bar in historical_data
            if contract_key not in self.historical_data:
                self.historical_data[contract_key] = []
            
            # Check if this is an update to the last bar or a new bar
            bars = self.historical_data[contract_key]
            bar_time = str(bar_data['date']).strip()
            
            if bars and str(bars[-1]['date']).strip() == bar_time:
                # Update existing bar (price changed within same time period)
                bars[-1] = bar_data
            else:
                # New bar
                bars.append(bar_data)
            
            # Update charts immediately - draw_idle() in chart code handles event coalescing
            # This provides real-time updates for trading while Qt event loop prevents blocking
            if contract_key.startswith("UNDERLYING_"):
                self.update_underlying_charts_complete(contract_key)
            elif contract_key.startswith("CHART_"):
                self.update_option_charts_complete(contract_key)
                
        except Exception as e:
            self.log_message(f"Error updating bar for {contract_key}: {e}", "ERROR")
            logger.exception(f"Error in on_historical_bar_update for {contract_key}")
    
    def update_underlying_chart_data(self, contract_key: str, bar_data: dict):
        """Update underlying chart data storage and trigger real-time chart updates"""
        try:
            # Convert bar data to chart format
            # Fix date format - IBKR sometimes has extra spaces
            date_str = str(bar_data['date']).strip().replace('  ', ' ')
            chart_bar = {
                'time': date_str,  # IBKR provides 'date' field
                'open': bar_data['open'],
                'high': bar_data['high'], 
                'low': bar_data['low'],
                'close': bar_data['close'],
                'volume': bar_data['volume']
            }
            
            if "TRADE" in contract_key:
                # This is for the trade chart - store separately or limit size
                if 'underlying_trade' not in self.chart_data:
                    self.chart_data['underlying_trade'] = []
                self.chart_data['underlying_trade'].append(chart_bar)
                # Keep only last 200 bars for trade chart
                if len(self.chart_data['underlying_trade']) > 200:
                    self.chart_data['underlying_trade'] = self.chart_data['underlying_trade'][-200:]
            elif contract_key == "ES_FUTURES_CONFIRM":
                # This is ES futures data for the confirmation chart
                if 'es_futures' not in self.chart_data:
                    self.chart_data['es_futures'] = []
                self.chart_data['es_futures'].append(chart_bar)
                # Keep only last 400 bars for confirmation chart
                if len(self.chart_data['es_futures']) > 400:
                    self.chart_data['es_futures'] = self.chart_data['es_futures'][-400:]
            else:
                # This is for the confirmation chart (legacy underlying data)
                self.chart_data['underlying'].append(chart_bar)
                # Keep only last 400 bars for confirmation chart
                if len(self.chart_data['underlying']) > 400:
                    self.chart_data['underlying'] = self.chart_data['underlying'][-400:]
                    
        except Exception as e:
            logger.error(f"Error updating underlying chart data: {e}")
    
    def update_option_chart_data(self, contract_key: str, bar_data: dict):
        """Update option chart data storage and trigger real-time chart updates"""
        try:
            # Handle new format: CHART_call_XSP_680_C_20251029 or CHART_put_XSP_680_P_20251029
            if contract_key.startswith("CHART_call_") or contract_key.startswith("CHART_put_"):
                # Parse the new format
                parts = contract_key.split("_", 2)  # Split into ["CHART", "call/put", "remaining"]
                option_type = parts[1]  # "call" or "put"
                actual_contract_key = parts[2]  # "XSP_680_C_20251029"
                
                # Convert bar data to chart format
                # Fix date format - IBKR sometimes has extra spaces
                date_str = str(bar_data['date']).strip().replace('  ', ' ')
                chart_bar = {
                    'time': date_str,
                    'open': bar_data['open'],
                    'high': bar_data['high'],
                    'low': bar_data['low'], 
                    'close': bar_data['close'],
                    'volume': bar_data['volume']
                }
                
                # Update the appropriate chart data and trigger real-time chart refresh
                if option_type == "call":
                    self.chart_data['selected_call'].append(chart_bar)
                    # Keep only last 200 bars
                    if len(self.chart_data['selected_call']) > 200:
                        self.chart_data['selected_call'] = self.chart_data['selected_call'][-200:]
                    # Update current call contract tracking
                    self.current_call_contract = actual_contract_key
                    
                elif option_type == "put":
                    self.chart_data['selected_put'].append(chart_bar)
                    # Keep only last 200 bars
                    if len(self.chart_data['selected_put']) > 200:
                        self.chart_data['selected_put'] = self.chart_data['selected_put'][-200:]
                    # Update current put contract tracking
                    self.current_put_contract = actual_contract_key
                
            else:
                # Legacy format handling
                actual_contract_key = contract_key.replace("CHART_", "")
                
                # Convert bar data to chart format
                # Fix date format - IBKR sometimes has extra spaces
                date_str = str(bar_data['date']).strip().replace('  ', ' ')
                chart_bar = {
                    'time': date_str,
                    'open': bar_data['open'],
                    'high': bar_data['high'],
                    'low': bar_data['low'], 
                    'close': bar_data['close'],
                    'volume': bar_data['volume']
                }
                
                if hasattr(self, 'current_call_contract') and actual_contract_key == self.current_call_contract:
                    self.chart_data['selected_call'].append(chart_bar)
                    if len(self.chart_data['selected_call']) > 200:
                        self.chart_data['selected_call'] = self.chart_data['selected_call'][-200:]
                        
                elif hasattr(self, 'current_put_contract') and actual_contract_key == self.current_put_contract:
                    self.chart_data['selected_put'].append(chart_bar)
                    if len(self.chart_data['selected_put']) > 200:
                        self.chart_data['selected_put'] = self.chart_data['selected_put'][-200:]
                    
        except Exception as e:
            logger.error(f"Error updating option chart data: {e}")
    
    def update_underlying_charts_complete(self, contract_key: str, immediate=False):
        """Update underlying charts when historical data is complete
        
        Args:
            contract_key: The contract key for the data
            immediate: If True, bypass throttling and update immediately (used for backfill)
        """
        try:
            # Use ALL historical data, not the truncated chart_data
            if contract_key in self.historical_data and self.historical_data[contract_key]:
                # Convert historical_data format to chart format
                chart_bars = []
                for bar in self.historical_data[contract_key]:
                    date_str = str(bar['date']).strip().replace('  ', ' ')
                    chart_bars.append({
                        'time': date_str,
                        'open': bar['open'],
                        'high': bar['high'],
                        'low': bar['low'],
                        'close': bar['close'],
                        'volume': bar['volume']
                    })
                
                if "TRADE" in contract_key:
                    # Update trade chart with ALL data
                    if immediate:
                        self.trade_chart_widget.update_chart(chart_bars)
                    else:
                        self.trade_chart_widget.update_chart_throttled(chart_bars)
                elif contract_key == "ES_FUTURES_CONFIRM":
                    # Update confirmation chart with ES futures data
                    if immediate:
                        self.confirm_chart_widget.update_chart(chart_bars, is_es_futures=True)
                    else:
                        self.confirm_chart_widget.update_chart_throttled(chart_bars, is_es_futures=True)
                else:
                    # Update confirmation chart with ALL data
                    if immediate:
                        self.confirm_chart_widget.update_chart(chart_bars)
                    else:
                        self.confirm_chart_widget.update_chart_throttled(chart_bars)
                    
        except Exception as e:
            logger.error(f"Error updating underlying charts: {e}")
    
    def update_option_charts_complete(self, contract_key: str):
        """Update option charts when historical data is complete"""
        try:
            # Use ALL historical data, not the truncated chart_data
            if contract_key in self.historical_data and self.historical_data[contract_key]:
                # Convert historical_data format to chart format
                chart_bars = []
                for bar in self.historical_data[contract_key]:
                    date_str = str(bar['date']).strip().replace('  ', ' ')
                    chart_bars.append({
                        'time': date_str,
                        'open': bar['open'],
                        'high': bar['high'],
                        'low': bar['low'],
                        'close': bar['close'],
                        'volume': bar['volume']
                    })
                
                # Handle new format: CHART_call_XSP_680_C_20251029 or CHART_put_XSP_680_P_20251029
                if contract_key.startswith("CHART_call_") or contract_key.startswith("CHART_put_"):
                    # Parse the new format
                    parts = contract_key.split("_", 2)  # Split into ["CHART", "call/put", "remaining"]
                    option_type = parts[1]  # "call" or "put"
                    actual_contract_key = parts[2]  # "XSP_680_C_20251029"
                    
                    if option_type == "call":
                        # Update call chart with ALL data - throttled for performance
                        description = self.get_option_description(actual_contract_key)
                        self.call_chart_widget.update_chart_throttled(chart_bars, description)
                        
                    elif option_type == "put":
                        # Update put chart with ALL data - throttled for performance
                        description = self.get_option_description(actual_contract_key)
                        self.put_chart_widget.update_chart_throttled(chart_bars, description)
                        
                else:
                    # Legacy format handling
                    actual_contract_key = contract_key.replace("CHART_", "")
                    
                    if hasattr(self, 'current_call_contract') and actual_contract_key == self.current_call_contract:
                        description = self.get_option_description(actual_contract_key)
                        self.call_chart_widget.update_chart_throttled(chart_bars, description)
                            
                    elif hasattr(self, 'current_put_contract') and actual_contract_key == self.current_put_contract:
                        description = self.get_option_description(actual_contract_key)
                        self.put_chart_widget.update_chart_throttled(chart_bars, description)
                    
        except Exception as e:
            logger.error(f"Error updating option charts: {e}")
    
    def get_option_description(self, contract_key: str) -> str:
        """Generate a description for an option contract"""
        try:
            # Parse contract key: XSP_680.0_C_20251029
            parts = contract_key.split('_')
            if len(parts) >= 4:
                symbol = parts[0]
                strike = parts[1]
                right = parts[2]
                expiry = parts[3]
                
                # Format expiry date
                if len(expiry) == 8:  # YYYYMMDD
                    formatted_date = f"{expiry[4:6]}/{expiry[6:8]}/{expiry[0:4]}"
                else:
                    formatted_date = expiry
                
                return f"{symbol} {strike} {right} Exp: {formatted_date}"
            else:
                return contract_key
                
        except Exception as e:
            logger.error(f"Error generating option description: {e}")
            return contract_key
    
    def round_to_strike(self, price: float) -> float:
        """Round price to the nearest valid strike price"""
        try:
            # Use strike_increment from instrument config
            strike_increment = self.instrument['strike_increment']
            return round(price / strike_increment) * strike_increment
        except Exception as e:
            logger.error(f"Error rounding to strike: {e}")
            return round(price)
    
    def update_charts_with_live_data(self):
        """Update charts with latest live data periodically"""
        try:
            current_time = time.time() * 1000  # Convert to milliseconds
            
            # Throttle updates to avoid excessive CPU usage
            if current_time - self.last_chart_update < self.chart_update_interval:
                return
                
            self.last_chart_update = current_time
            
            # Update charts if we have new data
            if self.underlying_price > 0:
                # Create current price bar for real-time updates
                current_bar = {
                    'time': datetime.now().isoformat(),
                    'open': self.underlying_price,
                    'high': self.underlying_price,
                    'low': self.underlying_price,
                    'close': self.underlying_price,
                    'volume': 0
                }
                
                # Add to underlying data if we have historical data
                if self.chart_data['underlying']:
                    # Replace the last bar if it's from the same minute, otherwise append
                    last_bar_time = datetime.fromisoformat(self.chart_data['underlying'][-1]['time'])
                    current_time_dt = datetime.now()
                    
                    if (last_bar_time.hour == current_time_dt.hour and 
                        last_bar_time.minute == current_time_dt.minute):
                        # Update the last bar's close price
                        self.chart_data['underlying'][-1]['close'] = self.underlying_price
                        self.chart_data['underlying'][-1]['high'] = max(
                            self.chart_data['underlying'][-1]['high'], self.underlying_price
                        )
                        self.chart_data['underlying'][-1]['low'] = min(
                            self.chart_data['underlying'][-1]['low'], self.underlying_price
                        )
                    else:
                        # Add new bar
                        self.chart_data['underlying'].append(current_bar)
                        
                    # Update both SPX charts
                    self.update_spx_chart(self.confirm_chart_widget, self.chart_data['underlying'])
                    
                    # Update trade chart if we have separate data
                    if 'underlying_trade' in self.chart_data and self.chart_data['underlying_trade']:
                        self.update_spx_chart(self.trade_chart_widget, self.chart_data['underlying_trade'])
                    
        except Exception as e:
            logger.error(f"Error updating charts with live data: {e}")
    
    # ========================================================================
    # OPTION CHAIN MANAGEMENT
    # ========================================================================
    
    def calculate_expiry_date(self, offset: int) -> str:
        """
        Calculate expiration date based on offset (0 = today, 1 = next, etc.)
        
        CRITICAL: After 4:00 PM local time, today's 0DTEs have expired.
        If offset=0 and time >= 4:00 PM local, return TOMORROW's expiration.
        
        Args:
            offset: Number of expirations ahead (0 = current 0DTE, 1 = next, etc.)
        
        Returns:
            Expiration date in YYYYMMDD format
        """
        # Get current time in local timezone
        now_local = datetime.now(self.local_tz)
        
        # Check if market has closed (4:00 PM local time)
        # NOTE: Market closes at 4:00 PM ET, but we use local time for user convenience
        market_close_hour = 16  # 4:00 PM
        
        # If after 4:00 PM local and looking for 0DTE (offset=0), skip to tomorrow
        # because today's options have expired
        if offset == 0 and now_local.hour >= market_close_hour:
            logger.info(f"After 4:00 PM local ({now_local.strftime('%I:%M %p')}), switching 0DTE to tomorrow")
            offset = 1  # Move to next expiration
        
        # Start from today
        target_date = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # XSP/SPX now have daily expirations Monday through Friday (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri)
        expiry_days = [0, 1, 2, 3, 4]  # Mon-Fri daily expirations
        
        expirations_found = 0
        days_checked = 0
        
        # Find the Nth expiration (where N = offset)
        while days_checked < 60:
            if target_date.weekday() in expiry_days:
                if expirations_found == offset:
                    result = target_date.strftime("%Y%m%d")
                    logger.debug(f"calculate_expiry_date(offset={offset}) = {result}")
                    return result
                expirations_found += 1
            target_date += timedelta(days=1)
            days_checked += 1
        
        # Fallback (should never hit this)
        logger.error("calculate_expiry_date exceeded max days - returning today")
        return now_local.strftime("%Y%m%d")
    
    def create_tradestation_tab(self):
        """Create the TradeStation integration tab"""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Top row: Strategy Monitor + Connection Controls
        top_row = QHBoxLayout()
        
        # Strategy Monitor Panel
        monitor_group = QGroupBox("Strategy Monitor")
        monitor_layout = QGridLayout(monitor_group)
        
        monitor_layout.addWidget(QLabel("Strategy State:"), 0, 0)
        self.ts_state_label = QLabel("FLAT")
        self.ts_state_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFF00;")
        monitor_layout.addWidget(self.ts_state_label, 0, 1)
        
        monitor_layout.addWidget(QLabel("Position Count:"), 1, 0)
        self.ts_position_count_label = QLabel("0")
        monitor_layout.addWidget(self.ts_position_count_label, 1, 1)
        
        monitor_layout.addWidget(QLabel("Last Signal:"), 2, 0)
        self.ts_last_signal_label = QLabel("None")
        monitor_layout.addWidget(self.ts_last_signal_label, 2, 1)
        
        monitor_layout.addWidget(QLabel("Active Contract:"), 3, 0)
        self.ts_active_contract_label = QLabel("0DTE")
        monitor_layout.addWidget(self.ts_active_contract_label, 3, 1)
        
        top_row.addWidget(monitor_group)
        
        # Connection Controls Panel
        controls_group = QGroupBox("TradeStation Connection")
        controls_layout = QVBoxLayout(controls_group)
        
        btn_layout = QHBoxLayout()
        self.enable_ts_btn = QPushButton("Enable TS")
        self.enable_ts_btn.clicked.connect(self.enable_tradestation)
        btn_layout.addWidget(self.enable_ts_btn)
        
        self.disable_ts_btn = QPushButton("Disable TS")
        self.disable_ts_btn.clicked.connect(self.disable_tradestation)
        self.disable_ts_btn.setEnabled(False)
        btn_layout.addWidget(self.disable_ts_btn)
        
        self.sync_ts_btn = QPushButton("Sync Strategy")
        self.sync_ts_btn.clicked.connect(self.sync_with_ts_strategy)
        self.sync_ts_btn.setEnabled(False)
        btn_layout.addWidget(self.sync_ts_btn)
        
        controls_layout.addLayout(btn_layout)
        
        self.ts_status_label = QLabel("Status: Disconnected")
        self.ts_status_label.setStyleSheet("color: #FF6B6B;")
        controls_layout.addWidget(self.ts_status_label)
        
        top_row.addWidget(controls_group)
        main_layout.addLayout(top_row)
        
        # Refresh Chains Button
        refresh_layout = QHBoxLayout()
        self.refresh_ts_chains_btn = QPushButton("Refresh Option Chains")
        self.refresh_ts_chains_btn.clicked.connect(self.refresh_ts_chains)
        self.refresh_ts_chains_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        refresh_layout.addWidget(self.refresh_ts_chains_btn)
        main_layout.addLayout(refresh_layout)
        
        # Option Chains Section (side by side)
        chains_layout = QHBoxLayout()
        
        # 0DTE Chain
        dte0_group = QGroupBox("0DTE Option Chain")
        dte0_layout = QVBoxLayout(dte0_group)
        
        self.ts_0dte_expiry_label = QLabel("Expiry: Not Set")
        dte0_layout.addWidget(self.ts_0dte_expiry_label)
        
        self.ts_0dte_table = QTableWidget()
        self.ts_0dte_table.setColumnCount(9)
        self.ts_0dte_table.setHorizontalHeaderLabels([
            "Call Delta", "Call Gamma", "Call Bid", "Call Ask", "Strike", 
            "Put Bid", "Put Ask", "Put Gamma", "Put Delta"
        ])
        self.ts_0dte_table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        header_0dte = self.ts_0dte_table.horizontalHeader()
        if header_0dte:
            header_0dte.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)  # Equal width columns
        self.ts_0dte_table.setAlternatingRowColors(False)
        self.ts_0dte_table.setStyleSheet("""
            QTableWidget {
                background-color: black;
                color: white;
                gridline-color: #333333;
            }
            QTableWidget::item:selected {
                background-color: #333333;
            }
        """)
        self.ts_0dte_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        dte0_layout.addWidget(self.ts_0dte_table)
        
        chains_layout.addWidget(dte0_group)
        
        # 1DTE Chain
        dte1_group = QGroupBox("1DTE Option Chain")
        dte1_layout = QVBoxLayout(dte1_group)
        
        self.ts_1dte_expiry_label = QLabel("Expiry: Not Set")
        dte1_layout.addWidget(self.ts_1dte_expiry_label)
        
        self.ts_1dte_table = QTableWidget()
        self.ts_1dte_table.setColumnCount(9)
        self.ts_1dte_table.setHorizontalHeaderLabels([
            "Call Delta", "Call Gamma", "Call Bid", "Call Ask", "Strike", 
            "Put Bid", "Put Ask", "Put Gamma", "Put Delta"
        ])
        self.ts_1dte_table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        header_1dte = self.ts_1dte_table.horizontalHeader()
        if header_1dte:
            header_1dte.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)  # Equal width columns
        self.ts_1dte_table.setAlternatingRowColors(False)
        self.ts_1dte_table.setStyleSheet("""
            QTableWidget {
                background-color: black;
                color: white;
                gridline-color: #333333;
            }
            QTableWidget::item:selected {
                background-color: #333333;
            }
        """)
        self.ts_1dte_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        dte1_layout.addWidget(self.ts_1dte_table)
        
        chains_layout.addWidget(dte1_group)
        main_layout.addLayout(chains_layout)
        
        # Middle section: Positions and Orders (side by side)
        pos_order_layout = QHBoxLayout()
        
        # TS Positions Table (left side)
        ts_positions_group = QGroupBox("Open Positions")
        ts_pos_layout = QVBoxLayout(ts_positions_group)
        
        self.ts_positions_table = QTableWidget()
        self.ts_positions_table.setColumnCount(11)
        self.ts_positions_table.setHorizontalHeaderLabels([
            "Contract", "Qty", "Entry", "Current", "P&L", "P&L %", "$ Cost Basis", "$ Mkt Value", "EntryTime", "TimeSpan", "Action"
        ])
        self.ts_positions_table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.ts_positions_table.setMaximumHeight(339)
        self.ts_positions_table.cellClicked.connect(self.on_ts_position_cell_clicked)
        self.ts_positions_table.setColumnWidth(0, 170)  # Contract column
        self.ts_positions_table.setStyleSheet("""
            QTableWidget::item { 
                height: 18px; 
            }
            QHeaderView::section { 
                height: 18px; 
            }
        """)
        ts_pos_layout.addWidget(self.ts_positions_table)
        
        # TS Orders Table (right side)
        ts_orders_group = QGroupBox("Active Orders")
        ts_orders_layout = QVBoxLayout(ts_orders_group)
        
        self.ts_orders_table = QTableWidget()
        self.ts_orders_table.setColumnCount(7)
        self.ts_orders_table.setHorizontalHeaderLabels([
            "Order ID", "Contract", "Action", "Qty", "Price", "Status", "Action"
        ])
        self.ts_orders_table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.ts_orders_table.setMaximumHeight(339)
        self.ts_orders_table.cellClicked.connect(self.on_ts_order_cell_clicked)
        self.ts_orders_table.setColumnWidth(1, 170)  # Contract column
        self.ts_orders_table.setStyleSheet("""
            QTableWidget::item { 
                height: 18px; 
            }
            QHeaderView::section { 
                height: 18px; 
            }
        """)
        ts_orders_layout.addWidget(self.ts_orders_table)
        
        pos_order_layout.addWidget(ts_positions_group)
        pos_order_layout.addWidget(ts_orders_group)
        main_layout.addLayout(pos_order_layout)
        
        # Bottom section: Signal History + Activity Log (side by side)
        bottom_layout = QHBoxLayout()
        
        # Signal History Table (left side)
        history_group = QGroupBox("Signal History")
        history_layout = QVBoxLayout(history_group)
        
        self.ts_signal_table = QTableWidget()
        self.ts_signal_table.setColumnCount(6)
        self.ts_signal_table.setHorizontalHeaderLabels([
            "Time", "Signal Type", "Action", "Contract", "Status", "Fill Price"
        ])
        v_header_signal = self.ts_signal_table.verticalHeader()
        if v_header_signal:
            v_header_signal.setVisible(False)  # Hide row numbers
        header_signal = self.ts_signal_table.horizontalHeader()
        if header_signal:
            header_signal.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)  # Equal width columns
        self.ts_signal_table.setAlternatingRowColors(True)
        self.ts_signal_table.setRowCount(0)
        history_layout.addWidget(self.ts_signal_table)
        
        bottom_layout.addWidget(history_group)
        
        # Activity Log (right side) - shows all GlobalDictionary messages
        activity_group = QGroupBox("Activity Log")
        activity_layout = QVBoxLayout(activity_group)
        
        self.ts_activity_log = QTextEdit()
        self.ts_activity_log.setReadOnly(True)
        # Note: QTextEdit doesn't have setMaximumBlockCount, we'll manage size in the handler
        self.ts_activity_log.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10px;
            }
        """)
        activity_layout.addWidget(self.ts_activity_log)
        
        bottom_layout.addWidget(activity_group)
        main_layout.addLayout(bottom_layout)
        
        return tab
    
    def create_option_contract(self, strike: float, right: str, symbol: str = "SPX", 
                              trading_class: str = "SPXW", expiry: Optional[str] = None) -> Contract:
        """
        Create an option contract with specified or current expiration.
        
        Args:
            strike: Strike price
            right: "C" for call or "P" for put
            symbol: Underlying symbol (default: "SPX")
            trading_class: Trading class (default: "SPXW" for SPX weeklies, "XSP" for XSP)
            expiry: Expiration date YYYYMMDD (default: use self.current_expiry)
        
        Returns:
            Contract object ready for IBKR API calls
        
        NOTE: For SPX weekly options (0DTE), MUST use tradingClass="SPXW"
        """
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "OPT"
        contract.currency = "USD"
        contract.exchange = "SMART"  # SMART routing works with proper tradingClass
        contract.tradingClass = trading_class  # "SPXW" for SPX weeklies, "XSP" for XSP
        contract.strike = strike
        contract.right = right  # "C" or "P"
        contract.lastTradeDateOrContractMonth = expiry if expiry else self.current_expiry
        contract.multiplier = "100"
        return contract
    
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
    
    def request_option_chain(self, force_center_strike=None):
        """
        Build and subscribe to option chain
        
        Args:
            force_center_strike: If provided, use this strike as the center instead of calculating from price.
                                This is used when recentering based on delta-detected ATM.
        """
        if self.connection_state != ConnectionState.CONNECTED:
            self.log_message("Cannot request option chain - not connected", "WARNING")
            return
        
        # Reset delta calibration flag ONLY for manual chain requests (not delta-based recenters)
        # This prevents oscillation between delta-based and ES-based recenters
        if force_center_strike is None:
            self.delta_calibration_done = False
            logger.debug("Manual chain request - resetting delta_calibration_done to allow initial calibration")
        else:
            logger.debug("Delta-based recenter - keeping delta_calibration_done to prevent ES recenter")
        
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
        
        # If force_center_strike is provided, use it directly (delta-based recenter)
        if force_center_strike is not None:
            reference_price = force_center_strike
            logger.info(f"🎯 RECENTERING on delta-detected ATM strike: ${reference_price:.2f}")
        # PRIORITY 1: Use actual underlying index price (XSP or SPX)
        # This is the CORRECT price for ATM strike calculation as it matches TWS
        elif (underlying_price := self.app_state.get('underlying_price', 0)) > 0:
            reference_price = underlying_price
            logger.info(f"Using actual {self.instrument['underlying_symbol']} index price ${reference_price:.2f} for ATM calculation")
        else:
            # FALLBACK: Use ES futures adjusted for cash offset (after-hours only)
            # WARNING: This gives approximate ATM and may not match TWS exactly during after-hours
            es_price = self.app_state['es_price']
            if es_price == 0:
                self.log_message("Waiting for price data (XSP index or ES futures)...", "INFO")
                QTimer.singleShot(2000, self.request_option_chain)
                return
            
            # Get ES price adjusted for cash offset
            adjusted_es_price = self.get_adjusted_es_price()
            if adjusted_es_price == 0:
                # Fallback to raw ES if adjustment fails
                adjusted_es_price = es_price / 10.0 if self.instrument['underlying_symbol'] == 'XSP' else es_price
            
            reference_price = adjusted_es_price
            
            # Log the adjustment being applied
            logger.warning(f"Using FALLBACK ES-derived price ${reference_price:.2f} (ES: {es_price:.2f}, offset: {self.es_to_cash_offset:+.2f})")
            logger.warning(f"ATM strike may not match TWS - {self.instrument['underlying_symbol']} index not available")
        
        strike_increment = self.instrument['strike_increment']
        center_strike = round(reference_price / strike_increment) * strike_increment
        
        # Track center strike for drift detection
        self.last_chain_center_strike = center_strike
        logger.info(f"Chain centered at strike {center_strike} (Reference: ${reference_price:.2f})")
        
        strikes = []
        current_strike = center_strike - (self.strikes_below * strike_increment)
        end_strike = center_strike + (self.strikes_above * strike_increment)
        
        while current_strike <= end_strike:
            strikes.append(current_strike)
            current_strike += strike_increment
        
        self.log_message(f"Creating option chain: {len(strikes)} strikes from {min(strikes)} to {max(strikes)}", "INFO")
        
        # Request live market data for options (type 1 = live, type 2 = frozen, type 3 = delayed, type 4 = delayed frozen)
        # SPX options require live data subscription
        self.ibkr_client.reqMarketDataType(1)
        logger.info("Set market data type to LIVE (1) for option chain")
        
        # Clear table
        self.option_table.setRowCount(0)
        self.option_table.setRowCount(len(strikes))
        
        # Subscribe to market data for each strike
        req_id = 100  # Start from 100 for option contracts
        new_req_ids = []  # Track new request IDs
        
        for row, strike in enumerate(strikes):
            # Create call contract using helper function and instrument configuration
            call_contract = self.create_option_contract(
                strike, "C", 
                self.instrument['options_symbol'], 
                self.instrument['options_trading_class']
            )
            
            # Log the contract details for debugging
            logger.info(
                f"Creating CALL contract: symbol={call_contract.symbol}, "
                f"strike={call_contract.strike}, right={call_contract.right}, "
                f"expiry={call_contract.lastTradeDateOrContractMonth}, "
                f"exchange={call_contract.exchange}, tradingClass={call_contract.tradingClass}, "
                f"multiplier={call_contract.multiplier}"
            )
            
            call_key = f"{self.instrument['options_symbol']}_{strike}_C_{self.current_expiry}"
            self.app_state['market_data_map'][req_id] = call_key
            self.ibkr_client.reqMktData(req_id, call_contract, "", False, False, [])
            logger.info(f"Requested market data for {call_key} with reqId={req_id}")
            new_req_ids.append(req_id)
            req_id += 1
            
            # Create put contract using helper function and instrument configuration
            put_contract = self.create_option_contract(
                strike, "P", 
                self.instrument['options_symbol'], 
                self.instrument['options_trading_class']
            )
            
            # Log the contract details for debugging
            logger.info(
                f"Creating PUT contract: symbol={put_contract.symbol}, "
                f"strike={put_contract.strike}, right={put_contract.right}, "
                f"expiry={put_contract.lastTradeDateOrContractMonth}, "
                f"exchange={put_contract.exchange}, tradingClass={put_contract.tradingClass}, "
                f"multiplier={put_contract.multiplier}"
            )
            
            put_key = f"{self.instrument['options_symbol']}_{strike}_P_{self.current_expiry}"
            self.app_state['market_data_map'][req_id] = put_key
            self.ibkr_client.reqMktData(req_id, put_contract, "", False, False, [])
            logger.info(f"Requested market data for {put_key} with reqId={req_id}")
            new_req_ids.append(req_id)
            req_id += 1
            
            # Set strike in table
            strike_item = QTableWidgetItem(f"{strike:.0f}")
            strike_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            strike_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            
            # Initial strike background based on price (will be updated by delta-based ATM)
            # Strikes above reference price = lighter blue (#2a4a6a)
            # Strikes below reference price = darker blue (#1a2a3a)
            if strike >= reference_price:
                strike_item.setBackground(QColor("#2a4a6a"))  # Above ATM: lighter blue
            else:
                strike_item.setBackground(QColor("#1a2a3a"))  # Below ATM: darker blue
            
            self.option_table.setItem(row, 10, strike_item)
        
        # Store active request IDs for future cleanup
        self.app_state['active_option_req_ids'] = new_req_ids
        self.log_message(f"Subscribed to {len(strikes) * 2} option contracts", "SUCCESS")
        
        # Clear recentering flags now that chain is loaded
        self.is_recentering_chain = False
        
        # IMPORTANT: Do NOT reset delta_calibration_done here!
        # If we're recentering based on delta-detected ATM (force_center_strike was used),
        # we want to KEEP delta_calibration_done = True to prevent ES-based recenter from running.
        # The calibration flag is only reset when user manually changes expiry/settings (new chain request).
        # This prevents oscillation: Delta recenter → New chain loads → Flag reset → ES recenter → Loop
        
        # Update recenter timestamp to give chain time to load and deltas to populate
        # before allowing initial calibration check (prevent immediate re-recenter)
        import time
        self.last_recenter_time = time.time()
    
    def update_option_chain_cell(self, contract_key: str):
        """Update a single option chain row with market data"""
        try:
            # Parse contract_key format: "{SYMBOL}_{STRIKE}_{RIGHT}_{EXPIRY}" (e.g., "SPX_6740_C_20251024" or "XSP_673_P_20251024")
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
                        items = [
                            QTableWidgetItem(f"{data.get('iv', 0):.2f}"),
                            QTableWidgetItem(f"{data.get('delta', 0):.3f}"),
                            QTableWidgetItem(f"{data.get('theta', 0):.2f}"),
                            QTableWidgetItem(f"{data.get('vega', 0):.2f}"),
                            QTableWidgetItem(f"{data.get('gamma', 0):.4f}"),
                            QTableWidgetItem(f"{int(data.get('volume', 0))}")
                        ]
                        for col, item in enumerate(items):
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            self.option_table.setItem(row, col, item)
                        
                        # Calculate change %
                        last = data.get('last', 0)
                        prev = data.get('prev_close', 0)
                        change_pct = ((last - prev) / prev * 100) if prev > 0 else 0
                        change_item = QTableWidgetItem(f"{change_pct:.1f}%")
                        change_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        change_item.setForeground(QColor("#00ff00" if change_pct >= 0 else "#ff0000"))
                        self.option_table.setItem(row, 6, change_item)
                        
                        price_items = [
                            (7, f"{last:.2f}"),
                            (8, f"{data.get('bid', 0):.2f}"),
                            (9, f"{data.get('ask', 0):.2f}")
                        ]
                        for col, text in price_items:
                            item = QTableWidgetItem(text)
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            self.option_table.setItem(row, col, item)
                    
                    elif right == 'P':  # Put options (right side)
                        # Columns: Bid, Ask, Last, CHANGE %, Volume, Gamma, Vega, Theta, Delta, Imp Vol
                        price_items = [
                            (11, f"{data.get('bid', 0):.2f}"),
                            (12, f"{data.get('ask', 0):.2f}"),
                            (13, f"{data.get('last', 0):.2f}")
                        ]
                        for col, text in price_items:
                            item = QTableWidgetItem(text)
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            self.option_table.setItem(row, col, item)
                        
                        # Calculate change %
                        last = data.get('last', 0)
                        prev = data.get('prev_close', 0)
                        change_pct = ((last - prev) / prev * 100) if prev > 0 else 0
                        change_item = QTableWidgetItem(f"{change_pct:.1f}%")
                        change_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        change_item.setForeground(QColor("#00ff00" if change_pct >= 0 else "#ff0000"))
                        self.option_table.setItem(row, 14, change_item)
                        
                        # Handle None values gracefully
                        volume = data.get('volume') or 0
                        gamma = data.get('gamma') or 0
                        vega = data.get('vega') or 0
                        theta = data.get('theta') or 0
                        delta = data.get('delta') or 0
                        iv = data.get('iv') or 0
                        
                        greeks_items = [
                            (15, f"{int(volume)}"),
                            (16, f"{gamma:.4f}"),
                            (17, f"{vega:.2f}"),
                            (18, f"{theta:.2f}"),
                            (19, f"{delta:.3f}"),
                            (20, f"{iv:.2f}")
                        ]
                        for col, text in greeks_items:
                            item = QTableWidgetItem(text)
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            self.option_table.setItem(row, col, item)
                    
                    break
        
        except Exception as e:
            logger.debug(f"Error updating option chain cell for {contract_key}: {e}")
    
    def update_strike_backgrounds_by_delta(self):
        """
        Update strike row backgrounds based on delta-based ATM identification.
        
        This method:
        1. Finds the true ATM strike using 0.5 delta
        2. Highlights the ATM strike row with gold/yellow
        3. Colors strikes above ATM lighter blue
        4. Colors strikes below ATM darker blue
        5. Updates the ATM strike label in the header
        6. Checks for drift from the last chain center and auto-recenters if needed
        
        Note: last_chain_center_strike is updated by request_option_chain() when the chain
        is loaded/reloaded. This method compares current ATM to that center point.
        """
        atm_strike = self.find_atm_strike_by_delta()
        
        if atm_strike == 0:
            return  # No ATM found yet, keep initial coloring
        
        # Update ATM strike label in header
        self.atm_strike_label.setText(f"ATM: {atm_strike:.0f}")
        self.atm_strike_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #FFD700;")
        
        # Check for drift and auto-recenter if needed
        # This compares ATM to last_chain_center_strike (set in request_option_chain)
        self.check_chain_drift_and_recenter(atm_strike)
        
        # Update all strike backgrounds based on delta-identified ATM
        for row in range(self.option_table.rowCount()):
            strike_item = self.option_table.item(row, 10)  # Strike column
            if not strike_item:
                continue
            
            try:
                strike = float(strike_item.text())
                
                if abs(strike - atm_strike) < 0.01:  # ATM strike (within rounding)
                    # Highlight ATM strike with gold/yellow
                    strike_item.setBackground(QColor("#FFD700"))  # Gold
                    strike_item.setForeground(QColor("#000000"))  # Black text
                elif strike > atm_strike:
                    # Above ATM: lighter blue
                    strike_item.setBackground(QColor("#2a4a6a"))
                    strike_item.setForeground(QColor("#ffffff"))  # White text
                else:
                    # Below ATM: darker blue
                    strike_item.setBackground(QColor("#1a2a3a"))
                    strike_item.setForeground(QColor("#ffffff"))  # White text
            
            except (ValueError, AttributeError):
                continue
    
    def check_chain_drift_and_recenter(self, atm_strike: float):
        """
        Check if the delta-based ATM strike has drifted from the chain center.
        Auto-recenter the chain if drift exceeds the configured threshold.
        
        Special handling for initial calibration:
        - On first ATM detection after chain load, if ATM is off-center by 2+ strikes,
          immediately recenter (don't wait for full drift threshold)
        - This handles large overnight moves where ES offset approximation is inaccurate
        
        Args:
            atm_strike: The current ATM strike identified by 0.5 delta
        """
        if self.last_chain_center_strike == 0:
            return  # First time setting ATM, no drift yet
        
        if self.connection_state != ConnectionState.CONNECTED:
            return  # Can't recenter if not connected
        
        # Prevent recentering loops
        if self.is_recentering_chain:
            return  # Already recentering, don't trigger again
        
        # Throttle recentering - don't recenter too frequently
        # During initial calibration: Wait 5 seconds after chain load for deltas to populate
        # After calibration: Wait 10 seconds between recenters for normal drift
        import time
        current_time = time.time()
        min_recenter_interval = 5 if not self.delta_calibration_done else 10
        if current_time - self.last_recenter_time < min_recenter_interval:
            return  # Too soon since last recenter
        
        # Calculate drift in number of strikes
        strike_increment = self.instrument['strike_increment']
        drift_strikes = abs(atm_strike - self.last_chain_center_strike) / strike_increment
        
        # Check if this is initial calibration (first ATM detection after chain load)
        # Initial calibration: If we just loaded chain and ATM is off by 2+ strikes, recenter immediately
        # This handles cases where ES offset approximation is significantly wrong (e.g., big overnight moves)
        is_initial_calibration = not self.delta_calibration_done
        initial_calibration_threshold = 2  # Recenter immediately if off by 2+ strikes on initial detection
        
        should_recenter = False
        reason = ""
        
        if is_initial_calibration and drift_strikes >= initial_calibration_threshold:
            # Initial calibration: ATM detection shows chain is off-center
            should_recenter = True
            reason = "INITIAL CALIBRATION"
            logger.info(
                f"🎯 Initial ATM calibration: True ATM at {atm_strike:.0f}, "
                f"chain centered at {self.last_chain_center_strike:.0f} "
                f"({drift_strikes:.1f} strikes off) - RECENTERING IMMEDIATELY"
            )
            # Mark calibration as done (will be reset on next chain load)
            self.delta_calibration_done = True
        elif drift_strikes >= self.chain_drift_threshold:
            # Normal drift: ATM moved beyond threshold
            should_recenter = True
            reason = "DRIFT THRESHOLD EXCEEDED"
            logger.info(
                f"🎯 ATM drifted {drift_strikes:.0f} strikes from center "
                f"(ATM: {atm_strike:.0f}, Center: {self.last_chain_center_strike:.0f}, "
                f"Threshold: {self.chain_drift_threshold} strikes) - AUTO-RECENTERING"
            )
        else:
            # If initial calibration check passed (drift < 2 strikes), mark it as done
            if is_initial_calibration:
                self.delta_calibration_done = True
                logger.info(
                    f"✅ Initial ATM calibration complete: ATM at {atm_strike:.0f}, "
                    f"chain centered at {self.last_chain_center_strike:.0f} "
                    f"({drift_strikes:.1f} strikes off - within tolerance)"
                )
        
        if should_recenter:
            # Set flag and timestamp to prevent loops
            self.is_recentering_chain = True
            self.last_recenter_time = current_time
            
            # Request new chain centered on current ATM (force center to detected ATM strike)
            self.request_option_chain(force_center_strike=atm_strike)
        else:
            # Log debug info about current drift (only after initial calibration is done)
            if self.delta_calibration_done:
                logger.debug(
                    f"ATM drift: {drift_strikes:.1f} strikes "
                    f"(ATM: {atm_strike:.0f}, Center: {self.last_chain_center_strike:.0f}, "
                    f"Threshold: {self.chain_drift_threshold})"
                )
    
    # ========== TradeStation Chain ATM Detection and Coloring Methods ==========
    
    def find_ts_atm_strike_by_delta(self, contract_type: str) -> float:
        """
        Find ATM strike for TS chains using delta closest to 0.5 (same logic as main chain).
        
        Args:
            contract_type: "0DTE" or "1DTE"
            
        Returns:
            float: The ATM strike price, or 0 if no deltas available
        """
        expiry = self.ts_0dte_expiry if contract_type == "0DTE" else self.ts_1dte_expiry
        if not expiry:
            return 0
        
        min_call_diff = float('inf')
        min_put_diff = float('inf')
        atm_call_strike = 0
        atm_put_strike = 0
        
        # Track all strikes with deltas for debugging
        call_deltas = []
        put_deltas = []
        
        # Search through market data for this expiry
        for contract_key, data in self.market_data.items():
            if f"_{expiry}" not in contract_key:
                continue
            if '_C_' not in contract_key and '_P_' not in contract_key:
                continue
            
            delta = data.get('delta', None)
            if delta is None or delta == 0:
                continue
            
            try:
                parts = contract_key.split('_')
                if len(parts) != 4:
                    continue
                strike = float(parts[1])
                
                if '_C_' in contract_key:
                    call_deltas.append((strike, delta))
                    if 0 < delta < 1:
                        diff = abs(delta - 0.5)
                        if diff < min_call_diff:
                            min_call_diff = diff
                            atm_call_strike = strike
                
                elif '_P_' in contract_key:
                    put_deltas.append((strike, abs(delta)))
                    if -1 < delta < 0:
                        diff = abs(abs(delta) - 0.5)
                        if diff < min_put_diff:
                            min_put_diff = diff
                            atm_put_strike = strike
            
            except (ValueError, IndexError):
                continue
        
        # Prefer call-based ATM
        if atm_call_strike > 0:
            logger.debug(f"[TS {contract_type}] ATM strike by CALL delta: {atm_call_strike:.0f} (delta: {0.5-min_call_diff:.3f})")
            return atm_call_strike
        elif atm_put_strike > 0:
            logger.debug(f"[TS {contract_type}] ATM strike by PUT delta: {atm_put_strike:.0f} (delta: {0.5-min_put_diff:.3f})")
            return atm_put_strike
        else:
            return 0
    
    def update_ts_strike_backgrounds_by_delta(self, contract_type: str):
        """
        Update TS chain strike backgrounds based on delta-identified ATM.
        Colors: ATM=gold/yellow, Above ATM=lighter blue, Below ATM=darker blue
        Also updates ATM label and checks for drift to trigger auto-recentering.
        
        Args:
            contract_type: "0DTE" or "1DTE"
        """
        atm_strike = self.find_ts_atm_strike_by_delta(contract_type)
        
        if atm_strike == 0:
            return  # No ATM found yet
        
        logger.debug(f"[TS {contract_type}] 🎨 Coloring strikes around ATM: {atm_strike:.0f}")
        
        # Select appropriate table and label
        if contract_type == "0DTE":
            table = self.ts_0dte_table
            label = self.ts_0dte_expiry_label
            current_expiry = self.ts_0dte_expiry
        else:
            table = self.ts_1dte_table
            label = self.ts_1dte_expiry_label
            current_expiry = self.ts_1dte_expiry
        
        # Update ATM label
        label.setText(f"Expiry: {current_expiry} | ATM: {atm_strike:.0f}")
        label.setStyleSheet("font-weight: bold; color: #FFD700;")
        
        # Check for drift and auto-recenter
        self.check_ts_chain_drift_and_recenter(contract_type, atm_strike)
        
        # Update strike column backgrounds
        for row in range(table.rowCount()):
            strike_item = table.item(row, 4)  # Strike is column 4
            if not strike_item:
                continue
            
            try:
                strike = float(strike_item.text())
                
                if abs(strike - atm_strike) < 0.01:  # ATM strike
                    strike_item.setBackground(QColor("#FFD700"))  # Gold
                    strike_item.setForeground(QColor("#000000"))  # Black text
                elif strike > atm_strike:
                    # Above ATM: lighter blue
                    strike_item.setBackground(QColor("#2a4a6a"))
                    strike_item.setForeground(QColor("#ffffff"))
                else:
                    # Below ATM: darker blue
                    strike_item.setBackground(QColor("#1a2a3a"))
                    strike_item.setForeground(QColor("#ffffff"))
            
            except (ValueError, AttributeError) as e:
                continue
    
    def check_ts_chain_drift_and_recenter(self, contract_type: str, atm_strike: float):
        """
        Check if TS chain ATM has drifted from center and auto-recenter if needed.
        Uses ts_chain_drift_threshold from settings.
        
        Args:
            contract_type: "0DTE" or "1DTE"
            atm_strike: Current ATM strike from delta detection
        """
        # Get appropriate tracking variables
        if contract_type == "0DTE":
            center_strike = self.ts_0dte_center_strike
            calibration_done = self.ts_0dte_delta_calibration_done
            last_recenter_time = self.ts_0dte_last_recenter_time
            is_recentering = self.ts_0dte_is_recentering
        else:
            center_strike = self.ts_1dte_center_strike
            calibration_done = self.ts_1dte_delta_calibration_done
            last_recenter_time = self.ts_1dte_last_recenter_time
            is_recentering = self.ts_1dte_is_recentering
        
        if center_strike == 0:
            return  # First ATM detection
        
        if self.connection_state != ConnectionState.CONNECTED:
            return
        
        if is_recentering:
            return  # Already recentering
        
        # Throttle recentering
        import time
        current_time = time.time()
        min_recenter_interval = 5 if not calibration_done else 10
        if current_time - last_recenter_time < min_recenter_interval:
            return
        
        # Calculate drift
        strike_increment = self.instrument['strike_increment']
        drift_strikes = abs(atm_strike - center_strike) / strike_increment
        
        # Check for initial calibration or normal drift
        is_initial_calibration = not calibration_done
        initial_calibration_threshold = 2
        
        should_recenter = False
        reason = ""
        
        if is_initial_calibration and drift_strikes >= initial_calibration_threshold:
            should_recenter = True
            reason = "INITIAL CALIBRATION"
            logger.info(
                f"🎯 [TS {contract_type}] Initial ATM calibration: ATM at {atm_strike:.0f}, "
                f"chain centered at {center_strike:.0f} ({drift_strikes:.1f} strikes off) - RECENTERING"
            )
            # Mark calibration done
            if contract_type == "0DTE":
                self.ts_0dte_delta_calibration_done = True
            else:
                self.ts_1dte_delta_calibration_done = True
        elif drift_strikes >= self.ts_chain_drift_threshold:
            should_recenter = True
            reason = "DRIFT THRESHOLD EXCEEDED"
            logger.info(
                f"🎯 [TS {contract_type}] ATM drifted {drift_strikes:.0f} strikes "
                f"(ATM: {atm_strike:.0f}, Center: {center_strike:.0f}, "
                f"Threshold: {self.ts_chain_drift_threshold}) - AUTO-RECENTERING"
            )
        else:
            # Mark calibration done if within tolerance
            if is_initial_calibration:
                if contract_type == "0DTE":
                    self.ts_0dte_delta_calibration_done = True
                else:
                    self.ts_1dte_delta_calibration_done = True
                logger.info(
                    f"✅ [TS {contract_type}] Initial calibration complete: ATM at {atm_strike:.0f}, "
                    f"center at {center_strike:.0f} ({drift_strikes:.1f} strikes off - OK)"
                )
        
        if should_recenter:
            # Set flags
            if contract_type == "0DTE":
                self.ts_0dte_is_recentering = True
                self.ts_0dte_last_recenter_time = current_time
            else:
                self.ts_1dte_is_recentering = True
                self.ts_1dte_last_recenter_time = current_time
            
            # Request new chain centered on ATM
            self.request_ts_chain_forced_center(contract_type, atm_strike)
        else:
            if calibration_done:
                logger.debug(
                    f"[TS {contract_type}] Drift: {drift_strikes:.1f} strikes "
                    f"(ATM: {atm_strike:.0f}, Center: {center_strike:.0f}, Threshold: {self.ts_chain_drift_threshold})"
                )
    
    # ========== End TS Chain ATM Methods ==========
    
    def on_option_cell_clicked(self, row: int, col: int):
        """Handle option chain cell click - with Ctrl+click for quick trading"""
        try:
            logger.info(f"Cell clicked: row={row}, col={col}")
            
            # Get strike from row
            strike_item = self.option_table.item(row, 10)
            if not strike_item:
                logger.warning(f"No strike item at row {row}, col 10")
                return
            
            strike = float(strike_item.text())
            logger.info(f"Strike: {strike}")
            
            # Check if Ctrl key is held down for quick trading
            modifiers = QApplication.keyboardModifiers()
            ctrl_held = modifiers & Qt.KeyboardModifier.ControlModifier
            
            # Determine if call or put was clicked
            if col < 10:  # Call side
                contract_key = f"{self.instrument['options_symbol']}_{strike}_C_{self.current_expiry}"
                
                # Quick trade with Ctrl+Click
                if ctrl_held:
                    if col == 8:  # Bid column - BUY at bid
                        self.log_message(f"🚀 QUICK BUY CALL (Ctrl+Click): {contract_key} @ bid", "SUCCESS")
                        bid_price = self.market_data.get(contract_key, {}).get('bid', 0)
                        if bid_price > 0:
                            quantity = self.trade_qty_spin.value()
                            self.place_order(contract_key, "BUY", quantity, bid_price, enable_chasing=True)
                        else:
                            self.log_message("Cannot trade - no bid price", "WARNING")
                    elif col == 9:  # Ask column - SELL at ask
                        self.log_message(f"🚀 QUICK SELL CALL (Ctrl+Click): {contract_key} @ ask", "SUCCESS")
                        ask_price = self.market_data.get(contract_key, {}).get('ask', 0)
                        if ask_price > 0:
                            quantity = self.trade_qty_spin.value()
                            self.place_order(contract_key, "SELL", quantity, ask_price, enable_chasing=True)
                        else:
                            self.log_message("Cannot trade - no ask price", "WARNING")
                    else:
                        # Regular chart request for other columns
                        self.log_message(f"Selected CALL: Strike {strike}", "INFO")
                        self.request_option_chart_data(contract_key, "call")
                else:
                    # Regular chart request without Ctrl
                    self.log_message(f"Selected CALL: Strike {strike}", "INFO")
                    self.request_option_chart_data(contract_key, "call")
                    
            elif col > 10:  # Put side
                contract_key = f"{self.instrument['options_symbol']}_{strike}_P_{self.current_expiry}"
                
                # Quick trade with Ctrl+Click
                if ctrl_held:
                    if col == 11:  # Bid column - BUY at bid
                        self.log_message(f"🚀 QUICK BUY PUT (Ctrl+Click): {contract_key} @ bid", "SUCCESS")
                        bid_price = self.market_data.get(contract_key, {}).get('bid', 0)
                        if bid_price > 0:
                            quantity = self.trade_qty_spin.value()
                            self.place_order(contract_key, "BUY", quantity, bid_price, enable_chasing=True)
                        else:
                            self.log_message("Cannot trade - no bid price", "WARNING")
                    elif col == 12:  # Ask column - SELL at ask
                        self.log_message(f"🚀 QUICK SELL PUT (Ctrl+Click): {contract_key} @ ask", "SUCCESS")
                        ask_price = self.market_data.get(contract_key, {}).get('ask', 0)
                        if ask_price > 0:
                            quantity = self.trade_qty_spin.value()
                            self.place_order(contract_key, "SELL", quantity, ask_price, enable_chasing=True)
                        else:
                            self.log_message("Cannot trade - no ask price", "WARNING")
                    else:
                        # Regular chart request for other columns
                        self.log_message(f"Selected PUT: Strike {strike}", "INFO")
                        self.request_option_chart_data(contract_key, "put")
                else:
                    # Regular chart request without Ctrl
                    self.log_message(f"Selected PUT: Strike {strike}", "INFO")
                    self.request_option_chart_data(contract_key, "put")
            else:
                logger.info(f"Clicked on strike column (col 10), ignoring")
                
        except Exception as e:
            logger.error(f"Error in on_option_cell_clicked: {e}", exc_info=True)
            self.log_message(f"Error handling cell click: {e}", "ERROR")
    
    # ========================================================================
    # HELPER METHODS - Historical Data & Orders
    # ========================================================================
    
    def place_order(self, contract_key: str, action: str, quantity: int, 
                   limit_price: float = 0, enable_chasing: bool = False) -> Optional[int]:
        """
        Universal order placement function with comprehensive validation and debugging
        
        Args:
            contract_key: Contract identifier format "{SYMBOL}_{STRIKE}_{RIGHT}_{EXPIRY}" (e.g., "SPX_6740_C_20251024" or "XSP_673_P_20251024")
            action: "BUY" or "SELL"
            quantity: Number of contracts
            limit_price: Limit price (0 = market order)
            enable_chasing: Enable mid-price chasing for manual orders
        
        Returns:
            order_id or None if failed
        """
        try:
            # STEP 1: Connection validation
            if self.connection_state != ConnectionState.CONNECTED:
                self.log_message("✗ Cannot place order: Not connected to IBKR", "ERROR")
                logger.error("Order rejected - not connected")
                return None
            
            if not self.app_state.get('data_server_ok'):
                self.log_message("✗ Cannot place order: Data server not ready", "ERROR")
                logger.error("Order rejected - data server not ready")
                return None
            
            # STEP 2: Parse contract key and create contract
            parts = contract_key.split('_')
            if len(parts) != 4:
                self.log_message(f"✗ Invalid contract key: {contract_key}", "ERROR")
                logger.error(f"Order rejected - invalid contract key: {contract_key}")
                return None
            
            symbol, strike_str, right, expiry = parts
            trading_class = "SPXW" if symbol == "SPX" else "XSP"
            
            logger.info(f"Parsing contract_key: {contract_key}")
            logger.info(f"  Symbol: {symbol}, Strike: {strike_str}, Right: {right}, Expiry: {expiry}")
            logger.info(f"  Trading Class: {trading_class}")
            
            # Create contract with full validation
            contract = self.create_option_contract(
                strike=float(strike_str),
                right=right,
                symbol=symbol,
                trading_class=trading_class,
                expiry=expiry
            )
            
            # STEP 3: Contract validation
            if not contract or not contract.symbol or not contract.secType:
                self.log_message("✗ Invalid contract - missing required fields", "ERROR")
                logger.error("Order rejected - invalid contract")
                return None
            
            if not contract.lastTradeDateOrContractMonth:
                self.log_message("✗ Invalid contract - missing expiration", "ERROR")
                logger.error("Order rejected - missing expiration")
                return None
            
            if not contract.strike or contract.strike <= 0:
                self.log_message("✗ Invalid contract - invalid strike", "ERROR")
                logger.error("Order rejected - invalid strike")
                return None
            
            if contract.right not in ["C", "P"]:
                self.log_message("✗ Invalid contract - invalid right (must be C or P)", "ERROR")
                logger.error("Order rejected - invalid right")
                return None
            
            # STEP 4: Create order with proper defaults
            order = Order()
            order.action = action
            order.totalQuantity = quantity
            order.orderType = "MKT" if limit_price == 0 else "LMT"
            
            if limit_price > 0:
                order.lmtPrice = limit_price
                order.auxPrice = 0  # CRITICAL: Clear auxPrice for LMT orders to prevent silent rejections
            
            order.tif = "DAY"
            order.transmit = True
            order.outsideRth = True  # CRITICAL: Enable "Fill outside RTH" for after-hours trading
            order.eTradeOnly = False  # CRITICAL: Disable eTradeOnly to prevent TWS rejection (error 10268)
            order.firmQuoteOnly = False  # CRITICAL: Disable firmQuoteOnly for better fill rates
            
            # Set account if available
            if self.app_state.get('account'):
                order.account = self.app_state['account']
            
            # CRITICAL: Validate order before submitting
            if order.totalQuantity <= 0:
                self.log_message(f"✗ Invalid quantity: {order.totalQuantity}", "ERROR")
                logger.error(f"Order rejected - invalid quantity: {order.totalQuantity}")
                return None
            
            if order.orderType == "LMT" and order.lmtPrice <= 0:
                self.log_message(f"✗ Invalid limit price: {order.lmtPrice}", "ERROR")
                logger.error(f"Order rejected - invalid limit price: {order.lmtPrice}")
                return None
            
            # Get order ID
            order_id = self.app_state.get('next_order_id', 1)
            self.app_state['next_order_id'] = order_id + 1
            
            # STEP 5: Detailed pre-order logging
            logger.info("="*70)
            logger.info(f"PLACING ORDER #{order_id}")
            logger.info("="*70)
            logger.info("CONTRACT DETAILS:")
            logger.info(f"  Symbol: {contract.symbol}")
            logger.info(f"  Strike: {contract.strike}")
            logger.info(f"  Right: {contract.right}")
            logger.info(f"  Expiry: {contract.lastTradeDateOrContractMonth}")
            logger.info(f"  Exchange: {contract.exchange}")
            logger.info(f"  TradingClass: {contract.tradingClass}")
            logger.info(f"  Multiplier: {contract.multiplier}")
            logger.info(f"  SecType: {contract.secType}")
            logger.info("ORDER DETAILS:")
            logger.info(f"  Order ID: {order_id}")
            logger.info(f"  Action: {order.action}")
            logger.info(f"  Quantity: {order.totalQuantity}")
            logger.info(f"  Order Type: {order.orderType}")
            if limit_price > 0:
                logger.info(f"  Limit Price: ${order.lmtPrice:.2f}")
                logger.info(f"  AuxPrice: {order.auxPrice} (must be 0 for LMT)")
            logger.info(f"  TIF: {order.tif}")
            logger.info(f"  Outside RTH: {order.outsideRth} (enables after-hours trading)")
            logger.info(f"  Account: {order.account if order.account else 'None'}")
            logger.info(f"  Enable Chasing: {enable_chasing}")
            logger.info("="*70)
            
            self.log_message(
                f"=== PLACING ORDER #{order_id} ===\n"
                f"Contract: {symbol} {strike_str}{right} {expiry}\n"
                f"Order: {action} {quantity} @ {'MKT' if limit_price == 0 else f'${limit_price:.2f}'}\n"
                f"TradingClass: {contract.tradingClass}",
                "INFO"
            )
            
            # STEP 6: Place order via IBKR API FIRST (before tracking)
            try:
                logger.info(f"Calling ibkr_client.placeOrder({order_id}, contract, order)...")
                self.ibkr_client.placeOrder(order_id, contract, order)
                logger.info(f"✓ placeOrder() API call completed for order #{order_id}")
                self.log_message(f"✓ Order #{order_id} sent to TWS successfully", "SUCCESS")
                
            except Exception as e:
                self.log_message(f"✗ EXCEPTION during placeOrder(): {e}", "ERROR")
                logger.error(f"placeOrder() exception: {e}", exc_info=True)
                return None
            
            # STEP 7: Track order ONLY AFTER successful placeOrder() call
            self.pending_orders[order_id] = {
                'contract_key': contract_key,
                'action': action,
                'quantity': quantity,
                'price': limit_price,
                'status': 'Submitted',
                'filled': 0
            }
            
            # Track for chasing if enabled
            if enable_chasing:
                self.chasing_orders[order_id] = {
                    'contract_key': contract_key,
                    'contract': contract,
                    'action': action,
                    'quantity': quantity,
                    'initial_mid': limit_price,
                    'last_mid': limit_price,
                    'last_price': limit_price,  # Track actual order price (different from mid during "give in")
                    'give_in_count': 0,  # Number of times we've given in (accumulates)
                    'attempts': 1,
                    'timestamp': datetime.now(),  # Reset every time price updates (for 10-second "give in" timer)
                    'order': order
                }
            
            # STEP 8: Update UI
            self.update_orders_display()
            self.update_ts_orders_display()
            
            # STEP 9: Start mid-price chasing if enabled
            if enable_chasing:
                # Start timer if not already running
                if not hasattr(self, '_chasing_timer_running') or not self._chasing_timer_running:
                    self._chasing_timer_running = True
                    QTimer.singleShot(1000, self.update_orders)
            
            return order_id
            
        except Exception as e:
            self.log_message(f"Error in place_order: {e}", "ERROR")
            logger.error(f"place_order() error: {e}", exc_info=True)
            return None
    
    def place_manual_order(self, contract_key: str, action: str, quantity: int, price: float = 0):
        """Place a manual order - wrapper for backward compatibility"""
        # Use new place_order method with chasing enabled for manual orders
        self.place_order(contract_key, action, quantity, price, enable_chasing=True)
    
    # ========================================================================
    # MID-PRICE CHASING SYSTEM (Item 3)
    # ========================================================================
    
    def round_to_option_tick(self, price: float) -> float:
        """
        Round price to options tick size based on current trading instrument
        
        Uses tick sizes from INSTRUMENT_CONFIG:
        - SPX: Prices >= $3.00: $0.10, < $3.00: $0.05
        - XSP: All prices: $0.05
        
        Per CBOE options rules and IBKR requirements
        """
        if price >= 3.00:
            # Use above-$3 tick size from instrument config
            tick = self.instrument['tick_size_above_3']
            return round(price / tick) * tick
        else:
            # Use below-$3 tick size from instrument config
            tick = self.instrument['tick_size_below_3']
            return round(price / tick) * tick
    
    def calculate_mid_price(self, contract_key: str) -> float:
        """
        Calculate mid-price from current bid/ask with proper rounding
        Returns 0 if no valid market data available
        """
        if contract_key not in self.market_data:
            return 0.0
        
        data = self.market_data[contract_key]
        bid = data.get('bid', 0)
        ask = data.get('ask', 0)
        
        if bid <= 0 or ask <= 0:
            return 0.0
        
        mid = (bid + ask) / 2.0
        return self.round_to_option_tick(mid)
    
    def find_option_by_max_risk(self, option_type: str, max_risk_dollars: float) -> tuple[str, float] | None:
        """
        Find option closest to max risk without exceeding it
        
        Args:
            option_type: "C" for calls, "P" for puts
            max_risk_dollars: Maximum risk in dollars (e.g., 500 for $5.00 per contract)
        
        Returns:
            Tuple of (contract_key, ask_price) or None if not found
        """
        try:
            # Convert max risk to per-contract price ($500 = $5.00)
            max_price = max_risk_dollars / 100.0
            
            best_option = None
            best_price = 0.0
            best_contract_key = None
            
            logger.info(f"Scanning for {option_type} option with ask ≤ ${max_price:.2f}...")
            
            for contract_key, data in self.market_data.items():
                # Check if this is the right option type and expiry
                if f'_{option_type}_' not in contract_key:
                    continue
                
                if self.current_expiry not in contract_key:
                    continue
                
                ask = data.get('ask', 0)
                
                # Must have valid ask price
                if ask <= 0 or ask > max_price:
                    continue
                
                # Find the option closest to max price (maximum value without exceeding)
                if ask > best_price:
                    best_price = ask
                    best_contract_key = contract_key
            
            if best_contract_key:
                logger.info(
                    f"✓ Found {option_type} option: {best_contract_key} @ ${best_price:.2f} "
                    f"(Risk: ${best_price * 100:.2f})"
                )
                return (best_contract_key, best_price)
            else:
                logger.warning(f"✗ No {option_type} options found with ask ≤ ${max_price:.2f}")
                return None
                
        except Exception as e:
            logger.error(f"Error in find_option_by_max_risk: {e}", exc_info=True)
            return None
    
    def find_option_by_delta(self, option_type: str, target_delta: float) -> tuple[str, float, float] | None:
        """
        Find option contract closest to target delta
        
        Args:
            option_type: "C" for call or "P" for put
            target_delta: Target delta value (0-100, e.g., 30 for 30 delta)
        
        Returns:
            tuple: (contract_key, ask_price, actual_delta) or None
        """
        try:
            if not self.market_data:
                logger.warning("No market data available")
                return None
            
            # Convert target delta to decimal (30 -> 0.30)
            target_delta_decimal = abs(target_delta / 100.0)
            
            best_delta_diff = float('inf')
            best_option = None
            best_contract_key = None
            best_price = 0
            best_delta = 0
            
            # Scan all options in market_data for current expiry
            for contract_key, data in self.market_data.items():
                # Skip if wrong option type
                if f'_{option_type}_' not in contract_key:
                    continue
                
                # Skip if wrong expiry
                if self.current_expiry not in contract_key:
                    continue
                
                # Must have valid greeks
                delta = data.get('delta')
                if delta is None or delta == 0:
                    continue
                
                # For puts, delta is negative - use absolute value
                abs_delta = abs(delta)
                
                # Find closest to target delta
                delta_diff = abs(abs_delta - target_delta_decimal)
                
                if delta_diff < best_delta_diff:
                    ask = data.get('ask', 0)
                    if ask > 0:  # Must have valid ask price
                        best_delta_diff = delta_diff
                        best_contract_key = contract_key
                        best_price = ask
                        best_delta = abs_delta * 100  # Convert back to 0-100 scale
            
            if best_contract_key:
                logger.info(
                    f"✓ Found {option_type} option: {best_contract_key} @ ${best_price:.2f} "
                    f"(Delta: {best_delta:.1f}, Target: {target_delta:.1f})"
                )
                return (best_contract_key, best_price, best_delta)
            else:
                logger.warning(
                    f"✗ No {option_type} options found with valid delta near {target_delta}"
                )
                return None
        except Exception as e:
            logger.error(f"Error in find_option_by_delta: {e}", exc_info=True)
            return None
    
    def update_orders(self):
        """
        Monitor all orders with intelligent mid-price chasing and "give in" logic
        
        Runs every 1 second to check if:
        1. Order is still open (not filled/cancelled)
        2. Mid-price has moved significantly (≥$0.05) → recalculate: current_mid ± X_ticks
        3. Every N seconds without fill → increment X_ticks, recalculate: current_mid ± X_ticks
        
        "Give in" logic: Price is ALWAYS current_mid ± X_ticks
        - X_ticks starts at 0 (initial order at pure mid)
        - After 10 sec: X_ticks = 1 → price = mid ± (1 * tick_size)
        - After 20 sec: X_ticks = 2 → price = mid ± (2 * tick_size)
        - After 30 sec: X_ticks = 3 → price = mid ± (3 * tick_size)
        - For BUY: price = mid + X_ticks (creeping toward ask)
        - For SELL: price = mid - X_ticks (creeping toward bid)
        - Uses SPX tick size rules (≥$3.00→$0.10, <$3.00→$0.05)
        """
        if not self.chasing_orders:
            # No orders to monitor - stop timer
            if hasattr(self, '_chasing_timer_running'):
                self._chasing_timer_running = False
            return
        
        orders_to_remove = []
        
        for order_id, order_info in list(self.chasing_orders.items()):
            # Check if order is still pending
            if order_id not in self.pending_orders:
                # Order was filled or cancelled - stop monitoring
                logger.info(f"Order #{order_id} no longer pending, stopping chase")
                orders_to_remove.append(order_id)
                continue
            
            contract_key = order_info['contract_key']
            current_mid = self.calculate_mid_price(contract_key)
            
            if current_mid == 0:
                continue  # No valid market data
            
            last_price = order_info.get('last_price', order_info['last_mid'])
            action = order_info['action']
            
            # Calculate time since last price update
            time_since_last_update = (datetime.now() - order_info['timestamp']).total_seconds()
            
            # Get market data for ask/bid
            market_data = self.market_data.get(contract_key, {})
            ask_price = market_data.get('ask', 0)
            bid_price = market_data.get('bid', 0)
            
            # Determine tick size based on current mid price (from instrument configuration)
            if current_mid >= 3.0:
                tick_size = self.instrument['tick_size_above_3']
            else:
                tick_size = self.instrument['tick_size_below_3']
            
            should_update = False
            update_reason = ""
            
            # Get current give-in tick count
            give_in_ticks = order_info.get('give_in_count', 0)
            
            # Check if we need to increment give-in counter
            if time_since_last_update >= self.give_in_interval:
                # Time to give in another tick
                give_in_ticks += 1
                order_info['give_in_count'] = give_in_ticks
                should_update = True
                update_reason = f"Give in timer ({time_since_last_update:.1f}s) → X_ticks={give_in_ticks}"
            
            # Check if mid-price has moved significantly (use minimum tick size as threshold)
            min_tick = min(self.instrument['tick_size_above_3'], self.instrument['tick_size_below_3'])
            if abs(current_mid - order_info['last_mid']) >= min_tick:
                should_update = True
                if update_reason:
                    update_reason += f" + Mid moved ${order_info['last_mid']:.2f}→${current_mid:.2f}"
                else:
                    update_reason = f"Mid moved ${order_info['last_mid']:.2f}→${current_mid:.2f}"
            
            # Calculate new price: ALWAYS current_mid ± (give_in_ticks * tick_size)
            if action == "BUY":
                # Buy: mid + X_ticks (creep toward ask)
                new_price = self.round_to_option_tick(
                    current_mid + (give_in_ticks * tick_size)
                )
                # Don't exceed ask price
                if ask_price > 0 and new_price > ask_price:
                    new_price = ask_price
                price_formula = f"${current_mid:.2f} + ({give_in_ticks} × ${tick_size:.2f}) = ${new_price:.2f}"
            else:  # SELL
                # Sell: mid - X_ticks (creep toward bid)
                new_price = self.round_to_option_tick(
                    current_mid - (give_in_ticks * tick_size)
                )
                # Don't go below bid price
                if bid_price > 0 and new_price < bid_price:
                    new_price = bid_price
                price_formula = f"${current_mid:.2f} - ({give_in_ticks} × ${tick_size:.2f}) = ${new_price:.2f}"
            
            # Update the order if needed (price changed OR timer triggered OR mid moved)
            if should_update and new_price != last_price:
                logger.info(f"Order #{order_id}: {update_reason} | {price_formula}")
                
                try:
                    # Parse contract key to recreate contract
                    parts = contract_key.split('_')
                    if len(parts) == 4:
                        symbol, strike_str, right, expiry = parts
                        trading_class = "SPXW" if symbol == "SPX" else "XSP"
                        
                        # Create contract
                        contract = self.create_option_contract(
                            strike=float(strike_str),
                            right=right,
                            symbol=symbol,
                            trading_class=trading_class,
                            expiry=expiry
                        )
                        
                        # Create modified order
                        order = Order()
                        order.action = order_info['action']
                        order.totalQuantity = order_info['quantity']
                        order.orderType = "LMT"
                        order.lmtPrice = new_price
                        order.auxPrice = 0
                        order.tif = "DAY"
                        order.outsideRth = True  # Enable after-hours trading
                        order.eTradeOnly = False
                        order.firmQuoteOnly = False
                        
                        # Modify order (use same order_id)
                        self.ibkr_client.placeOrder(order_id, contract, order)
                        
                        # Update tracking
                        order_info['last_mid'] = current_mid  # Track current mid
                        order_info['last_price'] = new_price  # Track actual order price
                        order_info['timestamp'] = datetime.now()  # Reset timer
                        order_info['attempts'] += 1
                        
                        # Update orders display
                        self.update_orders_display()
                        self.update_ts_orders_display()
                        
                        logger.info(f"✓ Order #{order_id} updated to ${new_price:.2f} (X_ticks={give_in_ticks})")
                        self.log_message(
                            f"Order #{order_id}: ${new_price:.2f} | X_ticks={give_in_ticks} | {update_reason}",
                            "INFO"
                        )
                        
                except Exception as e:
                    logger.error(f"Error updating order #{order_id}: {e}", exc_info=True)
        
        # Remove filled/cancelled orders from monitoring
        for order_id in orders_to_remove:
            if order_id in self.chasing_orders:
                del self.chasing_orders[order_id]
        
        # Continue monitoring if orders remain
        if self.chasing_orders:
            QTimer.singleShot(1000, self.update_orders)
        else:
            # No more orders - stop timer
            if hasattr(self, '_chasing_timer_running'):
                self._chasing_timer_running = False
    
    # ========================================================================
    # HISTORICAL DATA
    # ========================================================================
    
    def request_historical_data(self, contract_key: str):
        """Request historical data for an option contract"""
        try:
            # Parse contract key: SYMBOL_STRIKE_RIGHT_EXPIRY
            parts = contract_key.split('_')
            if len(parts) != 4:
                self.log_message(f"Invalid contract key format: {contract_key}", "ERROR")
                return
            
            symbol, strike_str, right, expiry = parts
            
            # Determine trading class based on symbol
            trading_class = "SPXW" if symbol == "SPX" else "XSP"
            
            # Create option contract using helper function
            contract = self.create_option_contract(
                strike=float(strike_str),
                right=right,
                symbol=symbol,
                trading_class=trading_class,
                expiry=expiry
            )
            
            self.log_message(
                f"Requesting hist data: {symbol} {strike_str} {right} {expiry} @ {contract.exchange} class={contract.tradingClass}",
                "INFO"
            )
            
            # Get next request ID
            req_id = self.app_state.get('next_order_id', 1)
            self.app_state['next_order_id'] = req_id + 1
            
            # Track request
            self.app_state['historical_data_requests'][req_id] = contract_key
            
            # Request historical data (IBKR returns in US/Eastern, we convert to Central Time)
            # Use empty string for end_time to get most recent data
            end_time = ""  # Empty string means current time
            
            self.ibkr_client.reqHistoricalData(
                req_id,
                contract,
                end_time,
                "2 D",  # Duration
                "5 mins",  # Bar size
                "TRADES",  # What to show
                0,  # Include after-hours data
                1,  # Format date
                True,  # Keep up to date - enables real-time bar updates via historicalDataUpdate
                []
            )
            
            self.log_message(f"Requesting historical data for {contract_key}", "INFO")
            
        except Exception as e:
            self.log_message(f"Error requesting historical data: {e}", "ERROR")
            logger.error(f"Historical data request error: {e}", exc_info=True)
    
    
    def update_orders_display(self):
        """Update the orders table with active orders and chase status"""
        self.orders_table.setRowCount(0)
        
        for order_id, order_info in list(self.pending_orders.items()):
            # Skip filled/cancelled orders (don't display them)
            status = order_info.get('status', 'Working')
            if status in ['Filled', 'Cancelled', 'Inactive']:
                continue
            
            row = self.orders_table.rowCount()
            self.orders_table.insertRow(row)
            
            # Check if this is a chasing order
            chasing_info = self.chasing_orders.get(order_id)
            
            # Get price string - use chasing_info for live chase price
            if chasing_info:
                current_price = chasing_info.get('last_price', chasing_info.get('last_mid', 0))
                price_str = f"${current_price:.2f}"
            elif order_info.get('price', 0) == 0:
                price_str = "MKT"
            else:
                price_str = f"${order_info['price']:.2f}"
            
            # Get status string - show chase status for chasing orders
            if chasing_info:
                give_in_ticks = chasing_info.get('give_in_count', 0)
                if give_in_ticks == 0:
                    status_str = "Chasing Mid"
                else:
                    status_str = f"Giving In x{give_in_ticks}"
            else:
                status_str = order_info.get('status', 'Working')
            
            # Populate row
            items = [
                QTableWidgetItem(str(order_id)),
                QTableWidgetItem(order_info['contract_key']),
                QTableWidgetItem(order_info['action']),
                QTableWidgetItem(str(order_info['quantity'])),
                QTableWidgetItem(price_str),
                QTableWidgetItem(status_str),
                QTableWidgetItem("Cancel")
            ]
            
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Status column - color based on chase status
                if col == 5:
                    if chasing_info:
                        give_in_ticks = chasing_info.get('give_in_count', 0)
                        if give_in_ticks == 0:
                            item.setForeground(QColor("#00CED1"))  # Cyan for chasing mid
                        else:
                            item.setForeground(QColor("#FFA500"))  # Orange for giving in
                
                # Cancel button styling
                if col == 6:
                    item.setBackground(QColor("#cc0000"))
                    item.setForeground(QColor("#ffffff"))
                
                self.orders_table.setItem(row, col, item)
    
    # ========================================================================
    # MANUAL TRADING
    # ========================================================================
    
    # ========================================================================
    # MANUAL TRADING
    # ========================================================================
    
    def manual_buy_call(self):
        """Manual buy call option - uses Master Settings for delta/quantity and places order with mid-price chasing"""
        self.log_message("=" * 60, "INFO")
        self.log_message("🔔 MANUAL BUY CALL INITIATED 🔔", "SUCCESS")
        self.log_message("=" * 60, "INFO")
        
        try:
            # Check connection
            if self.connection_state != ConnectionState.CONNECTED:
                self.log_message("❌ Cannot place order: Not connected to IBKR", "ERROR")
                return
            
            if not self.app_state.get('data_server_ok', False):
                self.log_message("❌ Cannot place order: Data server not ready", "ERROR")
                return
            
            # Get settings from Master Settings panel
            target_delta = self.target_delta_spin.value()
            max_risk = self.max_risk_spin.value()
            
            self.log_message(f"Master Settings: Target Δ={target_delta}, Max Risk=${max_risk:.0f}", "INFO")
            self.log_message(f"Searching for CALL option near {target_delta} delta...", "INFO")
            
            # Find call option by delta
            result = self.find_option_by_delta("C", target_delta)
            if not result:
                self.log_message(f"No suitable call options found near {target_delta} delta", "WARNING")
                return
            
            contract_key, ask_price, actual_delta = result
            
            # Calculate mid price for order
            mid_price = self.calculate_mid_price(contract_key)
            if mid_price == 0:
                self.log_message("Cannot calculate mid price - using ask price", "WARNING")
                mid_price = ask_price
            
            # Calculate quantity based on position size mode
            if self.position_size_mode == "fixed":
                quantity = self.trade_qty_spin.value()
                size_description = f"{quantity} contract(s) (Fixed)"
            else:  # calculated by risk
                # Calculate contracts based on max risk: contracts = max_risk / (option_price * 100)
                option_cost = mid_price * 100  # Cost per contract
                quantity = max(1, int(max_risk / option_cost))
                size_description = f"{quantity} contract(s) (By Risk: ${max_risk:.0f} ÷ ${option_cost:.0f})"
            
            # Log order details
            self.log_message(
                f"Placing BUY CALL: {quantity} × {contract_key}\n"
                f"Delta: {actual_delta:.1f} (Target: {target_delta})\n"
                f"Mid Price: ${mid_price:.2f} (~${mid_price * 100:.0f} per contract)\n"
                f"Position Size: {size_description}\n"
                f"Total Cost: ~${mid_price * 100 * quantity:.0f}",
                "INFO"
            )
            
            # Place order with mid-price chasing enabled (no confirmation for speed)
            order_id = self.place_order(
                contract_key=contract_key,
                action="BUY",
                quantity=quantity,
                limit_price=mid_price,
                enable_chasing=True  # Enable mid-price chasing for manual orders
            )
            
            if order_id:
                self.log_message(
                    f"✓ Manual CALL order #{order_id} submitted: {quantity} × ${mid_price:.2f} with mid-price chasing",
                    "SUCCESS"
                )
            
            self.log_message("=" * 60, "INFO")
            
        except Exception as e:
            self.log_message(f"Error in manual_buy_call: {e}", "ERROR")
            logger.error(f"Manual buy call error: {e}", exc_info=True)
    
    def manual_buy_put(self):
        """Manual buy put option - uses Master Settings for delta/quantity and places order with mid-price chasing"""
        self.log_message("=" * 60, "INFO")
        self.log_message("🔔 MANUAL BUY PUT INITIATED 🔔", "SUCCESS")
        self.log_message("=" * 60, "INFO")
        
        try:
            # Check connection
            if self.connection_state != ConnectionState.CONNECTED:
                self.log_message("❌ Cannot place order: Not connected to IBKR", "ERROR")
                return
            
            if not self.app_state.get('data_server_ok', False):
                self.log_message("❌ Cannot place order: Data server not ready", "ERROR")
                return
            
            # Get settings from Master Settings panel
            target_delta = self.target_delta_spin.value()
            max_risk = self.max_risk_spin.value()
            
            self.log_message(f"Master Settings: Target Δ={target_delta}, Max Risk=${max_risk:.0f}", "INFO")
            self.log_message(f"Searching for PUT option near {target_delta} delta...", "INFO")
            
            # Find put option by delta
            result = self.find_option_by_delta("P", target_delta)
            if not result:
                self.log_message(f"No suitable put options found near {target_delta} delta", "WARNING")
                return
            
            contract_key, ask_price, actual_delta = result
            
            # Calculate mid price for order
            mid_price = self.calculate_mid_price(contract_key)
            if mid_price == 0:
                self.log_message("Cannot calculate mid price - using ask price", "WARNING")
                mid_price = ask_price
            
            # Calculate quantity based on position size mode
            if self.position_size_mode == "fixed":
                quantity = self.trade_qty_spin.value()
                size_description = f"{quantity} contract(s) (Fixed)"
            else:  # calculated by risk
                # Calculate contracts based on max risk: contracts = max_risk / (option_price * 100)
                option_cost = mid_price * 100  # Cost per contract
                quantity = max(1, int(max_risk / option_cost))
                size_description = f"{quantity} contract(s) (By Risk: ${max_risk:.0f} ÷ ${option_cost:.0f})"
            
            # Log order details
            self.log_message(
                f"Placing BUY PUT: {quantity} × {contract_key}\n"
                f"Delta: {actual_delta:.1f} (Target: {target_delta})\n"
                f"Mid Price: ${mid_price:.2f} (~${mid_price * 100:.0f} per contract)\n"
                f"Position Size: {size_description}\n"
                f"Total Cost: ~${mid_price * 100 * quantity:.0f}",
                "INFO"
            )
            
            # Place order with mid-price chasing enabled (no confirmation for speed)
            order_id = self.place_order(
                contract_key=contract_key,
                action="BUY",
                quantity=quantity,
                limit_price=mid_price,
                enable_chasing=True  # Enable mid-price chasing for manual orders
            )
            
            if order_id:
                self.log_message(
                    f"✓ Manual PUT order #{order_id} submitted: {quantity} × ${mid_price:.2f} with mid-price chasing",
                    "SUCCESS"
                )
            
            self.log_message("=" * 60, "INFO")
            
        except Exception as e:
            self.log_message(f"Error in manual_buy_put: {e}", "ERROR")
            logger.error(f"Manual buy put error: {e}", exc_info=True)
    
    def manual_buy_call_automated(self):
        """
        Automated buy call for straddle strategy - NO user confirmation.
        Uses Master Settings for delta/quantity.
        Places order WITHOUT mid-price chasing (enable_chasing=False).
        """
        try:
            # Check connection
            if self.connection_state != ConnectionState.CONNECTED:
                self.log_message("❌ Cannot place order: Not connected to IBKR", "ERROR")
                return
            
            if not self.app_state.get('data_server_ok', False):
                self.log_message("❌ Cannot place order: Data server not ready", "ERROR")
                return
            
            # Get settings from Master Settings panel
            target_delta = self.target_delta_spin.value()
            max_risk = self.max_risk_spin.value()
            
            self.log_message(f"Automated CALL Entry: Target Δ={target_delta}, Max Risk=${max_risk:.0f}", "INFO")
            
            # Find call option by delta (same as manual)
            result = self.find_option_by_delta("C", target_delta)
            if not result:
                self.log_message("No suitable call options found for automated entry", "WARNING")
                return
            
            contract_key, ask_price, actual_delta = result
            
            # Calculate mid price for order
            mid_price = self.calculate_mid_price(contract_key)
            if mid_price == 0:
                self.log_message("Cannot calculate mid price - using ask price", "WARNING")
                mid_price = ask_price
            
            # Calculate quantity based on position size mode (same as manual)
            if self.position_size_mode == "fixed":
                quantity = self.trade_qty_spin.value()
                size_description = f"{quantity} contract(s) (Fixed)"
            else:  # calculated by risk
                option_cost = mid_price * 100
                quantity = max(1, int(max_risk / option_cost))
                size_description = f"{quantity} contract(s) (By Risk: ${max_risk:.0f} ÷ ${option_cost:.0f})"
            
            # Place order WITHOUT chasing (automated strategy doesn't chase)
            order_id = self.place_order(
                contract_key=contract_key,
                action="BUY",
                quantity=quantity,
                limit_price=mid_price,
                enable_chasing=False  # No chasing for automated strategy
            )
            
            if order_id:
                self.log_message(
                    f"✓ Automated CALL order #{order_id}: {contract_key} Δ={actual_delta:.1f}, {quantity} × ${mid_price:.2f} ({size_description})",
                    "SUCCESS"
                )
                # Track as straddle leg
                self.active_straddles.append({
                    'contract_key': contract_key,
                    'order_id': order_id,
                    'leg': 'CALL',
                    'timestamp': datetime.now()
                })
            
        except Exception as e:
            self.log_message(f"Error in automated call entry: {e}", "ERROR")
            logger.error(f"Automated buy call error: {e}", exc_info=True)
    
    def manual_buy_put_automated(self):
        """
        Automated buy put for straddle strategy - NO user confirmation.
        Uses Master Settings for delta/quantity.
        Places order WITHOUT mid-price chasing (enable_chasing=False).
        """
        try:
            # Check connection
            if self.connection_state != ConnectionState.CONNECTED:
                self.log_message("❌ Cannot place order: Not connected to IBKR", "ERROR")
                return
            
            if not self.app_state.get('data_server_ok', False):
                self.log_message("❌ Cannot place order: Data server not ready", "ERROR")
                return
            
            # Get settings from Master Settings panel
            target_delta = self.target_delta_spin.value()
            max_risk = self.max_risk_spin.value()
            
            self.log_message(f"Automated PUT Entry: Target Δ={target_delta}, Max Risk=${max_risk:.0f}", "INFO")
            
            # Find put option by delta (same as manual)
            result = self.find_option_by_delta("P", target_delta)
            if not result:
                self.log_message("No suitable put options found for automated entry", "WARNING")
                return
            
            contract_key, ask_price, actual_delta = result
            
            # Calculate mid price for order
            mid_price = self.calculate_mid_price(contract_key)
            if mid_price == 0:
                self.log_message("Cannot calculate mid price - using ask price", "WARNING")
                mid_price = ask_price
            
            # Calculate quantity based on position size mode (same as manual)
            if self.position_size_mode == "fixed":
                quantity = self.trade_qty_spin.value()
                size_description = f"{quantity} contract(s) (Fixed)"
            else:  # calculated by risk
                option_cost = mid_price * 100
                quantity = max(1, int(max_risk / option_cost))
                size_description = f"{quantity} contract(s) (By Risk: ${max_risk:.0f} ÷ ${option_cost:.0f})"
            
            # Place order WITHOUT chasing (automated strategy doesn't chase)
            order_id = self.place_order(
                contract_key=contract_key,
                action="BUY",
                quantity=quantity,
                limit_price=mid_price,
                enable_chasing=False  # No chasing for automated strategy
            )
            
            if order_id:
                self.log_message(
                    f"✓ Automated PUT order #{order_id}: {contract_key} Δ={actual_delta:.1f}, {quantity} × ${mid_price:.2f} ({size_description})",
                    "SUCCESS"
                )
                # Track as straddle leg
                self.active_straddles.append({
                    'contract_key': contract_key,
                    'order_id': order_id,
                    'leg': 'PUT',
                    'timestamp': datetime.now()
                })
            
        except Exception as e:
            self.log_message(f"Error in automated put entry: {e}", "ERROR")
            logger.error(f"Automated buy put error: {e}", exc_info=True)
    
    # ========================================================================
    # POSITIONS AND ORDERS
    # ========================================================================
    
    def update_positions_display(self):
        """Update positions table with real-time P&L and time tracking"""
        self.positions_table.setRowCount(0)
        total_pnl = 0
        total_cost_basis = 0
        total_mkt_value = 0
        
        for row, (contract_key, pos) in enumerate(self.positions.items()):
            self.positions_table.insertRow(row)
            
            # Update P&L from current market data (mid-price)
            if contract_key in self.market_data:
                md = self.market_data[contract_key]
                bid, ask = md.get('bid', 0), md.get('ask', 0)
                if bid > 0 and ask > 0:
                    current_price = (bid + ask) / 2
                    pos['currentPrice'] = current_price
                    pos['pnl'] = (current_price - pos['avgCost']) * pos['position'] * 100
                else:
                    # Option has no valid bid/ask (worthless or no market data)
                    # Treat as worthless: set price to 0 and calculate total loss
                    pos['currentPrice'] = 0.0
                    pos['pnl'] = (0.0 - pos['avgCost']) * pos['position'] * 100
                    # Removed debug spam - position updates every second don't need logging
            else:
                # No market data at all - treat as worthless
                pos['currentPrice'] = 0.0
                pos['pnl'] = (0.0 - pos['avgCost']) * pos['position'] * 100
            
            pnl = pos.get('pnl', 0)
            pnl_pct = (pos['currentPrice'] / pos['avgCost'] - 1) * 100 if pos['avgCost'] > 0 else 0
            total_pnl += pnl
            
            # Calculate time tracking
            entry_time = pos.get('entryTime', datetime.now())
            time_span = datetime.now() - entry_time
            
            # Format time strings (HH:MM:SS)
            entry_time_str = entry_time.strftime("%H:%M:%S")
            hours, remainder = divmod(int(time_span.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_span_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # Calculate cost basis and market value
            cost_basis = pos['avgCost'] * abs(pos['position']) * 100
            market_value = pos['currentPrice'] * abs(pos['position']) * 100
            total_cost_basis += cost_basis
            total_mkt_value += market_value
            
            # Populate row (11 columns now: Contract, Qty, Entry, Current, P&L, P&L %, $ Cost Basis, $ Mkt Value, EntryTime, TimeSpan, Action)
            items = [
                QTableWidgetItem(contract_key),
                QTableWidgetItem(f"{pos['position']:.0f}"),
                QTableWidgetItem(f"${pos['avgCost']:.2f}"),
                QTableWidgetItem(f"${pos['currentPrice']:.2f}"),
                QTableWidgetItem(f"${pnl:.2f}"),
                QTableWidgetItem(f"{pnl_pct:.2f}%"),
                QTableWidgetItem(f"${cost_basis:.2f}"),
                QTableWidgetItem(f"${market_value:.2f}"),
                QTableWidgetItem(entry_time_str),
                QTableWidgetItem(time_span_str),
                QTableWidgetItem("Close")
            ]
            
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Color P&L cells (columns 4 and 5)
                if col == 4 or col == 5:
                    if pnl > 0:
                        item.setForeground(QColor("#00ff00"))
                    elif pnl < 0:
                        item.setForeground(QColor("#ff0000"))
                
                # Close button styling (now column 10)
                if col == 10:
                    item.setBackground(QColor("#cc0000"))
                    item.setForeground(QColor("#ffffff"))
                
                self.positions_table.setItem(row, col, item)
        
        # Update total P&L label with color
        pnl_color = "#44ff44" if total_pnl >= 0 else "#ff4444"
        self.pnl_label.setText(f"Total P&L: ${total_pnl:.2f}")
        self.pnl_label.setStyleSheet(f"font-weight: bold; color: {pnl_color}; padding: 2px 12px;")
        
        # Update total cost basis and market value labels
        self.cost_basis_label.setText(f"Total Cost Basis: ${total_cost_basis:.2f}")
        self.mkt_value_label.setText(f"Total Mkt Value: ${total_mkt_value:.2f}")
    
    def on_position_cell_clicked(self, row: int, col: int):
        """
        Handle position table cell click - Close button functionality
        Matches Tkinter version exactly with mid-price chasing and protection checks
        """
        # DEBUG: Log every click
        logger.info(f"Position cell clicked: row={row}, col={col}")
        self.log_message(f"Position table click: row={row}, col={col}", "INFO")
        
        if col != 10:  # Only handle Close button column (column 10)
            logger.info(f"Click on column {col} - not Close button (column 10), ignoring")
            return
        
        logger.info("Close button clicked - starting close position flow")
        self.log_message("=" * 60, "INFO")
        self.log_message("CLOSE BUTTON CLICKED", "INFO")
        
        # Get contract key from first column
        contract_key_item = self.positions_table.item(row, 0)
        if not contract_key_item:
            logger.error("No contract_key item in row 0")
            self.log_message("Error: No contract key found in position table", "ERROR")
            return
        
        contract_key = contract_key_item.text()
        logger.info(f"Contract key from table: {contract_key}")
        self.log_message(f"Contract: {contract_key}", "INFO")
        
        # Get position info
        if contract_key not in self.positions:
            self.log_message(f"Position {contract_key} not found", "WARNING")
            return
        
        pos = self.positions[contract_key]
        position_size = pos['position']
        
        # PROTECTION: Check if position is zero (nothing to close)
        if position_size == 0:
            self.log_message(f"⚠️ WARNING: Position for {contract_key} is zero - nothing to close!", "WARNING")
            return
        
        # PROTECTION: Check for pending exit orders for this contract
        pending_exit_orders = []
        for order_id, order_info in self.chasing_orders.items():
            if order_info['contract_key'] == contract_key:
                # Check if this is an exit order (opposite direction of position)
                is_exit_order = (position_size > 0 and order_info['action'] == "SELL") or \
                               (position_size < 0 and order_info['action'] == "BUY")
                if is_exit_order:
                    pending_exit_orders.append(order_id)
        
        if pending_exit_orders:
            action_type = "SELL" if position_size > 0 else "BUY"
            self.log_message(f"⚠️ WARNING: Already have {len(pending_exit_orders)} pending {action_type} order(s) for {contract_key}!", "WARNING")
            self.log_message(f"Order IDs: {', '.join(map(str, pending_exit_orders))} - allowing duplicate for speed", "WARNING")
            # Continue anyway for maximum speed (user takes responsibility)
        
        # Get current P&L for logging
        current_pnl = pos.get('pnl', 0)
        
        # Log close details (no confirmation for speed)
        self.log_message("=" * 60, "INFO")
        self.log_message(f"MANUAL CLOSE POSITION: {contract_key}", "SUCCESS")
        self.log_message(f"Quantity: {position_size:.0f}, Current P&L: ${current_pnl:.2f}", "INFO")
        
        # Determine action based on position direction
        if position_size > 0:
            action = "SELL"  # Close long position
            qty = int(abs(position_size))
        elif position_size < 0:
            action = "BUY"   # Close short position (should never happen with options!)
            qty = int(abs(position_size))
            self.log_message("⚠️ WARNING: Closing SHORT position - this should not happen with long-only options!", "WARNING")
        else:
            self.log_message("❌ ERROR: Position quantity is zero, nothing to close", "ERROR")
            return
        
        # Calculate mid price for exit (with fallback to last price)
        mid_price = self.calculate_mid_price(contract_key)
        if mid_price == 0:
            # Fallback to current price from position
            mid_price = pos['currentPrice']
            self.log_message(f"Using last price ${mid_price:.2f} for exit", "WARNING")
        
        self.log_message(f"Exit order: {action} {qty} @ ${mid_price:.2f}", "INFO")
        
        # Place exit order with mid-price chasing enabled
        self.place_manual_order(contract_key, action, qty, mid_price)
        self.log_message(f"Exit order submitted with mid-price chasing", "SUCCESS")
        self.log_message("=" * 60, "INFO")
    
    def on_order_cell_clicked(self, row: int, col: int):
        """Handle order table cell click"""
        if col == 6:  # Cancel button
            # Get order ID from first column
            order_id_item = self.orders_table.item(row, 0)
            if not order_id_item:
                return
            
            order_id = int(order_id_item.text())
            
            # Get order info
            if order_id not in self.pending_orders:
                self.log_message(f"Order #{order_id} not found in pending orders", "WARNING")
                return
            
            order_info = self.pending_orders[order_id]
            
            # Log cancel details (no confirmation for speed)
            self.log_message(f"Cancelling order #{order_id}: {order_info['action']} {order_info['quantity']} {order_info['contract_key']}", "INFO")
            
            # Cancel order via IBKR API
            self.ibkr_client.cancelOrder(order_id)
            self.log_message(f"Order #{order_id} cancellation sent", "SUCCESS")
            
            # Update order status
            self.pending_orders[order_id]['status'] = 'Cancelled'
            self.update_orders_display()
    
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
    # MASTER SETTINGS PANEL CALLBACKS
    # ========================================================================
    
    def set_strategy_enabled(self, enabled: bool):
        """Enable or disable automated strategy"""
        self.strategy_enabled = enabled
        self.update_strategy_button_states()
        status = "ENABLED" if enabled else "DISABLED"
        self.log_message(f"Automated Strategy {status}", "SUCCESS" if enabled else "INFO")
        logger.info(f"Strategy automation {status}")
        self.save_settings()
    
    def update_strategy_button_states(self):
        """Update visual state of strategy ON/OFF buttons"""
        if self.strategy_enabled:
            self.strategy_on_btn.setEnabled(False)
            self.strategy_off_btn.setEnabled(True)
            self.strategy_status_label.setText("ON")
            self.strategy_status_label.setStyleSheet("font-weight: bold; color: #44ff44;")
        else:
            self.strategy_on_btn.setEnabled(True)
            self.strategy_off_btn.setEnabled(False)
            self.strategy_status_label.setText("OFF")
            self.strategy_status_label.setStyleSheet("font-weight: bold; color: #808080;")
    
    def on_master_settings_changed(self):
        """Called when any master setting changes"""
        self.vix_threshold = self.vix_threshold_spin.value()
        self.time_stop = self.time_stop_spin.value()
        self.target_delta = self.target_delta_spin.value()
        self.max_risk = self.max_risk_spin.value()
        self.trade_qty = self.trade_qty_spin.value()
        self.save_settings()
    
    def on_position_mode_changed(self):
        """Called when position size mode radio buttons change"""
        if self.fixed_radio.isChecked():
            self.position_size_mode = "fixed"
            self.trade_qty_spin.setEnabled(True)
            self.max_risk_spin.setEnabled(False)
        else:
            self.position_size_mode = "calculated"
            self.trade_qty_spin.setEnabled(False)
            self.max_risk_spin.setEnabled(True)
        
        mode_text = "Fixed Quantity" if self.position_size_mode == "fixed" else "By Max Risk"
        self.log_message(f"Position Size Mode: {mode_text}", "INFO")
        self.save_settings()
    
    # Note: on_chain_settings_changed removed - chain settings moved to Settings tab
    
    # ========================================================================
    # STRADDLE STRATEGY CALLBACKS
    # ========================================================================
    
    def set_straddle_enabled(self, enabled: bool):
        """Enable or disable automated straddle entry"""
        self.straddle_enabled = enabled
        self.update_straddle_button_states()
        status = "ENABLED" if enabled else "DISABLED"
        self.log_message(f"Straddle Auto-Entry {status}", "SUCCESS" if enabled else "INFO")
        logger.info(f"Straddle automation {status}")
        
        if enabled:
            # Start the straddle timer
            if self.straddle_timer is None:
                self.straddle_timer = QTimer()
                self.straddle_timer.timeout.connect(self.check_straddle_timer)
            
            # Set initial timestamp
            self.last_straddle_time = datetime.now()
            
            # Start timer (check every second for smooth countdown)
            self.straddle_timer.start(1000)
            self.log_message(
                f"Straddle timer started: Frequency = {self.straddle_frequency} minutes",
                "SUCCESS"
            )
        else:
            # Stop the straddle timer
            if self.straddle_timer:
                self.straddle_timer.stop()
                self.log_message("Straddle timer stopped", "INFO")
            
            # Reset countdown display
            self.straddle_next_label.setText("Next: --:--")
            self.straddle_next_label.setStyleSheet("color: #808080; font-size: 8pt;")
        
        self.save_settings()
    
    def update_straddle_button_states(self):
        """Update visual state of straddle ON/OFF buttons"""
        if self.straddle_enabled:
            self.straddle_on_btn.setEnabled(False)
            self.straddle_off_btn.setEnabled(True)
            self.straddle_status_label.setText("ON")
            self.straddle_status_label.setStyleSheet("font-weight: bold; color: #44ff44;")
        else:
            self.straddle_on_btn.setEnabled(True)
            self.straddle_off_btn.setEnabled(False)
            self.straddle_status_label.setText("OFF")
            self.straddle_status_label.setStyleSheet("font-weight: bold; color: #808080;")
    
    def on_straddle_settings_changed(self):
        """Called when straddle settings change"""
        self.straddle_frequency = self.straddle_frequency_spin.value()
        self.save_settings()
    
    def check_straddle_timer(self):
        """
        Check if it's time to enter a new straddle based on configured frequency.
        Runs every second to provide smooth countdown display.
        Only executes during regular market hours (9:30 AM - 4:00 PM ET).
        """
        if not self.straddle_enabled:
            return
        
        now = datetime.now()
        
        # Check if market is open
        if not self.is_market_open():
            # Market closed - update status
            self.straddle_next_label.setText("Market Closed")
            self.straddle_next_label.setStyleSheet("color: #FF0000; font-size: 8pt;")
            return
        
        # Market is open - check if it's time to trade
        if self.last_straddle_time is None:
            # Should not happen (set in set_straddle_enabled)
            # But if it does, start timer now
            self.last_straddle_time = now
            return
        
        # Check if enough time has elapsed
        elapsed_minutes = (now - self.last_straddle_time).total_seconds() / 60
        
        if elapsed_minutes >= self.straddle_frequency:
            self.log_message(
                f"Straddle timer triggered ({elapsed_minutes:.1f} min elapsed, "
                f"frequency: {self.straddle_frequency} min)",
                "INFO"
            )
            self.execute_straddle_entry()
            self.last_straddle_time = now
        else:
            # Update countdown display
            remaining = self.straddle_frequency - elapsed_minutes
            next_time = now + timedelta(minutes=remaining)
            self.straddle_next_label.setText(f"Next: {next_time.strftime('%H:%M')}")
            self.straddle_next_label.setStyleSheet("color: #00BFFF; font-size: 8pt;")
    
    def execute_straddle_entry(self):
        """
        Enter a long straddle using the same logic as Manual Buy Call/Put buttons.
        Uses Master Settings for target delta and position sizing.
        
        This is the STRADDLE STRATEGY function - only runs when straddle_enabled = True.
        """
        # Double-check straddle is enabled
        if not self.straddle_enabled:
            self.log_message("Straddle strategy is disabled - skipping entry", "INFO")
            return
        
        # Check connection
        if self.connection_state != ConnectionState.CONNECTED:
            self.log_message("Cannot enter straddle: Not connected to IBKR", "WARNING")
            return
        
        if not self.app_state.get('data_server_ok', False):
            self.log_message("Cannot enter straddle: Data server not ready", "WARNING")
            return
        
        # Check if market is open
        if not self.is_market_open():
            self.log_message(
                "Cannot enter straddle: Market is closed (Regular hours: 9:30 AM - 4:00 PM ET)",
                "WARNING"
            )
            return
        
        self.log_message("=" * 60, "INFO")
        self.log_message("🔔 STRADDLE STRATEGY ENTRY TRIGGERED 🔔", "SUCCESS")
        self.log_message("=" * 60, "INFO")
        self.log_message(
            f"Master Settings: Target Δ={self.target_delta}, Mode={self.position_size_mode}, "
            f"Qty={self.trade_qty if self.position_size_mode == 'fixed' else f'Risk=${self.max_risk}'}",
            "INFO"
        )
        
        # Enter CALL leg (uses Master Settings automatically)
        self.log_message("Entering CALL leg...", "INFO")
        self.manual_buy_call_automated()  # Call without user confirmation
        
        # Small delay before PUT leg (500ms)
        QTimer.singleShot(500, lambda: self.log_message("Entering PUT leg...", "INFO"))
        QTimer.singleShot(1000, self.manual_buy_put_automated)  # 1 second delay
        
        self.log_message("=" * 60, "INFO")
    
    def is_market_open(self) -> bool:
        """
        Check if market is currently open.
        Regular hours: 9:30 AM - 4:00 PM ET (Monday - Friday)
        
        Returns:
            bool: True if market is open, False otherwise
        """
        now = datetime.now()
        
        # Check if weekend
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check time (simplified - assumes local time is ET)
        # TODO: Add proper timezone handling for production
        current_time = now.time()
        market_open = datetime.strptime("09:30", "%H:%M").time()
        market_close = datetime.strptime("16:00", "%H:%M").time()
        
        return market_open <= current_time <= market_close
    
    def check_market_close_refresh(self):
        """
        Check if we've passed 4:00 PM local time and need to refresh option chain.
        Also handles automatic chain recentering if SPX price has drifted.
        
        After 4:00 PM, today's 0DTEs have expired, so we auto-switch to tomorrow.
        This timer runs every 60 seconds to detect when we cross the 4:00 PM threshold.
        """
        now_local = datetime.now(self.local_tz)
        current_date = now_local.date()
        
        # If we've moved to a new day after last refresh, trigger refresh
        if current_date > self.last_refresh_date:
            logger.info(f"New day detected ({current_date}), refreshing option chain")
            self.last_refresh_date = current_date
            if self.connection_state == ConnectionState.CONNECTED:
                # Recalculate expiry (will auto-switch to tomorrow if after 4PM)
                old_expiry = self.current_expiry
                self.current_expiry = self.calculate_expiry_date(0)
                if self.current_expiry != old_expiry:
                    logger.info(f"Expiration auto-switched from {old_expiry} to {self.current_expiry}")
                    self.request_option_chain()
        
        # Also check if we just passed 4:00 PM local time on the same day
        elif now_local.hour == 16 and now_local.minute == 0:
            logger.info("4:00 PM local - Refreshing option chain (today's options expired)")
            if self.connection_state == ConnectionState.CONNECTED:
                old_expiry = self.current_expiry
                self.current_expiry = self.calculate_expiry_date(0)  # Will switch to tomorrow
                if self.current_expiry != old_expiry:
                    logger.info(f"Expiration auto-switched from {old_expiry} to {self.current_expiry}")
                    self.request_option_chain()
        
        # AUTO-RECENTER: Check if ES price has drifted from last center strike
        # NOTE: This ES-based recenter is DISABLED after delta calibration is complete.
        # Once we have live deltas, the delta-based recenter (check_chain_drift_and_recenter)
        # takes over as it's far more accurate. ES-based recenter should only run before
        # delta calibration to prevent chain from drifting too far while waiting for deltas.
        if (self.connection_state == ConnectionState.CONNECTED and 
            self.chain_refresh_interval > 0 and 
            not self.delta_calibration_done):  # ✅ ONLY run before delta calibration
            
            es_price = self.app_state.get('es_price', 0)
            if es_price > 0 and self.last_chain_center_strike > 0:
                # Use adjusted ES price (same as in request_option_chain)
                adjusted_es_price = self.get_adjusted_es_price()
                if adjusted_es_price == 0:
                    # Fallback to raw ES if adjustment fails
                    adjusted_es_price = es_price / 10.0 if self.instrument['underlying_symbol'] == 'XSP' else es_price
                
                reference_price = adjusted_es_price
                strike_increment = self.instrument['strike_increment']
                current_center = round(reference_price / strike_increment) * strike_increment
                drift = abs(current_center - self.last_chain_center_strike)
                
                # Auto-recenter if drifted more than threshold (configurable number of strikes)
                drift_threshold = self.chain_drift_threshold * strike_increment
                if drift >= drift_threshold:
                    logger.info(
                        f"[ES-BASED RECENTER - PRE-CALIBRATION] Price drifted {drift:.0f} points from center strike {self.last_chain_center_strike} "
                        f"to {current_center} (threshold: {drift_threshold:.0f}), auto-recentering chain"
                    )
                    self.request_option_chain()
    
    def calculate_offset_from_historical_close(self):
        """
        Calculate ES-to-cash offset from historical 3:00 PM CT close prices.
        Used when app starts after market hours and no offset was saved from today's session.
        Fetches 5-minute historical data for both SPX and ES, compares their 3pm closes.
        """
        if self.connection_state != ConnectionState.CONNECTED:
            logger.warning("Cannot calculate historical offset - not connected")
            return False
        
        import pytz
        ct_tz = pytz.timezone('US/Central')
        now_ct = datetime.now(ct_tz)
        
        # Determine today's date in CT
        today_ct = now_ct.date()
        
        # Define 3:00 PM CT close time for today
        close_time = datetime.combine(today_ct, datetime.min.time().replace(hour=15, minute=0))
        close_time_ct = ct_tz.localize(close_time)
        
        logger.info(f"Fetching historical data to calculate offset from {close_time_ct.strftime('%Y-%m-%d 3:00 PM CT')} close")
        self.log_message("Calculating offset from historical 3pm close...", "INFO")
        
        # Create temporary storage for historical close data
        self.historical_close_data = {
            'spx_close': None,
            'es_close': None,
            'requests_pending': 2  # Track both requests
        }
        
        try:
            # Request 1: SPX 5-minute bars for today up to 3:05 PM
            spx_contract = Contract()
            spx_contract.symbol = self.instrument['underlying_symbol']
            spx_contract.secType = self.instrument['underlying_type']
            spx_contract.currency = "USD"
            spx_contract.exchange = self.instrument['underlying_exchange']
            
            spx_req_id = 9001  # Unique ID for historical close request
            self.app_state['historical_close_spx_req_id'] = spx_req_id
            
            # Request 1 day of 5-minute bars ending at current time
            self.ibkr_client.reqHistoricalData(
                spx_req_id,
                spx_contract,
                "",  # End time (empty = now)
                "1 D",  # Duration: 1 day
                "5 mins",  # Bar size
                "TRADES",
                1,  # Use RTH (regular trading hours only)
                1,  # Format date as string
                False,  # Don't keep up to date
                []
            )
            logger.info(f"Requested historical SPX data for offset calculation (reqId={spx_req_id})")
            
            # Request 2: ES 5-minute bars for today up to 3:05 PM
            es_contract = Contract()
            es_contract.symbol = "ES"
            es_contract.secType = "FUT"
            es_contract.currency = "USD"
            es_contract.exchange = "CME"
            es_contract.lastTradeDateOrContractMonth = self.get_es_front_month()
            
            es_req_id = 9002  # Unique ID for historical close request
            self.app_state['historical_close_es_req_id'] = es_req_id
            
            self.ibkr_client.reqHistoricalData(
                es_req_id,
                es_contract,
                "",  # End time (empty = now)
                "1 D",  # Duration: 1 day
                "5 mins",  # Bar size
                "TRADES",
                1,  # Use RTH
                1,  # Format date as string
                False,  # Don't keep up to date
                []
            )
            logger.info(f"Requested historical ES data for offset calculation (reqId={es_req_id})")
            
            return True
            
        except Exception as e:
            logger.error(f"Error requesting historical close data: {e}", exc_info=True)
            self.log_message(f"Error fetching historical data: {e}", "ERROR")
            return False
    
    def on_historical_close_data_received(self, req_id: int, bar_data: dict):
        """Handle historical bar data for offset calculation from 3pm close"""
        # Safety check: ensure historical_close_data exists
        if not hasattr(self, 'historical_close_data') or self.historical_close_data is None:
            return
            
        if req_id == self.app_state.get('historical_close_spx_req_id'):
            # SPX bar received - look for 3:00 PM bar
            bar_time_str = str(bar_data['date']).strip()
            if '15:00' in bar_time_str or '1500' in bar_time_str:  # 3:00 PM bar
                self.historical_close_data['spx_close'] = bar_data['close']
                logger.info(f"SPX 3pm close: {bar_data['close']:.2f}")
                
        elif req_id == self.app_state.get('historical_close_es_req_id'):
            # ES bar received - look for 3:00 PM bar
            bar_time_str = str(bar_data['date']).strip()
            if '15:00' in bar_time_str or '1500' in bar_time_str:  # 3:00 PM bar
                self.historical_close_data['es_close'] = bar_data['close']
                logger.info(f"ES 3pm close: {bar_data['close']:.2f}")
    
    def on_historical_close_data_complete(self, req_id: int):
        """Called when historical data request completes"""
        # Safety check: ensure historical_close_data exists
        if not hasattr(self, 'historical_close_data') or self.historical_close_data is None:
            return
            
        if req_id in [self.app_state.get('historical_close_spx_req_id'), self.app_state.get('historical_close_es_req_id')]:
            # Decrement pending requests
            self.historical_close_data['requests_pending'] -= 1
            
            # If both requests complete, calculate offset
            if self.historical_close_data['requests_pending'] == 0:
                underlying_close = self.historical_close_data.get('spx_close')  # Actually could be XSP
                es_close = self.historical_close_data.get('es_close')
                
                if underlying_close and es_close:
                    # Calculate offset based on instrument type
                    # For XSP, we need to scale ES to match XSP scale (ES/10)
                    if self.instrument['underlying_symbol'] == 'XSP':
                        # ES futures vs XSP cash: ES/10 - XSP
                        scaled_es = es_close / 10.0
                        offset = scaled_es - underlying_close
                        logger.info(f"✓ Calculated offset from historical 3pm close: {offset:+.2f} (ES: {es_close:.2f} -> {scaled_es:.2f}, XSP: {underlying_close:.2f})")
                    else:
                        # ES futures vs SPX cash: ES - SPX
                        offset = es_close - underlying_close
                        logger.info(f"✓ Calculated offset from historical 3pm close: {offset:+.2f} (ES: {es_close:.2f}, SPX: {underlying_close:.2f})")
                    
                    self.es_to_cash_offset = offset
                    self.last_offset_update_time = time.time()
                    
                    self.log_message(f"Offset calculated from 3pm close: {offset:+.2f}", "SUCCESS")
                    self.update_offset_display()
                    
                    # Save to settings
                    self.save_settings()
                else:
                    symbol = self.instrument['underlying_symbol']
                    logger.warning(f"Could not find 3pm close bars ({symbol}: {underlying_close}, ES: {es_close})")
                    self.log_message("Could not calculate offset - missing 3pm close data", "WARNING")
                
                # Cleanup
                self.historical_close_data = None
                self.app_state.pop('historical_close_spx_req_id', None)
                self.app_state.pop('historical_close_es_req_id', None)
    
    def check_offset_monitoring(self):
        """
        Check market hours and update ES offset monitoring status.
        Also monitor ES futures market state transitions (closed -> open).
        Called every minute to determine if offset updates should be enabled
        and if ES subscription needs to switch from snapshot to streaming mode.
        Market hours: 8:30 AM - 3:00 PM Central Time (Monday-Friday)
        ES futures market: 23/6 except 4:00-5:00 PM CT daily, all day Sat/Sun
        """
        old_status = self.offset_update_enabled
        self.offset_update_enabled = self.is_market_hours()
        
        # Update display and log if status changed
        if old_status != self.offset_update_enabled:
            import pytz
            ct_tz = pytz.timezone('US/Central')
            now_ct = datetime.now(ct_tz).strftime('%I:%M %p CT')
            
            if self.offset_update_enabled:
                status_text = "STARTED"
                detail = f"Now tracking ES-to-cash offset during market hours (8:30 AM - 3:00 PM CT). Current time: {now_ct}"
            else:
                status_text = "STOPPED"
                detail = f"Offset tracking stopped (outside market hours). Using saved offset: {self.es_to_cash_offset:+.2f}. Current time: {now_ct}"
            
            logger.info(f"ES offset monitoring {status_text} - {detail}")
            self.log_message(f"ES offset tracking {status_text.lower()}", "INFO")
            self.update_offset_display()
        
        # Check for ES futures market state transitions
        es_closed_now = self.is_futures_market_closed()
        
        # Initialize on first check
        if self.es_futures_was_closed is None:
            self.es_futures_was_closed = es_closed_now
            return
        
        # Detect transition from closed to open (5:00 PM CT market reopening)
        if self.es_futures_was_closed and not es_closed_now:
            import pytz
            ct_tz = pytz.timezone('US/Central')
            now_ct = datetime.now(ct_tz).strftime('%I:%M %p CT')
            
            logger.info(f"ES futures market reopened at {now_ct} - switching to streaming mode")
            self.log_message("ES futures market reopened - switching to streaming mode", "INFO")
            
            # Cancel old subscription and re-subscribe with streaming mode
            if self.app_state.get('es_req_id') is not None:
                try:
                    self.ibkr_client.cancelMktData(self.app_state['es_req_id'])
                    logger.info("Cancelled previous ES futures snapshot subscription")
                except Exception as e:
                    logger.error(f"Error cancelling ES subscription: {e}")
            
            # Re-subscribe with streaming mode (snapshot=False)
            self.subscribe_es_price()
        
        # Update state for next check
        self.es_futures_was_closed = es_closed_now
    
    def save_offset_to_settings(self):
        """
        Save ES-to-cash offset to settings file every minute during market hours.
        This preserves the offset determined during day session for use at night.
        """
        # Only save during market hours when offset is being actively tracked
        if not self.is_market_hours():
            return
        
        # Only save if we have a valid offset
        if self.es_to_cash_offset == 0.0:
            return
        
        try:
            # Update the offset in settings and save
            self.save_settings()
            logger.debug(f"ES offset saved: {self.es_to_cash_offset:+.2f} (market hours tracking)")
        except Exception as e:
            logger.error(f"Error saving ES offset: {e}", exc_info=True)
    
    def recenter_option_chain(self):
        """
        Recenter option chain around current ES futures price.
        
        Uses ES futures price (23/6 trading) to calculate ATM strike, then
        creates a new chain with strikes_above and strikes_below around ATM.
        """
        es_price = self.app_state['es_price']
        
        if es_price <= 0:
            self.log_message("Cannot recenter - ES futures price not available", "WARNING")
            return
        
        # Get ES price adjusted for cash offset (same as in request_option_chain)
        adjusted_es_price = self.get_adjusted_es_price()
        if adjusted_es_price == 0:
            # Fallback to raw ES if adjustment fails
            adjusted_es_price = es_price / 10.0 if self.instrument['underlying_symbol'] == 'XSP' else es_price
        
        # Calculate ATM strike using instrument-specific increment
        strike_increment = self.instrument['strike_increment']
        atm_strike = round(adjusted_es_price / strike_increment) * strike_increment
        
        symbol = self.instrument['underlying_symbol']
        self.log_message(f"Recentering option chain around ATM strike: {atm_strike} (Adjusted ES: {adjusted_es_price:.2f}, Raw ES: {es_price:.2f})", "INFO")
        
        # Refresh option chain (will use current strikes_above/strikes_below settings)
        if self.connection_state == ConnectionState.CONNECTED:
            self.request_option_chain()
        else:
            self.log_message("Cannot recenter - not connected to IBKR", "WARNING")
    
    # ========================================================================
    # CHART SETTINGS CALLBACKS
    # ========================================================================
    
    def on_chart_settings_changed(self):
        """Called when any chart setting changes"""
        self.confirm_ema_length = self.confirm_ema_spin.value()
        self.confirm_z_period = self.confirm_z_period_spin.value()
        self.confirm_z_threshold = self.confirm_z_threshold_spin.value()
        self.trade_ema_length = self.trade_ema_spin.value()
        self.trade_z_period = self.trade_z_period_spin.value()
        self.trade_z_threshold = self.trade_z_threshold_spin.value()
        self.save_settings()
    
    def refresh_confirm_chart(self):
        """Refresh the confirmation chart with current settings"""
        self.log_message(f"Refreshing confirmation chart (EMA={self.confirm_ema_length}, Z={self.confirm_z_period}±{self.confirm_z_threshold})", "INFO")
        # TODO: Implement chart refresh logic when charts are integrated
    
    def refresh_trade_chart(self):
        """Refresh the trade chart with current settings"""
        self.log_message(f"Refreshing trade chart (EMA={self.trade_ema_length}, Z={self.trade_z_period}±{self.trade_z_threshold})", "INFO")
        # TODO: Implement chart refresh logic when charts are integrated
    
    # ========================================================================
    # SETTINGS MANAGEMENT
    # ========================================================================
    
    def save_settings(self):
        """Save settings to JSON file"""
        try:
            # Sync chain settings from Settings tab spinners
            self.strikes_above = self.strikes_above_settings_spin.value()
            self.strikes_below = self.strikes_below_settings_spin.value()
            self.chain_refresh_interval = self.chain_refresh_settings_spin.value()
            self.chain_drift_threshold = self.chain_drift_settings_spin.value()
            
            # Sync TradeStation chain settings
            self.ts_strikes_above = self.ts_strikes_above_spin.value()
            self.ts_strikes_below = self.ts_strikes_below_spin.value()
            self.ts_chain_drift_threshold = self.ts_chain_drift_spin.value()
            
            settings = {
                # Connection settings
                'host': self.host_edit.text(),
                'port': int(self.port_edit.text()),
                'client_id': int(self.client_id_edit.text()),
                
                # Chain Settings
                'strikes_above': self.strikes_above,
                'strikes_below': self.strikes_below,
                'chain_refresh_interval': self.chain_refresh_interval,
                'chain_drift_threshold': self.chain_drift_threshold,
                
                # TradeStation Chain Settings
                'ts_strikes_above': self.ts_strikes_above,
                'ts_strikes_below': self.ts_strikes_below,
                'ts_chain_drift_threshold': self.ts_chain_drift_threshold,
                
                # ES Offset Settings (persistent through restarts)
                'es_to_cash_offset': self.es_to_cash_offset,
                'last_offset_update_time': self.last_offset_update_time,
                
                # Master Settings
                'strategy_enabled': self.strategy_enabled,
                'vix_threshold': self.vix_threshold,
                'time_stop': self.time_stop,
                'target_delta': self.target_delta,
                'max_risk': self.max_risk,
                'trade_qty': self.trade_qty,
                'position_size_mode': self.position_size_mode,
                
                # Straddle Settings
                'straddle_enabled': self.straddle_enabled,
                'straddle_frequency': self.straddle_frequency,
                
                # Chart Settings - Confirmation
                'confirm_ema_length': self.confirm_ema_length,
                'confirm_z_period': self.confirm_z_period,
                'confirm_z_threshold': self.confirm_z_threshold,
                
                # Chart Settings - Trade
                'trade_ema_length': self.trade_ema_length,
                'trade_z_period': self.trade_z_period,
                'trade_z_threshold': self.trade_z_threshold,
            }
            
            Path('settings.json').write_text(json.dumps(settings, indent=2))
            logger.debug("Settings saved successfully")
        except Exception as e:
            self.log_message(f"Error saving settings: {e}", "ERROR")
            logger.error(f"Error saving settings: {e}", exc_info=True)
    
    # ==================== TradeStation Integration Methods ====================
    
    def enable_tradestation(self):
        """Enable TradeStation integration"""
        if not TRADESTATION_AVAILABLE:
            self.log_message("TradeStation not available - GlobalDictionary not found", "ERROR")
            return
        
        if self.ts_enabled:
            self.log_message("TradeStation already enabled", "WARNING")
            return
        
        try:
            # Start TradeStation manager thread
            self.ts_manager = TradeStationManager(self.ts_signals)
            self.ts_manager.start()
            
            self.ts_enabled = True
            self.enable_ts_btn.setEnabled(False)
            self.disable_ts_btn.setEnabled(True)
            self.sync_ts_btn.setEnabled(True)
            
            self.log_message("TradeStation integration enabled", "SUCCESS")
            
            # Update active contract label but DON'T auto-request chains
            # User can manually click refresh buttons to load chain data
            self.update_ts_active_contract()
            logger.info("[TS] TradeStation enabled - chains NOT auto-requested to avoid duplicate req IDs")
            
        except Exception as e:
            self.log_message(f"Error enabling TradeStation: {e}", "ERROR")
            logger.error(f"Error enabling TradeStation: {e}", exc_info=True)
    
    def disable_tradestation(self):
        """Disable TradeStation integration"""
        if not self.ts_enabled:
            return
        
        try:
            if self.ts_manager:
                self.ts_manager.stop()
                # No .wait() needed - not a QThread anymore
                self.ts_manager = None
            
            self.ts_enabled = False
            self.enable_ts_btn.setEnabled(True)
            self.disable_ts_btn.setEnabled(False)
            self.sync_ts_btn.setEnabled(False)
            
            self.log_message("TradeStation integration disabled", "INFO")
            
        except Exception as e:
            self.log_message(f"Error disabling TradeStation: {e}", "ERROR")
            logger.error(f"Error disabling TradeStation: {e}", exc_info=True)
    
    @pyqtSlot(bool)
    def on_ts_connected(self, connected: bool):
        """Handle TradeStation connection status"""
        if connected:
            self.ts_status_label.setText("Status: Connected")
            self.ts_status_label.setStyleSheet("color: #4CAF50;")
            self.log_message("TradeStation GlobalDictionary connected", "SUCCESS")
        else:
            self.ts_status_label.setText("Status: Disconnected")
            self.ts_status_label.setStyleSheet("color: #FF6B6B;")
            self.log_message("TradeStation GlobalDictionary disconnected", "WARNING")
    
    @pyqtSlot(str)
    def on_ts_message(self, message: str):
        """Handle TradeStation log messages"""
        self.log_message(f"[TS] {message}", "INFO")
    
    @pyqtSlot(str)
    def on_ts_activity(self, message: str):
        """Handle TradeStation activity log messages (all GD messages)"""
        try:
            from datetime import datetime
            timestamp = datetime.now(self.local_tz).strftime("%H:%M:%S.%f")[:-3]
            self.ts_activity_log.append(f"{timestamp} {message}")
            
            # Manually limit to 500 lines by removing old lines
            # QTextEdit doesn't have setMaximumBlockCount, so we manage it manually
            text = self.ts_activity_log.toPlainText()
            lines = text.split('\n')
            if len(lines) > 500:
                # Keep only the last 500 lines
                self.ts_activity_log.setPlainText('\n'.join(lines[-500:]))
                # Move cursor to end to show latest
                cursor = self.ts_activity_log.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.ts_activity_log.setTextCursor(cursor)
        except Exception as e:
            logger.error(f"Error adding to activity log: {e}")
    
    @pyqtSlot(dict)
    def on_ts_entry_signal(self, signal_data: dict):
        """Handle entry signal from TradeStation"""
        try:
            action = signal_data.get('action', '')
            symbol = signal_data.get('symbol', SELECTED_INSTRUMENT)
            quantity = signal_data.get('quantity', 1)
            signal_id = signal_data.get('signal_id', '')
            
            self.log_message(f"Entry signal received: {action} {quantity}x {symbol}", "INFO")
            
            # Determine which contract type to use based on time
            contract_type = self.get_ts_active_contract_type()
            self.ts_active_contract_type = contract_type
            self.ts_active_contract_label.setText(contract_type)
            
            # Route to appropriate entry method
            if action == "BUY_CALL":
                self.execute_ts_buy_call(symbol, quantity, contract_type, signal_id)
            elif action == "BUY_PUT":
                self.execute_ts_buy_put(symbol, quantity, contract_type, signal_id)
            elif action == "BUY_STRADDLE":
                self.execute_ts_buy_straddle(symbol, quantity, contract_type, signal_id)
            else:
                self.log_message(f"Unknown entry action: {action}", "ERROR")
                
            # Update last signal time
            self.ts_last_signal_time = datetime.now()
            self.ts_last_signal_label.setText(self.ts_last_signal_time.strftime("%H:%M:%S"))
            
        except Exception as e:
            self.log_message(f"Error processing entry signal: {e}", "ERROR")
            logger.error(f"Error processing entry signal: {e}", exc_info=True)
    
    @pyqtSlot(dict)
    def on_ts_exit_signal(self, signal_data: dict):
        """Handle exit signal from TradeStation"""
        try:
            action = signal_data.get('action', '')
            symbol = signal_data.get('symbol', SELECTED_INSTRUMENT)
            signal_id = signal_data.get('signal_id', '')
            
            self.log_message(f"Exit signal received: {action} for {symbol}", "INFO")
            
            # Route to appropriate exit method
            if action == "CLOSE_ALL":
                self.execute_ts_close_all(symbol, signal_id)
            elif action == "CLOSE_CALLS":
                self.execute_ts_close_calls(symbol, signal_id)
            elif action == "CLOSE_PUTS":
                self.execute_ts_close_puts(symbol, signal_id)
            elif action == "CLOSE_POSITION":
                contract_key = signal_data.get('contract_key')
                if contract_key:
                    self.execute_ts_close_position(contract_key, signal_id)
                else:
                    self.log_message("No contract_key provided for CLOSE_POSITION", "ERROR")
            else:
                self.log_message(f"Unknown exit action: {action}", "ERROR")
                
            # Update last signal time
            self.ts_last_signal_time = datetime.now()
            self.ts_last_signal_label.setText(self.ts_last_signal_time.strftime("%H:%M:%S"))
            
        except Exception as e:
            self.log_message(f"Error processing exit signal: {e}", "ERROR")
            logger.error(f"Error processing exit signal: {e}", exc_info=True)
    
    @pyqtSlot(dict)
    def on_ts_signal_update(self, signal_data: dict):
        """Handle signal update from TradeStation"""
        pass  # Reserved for future use
    
    @pyqtSlot(str)
    def on_ts_strategy_state_changed(self, state: str):
        """Handle strategy state change from TradeStation"""
        self.ts_strategy_state = state
        self.ts_state_label.setText(state)
        
        # Color code the state
        if state == "FLAT":
            self.ts_state_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFF00;")
        elif state == "LONG":
            self.ts_state_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #4CAF50;")
        elif state == "SHORT":
            self.ts_state_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #FF6B6B;")
        else:
            self.ts_state_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFFFF;")
        
        self.log_message(f"TS Strategy state changed to: {state}", "INFO")
    
    def sync_with_ts_strategy(self):
        """Manually sync strategy state with TradeStation"""
        try:
            if not self.ts_manager or not self.ts_enabled:
                self.log_message("TradeStation not connected", "WARNING")
                return
            
            # Count current positions
            position_count = len([p for p in self.app_state.get('positions', {}).values() 
                                  if p.get('quantity', 0) != 0])
            self.ts_position_count = position_count
            self.ts_position_count_label.setText(str(position_count))
            
            self.log_message(f"Synced with TS - {position_count} positions", "INFO")
            
        except Exception as e:
            self.log_message(f"Error syncing with TradeStation: {e}", "ERROR")
            logger.error(f"Error syncing with TradeStation: {e}", exc_info=True)
    
    def refresh_ts_chains(self):
        """Refresh both 0DTE and 1DTE option chains for TradeStation tab"""
        if self.connection_state != ConnectionState.CONNECTED:
            self.log_message("Cannot refresh chains - not connected to IBKR", "WARNING")
            return
        
        try:
            # Request both chains
            self.request_ts_chain("0DTE")
            self.request_ts_chain("1DTE")
            self.log_message("Refreshing TradeStation option chains...", "INFO")
        except Exception as e:
            self.log_message(f"Error refreshing TS chains: {e}", "ERROR")
            logger.error(f"Error refreshing TS chains: {e}", exc_info=True)
    
    def get_ts_active_contract_type(self) -> str:
        """Determine which contract type (0DTE or 1DTE) to use based on current time"""
        try:
            import pytz
            from datetime import time as dt_time
            ct_tz = pytz.timezone('America/Chicago')
            now_ct = datetime.now(ct_tz)
            current_time = now_ct.time()
            
            # 0DTE: 7:15 PM - 11:00 AM CT
            # 1DTE: 11:00 AM - 4:00 PM CT
            time_11am = dt_time(11, 0)
            time_4pm = dt_time(16, 0)
            
            if time_11am <= current_time < time_4pm:
                return "1DTE"
            else:
                return "0DTE"
                
        except Exception as e:
            logger.error(f"Error determining active contract type: {e}", exc_info=True)
            return "0DTE"  # Default fallback
    
    def update_ts_active_contract(self):
        """Update the active contract type label"""
        contract_type = self.get_ts_active_contract_type()
        self.ts_active_contract_type = contract_type
        self.ts_active_contract_label.setText(contract_type)
    
    def request_ts_chain(self, contract_type: str, force_center_strike: float | None = None):
        """Request option chain data for specified contract type (0DTE or 1DTE) - works like main chain
        
        Args:
            contract_type: "0DTE" or "1DTE"
            force_center_strike: If provided, center chain at this exact strike (for recentering)
        """
        try:
            logger.info(f"[TS CHAIN] === Starting request_ts_chain for {contract_type} ===")
            
            # Reset calibration flag if this is a manual/new request (not a forced recenter)
            if force_center_strike is None:
                if contract_type == "0DTE":
                    self.ts_0dte_delta_calibration_done = False
                    self.ts_0dte_is_recentering = False
                else:
                    self.ts_1dte_delta_calibration_done = False
                    self.ts_1dte_is_recentering = False
            
            # Check IBKR connection
            if self.connection_state != ConnectionState.CONNECTED:
                self.log_message("IBKR not connected - cannot request chains", "WARNING")
                logger.warning(f"[TS CHAIN] Connection state is {self.connection_state}, not CONNECTED")
                return
            
            # Calculate expiry
            if contract_type == "0DTE":
                expiry = self.calculate_expiry_date(0)  # Today's expiration (or tomorrow if after 4PM)
                self.ts_0dte_expiry = expiry
                self.ts_0dte_expiry_label.setText(f"Expiry: {expiry}")
            else:  # 1DTE
                # For 1DTE, we want the NEXT trading day after 0DTE
                # So if 0DTE offset is 0, 1DTE should be offset 1
                # But we need to ensure they're always different days
                expiry_0dte = self.calculate_expiry_date(0)
                expiry_1dte = self.calculate_expiry_date(1)
                
                # If both are same (shouldn't happen but safety check), use offset 2
                if expiry_1dte == expiry_0dte:
                    expiry = self.calculate_expiry_date(2)
                    logger.warning(f"[TS CHAIN] 1DTE matched 0DTE ({expiry_0dte}), using offset 2: {expiry}")
                else:
                    expiry = expiry_1dte
                
                self.ts_1dte_expiry = expiry
                self.ts_1dte_expiry_label.setText(f"Expiry: {expiry}")
            
            # Determine reference price (same logic as main chain)
            # If force_center_strike is provided, use it directly (for recentering)
            strike_interval = self.instrument['strike_increment']
            
            if force_center_strike is not None:
                center_strike = force_center_strike
                logger.info(f"[TS {contract_type}] FORCED RECENTER to strike {center_strike}")
            else:
                if (underlying_price := self.app_state.get('underlying_price', 0)) > 0:
                    reference_price = underlying_price
                    logger.info(f"[TS {contract_type}] Using {self.instrument['underlying_symbol']} index price ${reference_price:.2f}")
                else:
                    # Fallback to ES futures adjusted for cash offset
                    adjusted_es_price = self.get_adjusted_es_price()
                    if adjusted_es_price == 0:
                        self.log_message(f"Waiting for price data for {contract_type} chain...", "INFO")
                        return
                    reference_price = adjusted_es_price
                    logger.warning(f"[TS {contract_type}] Using fallback ES-derived price ${reference_price:.2f}")
                
                # Calculate center strike
                center_strike = round(reference_price / strike_interval) * strike_interval
                logger.info(f"[TS {contract_type}] Chain centered at strike {center_strike} (Ref: ${reference_price:.2f})")
            
            # Track center strike for drift detection
            if contract_type == "0DTE":
                self.ts_0dte_center_strike = center_strike
            else:
                self.ts_1dte_center_strike = center_strike
            
            # Build strike list using TS chain settings
            strikes = []
            current_strike = center_strike - (self.ts_strikes_below * strike_interval)
            end_strike = center_strike + (self.ts_strikes_above * strike_interval)
            
            while current_strike <= end_strike:
                strikes.append(current_strike)
                current_strike += strike_interval
            
            logger.info(f"[TS {contract_type}] Requesting {len(strikes)} strikes from {min(strikes):.0f} to {max(strikes):.0f} (center: {center_strike:.0f})")
            
            # Determine trading class
            trading_class = "SPXW" if SELECTED_INSTRUMENT == "SPX" else "XSP"
            
            # Request market data for each strike
            for strike in strikes:
                # Request call
                call_contract = self.create_option_contract(
                    strike=strike,
                    right='C',
                    symbol=SELECTED_INSTRUMENT,
                    trading_class=trading_class,
                    expiry=expiry
                )
                call_key = f"{SELECTED_INSTRUMENT}_{strike}_C_{expiry}"
                req_id = self.app_state['next_req_id']
                self.ibkr_client.reqMktData(req_id, call_contract, "", False, False, [])
                self.app_state['market_data_map'][req_id] = call_key
                self.app_state['next_req_id'] += 1
                
                # Request put
                put_contract = self.create_option_contract(
                    strike=strike,
                    right='P',
                    symbol=SELECTED_INSTRUMENT,
                    trading_class=trading_class,
                    expiry=expiry
                )
                put_key = f"{SELECTED_INSTRUMENT}_{strike}_P_{expiry}"
                req_id = self.app_state['next_req_id']
                self.ibkr_client.reqMktData(req_id, put_contract, "", False, False, [])
                self.app_state['market_data_map'][req_id] = put_key
                self.app_state['next_req_id'] += 1
            
            logger.info(f"[TS {contract_type}] Chain request complete: {len(strikes)} strikes requested")
            
            # Initialize the table with empty rows for these strikes
            self.initialize_ts_chain_table(contract_type, strikes)
            
        except Exception as e:
            logger.error(f"[TS CHAIN] Error requesting {contract_type} chain: {e}", exc_info=True)
            self.log_message(f"Error requesting {contract_type} chain: {str(e)}", "ERROR")
    
    def initialize_ts_chain_table(self, contract_type: str, strikes: list):
        """Initialize TS chain table with rows for given strikes"""
        try:
            # Select the appropriate table
            table = self.ts_0dte_table if contract_type == "0DTE" else self.ts_1dte_table
            
            # Sort strikes descending (highest first)
            sorted_strikes = sorted(strikes, reverse=True)
            
            # Set row count
            table.setRowCount(len(sorted_strikes))
            
            # Initialize each row with strike and empty cells
            for row, strike in enumerate(sorted_strikes):
                # Column layout: Call Delta, Call Gamma, Call Bid, Call Ask, Strike, Put Bid, Put Ask, Put Gamma, Put Delta
                
                # Initialize all cells with zeros (centered)
                for col in range(9):
                    if col == 4:  # Strike column
                        strike_item = QTableWidgetItem(f"{strike:.2f}")
                        strike_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        # Don't set initial background - will be colored by ATM detection
                        table.setItem(row, col, strike_item)
                    else:
                        item = QTableWidgetItem("0.00")
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        table.setItem(row, col, item)
            
            logger.debug(f"[TS {contract_type}] Initialized table with {len(sorted_strikes)} strikes")
        except Exception as e:
            logger.error(f"Error initializing TS chain table: {e}", exc_info=True)
    
    def update_ts_chain_cell(self, contract_key: str):
        """Update a single cell in TS chain tables when market data arrives.
        Also triggers ATM detection and strike coloring after updating."""
        try:
            # Parse contract key: SYMBOL_STRIKE_RIGHT_EXPIRY
            parts = contract_key.split('_')
            if len(parts) < 4:
                return
            
            symbol = parts[0]
            strike = float(parts[1])
            right = parts[2]  # 'C' or 'P'
            expiry = parts[3]
            
            # Determine which table(s) to update and which contract type(s)
            tables_to_update = []
            contract_types = []
            if hasattr(self, 'ts_0dte_expiry') and expiry == self.ts_0dte_expiry:
                tables_to_update.append(self.ts_0dte_table)
                contract_types.append("0DTE")
            if hasattr(self, 'ts_1dte_expiry') and expiry == self.ts_1dte_expiry:
                tables_to_update.append(self.ts_1dte_table)
                contract_types.append("1DTE")
            
            if not tables_to_update:
                return  # Not a TS chain expiry
            
            # Get market data for this contract
            data = self.market_data.get(contract_key, {})
            
            # Track if we should trigger ATM update (for call options with delta data)
            should_update_atm = (right == 'C' and data.get('delta') is not None)
            
            for idx, table in enumerate(tables_to_update):
                # Find the row for this strike
                for row in range(table.rowCount()):
                    strike_item = table.item(row, 4)  # Strike is column 4
                    if strike_item and abs(float(strike_item.text()) - strike) < 0.01:
                        # Found the row! Now update the appropriate columns
                        if right == 'C':  # Call option
                            # Call Delta (column 0)
                            delta_val = data.get('delta', 0.0) or 0.0
                            item = QTableWidgetItem(f"{delta_val:.3f}")
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            table.setItem(row, 0, item)
                            # Call Gamma (column 1)
                            gamma_val = data.get('gamma', 0.0) or 0.0
                            item = QTableWidgetItem(f"{gamma_val:.4f}")
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            table.setItem(row, 1, item)
                            # Call Bid (column 2)
                            bid_val = data.get('bid', 0.0) or 0.0
                            item = QTableWidgetItem(f"{bid_val:.2f}")
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            table.setItem(row, 2, item)
                            # Call Ask (column 3)
                            ask_val = data.get('ask', 0.0) or 0.0
                            item = QTableWidgetItem(f"{ask_val:.2f}")
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            table.setItem(row, 3, item)
                        else:  # Put option
                            # Put Bid (column 5)
                            bid_val = data.get('bid', 0.0) or 0.0
                            item = QTableWidgetItem(f"{bid_val:.2f}")
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            table.setItem(row, 5, item)
                            # Put Ask (column 6)
                            ask_val = data.get('ask', 0.0) or 0.0
                            item = QTableWidgetItem(f"{ask_val:.2f}")
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            table.setItem(row, 6, item)
                            # Put Gamma (column 7)
                            gamma_val = data.get('gamma', 0.0) or 0.0
                            item = QTableWidgetItem(f"{gamma_val:.4f}")
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            table.setItem(row, 7, item)
                            # Put Delta (column 8)
                            delta_val = data.get('delta', 0.0) or 0.0
                            item = QTableWidgetItem(f"{delta_val:.3f}")
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            table.setItem(row, 8, item)
                        break  # Found the row, no need to continue
            
            # After updating all tables for this contract, trigger ATM detection if appropriate
            # Only for call options with delta data, throttled to once per second per contract type
            if should_update_atm and contract_types:
                import time
                current_time = time.time()
                
                # Initialize throttle tracking if not present
                if not hasattr(self, '_ts_0dte_last_atm_update_time'):
                    self._ts_0dte_last_atm_update_time = 0
                if not hasattr(self, '_ts_1dte_last_atm_update_time'):
                    self._ts_1dte_last_atm_update_time = 0
                
                # Update each contract type that was affected
                for contract_type in set(contract_types):  # Use set to avoid duplicates
                    if contract_type == "0DTE":
                        if current_time - self._ts_0dte_last_atm_update_time >= 1.0:
                            self._ts_0dte_last_atm_update_time = current_time
                            self.update_ts_strike_backgrounds_by_delta(contract_type)
                    else:  # 1DTE
                        if current_time - self._ts_1dte_last_atm_update_time >= 1.0:
                            self._ts_1dte_last_atm_update_time = current_time
                            self.update_ts_strike_backgrounds_by_delta(contract_type)
                    
        except Exception as e:
            logger.error(f"Error updating TS chain cell for {contract_key}: {e}", exc_info=True)
    
    def request_ts_chain_forced_center(self, contract_type: str, center_strike: float):
        """Helper method to request TS chain with forced center strike (for recentering)"""
        self.request_ts_chain(contract_type, force_center_strike=center_strike)
    
    def update_ts_chain_table(self, contract_type: str):
        """Update the option chain table for specified contract type"""
        try:
            # Select the appropriate table and data
            if contract_type == "0DTE":
                table = self.ts_0dte_table
                expiry = self.ts_0dte_expiry
            else:  # 1DTE
                table = self.ts_1dte_table
                expiry = self.ts_1dte_expiry
            
            if not expiry:
                return
            
            # Get all strikes for this expiry from app_state
            chain_data = {}
            for contract_key, data in self.app_state.get('option_chain', {}).items():
                parts = contract_key.split('_')
                if len(parts) >= 4 and parts[3] == expiry:
                    strike = float(parts[1])
                    if strike not in chain_data:
                        chain_data[strike] = {'call': {}, 'put': {}}
                    
                    if parts[2] == 'C':
                        chain_data[strike]['call'] = data
                    else:
                        chain_data[strike]['put'] = data
            
            # Sort strikes
            sorted_strikes = sorted(chain_data.keys(), reverse=True)
            
            # Update table
            table.setRowCount(len(sorted_strikes))
            
            for row, strike in enumerate(sorted_strikes):
                call_data = chain_data[strike]['call']
                put_data = chain_data[strike]['put']
                
                # Column layout: Call Δ, Call Γ, Call Bid, Call Ask, Strike, Put Bid, Put Ask, Put Γ, Put Δ
                
                # Call Delta (column 0)
                table.setItem(row, 0, QTableWidgetItem(f"{call_data.get('delta', 0.0):.3f}"))
                
                # Call Gamma (column 1)
                table.setItem(row, 1, QTableWidgetItem(f"{call_data.get('gamma', 0.0):.4f}"))
                
                # Call Bid (column 2)
                table.setItem(row, 2, QTableWidgetItem(f"{call_data.get('bid', 0.0):.2f}"))
                
                # Call Ask (column 3)
                table.setItem(row, 3, QTableWidgetItem(f"{call_data.get('ask', 0.0):.2f}"))
                
                # Strike (column 4 - center)
                strike_item = QTableWidgetItem(f"{strike:.2f}")
                strike_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                strike_item.setBackground(QColor(60, 60, 60))  # Highlight strike column
                table.setItem(row, 4, strike_item)
                
                # Put Bid (column 5)
                table.setItem(row, 5, QTableWidgetItem(f"{put_data.get('bid', 0.0):.2f}"))
                
                # Put Ask (column 6)
                table.setItem(row, 6, QTableWidgetItem(f"{put_data.get('ask', 0.0):.2f}"))
                
                # Put Gamma (column 7)
                table.setItem(row, 7, QTableWidgetItem(f"{put_data.get('gamma', 0.0):.4f}"))
                
                # Put Delta (column 8)
                table.setItem(row, 8, QTableWidgetItem(f"{put_data.get('delta', 0.0):.3f}"))
            
        except Exception as e:
            logger.error(f"Error updating {contract_type} chain table: {e}", exc_info=True)
    
    def execute_ts_buy_call(self, symbol: str, quantity: int, contract_type: str, signal_id: str):
        """Execute buy call order from TradeStation signal"""
        try:
            # Determine expiry based on contract type
            expiry = self.ts_0dte_expiry if contract_type == "0DTE" else self.ts_1dte_expiry
            
            if not expiry:
                self.log_message(f"No expiry set for {contract_type}", "ERROR")
                return
            
            # Find ATM strike
            atm_strike = self.find_atm_strike_by_delta()
            if not atm_strike:
                self.log_message("Could not determine ATM strike", "ERROR")
                return
            
            # Select 1 strike OTM (for calls, this is above ATM)
            strike = atm_strike + self.strike_interval
            
            # Get mid price for limit order
            contract_key = f"{symbol}_{strike}_C_{expiry}"
            option_data = self.app_state.get('option_chain', {}).get(contract_key, {})
            bid = option_data.get('bid', 0)
            ask = option_data.get('ask', 0)
            mid_price = round((bid + ask) / 2, 2) if bid and ask else 0
            
            if mid_price == 0:
                self.log_message(f"No market data for {contract_key}", "ERROR")
                return
            
            # Place order with chasing enabled
            self.place_order(contract_key, "BUY", quantity, mid_price, True)
            
            # Add to signal log
            self.add_ts_signal_to_log("ENTRY", "BUY_CALL", contract_key, "SUBMITTED", mid_price, f"Signal: {signal_id}")
            
        except Exception as e:
            self.log_message(f"Error executing TS buy call: {e}", "ERROR")
            logger.error(f"Error executing TS buy call: {e}", exc_info=True)
    
    def execute_ts_buy_put(self, symbol: str, quantity: int, contract_type: str, signal_id: str):
        """Execute buy put order from TradeStation signal"""
        try:
            # Determine expiry based on contract type
            expiry = self.ts_0dte_expiry if contract_type == "0DTE" else self.ts_1dte_expiry
            
            if not expiry:
                self.log_message(f"No expiry set for {contract_type}", "ERROR")
                return
            
            # Find ATM strike
            atm_strike = self.find_atm_strike_by_delta()
            if not atm_strike:
                self.log_message("Could not determine ATM strike", "ERROR")
                return
            
            # Select 1 strike OTM (for puts, this is below ATM)
            strike = atm_strike - self.strike_interval
            
            # Get mid price for limit order
            contract_key = f"{symbol}_{strike}_P_{expiry}"
            option_data = self.app_state.get('option_chain', {}).get(contract_key, {})
            bid = option_data.get('bid', 0)
            ask = option_data.get('ask', 0)
            mid_price = round((bid + ask) / 2, 2) if bid and ask else 0
            
            if mid_price == 0:
                self.log_message(f"No market data for {contract_key}", "ERROR")
                return
            
            # Place order with chasing enabled
            self.place_order(contract_key, "BUY", quantity, mid_price, True)
            
            # Add to signal log
            self.add_ts_signal_to_log("ENTRY", "BUY_PUT", contract_key, "SUBMITTED", mid_price, f"Signal: {signal_id}")
            
        except Exception as e:
            self.log_message(f"Error executing TS buy put: {e}", "ERROR")
            logger.error(f"Error executing TS buy put: {e}", exc_info=True)
    
    def execute_ts_buy_straddle(self, symbol: str, quantity: int, contract_type: str, signal_id: str):
        """Execute buy straddle (call + put) from TradeStation signal"""
        try:
            # Execute both call and put
            self.execute_ts_buy_call(symbol, quantity, contract_type, f"{signal_id}_CALL")
            self.execute_ts_buy_put(symbol, quantity, contract_type, f"{signal_id}_PUT")
            
        except Exception as e:
            self.log_message(f"Error executing TS buy straddle: {e}", "ERROR")
            logger.error(f"Error executing TS buy straddle: {e}", exc_info=True)
    
    def execute_ts_close_all(self, symbol: str, signal_id: str):
        """Close all positions for the symbol"""
        try:
            positions = self.app_state.get('positions', {})
            closed_count = 0
            
            for contract_key, pos_data in positions.items():
                if pos_data.get('symbol') == symbol and pos_data.get('quantity', 0) != 0:
                    self.close_position_by_key(contract_key)
                    closed_count += 1
            
            self.log_message(f"Closed {closed_count} positions for {symbol}", "INFO")
            
            # Add to signal log
            self.add_ts_signal_to_log("EXIT", "CLOSE_ALL", symbol, "EXECUTED", 0, f"Closed {closed_count} positions")
            
        except Exception as e:
            self.log_message(f"Error closing all positions: {e}", "ERROR")
            logger.error(f"Error closing all positions: {e}", exc_info=True)
    
    def execute_ts_close_calls(self, symbol: str, signal_id: str):
        """Close all call positions for the symbol"""
        try:
            positions = self.app_state.get('positions', {})
            closed_count = 0
            
            for contract_key, pos_data in positions.items():
                if (pos_data.get('symbol') == symbol and 
                    pos_data.get('right') == 'C' and 
                    pos_data.get('quantity', 0) != 0):
                    self.close_position_by_key(contract_key)
                    closed_count += 1
            
            self.log_message(f"Closed {closed_count} call positions for {symbol}", "INFO")
            
            # Add to signal log
            self.add_ts_signal_to_log("EXIT", "CLOSE_CALLS", symbol, "EXECUTED", 0, f"Closed {closed_count} calls")
            
        except Exception as e:
            self.log_message(f"Error closing call positions: {e}", "ERROR")
            logger.error(f"Error closing call positions: {e}", exc_info=True)
    
    def execute_ts_close_puts(self, symbol: str, signal_id: str):
        """Close all put positions for the symbol"""
        try:
            positions = self.app_state.get('positions', {})
            closed_count = 0
            
            for contract_key, pos_data in positions.items():
                if (pos_data.get('symbol') == symbol and 
                    pos_data.get('right') == 'P' and 
                    pos_data.get('quantity', 0) != 0):
                    self.close_position_by_key(contract_key)
                    closed_count += 1
            
            self.log_message(f"Closed {closed_count} put positions for {symbol}", "INFO")
            
            # Add to signal log
            self.add_ts_signal_to_log("EXIT", "CLOSE_PUTS", symbol, "EXECUTED", 0, f"Closed {closed_count} puts")
            
        except Exception as e:
            self.log_message(f"Error closing put positions: {e}", "ERROR")
            logger.error(f"Error closing put positions: {e}", exc_info=True)
    
    def close_position_by_key(self, contract_key: str):
        """Close a position by contract key (used by TradeStation signal handling)"""
        try:
            # Get position info
            if contract_key not in self.positions:
                self.log_message(f"Position {contract_key} not found", "WARNING")
                return
            
            pos = self.positions[contract_key]
            position_size = pos.get('quantity', 0)
            
            # Check if position is zero
            if position_size == 0:
                self.log_message(f"Position for {contract_key} is zero - nothing to close", "WARNING")
                return
            
            # Determine action based on position direction
            if position_size > 0:
                action = "SELL"  # Close long position
                qty = int(abs(position_size))
            elif position_size < 0:
                action = "BUY"   # Close short position
                qty = int(abs(position_size))
            else:
                return
            
            # Calculate mid price for exit
            mid_price = self.calculate_mid_price(contract_key)
            if mid_price == 0:
                # Fallback to current price from position
                mid_price = pos.get('currentPrice', 0)
                if mid_price == 0:
                    self.log_message(f"Cannot determine exit price for {contract_key}", "ERROR")
                    return
            
            self.log_message(f"Closing position: {contract_key} - {action} {qty} @ ${mid_price:.2f}", "INFO")
            
            # Place exit order with mid-price chasing
            self.place_manual_order(contract_key, action, qty, mid_price)
            
        except Exception as e:
            self.log_message(f"Error closing position {contract_key}: {e}", "ERROR")
            logger.error(f"Error closing position {contract_key}: {e}", exc_info=True)
    
    def execute_ts_close_position(self, contract_key: str, signal_id: str):
        """Close a specific position by contract key"""
        try:
            if not contract_key:
                self.log_message("No contract key provided for position close", "ERROR")
                return
            
            self.close_position_by_key(contract_key)
            
            # Add to signal log
            self.add_ts_signal_to_log("EXIT", "CLOSE_POSITION", contract_key, "EXECUTED", 0, f"Signal: {signal_id}")
            
        except Exception as e:
            self.log_message(f"Error closing specific position: {e}", "ERROR")
            logger.error(f"Error closing specific position: {e}", exc_info=True)
    
    def add_ts_signal_to_log(self, signal_type: str, action: str, contract: str, 
                            status: str, fill_price: float, details: str):
        """Add entry to TradeStation signal history table"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            row = self.ts_signal_table.rowCount()
            self.ts_signal_table.insertRow(row)
            
            self.ts_signal_table.setItem(row, 0, QTableWidgetItem(timestamp))
            self.ts_signal_table.setItem(row, 1, QTableWidgetItem(signal_type))
            self.ts_signal_table.setItem(row, 2, QTableWidgetItem(action))
            self.ts_signal_table.setItem(row, 3, QTableWidgetItem(contract))
            self.ts_signal_table.setItem(row, 4, QTableWidgetItem(status))
            self.ts_signal_table.setItem(row, 5, QTableWidgetItem(f"{fill_price:.2f}" if fill_price else "N/A"))
            self.ts_signal_table.setItem(row, 6, QTableWidgetItem(details))
            
            # Keep log to last 100 entries
            if self.ts_signal_table.rowCount() > 100:
                self.ts_signal_table.removeRow(0)
            
            # Scroll to bottom
            self.ts_signal_table.scrollToBottom()
            
        except Exception as e:
            logger.error(f"Error adding signal to log: {e}", exc_info=True)
    
    def on_ts_position_cell_clicked(self, row: int, col: int):
        """
        Handle TS position table cell click - Close button functionality
        Uses same logic as main positions table with mid-price chasing
        """
        # DEBUG: Log every click
        logger.info(f"TS Position cell clicked: row={row}, col={col}")
        self.log_message(f"TS Position table click: row={row}, col={col}", "INFO")
        
        if col != 10:  # Only handle Close button column (column 10)
            logger.info(f"Click on column {col} - not Close button (column 10), ignoring")
            return
        
        logger.info("TS Close button clicked - starting close position flow")
        self.log_message("=" * 60, "INFO")
        self.log_message("TS CLOSE BUTTON CLICKED", "INFO")
        
        # Get contract key from first column
        contract_key_item = self.ts_positions_table.item(row, 0)
        if not contract_key_item:
            logger.error("No contract_key item in row 0")
            self.log_message("Error: No contract key found in position table", "ERROR")
            return
        
        contract_key = contract_key_item.text()
        logger.info(f"Contract key from table: {contract_key}")
        self.log_message(f"Contract: {contract_key}", "INFO")
        
        # Get position info
        if contract_key not in self.positions:
            self.log_message(f"Position {contract_key} not found", "WARNING")
            return
        
        pos = self.positions[contract_key]
        position_size = pos.get('quantity', 0)
        
        # PROTECTION: Check if position is zero (nothing to close)
        if position_size == 0:
            self.log_message(f"⚠️ WARNING: Position for {contract_key} is zero - nothing to close!", "WARNING")
            return
        
        # PROTECTION: Check for pending exit orders for this contract
        pending_exit_orders = []
        for order_id, order_info in self.chasing_orders.items():
            if order_info['contract_key'] == contract_key:
                # Check if this is an exit order (opposite direction of position)
                is_exit_order = (position_size > 0 and order_info['action'] == "SELL") or \
                               (position_size < 0 and order_info['action'] == "BUY")
                if is_exit_order:
                    pending_exit_orders.append(order_id)
        
        if pending_exit_orders:
            action_type = "SELL" if position_size > 0 else "BUY"
            self.log_message(f"⚠️ WARNING: Already have {len(pending_exit_orders)} pending {action_type} order(s) for {contract_key}!", "WARNING")
            self.log_message(f"Order IDs: {', '.join(map(str, pending_exit_orders))} - allowing duplicate for speed", "WARNING")
            # Continue anyway for maximum speed (user takes responsibility)
        
        # Get current P&L for logging
        current_pnl = pos.get('pnl', 0)
        
        # Log close details (no confirmation for speed)
        self.log_message("=" * 60, "INFO")
        self.log_message(f"TS MANUAL CLOSE POSITION: {contract_key}", "SUCCESS")
        self.log_message(f"Quantity: {position_size:.0f}, Current P&L: ${current_pnl:.2f}", "INFO")
        
        # Determine action based on position direction
        if position_size > 0:
            action = "SELL"  # Close long position
            qty = int(abs(position_size))
        elif position_size < 0:
            action = "BUY"   # Close short position (should never happen with options!)
            qty = int(abs(position_size))
            self.log_message("⚠️ WARNING: Closing SHORT position - this should not happen with long-only options!", "WARNING")
        else:
            self.log_message("❌ ERROR: Position quantity is zero, nothing to close", "ERROR")
            return
        
        # Calculate mid price for exit (with fallback to last price)
        mid_price = self.calculate_mid_price(contract_key)
        if mid_price == 0:
            # Fallback to current price from position
            mid_price = pos['currentPrice']
            self.log_message(f"Using last price ${mid_price:.2f} for exit", "WARNING")
        
        self.log_message(f"Exit order: {action} {qty} @ ${mid_price:.2f}", "INFO")
        
        # Place exit order with mid-price chasing enabled
        self.place_manual_order(contract_key, action, qty, mid_price)
        self.log_message(f"Exit order submitted with mid-price chasing", "SUCCESS")
        self.log_message("=" * 60, "INFO")
    
    def on_ts_order_cell_clicked(self, row: int, col: int):
        """Handle TS order table cell click - Cancel button"""
        if col == 6:  # Cancel button
            # Get order ID from first column
            order_id_item = self.ts_orders_table.item(row, 0)
            if not order_id_item:
                return
            
            order_id = int(order_id_item.text())
            
            # Get order info
            if order_id not in self.pending_orders:
                self.log_message(f"Order #{order_id} not found in pending orders", "WARNING")
                return
            
            order_info = self.pending_orders[order_id]
            
            # Log cancel details (no confirmation for speed)
            self.log_message(f"Cancelling TS order #{order_id}: {order_info['action']} {order_info['quantity']} {order_info['contract_key']}", "INFO")
            
            # Cancel order via IBKR API
            self.ibkr_client.cancelOrder(order_id)
            self.log_message(f"TS Order #{order_id} cancellation sent", "SUCCESS")
            
            # Update order status
            self.pending_orders[order_id]['status'] = 'Cancelled'
            self.update_ts_orders_display()
    
    def update_ts_positions_display(self):
        """Update TS positions table with real-time P&L and time tracking"""
        self.ts_positions_table.setRowCount(0)
        total_pnl = 0
        total_cost_basis = 0
        total_mkt_value = 0
        
        for row, (contract_key, pos) in enumerate(self.positions.items()):
            self.ts_positions_table.insertRow(row)
            
            # Update P&L from current market data (mid-price)
            if contract_key in self.market_data:
                md = self.market_data[contract_key]
                bid, ask = md.get('bid', 0), md.get('ask', 0)
                if bid > 0 and ask > 0:
                    current_price = (bid + ask) / 2
                    pos['currentPrice'] = current_price
                    pos['pnl'] = (current_price - pos['avgCost']) * pos['position'] * 100
                else:
                    pos['currentPrice'] = 0.0
                    pos['pnl'] = (0.0 - pos['avgCost']) * pos['position'] * 100
            else:
                pos['currentPrice'] = 0.0
                pos['pnl'] = (0.0 - pos['avgCost']) * pos['position'] * 100
            
            pnl = pos.get('pnl', 0)
            pnl_pct = (pos['currentPrice'] / pos['avgCost'] - 1) * 100 if pos['avgCost'] > 0 else 0
            total_pnl += pnl
            
            # Calculate time tracking
            entry_time = pos.get('entryTime', datetime.now())
            time_span = datetime.now() - entry_time
            
            # Format time strings
            entry_time_str = entry_time.strftime("%H:%M:%S")
            hours, remainder = divmod(int(time_span.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_span_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # Calculate cost basis and market value
            cost_basis = pos['avgCost'] * abs(pos['position']) * 100
            market_value = pos['currentPrice'] * abs(pos['position']) * 100
            total_cost_basis += cost_basis
            total_mkt_value += market_value
            
            # Populate row
            items = [
                QTableWidgetItem(contract_key),
                QTableWidgetItem(f"{pos['position']:.0f}"),
                QTableWidgetItem(f"${pos['avgCost']:.2f}"),
                QTableWidgetItem(f"${pos['currentPrice']:.2f}"),
                QTableWidgetItem(f"${pnl:.2f}"),
                QTableWidgetItem(f"{pnl_pct:.2f}%"),
                QTableWidgetItem(f"${cost_basis:.2f}"),
                QTableWidgetItem(f"${market_value:.2f}"),
                QTableWidgetItem(entry_time_str),
                QTableWidgetItem(time_span_str),
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
                if col == 10:
                    item.setBackground(QColor("#cc0000"))
                    item.setForeground(QColor("#ffffff"))
                
                self.ts_positions_table.setItem(row, col, item)
    
    def update_ts_orders_display(self):
        """Update TS orders table with active orders and chase status"""
        self.ts_orders_table.setRowCount(0)
        
        for order_id, order_info in list(self.pending_orders.items()):
            # Skip filled/cancelled orders
            status = order_info.get('status', 'Working')
            if status in ['Filled', 'Cancelled', 'Inactive']:
                continue
            
            row = self.ts_orders_table.rowCount()
            self.ts_orders_table.insertRow(row)
            
            # Check if this is a chasing order
            chasing_info = self.chasing_orders.get(order_id)
            
            # Get price string
            if chasing_info:
                current_price = chasing_info.get('last_price', chasing_info.get('last_mid', 0))
                price_str = f"${current_price:.2f}"
            elif order_info.get('price', 0) == 0:
                price_str = "MKT"
            else:
                price_str = f"${order_info['price']:.2f}"
            
            # Get status string
            if chasing_info:
                give_in_ticks = chasing_info.get('give_in_count', 0)
                if give_in_ticks == 0:
                    status_str = "Chasing Mid"
                else:
                    status_str = f"Giving In x{give_in_ticks}"
            else:
                status_str = order_info.get('status', 'Working')
            
            # Populate row
            items = [
                QTableWidgetItem(str(order_id)),
                QTableWidgetItem(order_info['contract_key']),
                QTableWidgetItem(order_info['action']),
                QTableWidgetItem(str(order_info['quantity'])),
                QTableWidgetItem(price_str),
                QTableWidgetItem(status_str),
                QTableWidgetItem("Cancel")
            ]
            
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Status column - color based on chase status
                if col == 5:
                    if chasing_info:
                        give_in_ticks = chasing_info.get('give_in_count', 0)
                        if give_in_ticks == 0:
                            item.setForeground(QColor("#00CED1"))  # Cyan for chasing mid
                        else:
                            item.setForeground(QColor("#FFA500"))  # Orange for giving in
                
                # Cancel button styling
                if col == 6:
                    item.setBackground(QColor("#cc0000"))
                    item.setForeground(QColor("#ffffff"))
                
                self.ts_orders_table.setItem(row, col, item)
    
    # ==================== End TradeStation Methods ====================
    
    def load_settings(self):
        """Load settings from JSON file"""
        try:
            if Path('settings.json').exists():
                settings = json.loads(Path('settings.json').read_text())
                
                # Connection settings
                self.host = settings.get('host', '127.0.0.1')
                self.port = settings.get('port', 7497)
                self.client_id = settings.get('client_id', 1)
                self.strikes_above = settings.get('strikes_above', 20)
                self.strikes_below = settings.get('strikes_below', 20)
                self.chain_refresh_interval = settings.get('chain_refresh_interval', 3600)
                self.chain_drift_threshold = settings.get('chain_drift_threshold', 5)
                
                # TradeStation Chain Settings
                self.ts_strikes_above = settings.get('ts_strikes_above', 6)
                self.ts_strikes_below = settings.get('ts_strikes_below', 6)
                self.ts_chain_drift_threshold = settings.get('ts_chain_drift_threshold', 3)
                
                # ES Offset Settings (restore persistent offset from day session)
                self.es_to_cash_offset = settings.get('es_to_cash_offset', 0.0)
                self.last_offset_update_time = settings.get('last_offset_update_time', 0)
                
                # Log loaded offset
                if self.es_to_cash_offset != 0.0:
                    from datetime import datetime
                    last_update = datetime.fromtimestamp(self.last_offset_update_time).strftime('%Y-%m-%d %H:%M:%S') if self.last_offset_update_time > 0 else "unknown"
                    logger.info(f"Loaded ES offset from settings: {self.es_to_cash_offset:+.2f} (last updated: {last_update})")
                
                # Update offset display after loading
                self.update_offset_display()
                
                # Master Settings
                self.strategy_enabled = settings.get('strategy_enabled', False)
                self.vix_threshold = settings.get('vix_threshold', 20.0)
                self.time_stop = settings.get('time_stop', 60)
                self.target_delta = settings.get('target_delta', 30)
                self.max_risk = settings.get('max_risk', 500)
                self.trade_qty = settings.get('trade_qty', 1)
                self.position_size_mode = settings.get('position_size_mode', 'fixed')
                
                # Straddle Settings
                self.straddle_enabled = settings.get('straddle_enabled', False)
                self.straddle_frequency = settings.get('straddle_frequency', 60)
                
                # Chart Settings - Confirmation
                self.confirm_ema_length = settings.get('confirm_ema_length', 9)
                self.confirm_z_period = settings.get('confirm_z_period', 30)
                self.confirm_z_threshold = settings.get('confirm_z_threshold', 1.5)
                
                # Chart Settings - Trade
                self.trade_ema_length = settings.get('trade_ema_length', 9)
                self.trade_z_period = settings.get('trade_z_period', 30)
                self.trade_z_threshold = settings.get('trade_z_threshold', 1.5)
                
                # Update connection UI
                self.host_edit.setText(self.host)
                self.port_edit.setText(str(self.port))
                self.client_id_edit.setText(str(self.client_id))
                
                # Update Settings tab chain settings
                self.strikes_above_settings_spin.setValue(self.strikes_above)
                self.strikes_below_settings_spin.setValue(self.strikes_below)
                self.chain_refresh_settings_spin.setValue(self.chain_refresh_interval)
                self.chain_drift_settings_spin.setValue(self.chain_drift_threshold)
                
                # Update Settings tab TradeStation chain settings
                self.ts_strikes_above_spin.setValue(self.ts_strikes_above)
                self.ts_strikes_below_spin.setValue(self.ts_strikes_below)
                self.ts_chain_drift_spin.setValue(self.ts_chain_drift_threshold)
                
                # Update Master Settings UI
                self.vix_threshold_spin.setValue(self.vix_threshold)
                self.time_stop_spin.setValue(self.time_stop)
                self.target_delta_spin.setValue(self.target_delta)
                self.max_risk_spin.setValue(self.max_risk)
                self.trade_qty_spin.setValue(self.trade_qty)
                
                if self.position_size_mode == "fixed":
                    self.fixed_radio.setChecked(True)
                else:
                    self.by_risk_radio.setChecked(True)
                
                # Update Straddle UI
                self.straddle_frequency_spin.setValue(self.straddle_frequency)
                
                # Update Chart Settings UI
                self.confirm_ema_spin.setValue(self.confirm_ema_length)
                self.confirm_z_period_spin.setValue(self.confirm_z_period)
                self.confirm_z_threshold_spin.setValue(self.confirm_z_threshold)
                self.trade_ema_spin.setValue(self.trade_ema_length)
                self.trade_z_period_spin.setValue(self.trade_z_period)
                self.trade_z_threshold_spin.setValue(self.trade_z_threshold)
                
                # Note: Chart interval/days are NOT restored from settings
                # All charts default to: 1 min interval, 2 days of data, 12 hours view
                
                # Update button states
                self.update_strategy_button_states()
                self.update_straddle_button_states()
                self.on_position_mode_changed()  # Update enabled state of qty/risk fields
                
                logger.info("Settings loaded successfully")
        except Exception as e:
            self.log_message(f"Error loading settings: {e}", "ERROR")
            logger.error(f"Error loading settings: {e}", exc_info=True)
    
    # ========================================================================
    # POSITION PERSISTENCE
    # ========================================================================
    
    def save_positions(self):
        """
        Save positions to JSON file to persist entryTime across restarts
        Called periodically and on app close
        """
        try:
            positions_data = {}
            for contract_key, pos in self.positions.items():
                # Serialize position with entryTime as ISO string
                positions_data[contract_key] = {
                    'position': pos['position'],
                    'avgCost': pos['avgCost'],
                    'entryTime': pos.get('entryTime', datetime.now()).isoformat()
                }
            
            Path('positions.json').write_text(json.dumps(positions_data, indent=2))
            logger.debug(f"Saved {len(positions_data)} positions to positions.json")
        except Exception as e:
            logger.error(f"Error saving positions: {e}", exc_info=True)
    
    def load_positions(self):
        """
        Load positions from JSON file on startup
        Merges with IBKR positions to preserve entryTime
        """
        try:
            if Path('positions.json').exists():
                positions_data = json.loads(Path('positions.json').read_text())
                logger.info(f"Loaded {len(positions_data)} positions from positions.json")
                
                # Store loaded positions for merging when IBKR positions arrive
                self.saved_positions = {}
                for contract_key, pos_data in positions_data.items():
                    # Parse ISO datetime string back to datetime object
                    entry_time = datetime.fromisoformat(pos_data['entryTime'])
                    self.saved_positions[contract_key] = {
                        'position': pos_data['position'],
                        'avgCost': pos_data['avgCost'],
                        'entryTime': entry_time
                    }
                
                logger.debug(f"Saved positions loaded: {list(self.saved_positions.keys())}")
        except Exception as e:
            logger.error(f"Error loading positions: {e}", exc_info=True)
            self.saved_positions = {}
    
    def merge_saved_positions(self, contract_key: str):
        """
        Merge saved position entryTime with IBKR position
        Called when IBKR position callback arrives
        """
        if hasattr(self, 'saved_positions') and contract_key in self.saved_positions:
            saved_pos = self.saved_positions[contract_key]
            if contract_key in self.positions:
                # Preserve entryTime from saved data
                self.positions[contract_key]['entryTime'] = saved_pos['entryTime']
                logger.info(f"Restored entryTime for {contract_key}: {saved_pos['entryTime'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ========================================================================
    # WINDOW LIFECYCLE
    # ========================================================================
    
    def cleanup_all_connections(self):
        """Comprehensive cleanup of all IBKR connections, subscriptions, and threads"""
        self.log_message("Starting comprehensive cleanup...", "INFO")
        logger.info("="*60)
        logger.info("CLEANUP: Comprehensive disconnection initiated")
        logger.info("="*60)
        
        try:
            # Cancel all market data subscriptions
            if self.app_state.get('market_data_map'):
                req_ids = list(self.app_state['market_data_map'].keys())
                self.log_message(f"Cancelling {len(req_ids)} market data subscriptions...", "INFO")
                for req_id in req_ids:
                    try:
                        self.ibkr_client.cancelMktData(req_id)
                        logger.debug(f"Cancelled market data reqId: {req_id}")
                    except Exception as e:
                        logger.debug(f"Error cancelling reqId {req_id}: {e}")
                self.app_state['market_data_map'].clear()
                if 'active_option_req_ids' in self.app_state:
                    self.app_state['active_option_req_ids'].clear()
            
            # Cancel all historical data requests
            if self.app_state.get('historical_data_requests'):
                req_ids = list(self.app_state['historical_data_requests'].keys())
                self.log_message(f"Cancelling {len(req_ids)} historical data requests...", "INFO")
                for req_id in req_ids:
                    try:
                        self.ibkr_client.cancelHistoricalData(req_id)
                        logger.debug(f"Cancelled historical data reqId: {req_id}")
                    except Exception as e:
                        logger.debug(f"Error cancelling historical reqId {req_id}: {e}")
                self.app_state['historical_data_requests'].clear()
            
            # Cancel position subscription
            try:
                self.log_message("Cancelling position subscription...", "INFO")
                self.ibkr_client.cancelPositions()
            except Exception as e:
                logger.debug(f"Error cancelling positions: {e}")
            
            # Cancel any pending orders
            if self.pending_orders:
                self.log_message(f"Cancelling {len(self.pending_orders)} pending orders...", "INFO")
                for order_id in list(self.pending_orders.keys()):
                    try:
                        self.ibkr_client.cancelOrder(order_id)
                        logger.debug(f"Cancelled order: {order_id}")
                    except Exception as e:
                        logger.debug(f"Error cancelling order {order_id}: {e}")
                self.pending_orders.clear()
            
            # Disconnect from IBKR
            try:
                self.log_message("Disconnecting from IBKR...", "INFO")
                self.ibkr_client.disconnect()
            except Exception as e:
                logger.debug(f"Error during disconnect: {e}")
            
            # Stop the API thread
            if self.ibkr_thread and self.ibkr_thread.isRunning():
                self.log_message("Waiting for API thread to terminate...", "INFO")
                if self.ibkr_thread.wait(2000):  # 2 second timeout
                    self.log_message("API thread terminated successfully", "SUCCESS")
                else:
                    self.log_message("API thread did not terminate cleanly (timeout)", "WARNING")
                    logger.warning("IBKR thread did not terminate within 2 seconds")
            
            self.connection_state = ConnectionState.DISCONNECTED
            self.log_message("Cleanup completed successfully", "SUCCESS")
            logger.info("CLEANUP: Completed successfully")
            logger.info("="*60)
            
        except Exception as e:
            self.log_message(f"Error during cleanup: {str(e)}", "ERROR")
            logger.error(f"Cleanup error: {e}", exc_info=True)
    
    # ========================================================================
    # VEGA DELTA NEUTRAL STRATEGY METHODS
    # ========================================================================
    
    def on_vega_strategy_toggle(self, state):
        """Handle vega strategy enable/disable toggle"""
        self.vega_strategy_enabled = (state == Qt.CheckState.Checked.value)
        status = "ENABLED" if self.vega_strategy_enabled else "DISABLED"
        self.log_message(f"Vega Strategy: {status}", "INFO")
        logger.info(f"Vega strategy toggled: {status}")
        
        if self.vega_strategy_enabled:
            self.log_message("Vega strategy is now active. Use 'Scan for Opportunities' to find trades.", "SUCCESS")
        else:
            self.log_message("Vega strategy is now inactive.", "INFO")
    
    def on_auto_hedge_toggle(self, state):
        """Handle auto delta hedging enable/disable toggle"""
        self.auto_hedge_enabled = (state == Qt.CheckState.Checked.value)
        status = "ENABLED" if self.auto_hedge_enabled else "DISABLED"
        self.log_message(f"Auto Delta Hedging: {status}", "INFO")
        logger.info(f"Auto delta hedging toggled: {status}")
        
        if self.auto_hedge_enabled:
            self.log_message("Auto hedging active. Portfolio delta will be monitored continuously.", "SUCCESS")
            # Start monitoring timer
            QTimer.singleShot(5000, self.monitor_portfolio_delta)
        else:
            self.log_message("Auto hedging disabled. Use manual hedge button when needed.", "INFO")
    
    def scan_vega_opportunities(self):
        """Scan the option chain for vega trading opportunities"""
        try:
            if not self.connection_state == ConnectionState.CONNECTED:
                self.log_message("Cannot scan: Not connected to IBKR", "ERROR")
                return
            
            if not self.current_expiry:
                self.log_message("Cannot scan: No expiry selected", "ERROR")
                return
            
            self.log_message("🔍 Scanning for vega opportunities...", "INFO")
            logger.info("Starting vega opportunity scan")
            
            # Clear previous results
            self.vega_scan_results.clear()
            self.vega_scanner_table.setRowCount(0)
            
            # Get current ATM strike using delta method
            atm_strike = self.find_atm_strike_by_delta()
            
            if not atm_strike or atm_strike == 0:
                # Fallback to ES-adjusted price
                atm_strike = self.get_adjusted_es_price()
            
            if not atm_strike or atm_strike == 0:
                self.log_message("Cannot determine ATM strike for scan", "ERROR")
                return
            
            # Scan logic: Look for strangles around ATM
            # Typically 5-10 delta OTM options (about 1-2 strikes away from ATM)
            strike_increment = self.instrument['strike_increment']
            
            # Find put and call strikes for strangle
            put_strike = atm_strike - (2 * strike_increment)
            call_strike = atm_strike + (2 * strike_increment)
            
            # Build contract keys
            put_key = f"{self.instrument['options_symbol']}_{put_strike}_P_{self.current_expiry}"
            call_key = f"{self.instrument['options_symbol']}_{call_strike}_C_{self.current_expiry}"
            
            # Get market data for both legs
            put_data = self.market_data.get(put_key, {})
            call_data = self.market_data.get(call_key, {})
            
            put_mid = (put_data.get('bid', 0) + put_data.get('ask', 0)) / 2 if put_data.get('bid') and put_data.get('ask') else 0
            call_mid = (call_data.get('bid', 0) + call_data.get('ask', 0)) / 2 if call_data.get('bid') and call_data.get('ask') else 0
            
            if put_mid == 0 or call_mid == 0:
                self.log_message("Insufficient market data for scan. Ensure chain is loaded.", "WARNING")
                return
            
            total_cost = put_mid + call_mid
            
            # Get IV values
            put_iv = put_data.get('impliedVolatility', 0) * 100
            call_iv = call_data.get('impliedVolatility', 0) * 100
            avg_iv = (put_iv + call_iv) / 2 if put_iv and call_iv else 0
            
            # For now, calculate simple IV rank (would need historical data for true IV rank)
            # Placeholder: assume IV rank based on absolute IV level
            iv_rank = "Low" if avg_iv < 15 else ("Medium" if avg_iv < 25 else "High")
            
            # Add to results
            result = {
                'expiry': self.current_expiry,
                'iv_rank': iv_rank,
                'put_strike': put_strike,
                'put_iv': put_iv,
                'call_strike': call_strike,
                'call_iv': call_iv,
                'total_cost': total_cost,
                'put_key': put_key,
                'call_key': call_key
            }
            
            self.vega_scan_results.append(result)
            
            # Update scanner table
            self.update_vega_scanner_table()
            
            self.log_message(f"✅ Scan complete. Found {len(self.vega_scan_results)} opportunity(ies)", "SUCCESS")
            logger.info(f"Vega scan complete: {len(self.vega_scan_results)} results")
            
        except Exception as e:
            logger.error(f"Error in scan_vega_opportunities: {e}", exc_info=True)
            self.log_message(f"Scan error: {e}", "ERROR")
    
    def update_vega_scanner_table(self):
        """Update the vega scanner results table"""
        try:
            self.vega_scanner_table.setRowCount(len(self.vega_scan_results))
            
            for row, result in enumerate(self.vega_scan_results):
                # Expiry
                self.vega_scanner_table.setItem(row, 0, QTableWidgetItem(result['expiry']))
                
                # IV Rank
                self.vega_scanner_table.setItem(row, 1, QTableWidgetItem(result['iv_rank']))
                
                # Put Strike
                self.vega_scanner_table.setItem(row, 2, QTableWidgetItem(f"{result['put_strike']:.1f}"))
                
                # Put IV
                self.vega_scanner_table.setItem(row, 3, QTableWidgetItem(f"{result['put_iv']:.1f}%"))
                
                # Call Strike
                self.vega_scanner_table.setItem(row, 4, QTableWidgetItem(f"{result['call_strike']:.1f}"))
                
                # Call IV
                self.vega_scanner_table.setItem(row, 5, QTableWidgetItem(f"{result['call_iv']:.1f}%"))
                
                # Total Cost
                self.vega_scanner_table.setItem(row, 6, QTableWidgetItem(f"${result['total_cost']:.2f}"))
                
                # Action button
                enter_btn = QPushButton("Enter Trade")
                enter_btn.clicked.connect(lambda checked, r=result: self.enter_vega_trade(r))
                self.vega_scanner_table.setCellWidget(row, 7, enter_btn)
        
        except Exception as e:
            logger.error(f"Error updating vega scanner table: {e}", exc_info=True)
    
    def enter_vega_trade(self, result):
        """Enter a vega delta neutral trade (long strangle + delta hedge)"""
        try:
            if not self.vega_strategy_enabled:
                self.log_message("Vega strategy is not enabled", "WARNING")
                return
            
            self.log_message(f"🎯 Entering vega trade: {result['put_strike']}/{result['call_strike']} strangle", "INFO")
            logger.info(f"Entering vega trade: {result}")
            
            # Generate unique trade ID
            trade_id = f"VEGA_{int(datetime.now().timestamp())}"
            
            # Place orders for both legs (long strangle)
            quantity = 1  # Start with 1 contract each
            
            # Buy Put
            put_data = self.market_data.get(result['put_key'], {})
            put_mid = (put_data.get('bid', 0) + put_data.get('ask', 0)) / 2 if put_data.get('bid') and put_data.get('ask') else 0
            
            if put_mid > 0:
                self.place_order(result['put_key'], "BUY", quantity, put_mid, enable_chasing=True)
                self.log_message(f"  ✓ BUY {quantity} PUT @ {result['put_strike']}", "SUCCESS")
            else:
                self.log_message("Cannot enter: No put price", "ERROR")
                return
            
            # Buy Call
            call_data = self.market_data.get(result['call_key'], {})
            call_mid = (call_data.get('bid', 0) + call_data.get('ask', 0)) / 2 if call_data.get('bid') and call_data.get('ask') else 0
            
            if call_mid > 0:
                self.place_order(result['call_key'], "BUY", quantity, call_mid, enable_chasing=True)
                self.log_message(f"  ✓ BUY {quantity} CALL @ {result['call_strike']}", "SUCCESS")
            else:
                self.log_message("Cannot enter: No call price", "ERROR")
                return
            
            # Store vega position
            self.vega_positions[trade_id] = {
                'entry_time': datetime.now().strftime('%H:%M:%S'),
                'put_key': result['put_key'],
                'call_key': result['call_key'],
                'put_strike': result['put_strike'],
                'call_strike': result['call_strike'],
                'put_qty': quantity,
                'call_qty': quantity,
                'hedge_shares': 0,  # Will be calculated and set by delta hedge
                'entry_cost': result['total_cost'] * quantity * self.instrument['multiplier']
            }
            
            self.log_message(f"✅ Vega trade entered: {trade_id}", "SUCCESS")
            
            # Execute initial delta hedge
            QTimer.singleShot(2000, lambda: self.calculate_and_hedge_delta(trade_id))
            
            # Update display
            self.update_vega_positions_table()
            
        except Exception as e:
            logger.error(f"Error entering vega trade: {e}", exc_info=True)
            self.log_message(f"Error entering trade: {e}", "ERROR")
    
    def place_mes_hedge_order(self, action: str, quantity: int, trade_id: Optional[str] = None):
        """
        Place MES futures hedge order.
        
        Args:
            action: "BUY" or "SELL"
            quantity: Number of MES contracts
            trade_id: Optional trade ID to associate hedge with specific vega position
            
        Returns:
            bool: True if order placed successfully, False otherwise
        """
        try:
            if self.connection_state != ConnectionState.CONNECTED:
                self.log_message("Cannot place hedge: Not connected to IBKR", "ERROR")
                return False
            
            if not self.mes_contract:
                self.log_message("MES contract not initialized. Subscribing now...", "WARNING")
                self.subscribe_mes_price()
                QTimer.singleShot(2000, lambda: self.place_mes_hedge_order(action, quantity, trade_id))
                return False
            
            if self.next_order_id is None:
                self.log_message("Cannot place hedge: No order ID available", "ERROR")
                return False
            
            # Create order
            order = Order()
            order.action = action
            order.orderType = "MKT"  # Market order for immediate execution
            order.totalQuantity = quantity
            order.transmit = True
            
            # Get order ID
            order_id = self.next_order_id
            self.next_order_id += 1
            
            # Track hedge order
            self.hedge_orders[order_id] = {
                'trade_id': trade_id,
                'action': action,
                'quantity': quantity,
                'contract': self.mes_contract.symbol,
                'month': self.mes_contract.lastTradeDateOrContractMonth,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
            
            # Place order
            self.ibkr_client.placeOrder(order_id, self.mes_contract, order)
            
            logger.info(f"MES hedge order placed: ID={order_id}, {action} {quantity} {self.mes_contract.symbol} {self.mes_contract.lastTradeDateOrContractMonth}")
            self.log_message(f"🛡️ Hedge order #{order_id}: {action} {quantity} MES", "INFO")
            
            return True
            
        except Exception as e:
            logger.error(f"Error placing MES hedge order: {e}", exc_info=True)
            self.log_message(f"Error placing hedge: {e}", "ERROR")
            return False
    
    def calculate_and_hedge_delta(self, trade_id):
        """Calculate portfolio delta and place hedge order"""
        try:
            if trade_id not in self.vega_positions:
                logger.warning(f"Trade ID {trade_id} not found in vega positions")
                return
            
            position = self.vega_positions[trade_id]
            
            # Get greeks for both legs
            put_data = self.market_data.get(position['put_key'], {})
            call_data = self.market_data.get(position['call_key'], {})
            
            put_delta = put_data.get('delta', 0)
            call_delta = call_data.get('delta', 0)
            
            # Calculate position delta (per contract)
            position_delta = (put_delta * position['put_qty']) + (call_delta * position['call_qty'])
            
            # Multiply by multiplier to get actual delta
            total_delta = position_delta * self.instrument['multiplier']
            
            self.log_message(f"Position delta: {total_delta:.2f}", "INFO")
            
            # Calculate shares needed to hedge
            # To neutralize delta, we need to short if delta is positive, long if negative
            shares_needed = -int(total_delta)  # Negative of delta, rounded to nearest share
            
            if shares_needed == 0:
                self.log_message("Delta already neutral (< 1 share needed)", "INFO")
                return
            
            # Determine action
            action = "BUY" if shares_needed > 0 else "SELL"
            shares = abs(shares_needed)
            
            self.log_message(f"🛡️ Delta hedge required: {total_delta:.2f} delta", "INFO")
            
            # Calculate MES contracts needed
            # XSP option delta (100 multiplier) / MES multiplier (5) = MES contracts
            # Example: 50 delta / 5 = 10 MES contracts
            mes_contracts_raw = total_delta / self.instrument['hedge_multiplier']
            mes_contracts = int(round(mes_contracts_raw))
            
            if mes_contracts == 0:
                self.log_message("Delta already neutral (< 1 MES contract needed)", "INFO")
                position['hedge_contracts'] = 0
                self.vega_positions[trade_id] = position
                self.update_vega_positions_table()
                return
            
            # Determine action (opposite of delta to neutralize)
            # Positive delta = bullish exposure → SELL MES to neutralize
            # Negative delta = bearish exposure → BUY MES to neutralize
            action = "SELL" if mes_contracts > 0 else "BUY"
            quantity = abs(mes_contracts)
            
            mes_month = self.mes_contract.lastTradeDateOrContractMonth if self.mes_contract else "pending"
            self.log_message(f"📊 Calculated hedge: {action} {quantity} MES contracts ({mes_month})", "INFO")
            
            # Place MES hedge order
            success = self.place_mes_hedge_order(action, quantity, trade_id)
            
            if success:
                # Update position record with actual hedge placed
                position['hedge_contracts'] = -mes_contracts  # Store negative for SELL, positive for BUY
                position['hedge_symbol'] = self.mes_contract.symbol if self.mes_contract else "MES"
                position['hedge_month'] = self.mes_contract.lastTradeDateOrContractMonth if self.mes_contract else mes_month
                self.vega_positions[trade_id] = position
                self.log_message(f"✅ Hedge order placed: {action} {quantity} MES", "SUCCESS")
            else:
                self.log_message(f"❌ Failed to place hedge order", "ERROR")
            
            # Update display
            self.update_vega_positions_table()
            
        except Exception as e:
            logger.error(f"Error calculating delta hedge: {e}", exc_info=True)
            self.log_message(f"Error calculating hedge: {e}", "ERROR")
    
    def manual_delta_hedge(self):
        """Manually execute delta hedge for all vega positions"""
        try:
            if not self.vega_positions:
                self.log_message("No active vega positions to hedge", "INFO")
                return
            
            self.log_message("⚖️ Executing manual delta hedge...", "INFO")
            
            # Calculate total portfolio delta from all vega positions
            total_delta = 0
            
            for trade_id, position in self.vega_positions.items():
                put_data = self.market_data.get(position['put_key'], {})
                call_data = self.market_data.get(position['call_key'], {})
                
                put_delta = put_data.get('delta', 0) * position['put_qty']
                call_delta = call_data.get('delta', 0) * position['call_qty']
                
                total_delta += (put_delta + call_delta) * self.instrument['multiplier']
            
            self.log_message(f"Total portfolio delta: {total_delta:.2f}", "INFO")
            
            # Update portfolio greeks display
            self.portfolio_greeks['delta'] = total_delta
            self.update_portfolio_greeks_display()
            
            # Calculate hedge needed
            shares_needed = -int(total_delta)
            
            if abs(shares_needed) < 1:
                self.log_message("✅ Portfolio already delta neutral", "SUCCESS")
                return
            
            # Calculate MES contracts needed
            mes_contracts_raw = total_delta / self.instrument['hedge_multiplier']
            mes_contracts = int(round(mes_contracts_raw))
            
            if mes_contracts == 0:
                self.log_message("✅ Portfolio already delta neutral (< 1 MES contract)", "SUCCESS")
                return
            
            # Determine action
            action = "SELL" if mes_contracts > 0 else "BUY"
            quantity = abs(mes_contracts)
            
            self.log_message(f"📊 Portfolio hedge: {action} {quantity} MES contracts (Δ={total_delta:.2f})", "INFO")
            
            # Place aggregate hedge order (not tied to specific trade)
            success = self.place_mes_hedge_order(action, quantity, trade_id=None)
            
            if success:
                self.log_message(f"✅ Portfolio hedge placed: {action} {quantity} MES", "SUCCESS")
            else:
                self.log_message(f"❌ Failed to place portfolio hedge", "ERROR")
            
        except Exception as e:
            logger.error(f"Error in manual_delta_hedge: {e}", exc_info=True)
            self.log_message(f"Error executing hedge: {e}", "ERROR")
    
    def monitor_portfolio_delta(self):
        """Continuously monitor portfolio delta and auto-hedge if needed"""
        try:
            if not self.auto_hedge_enabled or not self.vega_positions:
                # Stop monitoring if auto-hedge disabled or no positions
                return
            
            # Calculate current portfolio delta
            total_delta = 0
            for trade_id, position in self.vega_positions.items():
                put_data = self.market_data.get(position['put_key'], {})
                call_data = self.market_data.get(position['call_key'], {})
                
                put_delta = put_data.get('delta', 0) * position['put_qty']
                call_delta = call_data.get('delta', 0) * position['call_qty']
                
                total_delta += (put_delta + call_delta) * self.instrument['multiplier']
            
            self.portfolio_greeks['delta'] = total_delta
            self.update_portfolio_greeks_display()
            
            # Check if rehedge needed
            threshold = self.max_delta_threshold_spin.value()
            if abs(total_delta) > threshold:
                self.log_message(f"⚠️ Delta threshold breached: {total_delta:.2f} (threshold: ±{threshold})", "WARNING")
                # Trigger auto-hedge
                # Note: This would place actual hedge orders
                self.manual_delta_hedge()
            
            # Schedule next check (every 30 seconds)
            if self.auto_hedge_enabled:
                QTimer.singleShot(30000, self.monitor_portfolio_delta)
            
        except Exception as e:
            logger.error(f"Error monitoring portfolio delta: {e}", exc_info=True)
    
    def update_portfolio_greeks_display(self):
        """Update the portfolio greeks display labels"""
        try:
            # Update labels with color coding
            delta = self.portfolio_greeks.get('delta', 0)
            self.portfolio_delta_label.setText(f"{delta:.2f}")
            
            # Color code delta (green if near zero, yellow if moderate, red if high)
            if abs(delta) < 5:
                self.portfolio_delta_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #00ff00;")
            elif abs(delta) < 15:
                self.portfolio_delta_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #ffff00;")
            else:
                self.portfolio_delta_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #ff0000;")
            
            # Update other greeks
            self.portfolio_gamma_label.setText(f"{self.portfolio_greeks.get('gamma', 0):.2f}")
            self.portfolio_vega_label.setText(f"{self.portfolio_greeks.get('vega', 0):.2f}")
            self.portfolio_theta_label.setText(f"{self.portfolio_greeks.get('theta', 0):.2f}")
            
        except Exception as e:
            logger.error(f"Error updating portfolio greeks display: {e}", exc_info=True)
    
    def update_vega_positions_table(self):
        """Update the active vega positions table"""
        try:
            self.vega_positions_table.setRowCount(len(self.vega_positions))
            
            row = 0
            for trade_id, position in self.vega_positions.items():
                # Trade ID
                self.vega_positions_table.setItem(row, 0, QTableWidgetItem(trade_id))
                
                # Entry Time
                self.vega_positions_table.setItem(row, 1, QTableWidgetItem(position['entry_time']))
                
                # Put
                put_str = f"{position['put_strike']} x{position['put_qty']}"
                self.vega_positions_table.setItem(row, 2, QTableWidgetItem(put_str))
                
                # Call
                call_str = f"{position['call_strike']} x{position['call_qty']}"
                self.vega_positions_table.setItem(row, 3, QTableWidgetItem(call_str))
                
                # Hedge MES Contracts (show with sign: -10 = short 10, +10 = long 10)
                hedge_contracts = position.get('hedge_contracts', 0)
                hedge_str = f"{hedge_contracts:+d} MES" if hedge_contracts != 0 else "None"
                self.vega_positions_table.setItem(row, 4, QTableWidgetItem(hedge_str))
                
                # Get current greeks
                put_data = self.market_data.get(position['put_key'], {})
                call_data = self.market_data.get(position['call_key'], {})
                
                put_delta = put_data.get('delta', 0) * position['put_qty']
                call_delta = call_data.get('delta', 0) * position['call_qty']
                pos_delta = (put_delta + call_delta) * self.instrument['multiplier']
                
                put_gamma = put_data.get('gamma', 0) * position['put_qty']
                call_gamma = call_data.get('gamma', 0) * position['call_qty']
                pos_gamma = (put_gamma + call_gamma) * self.instrument['multiplier']
                
                put_vega = put_data.get('vega', 0) * position['put_qty']
                call_vega = call_data.get('vega', 0) * position['call_qty']
                pos_vega = (put_vega + call_vega) * self.instrument['multiplier']
                
                put_theta = put_data.get('theta', 0) * position['put_qty']
                call_theta = call_data.get('theta', 0) * position['call_qty']
                pos_theta = (put_theta + call_theta) * self.instrument['multiplier']
                
                # Portfolio Greeks
                self.vega_positions_table.setItem(row, 5, QTableWidgetItem(f"{pos_delta:.2f}"))
                self.vega_positions_table.setItem(row, 6, QTableWidgetItem(f"{pos_gamma:.2f}"))
                self.vega_positions_table.setItem(row, 7, QTableWidgetItem(f"{pos_vega:.2f}"))
                self.vega_positions_table.setItem(row, 8, QTableWidgetItem(f"{pos_theta:.2f}"))
                
                # Calculate P&L
                put_mid = (put_data.get('bid', 0) + put_data.get('ask', 0)) / 2 if put_data.get('bid') and put_data.get('ask') else 0
                call_mid = (call_data.get('bid', 0) + call_data.get('ask', 0)) / 2 if call_data.get('bid') and call_data.get('ask') else 0
                
                current_value = (put_mid * position['put_qty'] + call_mid * position['call_qty']) * self.instrument['multiplier']
                pnl = current_value - position.get('entry_cost', 0)
                
                pnl_item = QTableWidgetItem(f"${pnl:.2f}")
                if pnl > 0:
                    pnl_item.setForeground(QColor(0, 255, 0))  # Green for profit
                else:
                    pnl_item.setForeground(QColor(255, 0, 0))  # Red for loss
                self.vega_positions_table.setItem(row, 9, pnl_item)
                
                # Action button (Close)
                close_btn = QPushButton("Close")
                close_btn.clicked.connect(lambda checked, tid=trade_id: self.close_vega_position(tid))
                self.vega_positions_table.setCellWidget(row, 10, close_btn)
                
                row += 1
        
        except Exception as e:
            logger.error(f"Error updating vega positions table: {e}", exc_info=True)
    
    def close_vega_position(self, trade_id):
        """Close a vega position (sell both legs)"""
        try:
            if trade_id not in self.vega_positions:
                self.log_message(f"Position {trade_id} not found", "ERROR")
                return
            
            position = self.vega_positions[trade_id]
            
            self.log_message(f"🔴 Closing vega position: {trade_id}", "INFO")
            
            # Sell Put
            put_data = self.market_data.get(position['put_key'], {})
            put_mid = (put_data.get('bid', 0) + put_data.get('ask', 0)) / 2 if put_data.get('bid') and put_data.get('ask') else 0
            
            if put_mid > 0:
                self.place_order(position['put_key'], "SELL", position['put_qty'], put_mid, enable_chasing=True)
                self.log_message(f"  ✓ SELL {position['put_qty']} PUT @ {position['put_strike']}", "SUCCESS")
            
            # Sell Call
            call_data = self.market_data.get(position['call_key'], {})
            call_mid = (call_data.get('bid', 0) + call_data.get('ask', 0)) / 2 if call_data.get('bid') and call_data.get('ask') else 0
            
            if call_mid > 0:
                self.place_order(position['call_key'], "SELL", position['call_qty'], call_mid, enable_chasing=True)
                self.log_message(f"  ✓ SELL {position['call_qty']} CALL @ {position['call_strike']}", "SUCCESS")
            
            # Close MES hedge position automatically
            hedge_contracts = position.get('hedge_contracts', 0)
            if hedge_contracts != 0:
                # Opposite action to close
                # If we SOLD MES (negative contracts), we need to BUY to close
                # If we BOUGHT MES (positive contracts), we need to SELL to close
                close_action = "BUY" if hedge_contracts < 0 else "SELL"
                close_quantity = abs(hedge_contracts)
                
                self.log_message(f"🛡️ Closing hedge: {close_action} {close_quantity} MES", "INFO")
                success = self.place_mes_hedge_order(close_action, close_quantity, trade_id)
                
                if success:
                    self.log_message(f"  ✓ Hedge closed: {close_action} {close_quantity} MES", "SUCCESS")
                else:
                    self.log_message(f"  ❌ Failed to close hedge - may need manual intervention", "WARNING")
            
            # Remove from active positions
            del self.vega_positions[trade_id]
            
            self.log_message(f"✅ Vega position fully closed: {trade_id}", "SUCCESS")
            
            # Update display
            self.update_vega_positions_table()
            
        except Exception as e:
            logger.error(f"Error closing vega position: {e}", exc_info=True)
            self.log_message(f"Error closing position: {e}", "ERROR")
    
    # ========================================================================
    # END VEGA DELTA NEUTRAL STRATEGY METHODS
    # ========================================================================
    
    # ========================================================================
    # LONG STRADDLES STRATEGY METHODS
    # ========================================================================
    
    def on_straddle_strategy_toggle(self, state):
        """Handle straddle strategy enable/disable toggle"""
        self.straddle_strategy_enabled = (state == Qt.CheckState.Checked.value)
        status = "ENABLED" if self.straddle_strategy_enabled else "DISABLED"
        self.log_message(f"Long Straddles Strategy: {status}", "INFO")
        logger.info(f"Straddle strategy toggled: {status}")
    
    def on_straddle_otm_changed(self, value):
        """Handle OTM strikes setting change"""
        self.straddle_otm_strikes = value
        self.log_message(f"Straddle OTM strikes set to: {value}", "INFO")
        self.update_straddle_strike_display()
    
    def get_straddle_strikes(self):
        """
        Get the call and put strikes for straddle entry based on OTM setting.
        
        Returns:
            tuple: (call_strike, put_strike, atm_strike) or (None, None, None) if not available
        """
        try:
            # Find ATM strike from delta
            atm_strike = self.find_atm_strike_by_delta()
            
            if atm_strike == 0:
                return None, None, None
            
            strike_increment = self.instrument['strike_increment']
            otm_offset = self.straddle_otm_strikes * strike_increment
            
            # Call strike: ATM + offset (OTM calls are above ATM)
            call_strike = atm_strike + otm_offset
            
            # Put strike: ATM - offset (OTM puts are below ATM)
            put_strike = atm_strike - otm_offset
            
            return call_strike, put_strike, atm_strike
        
        except Exception as e:
            logger.error(f"Error calculating straddle strikes: {e}")
            return None, None, None
    
    def update_straddle_strike_display(self):
        """Update the strike selection display with current prices and greeks"""
        try:
            # Safety check: ensure widgets exist
            if not hasattr(self, 'straddle_atm_label'):
                return
            
            call_strike, put_strike, atm_strike = self.get_straddle_strikes()
            
            if call_strike is None:
                # No data available yet
                logger.debug("Straddle: No ATM strike available yet (waiting for market data)")
                self.straddle_atm_label.setText("--")
                self.straddle_call_strike_label.setText("--")
                self.straddle_put_strike_label.setText("--")
                self.straddle_call_iv_label.setText("--")
                self.straddle_call_delta_label.setText("--")
                self.straddle_call_price_label.setText("--")
                self.straddle_put_iv_label.setText("--")
                self.straddle_put_delta_label.setText("--")
                self.straddle_put_price_label.setText("--")
                self.straddle_total_cost_label.setText("--")
                self.straddle_max_risk_label.setText("--")
                return
            
            logger.debug(f"Straddle: ATM={atm_strike:.0f}, Call={call_strike:.0f}, Put={put_strike:.0f}")
            
            # Update ATM
            self.straddle_atm_label.setText(f"{atm_strike:.0f}")
            
            # Get call data
            call_key = f"{self.instrument['options_symbol']}_{call_strike:.0f}_C_{self.current_expiry}"
            call_data = self.market_data.get(call_key, {})
            call_bid = call_data.get('bid', 0)
            call_ask = call_data.get('ask', 0)
            call_mid = (call_bid + call_ask) / 2 if call_bid and call_ask else 0
            call_iv = call_data.get('iv', 0)
            call_delta = call_data.get('delta', 0)
            
            # Update call display
            self.straddle_call_strike_label.setText(f"{call_strike:.0f}")
            self.straddle_call_iv_label.setText(f"{call_iv*100:.1f}%" if call_iv > 0 else "--")
            self.straddle_call_delta_label.setText(f"{call_delta:.3f}" if call_delta != 0 else "--")
            self.straddle_call_price_label.setText(f"${call_mid:.2f}" if call_mid > 0 else "--")
            
            # Get put data
            put_key = f"{self.instrument['options_symbol']}_{put_strike:.0f}_P_{self.current_expiry}"
            put_data = self.market_data.get(put_key, {})
            put_bid = put_data.get('bid', 0)
            put_ask = put_data.get('ask', 0)
            put_mid = (put_bid + put_ask) / 2 if put_bid and put_ask else 0
            put_iv = put_data.get('iv', 0)
            put_delta = put_data.get('delta', 0)
            
            # Update put display
            self.straddle_put_strike_label.setText(f"{put_strike:.0f}")
            self.straddle_put_iv_label.setText(f"{put_iv*100:.1f}%" if put_iv > 0 else "--")
            self.straddle_put_delta_label.setText(f"{put_delta:.3f}" if put_delta != 0 else "--")
            self.straddle_put_price_label.setText(f"${put_mid:.2f}" if put_mid > 0 else "--")
            
            # Calculate totals
            if call_mid > 0 and put_mid > 0:
                qty = self.straddle_qty_spin.value()
                total_cost = (call_mid + put_mid) * qty * self.instrument['multiplier']
                max_risk = total_cost  # Max risk for long straddle is premium paid
                
                self.straddle_total_cost_label.setText(f"${total_cost:.2f}")
                self.straddle_max_risk_label.setText(f"${max_risk:.2f}")
            else:
                self.straddle_total_cost_label.setText("--")
                self.straddle_max_risk_label.setText("--")
        
        except Exception as e:
            logger.error(f"Error updating straddle strike display: {e}")
    
    def enter_straddle_position(self):
        """Enter a long straddle position"""
        try:
            if not self.straddle_strategy_enabled:
                self.log_message("❌ Straddle strategy not enabled", "WARNING")
                return
            
            if self.connection_state != ConnectionState.CONNECTED:
                self.log_message("❌ Not connected to IBKR", "WARNING")
                return
            
            # Get strikes
            call_strike, put_strike, atm_strike = self.get_straddle_strikes()
            
            if call_strike is None:
                self.log_message("❌ Cannot determine strikes - wait for market data", "WARNING")
                return
            
            # Get market data
            call_key = f"{self.instrument['options_symbol']}_{call_strike:.0f}_C_{self.current_expiry}"
            put_key = f"{self.instrument['options_symbol']}_{put_strike:.0f}_P_{self.current_expiry}"
            
            call_data = self.market_data.get(call_key, {})
            put_data = self.market_data.get(put_key, {})
            
            call_bid = call_data.get('bid', 0)
            call_ask = call_data.get('ask', 0)
            put_bid = put_data.get('bid', 0)
            put_ask = put_data.get('ask', 0)
            
            if not all([call_bid, call_ask, put_bid, put_ask]):
                self.log_message("❌ Missing market data for strikes", "WARNING")
                return
            
            # Calculate mid prices
            call_mid = (call_bid + call_ask) / 2
            put_mid = (put_bid + put_ask) / 2
            
            qty = self.straddle_qty_spin.value()
            
            # Generate trade ID
            trade_id = f"STRAD_{self.straddle_trade_counter:04d}"
            self.straddle_trade_counter += 1
            
            self.log_message(f"🎯 Entering Long Straddle: {trade_id}", "INFO")
            self.log_message(f"  ATM: {atm_strike:.0f}, Call: {call_strike:.0f}, Put: {put_strike:.0f}", "INFO")
            
            # Buy Call
            self.place_order(call_key, "BUY", qty, call_mid, enable_chasing=True)
            self.log_message(f"  ✓ BUY {qty} CALL @ {call_strike:.0f} (Mid: ${call_mid:.2f})", "SUCCESS")
            
            # Buy Put
            self.place_order(put_key, "BUY", qty, put_mid, enable_chasing=True)
            self.log_message(f"  ✓ BUY {qty} PUT @ {put_strike:.0f} (Mid: ${put_mid:.2f})", "SUCCESS")
            
            # Calculate entry cost
            entry_cost = (call_mid + put_mid) * qty * self.instrument['multiplier']
            
            # Store position
            self.straddle_positions[trade_id] = {
                'trade_id': trade_id,
                'entry_time': datetime.now(),
                'call_strike': call_strike,
                'call_key': call_key,
                'call_qty': qty,
                'call_entry_price': call_mid,
                'put_strike': put_strike,
                'put_key': put_key,
                'put_qty': qty,
                'put_entry_price': put_mid,
                'entry_cost': entry_cost,
                'atm_at_entry': atm_strike
            }
            
            self.log_message(f"✅ Straddle entered: Cost ${entry_cost:.2f}", "SUCCESS")
            
            # Update display
            self.update_straddle_positions_table()
        
        except Exception as e:
            logger.error(f"Error entering straddle position: {e}")
            self.log_message(f"Error entering straddle: {e}", "ERROR")
    
    def update_straddle_positions_table(self):
        """Update the straddle positions table with current data"""
        try:
            self.straddle_positions_table.setRowCount(0)
            
            for trade_id, position in self.straddle_positions.items():
                row = self.straddle_positions_table.rowCount()
                self.straddle_positions_table.insertRow(row)
                
                # Trade ID
                self.straddle_positions_table.setItem(row, 0, QTableWidgetItem(trade_id))
                
                # Entry Time
                entry_time_str = position['entry_time'].strftime("%H:%M:%S")
                self.straddle_positions_table.setItem(row, 1, QTableWidgetItem(entry_time_str))
                
                # Call Strike & Qty
                self.straddle_positions_table.setItem(row, 2, QTableWidgetItem(f"{position['call_strike']:.0f}"))
                self.straddle_positions_table.setItem(row, 3, QTableWidgetItem(str(position['call_qty'])))
                
                # Put Strike & Qty
                self.straddle_positions_table.setItem(row, 4, QTableWidgetItem(f"{position['put_strike']:.0f}"))
                self.straddle_positions_table.setItem(row, 5, QTableWidgetItem(str(position['put_qty'])))
                
                # Entry Cost
                entry_cost = position['entry_cost']
                cost_item = QTableWidgetItem(f"${entry_cost:.2f}")
                self.straddle_positions_table.setItem(row, 6, cost_item)
                
                # Get current market data
                call_data = self.market_data.get(position['call_key'], {})
                put_data = self.market_data.get(position['put_key'], {})
                
                call_bid = call_data.get('bid', 0)
                call_ask = call_data.get('ask', 0)
                put_bid = put_data.get('bid', 0)
                put_ask = put_data.get('ask', 0)
                
                # Calculate current value and P&L
                if all([call_bid, call_ask, put_bid, put_ask]):
                    call_mid = (call_bid + call_ask) / 2
                    put_mid = (put_bid + put_ask) / 2
                    
                    current_value = (call_mid * position['call_qty'] + put_mid * position['put_qty']) * self.instrument['multiplier']
                    pnl = current_value - entry_cost
                    pnl_pct = (pnl / entry_cost * 100) if entry_cost > 0 else 0
                    
                    # Current Value
                    value_item = QTableWidgetItem(f"${current_value:.2f}")
                    self.straddle_positions_table.setItem(row, 7, value_item)
                    
                    # P&L
                    pnl_item = QTableWidgetItem(f"${pnl:+.2f}")
                    pnl_item.setForeground(QColor("#00ff00") if pnl >= 0 else QColor("#ff4444"))
                    self.straddle_positions_table.setItem(row, 8, pnl_item)
                    
                    # P&L %
                    pnl_pct_item = QTableWidgetItem(f"{pnl_pct:+.1f}%")
                    pnl_pct_item.setForeground(QColor("#00ff00") if pnl_pct >= 0 else QColor("#ff4444"))
                    self.straddle_positions_table.setItem(row, 9, pnl_pct_item)
                    
                    # Greeks
                    call_delta = call_data.get('delta', 0)
                    put_delta = put_data.get('delta', 0)
                    call_gamma = call_data.get('gamma', 0)
                    put_gamma = put_data.get('gamma', 0)
                    call_vega = call_data.get('vega', 0)
                    put_vega = put_data.get('vega', 0)
                    call_theta = call_data.get('theta', 0)
                    put_theta = put_data.get('theta', 0)
                    
                    total_delta = (call_delta * position['call_qty'] + put_delta * position['put_qty'])
                    total_gamma = (call_gamma * position['call_qty'] + put_gamma * position['put_qty'])
                    total_vega = (call_vega * position['call_qty'] + put_vega * position['put_qty'])
                    total_theta = (call_theta * position['call_qty'] + put_theta * position['put_qty'])
                    
                    greeks_str = f"Δ:{total_delta:.2f} Γ:{total_gamma:.3f} V:{total_vega:.1f} Θ:{total_theta:.2f}"
                    self.straddle_positions_table.setItem(row, 10, QTableWidgetItem(greeks_str))
                else:
                    self.straddle_positions_table.setItem(row, 7, QTableWidgetItem("--"))
                    self.straddle_positions_table.setItem(row, 8, QTableWidgetItem("--"))
                    self.straddle_positions_table.setItem(row, 9, QTableWidgetItem("--"))
                    self.straddle_positions_table.setItem(row, 10, QTableWidgetItem("--"))
                
                # Close button
                close_btn = QPushButton("Close")
                close_btn.setStyleSheet("background-color: #8b0000; color: white;")
                close_btn.clicked.connect(lambda checked, tid=trade_id: self.close_straddle_position(tid))
                self.straddle_positions_table.setCellWidget(row, 11, close_btn)
        
        except Exception as e:
            logger.error(f"Error updating straddle positions table: {e}")
    
    def close_straddle_position(self, trade_id):
        """Close a straddle position (sell both legs)"""
        try:
            if trade_id not in self.straddle_positions:
                self.log_message(f"Position {trade_id} not found", "ERROR")
                return
            
            position = self.straddle_positions[trade_id]
            
            self.log_message(f"🔴 Closing straddle position: {trade_id}", "INFO")
            
            # Sell Call
            call_data = self.market_data.get(position['call_key'], {})
            call_mid = (call_data.get('bid', 0) + call_data.get('ask', 0)) / 2 if call_data.get('bid') and call_data.get('ask') else 0
            
            if call_mid > 0:
                self.place_order(position['call_key'], "SELL", position['call_qty'], call_mid, enable_chasing=True)
                self.log_message(f"  ✓ SELL {position['call_qty']} CALL @ {position['call_strike']:.0f}", "SUCCESS")
            
            # Sell Put
            put_data = self.market_data.get(position['put_key'], {})
            put_mid = (put_data.get('bid', 0) + put_data.get('ask', 0)) / 2 if put_data.get('bid') and put_data.get('ask') else 0
            
            if put_mid > 0:
                self.place_order(position['put_key'], "SELL", position['put_qty'], put_mid, enable_chasing=True)
                self.log_message(f"  ✓ SELL {position['put_qty']} PUT @ {position['put_strike']:.0f}", "SUCCESS")
            
            # Remove from active positions
            del self.straddle_positions[trade_id]
            
            self.log_message(f"✅ Straddle position fully closed: {trade_id}", "SUCCESS")
            
            # Update display
            self.update_straddle_positions_table()
        
        except Exception as e:
            logger.error(f"Error closing straddle position: {e}")
            self.log_message(f"Error closing position: {e}", "ERROR")
    
    # ========================================================================
    # END LONG STRADDLES STRATEGY METHODS
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
            # Save positions before closing
            self.save_positions()
            logger.info("Positions saved on app close")
            
            # Comprehensive cleanup
            if self.connection_state == ConnectionState.CONNECTED:
                self.cleanup_all_connections()
            
            a0.accept()  # type: ignore[union-attr]
            
            # Force exit
            logger.info("Application closing - forcing exit")
            sys.exit(0)
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
