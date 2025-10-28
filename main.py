"""
SPX 0DTE Options Trading Application - PyQt6 Edition
Professional Bloomberg-style GUI for Interactive Brokers API
Author: VJS World
Date: January 2025

Technology Stack:
- PyQt6: Modern GUI framework with native performance
- PyQt6-Charts: Native Qt candlestick charting for real-time visualization
- IBKR API: Real-time market data, order execution, and model-based greeks
- Dual-instrument support: SPX and XSP with symbol-agnostic architecture
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
import pytz  # For timezone-aware datetime (Eastern Time)


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
    QStatusBar, QGroupBox, QSpinBox, QDoubleSpinBox, QRadioButton, QButtonGroup, QScrollArea, QCheckBox
)
    from PyQt6.QtCore import (  # type: ignore[import-untyped]
        Qt, QTimer, pyqtSignal, QObject, QThread, pyqtSlot, QMargins, QMetaObject, Q_ARG
    )
    from PyQt6.QtGui import QColor, QFont, QPalette, QPainter  # type: ignore[import-untyped]
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

# Charts are now handled by matplotlib/mplfinance (see chart_widget_matplotlib.py)
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
        'description': 'S&P 500 Index Options (Full size, $100 multiplier)'
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
        'tick_size_above_3': 0.05,
        'tick_size_below_3': 0.05,
        'description': 'Mini-SPX Index Options (1/10 size of SPX, $100 multiplier)'
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
    underlying_price_updated = pyqtSignal(float)  # Underlying instrument price (SPX, XSP, etc.)
    es_price_updated = pyqtSignal(float)  # ES futures price (23/6 trading)
    market_data_tick = pyqtSignal(str, str, float)  # contract_key, tick_type, value
    greeks_updated = pyqtSignal(str, dict)  # contract_key, greeks_dict
    
    # Position and order signals
    position_update = pyqtSignal(str, dict)  # contract_key, position_data
    position_closed = pyqtSignal(str)  # contract_key - position quantity = 0
    order_status_update = pyqtSignal(int, dict)  # order_id, status_data
    
    # Historical data signals
    historical_bar = pyqtSignal(str, dict)  # contract_key, bar_data
    historical_complete = pyqtSignal(str)  # contract_key
    
    # Account signals
    next_order_id = pyqtSignal(int)
    managed_accounts = pyqtSignal(str)


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
                
            self.signals.connection_message.emit(f"Client ID {self._main_window.client_id} already in use", "WARNING")
            if self._main_window.client_id_iterator < self._main_window.max_client_id:
                self._main_window.client_id_iterator += 1
                self._main_window.client_id = self._main_window.client_id_iterator
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
    
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float, attrib: TickAttrib):
        """Receives real-time price updates"""
        # Underlying instrument price (SPX, XSP, etc.) for display
        if reqId == self.app.get('underlying_req_id'):
            if tickType == 4:  # LAST price
                self.app['underlying_price'] = price
                self.signals.underlying_price_updated.emit(price)
            return
        
        # ES futures price (for strike calculations - always available)
        if reqId == self.app.get('es_req_id'):
            if tickType == 4:  # LAST price
                self.app['es_price'] = price
                self.signals.es_price_updated.emit(price)
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
# CHART WIDGET - PROFESSIONAL MATPLOTLIB/MPLFINANCE
# ============================================================================
# Import the simple, professional matplotlib-based chart widget
# from chart_widget_matplotlib import ChartWidget  # TODO: Implement chart widget


# ============================================================================
# CHART WIDGET - PROFESSIONAL MATPLOTLIB/MPLFINANCE IMPLEMENTATION
# ============================================================================

# Import the new matplotlib-based ChartWidget (see chart_widget_matplotlib.py)
# from chart_widget_matplotlib import ChartWidget  # TODO: Implement chart widget


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
        
        # Trading state
        self.positions = {}  # contract_key -> position_data
        self.saved_positions = {}  # Loaded from positions.json for entryTime persistence
        self.market_data = {}  # contract_key -> market_data
        self.pending_orders = {}  # order_id -> (contract_key, action, quantity)
        self.chasing_orders = {}  # order_id -> chasing_order_info (for all orders with mid-price chasing enabled)
        self.historical_data = {}  # contract_key -> bars
        
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
        
        # Set window title based on selected instrument
        self.setWindowTitle(f"{self.instrument['name']} 0DTE Options Trader - PyQt6 Professional Edition")
        self.setGeometry(100, 100, 1600, 900)
        
        logger.info(f"═══════════════════════════════════════════════════════")
        logger.info(f"TRADING INSTRUMENT: {self.instrument['name']}")
        logger.info(f"Description: {self.instrument['description']}")
        logger.info(f"Strike Increment: ${self.instrument['strike_increment']}")
        logger.info(f"Tick Sizes: ≥$3.00→${self.instrument['tick_size_above_3']}, <$3.00→${self.instrument['tick_size_below_3']}")
        logger.info(f"═══════════════════════════════════════════════════════")
        
        # Get local timezone from system (MUST be set before calculate_expiry_date)
        self.local_tz = datetime.now().astimezone().tzinfo
        logger.info(f"Detected local timezone: {self.local_tz}")
        self.last_refresh_date = datetime.now(self.local_tz).date()
        
        # Strategy parameters
        self.strikes_above = 20
        self.strikes_below = 20
        self.current_expiry = self.calculate_expiry_date(0)
        self.chain_refresh_interval = 3600  # Auto-refresh chain every hour (in seconds)
        self.last_chain_center_strike = 0  # Track last center strike for drift detection
        self.chain_drift_threshold = 5  # Number of strikes to drift before auto-recentering (default: 5)
        
        # Auto-refresh timer for 4:00 PM ET expiration switch
        self.market_close_timer = QTimer()
        self.market_close_timer.timeout.connect(self.check_market_close_refresh)
        self.market_close_timer.start(60000)  # Check every 60 seconds
        
        # ES offset monitoring timer (check market hours every 5 minutes)
        self.offset_monitor_timer = QTimer()
        self.offset_monitor_timer.timeout.connect(self.check_offset_monitoring)
        self.offset_monitor_timer.start(300000)  # Check every 5 minutes
        
        # Manual trading settings
        self.give_in_interval = 10.0  # Seconds between "give in" price adjustments (configurable)
        
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
        
        # Connect signals
        self.connect_signals()
        
        # Setup UI
        self.setup_ui()
        self.apply_dark_theme()
        
        # Load settings
        self.load_settings()
        self.load_positions()  # Load saved positions to preserve entryTime
        
        # Start position auto-update timer (1-second updates for time tracking and P&L)
        self.position_update_timer = QTimer()
        self.position_update_timer.timeout.connect(self.update_positions_display)
        self.position_update_timer.start(1000)  # Update every 1000ms (1 second)
        
        # Start position auto-save timer (save every 60 seconds)
        self.position_save_timer = QTimer()
        self.position_save_timer.timeout.connect(self.save_positions)
        self.position_save_timer.start(60000)  # Save every 60 seconds
        
        # Auto-connect after 2 seconds
        QTimer.singleShot(2000, self.connect_to_ibkr)
    
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
        
        header_layout.addStretch()
        
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
            "Imp Vol", "Delta", "Theta", "Vega", "Gamma", "Volume", "CHANGE %", "Last", "Ask", "Bid",
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

        # Charts panel (TODO: Implement ChartWidget)
        charts_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Placeholder for charts until ChartWidget is implemented
        call_chart_placeholder = QLabel("Call Chart\n(Coming Soon)")
        call_chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        call_chart_placeholder.setStyleSheet("font-size: 14pt; color: #888888;")
        
        put_chart_placeholder = QLabel("Put Chart\n(Coming Soon)")
        put_chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        put_chart_placeholder.setStyleSheet("font-size: 14pt; color: #888888;")
        
        charts_splitter.addWidget(call_chart_placeholder)
        charts_splitter.addWidget(put_chart_placeholder)
        charts_splitter.setSizes([400, 400])
        
        trading_layout.addWidget(charts_splitter)

        # Positions and Orders panel
        pos_order_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Positions
        positions_group = QGroupBox("Open Positions")
        pos_layout = QVBoxLayout(positions_group)
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(9)
        self.positions_table.setHorizontalHeaderLabels([
            "Contract", "Qty", "Entry", "Current", "P&L", "P&L %", "EntryTime", "TimeSpan", "Action"
        ])
        self.positions_table.verticalHeader().setVisible(False)  # type: ignore[union-attr]
        self.positions_table.setMaximumHeight(113)  # Reduced by 25% (was 150)
        self.positions_table.cellClicked.connect(self.on_position_cell_clicked)
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
        self.orders_table.setMaximumHeight(113)  # Reduced by 25% (was 150)
        self.orders_table.cellClicked.connect(self.on_order_cell_clicked)
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
        panels_layout.setSpacing(5)        # --- PANEL 1: Master Settings (Strategy Control) - EXPANDED ---
        self.master_group = QGroupBox("Master Settings")
        self.master_group.setFixedWidth(280)  # Expanded from 220 to 280
        master_layout = QGridLayout(self.master_group)
        master_layout.setVerticalSpacing(3)  # Reduce vertical spacing
        master_layout.setHorizontalSpacing(8)  # Increase horizontal spacing for better organization
        
        # Row 0: Strategy ON/OFF buttons (span full width)
        master_layout.addWidget(QLabel("<b>Auto:</b>"), 0, 0)
        
        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(3)
        
        self.strategy_on_btn = QPushButton("ON")
        self.strategy_on_btn.setProperty("success", True)
        self.strategy_on_btn.setFixedWidth(60)  # Increased from 50 to 60
        self.strategy_on_btn.clicked.connect(lambda: self.set_strategy_enabled(True))
        button_layout.addWidget(self.strategy_on_btn)
        
        self.strategy_off_btn = QPushButton("OFF")
        self.strategy_off_btn.setProperty("danger", True)
        self.strategy_off_btn.setFixedWidth(60)  # Increased from 50 to 60
        self.strategy_off_btn.clicked.connect(lambda: self.set_strategy_enabled(False))
        button_layout.addWidget(self.strategy_off_btn)
        
        self.strategy_status_label = QLabel("OFF")
        self.strategy_status_label.setStyleSheet("font-weight: bold; color: #808080; font-size: 8pt;")
        button_layout.addWidget(self.strategy_status_label)
        button_layout.addStretch()  # Push everything left
        
        master_layout.addWidget(button_frame, 0, 1, 1, 3)
        
        # Row 1: VIX, Delta, Max Risk (3 columns)
        master_layout.addWidget(QLabel("VIX:"), 1, 0)
        self.vix_threshold_spin = QDoubleSpinBox()
        self.vix_threshold_spin.setRange(0, 100)
        self.vix_threshold_spin.setValue(self.vix_threshold)
        self.vix_threshold_spin.setDecimals(1)
        self.vix_threshold_spin.setFixedWidth(60)  # Increased from 50 to 60
        self.vix_threshold_spin.valueChanged.connect(self.on_master_settings_changed)
        master_layout.addWidget(self.vix_threshold_spin, 1, 1)
        
        master_layout.addWidget(QLabel("Δ:"), 1, 2)
        self.target_delta_spin = QSpinBox()
        self.target_delta_spin.setRange(10, 50)
        self.target_delta_spin.setSingleStep(10)
        self.target_delta_spin.setValue(self.target_delta)
        self.target_delta_spin.setFixedWidth(55)  # Increased from 45 to 55
        self.target_delta_spin.valueChanged.connect(self.on_master_settings_changed)
        master_layout.addWidget(self.target_delta_spin, 1, 3)
        
        # Row 2: Max Risk, Trade Qty (2 columns)
        master_layout.addWidget(QLabel("Risk $:"), 2, 0)
        self.max_risk_spin = QSpinBox()
        self.max_risk_spin.setRange(100, 10000)
        self.max_risk_spin.setSingleStep(50)
        self.max_risk_spin.setValue(self.max_risk)
        self.max_risk_spin.setFixedWidth(80)  # Increased from 60 to 80
        self.max_risk_spin.valueChanged.connect(self.on_master_settings_changed)
        master_layout.addWidget(self.max_risk_spin, 2, 1)
        
        master_layout.addWidget(QLabel("Qty:"), 2, 2)
        self.trade_qty_spin = QSpinBox()
        self.trade_qty_spin.setRange(1, 100)
        self.trade_qty_spin.setValue(self.trade_qty)
        self.trade_qty_spin.setFixedWidth(55)  # Increased from 45 to 55
        self.trade_qty_spin.valueChanged.connect(self.on_master_settings_changed)
        master_layout.addWidget(self.trade_qty_spin, 2, 3)
        
        # Row 3: Position Size Mode (compact horizontal layout)
        master_layout.addWidget(QLabel("Size:"), 3, 0)
        
        radio_frame = QWidget()
        radio_layout = QHBoxLayout(radio_frame)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setSpacing(8)
        
        self.fixed_radio = QRadioButton("Fixed")
        self.fixed_radio.setChecked(self.position_size_mode == "fixed")
        self.fixed_radio.toggled.connect(self.on_position_mode_changed)
        radio_layout.addWidget(self.fixed_radio)
        
        self.by_risk_radio = QRadioButton("Risk")
        self.by_risk_radio.setChecked(self.position_size_mode == "calculated")
        self.by_risk_radio.toggled.connect(self.on_position_mode_changed)
        radio_layout.addWidget(self.by_risk_radio)
        radio_layout.addStretch()
        
        master_layout.addWidget(radio_frame, 3, 1, 1, 3)
        
        # Row 4: Separator (reduced height)
        separator = QLabel()
        separator.setFrameStyle(QLabel.Shape.HLine | QLabel.Shadow.Sunken)
        separator.setMaximumHeight(1)
        master_layout.addWidget(separator, 4, 0, 1, 4)
        
        # Row 5: Chain Settings (compact layout)
        master_layout.addWidget(QLabel("±Strikes:"), 5, 0)
        self.strikes_above_spin = QSpinBox()
        self.strikes_above_spin.setRange(5, 50)
        self.strikes_above_spin.setValue(self.strikes_above)
        self.strikes_above_spin.setToolTip("Strikes above ATM")
        self.strikes_above_spin.setFixedWidth(50)  # Increased from 40 to 50
        self.strikes_above_spin.valueChanged.connect(self.on_chain_settings_changed)
        master_layout.addWidget(self.strikes_above_spin, 5, 1)
        
        self.strikes_below_spin = QSpinBox()
        self.strikes_below_spin.setRange(5, 50)
        self.strikes_below_spin.setValue(self.strikes_below)
        self.strikes_below_spin.setToolTip("Strikes below ATM")
        self.strikes_below_spin.setFixedWidth(50)  # Increased from 40 to 50
        self.strikes_below_spin.valueChanged.connect(self.on_chain_settings_changed)
        master_layout.addWidget(self.strikes_below_spin, 5, 2)
        
        # Time Stop in same row
        master_layout.addWidget(QLabel("Stop:"), 5, 3)
        self.time_stop_spin = QSpinBox()
        self.time_stop_spin.setRange(1, 300)
        self.time_stop_spin.setSingleStep(5)
        self.time_stop_spin.setValue(self.time_stop)
        self.time_stop_spin.setToolTip("Time stop (min)")
        self.time_stop_spin.setFixedWidth(55)  # Increased from 45 to 55
        self.time_stop_spin.valueChanged.connect(self.on_master_settings_changed)
        master_layout.addWidget(self.time_stop_spin, 5, 4)
        
        # Row 6: Chain Refresh and Drift (compact)
        master_layout.addWidget(QLabel("Refresh:"), 6, 0)
        self.chain_refresh_spin = QSpinBox()
        self.chain_refresh_spin.setRange(0, 7200)
        self.chain_refresh_spin.setSingleStep(60)
        self.chain_refresh_spin.setValue(self.chain_refresh_interval)
        self.chain_refresh_spin.setToolTip("Auto-refresh (sec)")
        self.chain_refresh_spin.setFixedWidth(60)  # Increased from 50 to 60
        self.chain_refresh_spin.valueChanged.connect(self.on_chain_settings_changed)
        master_layout.addWidget(self.chain_refresh_spin, 6, 1)
        
        master_layout.addWidget(QLabel("Drift:"), 6, 2)
        self.chain_drift_spin = QSpinBox()
        self.chain_drift_spin.setRange(1, 20)
        self.chain_drift_spin.setSingleStep(1)
        self.chain_drift_spin.setValue(self.chain_drift_threshold)
        self.chain_drift_spin.setToolTip("Drift threshold (strikes)")
        self.chain_drift_spin.setFixedWidth(50)  # Increased from 40 to 50
        self.chain_drift_spin.valueChanged.connect(self.on_chain_settings_changed)
        master_layout.addWidget(self.chain_drift_spin, 6, 3)
        
        panels_layout.addWidget(self.master_group)
        
        # --- PANEL 2: Confirmation Settings ---
        confirm_group = QGroupBox("Confirmation Settings")
        confirm_group.setFixedWidth(280)  # Expanded from 220 to 280
        confirm_layout = QGridLayout(confirm_group)
        
        confirm_layout.addWidget(QLabel("EMA Len:"), 0, 0)
        self.confirm_ema_spin = QSpinBox()
        self.confirm_ema_spin.setRange(1, 100)
        self.confirm_ema_spin.setValue(self.confirm_ema_length)
        self.confirm_ema_spin.valueChanged.connect(self.on_chart_settings_changed)
        confirm_layout.addWidget(self.confirm_ema_spin, 0, 1)
        
        confirm_layout.addWidget(QLabel("Z Period:"), 1, 0)
        self.confirm_z_period_spin = QSpinBox()
        self.confirm_z_period_spin.setRange(1, 100)
        self.confirm_z_period_spin.setValue(self.confirm_z_period)
        self.confirm_z_period_spin.valueChanged.connect(self.on_chart_settings_changed)
        confirm_layout.addWidget(self.confirm_z_period_spin, 1, 1)
        
        confirm_layout.addWidget(QLabel("Z ±:"), 2, 0)
        self.confirm_z_threshold_spin = QDoubleSpinBox()
        self.confirm_z_threshold_spin.setRange(0.1, 5.0)
        self.confirm_z_threshold_spin.setSingleStep(0.1)
        self.confirm_z_threshold_spin.setValue(self.confirm_z_threshold)
        self.confirm_z_threshold_spin.valueChanged.connect(self.on_chart_settings_changed)
        confirm_layout.addWidget(self.confirm_z_threshold_spin, 2, 1)
        
        self.confirm_refresh_btn = QPushButton("Refresh")
        self.confirm_refresh_btn.clicked.connect(self.refresh_confirm_chart)
        confirm_layout.addWidget(self.confirm_refresh_btn, 3, 0, 1, 2)
        
        panels_layout.addWidget(confirm_group)
        
        # --- PANEL 3: Trade Chart Settings ---
        trade_chart_group = QGroupBox("Trade Chart Settings")
        trade_chart_group.setFixedWidth(280)  # Expanded from 220 to 280
        trade_layout = QGridLayout(trade_chart_group)
        
        trade_layout.addWidget(QLabel("EMA Len:"), 0, 0)
        self.trade_ema_spin = QSpinBox()
        self.trade_ema_spin.setRange(1, 100)
        self.trade_ema_spin.setValue(self.trade_ema_length)
        self.trade_ema_spin.valueChanged.connect(self.on_chart_settings_changed)
        trade_layout.addWidget(self.trade_ema_spin, 0, 1)
        
        trade_layout.addWidget(QLabel("Z Period:"), 1, 0)
        self.trade_z_period_spin = QSpinBox()
        self.trade_z_period_spin.setRange(1, 100)
        self.trade_z_period_spin.setValue(self.trade_z_period)
        self.trade_z_period_spin.valueChanged.connect(self.on_chart_settings_changed)
        trade_layout.addWidget(self.trade_z_period_spin, 1, 1)
        
        trade_layout.addWidget(QLabel("Z ±:"), 2, 0)
        self.trade_z_threshold_spin = QDoubleSpinBox()
        self.trade_z_threshold_spin.setRange(0.1, 5.0)
        self.trade_z_threshold_spin.setSingleStep(0.1)
        self.trade_z_threshold_spin.setValue(self.trade_z_threshold)
        self.trade_z_threshold_spin.valueChanged.connect(self.on_chart_settings_changed)
        trade_layout.addWidget(self.trade_z_threshold_spin, 2, 1)
        
        self.trade_refresh_btn = QPushButton("Refresh")
        self.trade_refresh_btn.clicked.connect(self.refresh_trade_chart)
        trade_layout.addWidget(self.trade_refresh_btn, 3, 0, 1, 2)
        
        panels_layout.addWidget(trade_chart_group)
        
        # --- PANEL 4: Auto Entry (Straddle) ---
        straddle_group = QGroupBox("Auto Entry")
        straddle_group.setFixedWidth(280)  # Expanded from 220 to 280
        straddle_layout = QGridLayout(straddle_group)
        
        # Row 0: Straddle ON/OFF
        straddle_layout.addWidget(QLabel("<b>Straddle:</b>"), 0, 0)
        
        straddle_btn_frame = QWidget()
        straddle_btn_layout = QHBoxLayout(straddle_btn_frame)
        straddle_btn_layout.setContentsMargins(0, 0, 0, 0)
        straddle_btn_layout.setSpacing(3)
        
        self.straddle_on_btn = QPushButton("ON")
        self.straddle_on_btn.setProperty("success", True)
        self.straddle_on_btn.setFixedWidth(60)  # Increased from 50 to 60
        self.straddle_on_btn.clicked.connect(lambda: self.set_straddle_enabled(True))
        straddle_btn_layout.addWidget(self.straddle_on_btn)
        
        self.straddle_off_btn = QPushButton("OFF")
        self.straddle_off_btn.setProperty("danger", True)
        self.straddle_off_btn.setFixedWidth(60)  # Increased from 50 to 60
        self.straddle_off_btn.clicked.connect(lambda: self.set_straddle_enabled(False))
        straddle_btn_layout.addWidget(self.straddle_off_btn)
        
        self.straddle_status_label = QLabel("OFF")
        self.straddle_status_label.setStyleSheet("font-weight: bold; color: #808080;")
        straddle_btn_layout.addWidget(self.straddle_status_label)
        straddle_btn_layout.addStretch()
        
        straddle_layout.addWidget(straddle_btn_frame, 0, 1)
        
        # Row 1: Frequency
        straddle_layout.addWidget(QLabel("Frequency:"), 1, 0)
        freq_frame = QWidget()
        freq_layout = QHBoxLayout(freq_frame)
        freq_layout.setContentsMargins(0, 0, 0, 0)
        self.straddle_frequency_spin = QSpinBox()
        self.straddle_frequency_spin.setRange(1, 300)
        self.straddle_frequency_spin.setValue(self.straddle_frequency)
        self.straddle_frequency_spin.valueChanged.connect(self.on_straddle_settings_changed)
        freq_layout.addWidget(self.straddle_frequency_spin)
        freq_layout.addWidget(QLabel("min"))
        straddle_layout.addWidget(freq_frame, 1, 1)
        
        # Row 2: Info label
        info_label = QLabel("Uses Master Settings\nfor Delta & Position Size")
        info_label.setStyleSheet("color: #888888; font-size: 8pt;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        straddle_layout.addWidget(info_label, 2, 0, 1, 2)
        
        # Row 3: Next entry countdown
        self.straddle_next_label = QLabel("Next: --:--")
        self.straddle_next_label.setStyleSheet("color: #00BFFF; font-size: 8pt;")
        straddle_layout.addWidget(self.straddle_next_label, 3, 0, 1, 2)
        
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
        
        manual_info = QLabel("Settings in Master panel →")
        manual_info.setStyleSheet("color: #888888; font-size: 8pt;")
        manual_info.setAlignment(Qt.AlignmentFlag.AlignLeft)
        manual_layout.addWidget(manual_info)
        manual_layout.addStretch()
        
        panels_layout.addWidget(manual_group)
        
        # --- PANEL 6: Chain Settings ---
        chain_settings_group = QGroupBox("Chain Settings")
        chain_settings_group.setFixedWidth(280)  # Expanded from 220 to 280
        chain_settings_layout = QGridLayout(chain_settings_group)
        
        # Strikes to show
        chain_settings_layout.addWidget(QLabel("Strikes:"), 0, 0)
        self.strikes_display_spin = QSpinBox()
        self.strikes_display_spin.setRange(5, 50)
        self.strikes_display_spin.setValue(20)
        self.strikes_display_spin.setFixedWidth(50)
        chain_settings_layout.addWidget(self.strikes_display_spin, 0, 1)
        
        # Refresh frequency
        chain_settings_layout.addWidget(QLabel("Refresh:"), 1, 0)
        self.refresh_freq_spin = QSpinBox()
        self.refresh_freq_spin.setRange(1, 30)
        self.refresh_freq_spin.setValue(2)
        self.refresh_freq_spin.setFixedWidth(50)
        chain_settings_layout.addWidget(self.refresh_freq_spin, 1, 1)
        chain_settings_layout.addWidget(QLabel("s"), 1, 2)
        
        panels_layout.addWidget(chain_settings_group)
        
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
        self.handling_client_id_error = False
        logger.info(f"Retrying connection with client ID {self.client_id}")
        # Update the client ID in the UI
        self.client_id_edit.setText(str(self.client_id))
        # Reset client_id_iterator to use the new client_id
        self.client_id_iterator = self.client_id
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
    
    def subscribe_underlying_price(self):
        """Subscribe to underlying price (SPX or XSP based on SELECTED_INSTRUMENT)"""
        underlying_contract = Contract()
        underlying_contract.symbol = self.instrument['underlying_symbol']
        underlying_contract.secType = self.instrument['underlying_type']
        underlying_contract.currency = "USD"
        underlying_contract.exchange = self.instrument['underlying_exchange']
        
        req_id = 1
        self.app_state['underlying_req_id'] = req_id
        
        # Request delayed market data type (3 = delayed frozen for after-hours)
        self.ibkr_client.reqMarketDataType(3)
        
        # Subscribe to market data (snapshot=True for delayed data when market closed)
        self.ibkr_client.reqMktData(req_id, underlying_contract, "", True, False, [])
        self.log_message(f"Subscribed to {self.instrument['underlying_symbol']} underlying price (with delayed data support)", "INFO")
    
    @pyqtSlot(float)
    def update_underlying_display(self, price: float):
        """Update underlying price display (SPX or XSP based on SELECTED_INSTRUMENT)"""
        self.app_state['underlying_price'] = price
        self.underlying_price_label.setText(f"{self.instrument['underlying_symbol']}: {price:.2f}")
        
        # Update ES-to-cash offset if conditions are met
        self.update_es_to_cash_offset(price, None)
    
    def is_market_hours(self):
        """Check if it's during regular market hours (9:30 AM - 4:00 PM ET)"""
        import pytz
        et_tz = pytz.timezone('US/Eastern')
        now_et = datetime.now(et_tz)
        
        # Market is open Monday-Friday, 9:30 AM - 4:00 PM ET
        if now_et.weekday() >= 5:  # Weekend
            return False
        
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now_et <= market_close
    
    def update_es_to_cash_offset(self, underlying_price=None, es_price=None):
        """Calculate and update ES-to-cash offset during market hours"""
        # Use current prices if not provided
        if underlying_price is None:
            underlying_price = self.app_state['underlying_price']
        if es_price is None:
            es_price = self.app_state['es_price']
        
        # Need both prices to calculate offset
        if underlying_price <= 0 or es_price <= 0:
            return
        
        # Only update offset during market hours when both prices are moving
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
            logger.info(f"ES-to-{symbol} offset updated: {offset:.2f} points (was {old_offset:.2f})")
    
    def update_offset_display(self):
        """Update the ES offset display label"""
        symbol = self.instrument['underlying_symbol']
        if self.es_to_cash_offset == 0.0:
            self.es_offset_label.setText(f"ES to {symbol} offset: N/A")
        else:
            status = "(live)" if self.offset_update_enabled else "(frozen)"
            self.es_offset_label.setText(f"ES to {symbol} offset: {self.es_to_cash_offset:+.2f} {status}")
            
            # Color coding: green for premium, red for discount, yellow for frozen
            if not self.offset_update_enabled:
                color = "#FFD700"  # Gold for frozen
            elif self.es_to_cash_offset > 0:
                color = "#90EE90"  # Light green for premium
            else:
                color = "#FFA07A"  # Light salmon for discount
            
            self.es_offset_label.setStyleSheet(f"font-size: 12pt; color: {color};")
    
    def get_adjusted_es_price(self):
        """Get ES price adjusted for the cash offset for strike calculations"""
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
        
        # ES futures trade almost 24/7, delayed data works after hours
        self.ibkr_client.reqMarketDataType(3)
        
        # Subscribe to market data
        self.ibkr_client.reqMktData(req_id, es_contract, "", False, False, [])
        self.log_message(f"Subscribed to ES futures {es_contract.lastTradeDateOrContractMonth} (23/6 trading)", "INFO")
    
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
        else:
            self.log_message(f"Received status for unknown order #{order_id}: {status_data.get('status')}", "INFO")
    
    @pyqtSlot(int)
    def remove_from_chasing_orders(self, order_id: int):
        """Remove order from chasing tracking (called when order is filled/cancelled)"""
        if order_id in self.chasing_orders:
            logger.info(f"Force-removing order #{order_id} from chasing_orders (order filled/cancelled)")
            del self.chasing_orders[order_id]
            self.update_orders_display()
    
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
        if contract_key not in self.historical_data:
            self.historical_data[contract_key] = []
        
        self.historical_data[contract_key].append(bar_data)
    
    @pyqtSlot(str)
    def on_historical_complete(self, contract_key: str):
        """Handle historical data complete"""
        if contract_key in self.historical_data:
            bars = self.historical_data[contract_key]
            self.log_message(f"Historical data complete for {contract_key}: {len(bars)} bars", "SUCCESS")
            
            # Determine if call or put and update appropriate chart
            # TODO: Implement chart widget integration
            if '_C_' in contract_key:
                # Update call chart (TODO: Implement ChartWidget)
                logger.info(f"CALL historical data ready: {len(bars)} bars")
                # if hasattr(self, 'call_chart'):
                #     self.call_chart.update_data(bars)
                #     self.log_message(f"Updated CALL chart with {len(bars)} bars", "INFO")
            elif '_P_' in contract_key:
                # Update put chart (TODO: Implement ChartWidget)
                logger.info(f"PUT historical data ready: {len(bars)} bars")
                # if hasattr(self, 'put_chart'):
                #     self.put_chart.update_data(bars)
                #     self.log_message(f"Updated PUT chart with {len(bars)} bars", "INFO")
    
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
    
    def request_option_chain(self):
        """Build and subscribe to option chain"""
        if self.connection_state != ConnectionState.CONNECTED:
            self.log_message("Cannot request option chain - not connected", "WARNING")
            return
        
        # Use ES price for strike calculations (trades 23/6 - always available)
        if self.app_state['es_price'] == 0:
            self.log_message("Waiting for ES futures price...", "INFO")
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
        
        # Use ES futures price for strike calculations (available 23 hours/day)
        es_price = self.app_state['es_price']
        if es_price == 0:
            self.log_message("Waiting for ES futures price...", "INFO")
            QTimer.singleShot(2000, self.request_option_chain)
            return
        
        # Get ES price adjusted for cash offset
        adjusted_es_price = self.get_adjusted_es_price()
        if adjusted_es_price == 0:
            # Fallback to raw ES if adjustment fails
            adjusted_es_price = es_price / 10.0 if self.instrument['underlying_symbol'] == 'XSP' else es_price
        
        reference_price = adjusted_es_price
        
        # Log the adjustment being applied
        if self.instrument['underlying_symbol'] == 'XSP':
            logger.info(f"Using adjusted ES price ${reference_price:.2f} for XSP (ES: {es_price:.2f}, offset: {self.es_to_cash_offset:+.2f})")
        else:
            logger.info(f"Using adjusted ES price ${reference_price:.2f} for SPX (ES: {es_price:.2f}, offset: {self.es_to_cash_offset:+.2f})")
        
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
            
            # Dynamic strike background based on ATM position (using adjusted ES price)
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
                            (8, f"{data.get('ask', 0):.2f}"),
                            (9, f"{data.get('bid', 0):.2f}")
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
    
    def on_option_cell_clicked(self, row: int, col: int):
        """Handle option chain cell click"""
        try:
            logger.info(f"Cell clicked: row={row}, col={col}")
            
            # Get strike from row
            strike_item = self.option_table.item(row, 10)
            if not strike_item:
                logger.warning(f"No strike item at row {row}, col 10")
                return
            
            strike = float(strike_item.text())
            logger.info(f"Strike: {strike}")
            
            # Determine if call or put was clicked
            if col < 10:  # Call side
                contract_key = f"{self.instrument['options_symbol']}_{strike}_C_{self.current_expiry}"
                self.log_message(f"Selected CALL: Strike {strike}", "INFO")
                self.request_historical_data(contract_key)
            elif col > 10:  # Put side
                contract_key = f"{self.instrument['options_symbol']}_{strike}_P_{self.current_expiry}"
                self.log_message(f"Selected PUT: Strike {strike}", "INFO")
                self.request_historical_data(contract_key)
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
            
            # Determine tick size based on current mid price
            if current_mid >= 3.0:
                tick_size = 0.10
            else:
                tick_size = 0.05
            
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
            
            # Check if mid-price has moved significantly
            if abs(current_mid - order_info['last_mid']) >= 0.05:
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
            
            # Request historical data with proper timezone format (US/Eastern for SPX)
            # Use empty string for end_time to get most recent data
            end_time = ""  # Empty string means current time
            
            self.ibkr_client.reqHistoricalData(
                req_id,
                contract,
                end_time,
                "2 D",  # Duration
                "5 mins",  # Bar size
                "TRADES",  # What to show
                1,  # Use RTH (regular trading hours)
                1,  # Format date
                False,  # Keep up to date
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
                QMessageBox.critical(self, "Not Connected", "Please connect to IBKR before trading")
                return
            
            if not self.app_state.get('data_server_ok', False):
                self.log_message("❌ Cannot place order: Data server not ready", "ERROR")
                QMessageBox.critical(self, "Not Ready", "Data server not ready. Please wait for confirmation.")
                return
            
            # Get settings from Master Settings panel
            target_delta = self.target_delta_spin.value()
            max_risk = self.max_risk_spin.value()
            
            self.log_message(f"Master Settings: Target Δ={target_delta}, Max Risk=${max_risk:.0f}", "INFO")
            self.log_message(f"Searching for CALL option near {target_delta} delta...", "INFO")
            
            # Find call option by delta
            result = self.find_option_by_delta("C", target_delta)
            if not result:
                self.log_message("No suitable call options found", "WARNING")
                QMessageBox.warning(
                    self, 
                    "No Options Found",
                    f"No call options found near {target_delta} delta"
                )
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
            
            # Confirm with user
            msg = QMessageBox()
            msg.setWindowTitle("Confirm BUY CALL")
            msg.setText(
                f"Buy {quantity} contract(s) of {contract_key}\n"
                f"Delta: {actual_delta:.1f} (Target: {target_delta})\n"
                f"Mid Price: ${mid_price:.2f} (~${mid_price * 100:.0f} per contract)\n"
                f"Ask Price: ${ask_price:.2f}\n"
                f"Position Size: {size_description}\n"
                f"Total Cost: ~${mid_price * 100 * quantity:.0f}\n\n"
                f"Order will chase mid-price if market moves."
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            
            if msg.exec() == QMessageBox.StandardButton.Yes:
                # Place order with mid-price chasing enabled
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
            else:
                self.log_message("Manual BUY CALL cancelled by user", "INFO")
            
            self.log_message("=" * 60, "INFO")
            
        except Exception as e:
            self.log_message(f"Error in manual_buy_call: {e}", "ERROR")
            logger.error(f"Manual buy call error: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to place call order: {e}")
    
    def manual_buy_put(self):
        """Manual buy put option - uses Master Settings for delta/quantity and places order with mid-price chasing"""
        self.log_message("=" * 60, "INFO")
        self.log_message("🔔 MANUAL BUY PUT INITIATED 🔔", "SUCCESS")
        self.log_message("=" * 60, "INFO")
        
        try:
            # Check connection
            if self.connection_state != ConnectionState.CONNECTED:
                self.log_message("❌ Cannot place order: Not connected to IBKR", "ERROR")
                QMessageBox.critical(self, "Not Connected", "Please connect to IBKR before trading")
                return
            
            if not self.app_state.get('data_server_ok', False):
                self.log_message("❌ Cannot place order: Data server not ready", "ERROR")
                QMessageBox.critical(self, "Not Ready", "Data server not ready. Please wait for confirmation.")
                return
            
            # Get settings from Master Settings panel
            target_delta = self.target_delta_spin.value()
            max_risk = self.max_risk_spin.value()
            
            self.log_message(f"Master Settings: Target Δ={target_delta}, Max Risk=${max_risk:.0f}", "INFO")
            self.log_message(f"Searching for PUT option near {target_delta} delta...", "INFO")
            
            # Find put option by delta
            result = self.find_option_by_delta("P", target_delta)
            if not result:
                self.log_message("No suitable put options found", "WARNING")
                QMessageBox.warning(
                    self,
                    "No Options Found",
                    f"No put options found near {target_delta} delta"
                )
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
            
            # Confirm with user
            msg = QMessageBox()
            msg.setWindowTitle("Confirm BUY PUT")
            msg.setText(
                f"Buy {quantity} contract(s) of {contract_key}\n"
                f"Delta: {actual_delta:.1f} (Target: {target_delta})\n"
                f"Mid Price: ${mid_price:.2f} (~${mid_price * 100:.0f} per contract)\n"
                f"Ask Price: ${ask_price:.2f}\n"
                f"Position Size: {size_description}\n"
                f"Total Cost: ~${mid_price * 100 * quantity:.0f}\n\n"
                f"Order will chase mid-price if market moves."
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            
            if msg.exec() == QMessageBox.StandardButton.Yes:
                # Place order with mid-price chasing enabled
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
            else:
                self.log_message("Manual BUY PUT cancelled by user", "INFO")
            
            self.log_message("=" * 60, "INFO")
            
        except Exception as e:
            self.log_message(f"Error in manual_buy_put: {e}", "ERROR")
            logger.error(f"Manual buy put error: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to put order: {e}")
    
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
                    # Removed debug spam - position updates every second don't need logging
            
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
            
            # Populate row (9 columns now: Contract, Qty, Entry, Current, P&L, P&L %, EntryTime, TimeSpan, Action)
            items = [
                QTableWidgetItem(contract_key),
                QTableWidgetItem(f"{pos['position']:.0f}"),
                QTableWidgetItem(f"${pos['avgCost']:.2f}"),
                QTableWidgetItem(f"${pos['currentPrice']:.2f}"),
                QTableWidgetItem(f"${pnl:.2f}"),
                QTableWidgetItem(f"{pnl_pct:.2f}%"),
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
                
                # Close button styling (now column 8)
                if col == 8:
                    item.setBackground(QColor("#cc0000"))
                    item.setForeground(QColor("#ffffff"))
                
                self.positions_table.setItem(row, col, item)
        
        # Update total P&L label with color
        pnl_color = "#44ff44" if total_pnl >= 0 else "#ff4444"
        self.pnl_label.setText(f"Total P&L: ${total_pnl:.2f}")
        self.pnl_label.setStyleSheet(f"font-weight: bold; color: {pnl_color};")
    
    def on_position_cell_clicked(self, row: int, col: int):
        """
        Handle position table cell click - Close button functionality
        Matches Tkinter version exactly with mid-price chasing and protection checks
        """
        # DEBUG: Log every click
        logger.info(f"Position cell clicked: row={row}, col={col}")
        self.log_message(f"Position table click: row={row}, col={col}", "INFO")
        
        if col != 8:  # Only handle Close button column (column 8)
            logger.info(f"Click on column {col} - not Close button (column 8), ignoring")
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
            msg = QMessageBox()
            msg.setWindowTitle("Invalid Position")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText("Position quantity is zero.\nThere is no position to close!\n\n"
                       "This may indicate the position was already closed or there's a tracking issue.")
            msg.exec()
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
            msg = QMessageBox()
            msg.setWindowTitle("Pending Exit Order")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText(f"There are already {len(pending_exit_orders)} pending {action_type} order(s) for this position!\n\n"
                       f"Order IDs: {', '.join(map(str, pending_exit_orders))}\n\n"
                       "Please wait for the existing order to fill or cancel it first.")
            msg.exec()
            return
        
        # Get current P&L for confirmation dialog
        current_pnl = pos.get('pnl', 0)
        
        # Confirm close
        msg = QMessageBox()
        msg.setWindowTitle("Close Position")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(f"Close position: {contract_key}\n"
                   f"Quantity: {position_size:.0f}\n"
                   f"Current P&L: ${current_pnl:.2f}\n\n"
                   f"Place exit order at mid-price?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        
        if msg.exec() != QMessageBox.StandardButton.Yes:
            self.log_message("Position close cancelled by user", "INFO")
            return
        
        # User confirmed - proceed with exit order
        self.log_message("=" * 60, "INFO")
        self.log_message(f"MANUAL CLOSE POSITION: {contract_key}", "SUCCESS")
        
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
            
            # Confirm cancel
            msg = QMessageBox()
            msg.setWindowTitle("Confirm Cancel Order")
            msg.setText(f"Cancel order #{order_id}?\n{order_info['action']} {order_info['quantity']} {order_info['contract_key']}")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            
            if msg.exec() == QMessageBox.StandardButton.Yes:
                # Cancel order via IBKR API
                self.ibkr_client.cancelOrder(order_id)
                self.log_message(f"Cancelling order #{order_id}", "SUCCESS")
                
                # Update order status
                self.pending_orders[order_id]['status'] = 'Cancelled'
                self.update_orders_display()
            else:
                self.log_message("Order cancel cancelled by user", "INFO")
    
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
    
    def on_chain_settings_changed(self):
        """Called when strikes above/below or refresh interval settings change"""
        old_above = self.strikes_above
        old_below = self.strikes_below
        old_interval = self.chain_refresh_interval
        old_drift = self.chain_drift_threshold
        
        self.strikes_above = self.strikes_above_spin.value()
        self.strikes_below = self.strikes_below_spin.value()
        self.chain_refresh_interval = self.chain_refresh_spin.value()
        self.chain_drift_threshold = self.chain_drift_spin.value()
        
        self.log_message(
            f"Chain Settings: Strikes +{self.strikes_above}/-{self.strikes_below}, "
            f"Refresh: {self.chain_refresh_interval}s, Drift: {self.chain_drift_threshold} strikes "
            f"(was +{old_above}/-{old_below}, {old_interval}s, {old_drift} strikes)",
            "INFO"
        )
        self.save_settings()
        
        # Auto-refresh chain if connected (so user sees new range immediately)
        if self.connection_state == ConnectionState.CONNECTED and (old_above != self.strikes_above or old_below != self.strikes_below):
            self.log_message("Auto-refreshing chain with new strike range...", "INFO")
            self.request_option_chain()
    
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
        if self.connection_state == ConnectionState.CONNECTED and self.chain_refresh_interval > 0:
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
                        f"Price drifted {drift:.0f} points from center strike {self.last_chain_center_strike} "
                        f"to {current_center} (threshold: {drift_threshold:.0f}), auto-recentering chain"
                    )
                    self.request_option_chain()
    
    def check_offset_monitoring(self):
        """
        Check market hours and update ES offset monitoring status.
        Called every 5 minutes to determine if offset updates should be enabled.
        """
        old_status = self.offset_update_enabled
        self.offset_update_enabled = self.is_market_hours()
        
        # Update display if status changed
        if old_status != self.offset_update_enabled:
            status_text = "enabled" if self.offset_update_enabled else "disabled"
            logger.info(f"ES offset monitoring {status_text} (market hours: {self.offset_update_enabled})")
            self.update_offset_display()
    
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
            # Sync strikes values from spin boxes to text edit fields (for Settings tab)
            self.strikes_above = self.strikes_above_spin.value()
            self.strikes_below = self.strikes_below_spin.value()
            self.chain_refresh_interval = self.chain_refresh_spin.value()
            self.chain_drift_threshold = self.chain_drift_spin.value()
            self.strikes_above_edit.setText(str(self.strikes_above))
            self.strikes_below_edit.setText(str(self.strikes_below))
            
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
                
                # ES Offset Settings (restore persistent offset)
                self.es_to_cash_offset = settings.get('es_to_cash_offset', 0.0)
                self.last_offset_update_time = settings.get('last_offset_update_time', 0)
                
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
                self.strikes_above_edit.setText(str(self.strikes_above))
                self.strikes_below_edit.setText(str(self.strikes_below))
                
                # Update Master Settings UI
                self.vix_threshold_spin.setValue(self.vix_threshold)
                self.time_stop_spin.setValue(self.time_stop)
                self.target_delta_spin.setValue(self.target_delta)
                self.max_risk_spin.setValue(self.max_risk)
                self.trade_qty_spin.setValue(self.trade_qty)
                self.strikes_above_spin.setValue(self.strikes_above)  # Chain settings
                self.strikes_below_spin.setValue(self.strikes_below)  # Chain settings
                self.chain_refresh_spin.setValue(self.chain_refresh_interval)  # Chain refresh
                self.chain_drift_spin.setValue(self.chain_drift_threshold)  # Chain drift threshold
                
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
