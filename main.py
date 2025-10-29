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
SELECTED_INSTRUMENT = 'SPX'  # Change to 'XSP' for mini-SPX trading
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
    historical_bar_update = pyqtSignal(str, dict)  # contract_key, bar_data (real-time updates)
    
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
        # Check both old and new request mapping systems
        contract_key = None
        if reqId in self.app.get('historical_data_requests', {}):
            contract_key = self.app['historical_data_requests'][reqId]
        elif self._main_window and hasattr(self._main_window, 'request_id_map') and reqId in self._main_window.request_id_map:
            contract_key = self._main_window.request_id_map[reqId]
            
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
        # Check both old and new request mapping systems  
        contract_key = None
        if reqId in self.app.get('historical_data_requests', {}):
            contract_key = self.app['historical_data_requests'][reqId]
        elif self._main_window and hasattr(self._main_window, 'request_id_map') and reqId in self._main_window.request_id_map:
            contract_key = self._main_window.request_id_map[reqId]
            
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
        self.background = None  # Cached background for blitting
        self.line_artist = None  # Line object for fast updates
        self.needs_full_redraw = True  # Flag to force full redraw
        self.last_update_time = 0  # Throttle updates - track last update timestamp
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
        
        # Days selector
        toolbar_layout.addWidget(QLabel("Days:"))
        self.days_combo = QComboBox()
        self.days_combo.addItems(["1", "2", "3", "5"])
        self.days_combo.setCurrentText("1")
        self.days_combo.setFixedWidth(50)
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
        """Update chart with price data (line chart for mid-price)"""
        if not price_data or len(price_data) < 2:
            self.draw_empty_chart()
            return
        
        try:
            # Save current view limits BEFORE clearing figure
            saved_xlim = None
            if hasattr(self, 'ax') and self.ax is not None:
                try:
                    saved_xlim = self.ax.get_xlim()
                except:
                    pass
            
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
            
            # Clear figure
            self.figure.clear()
            self.ax = self.figure.add_subplot(111)
            
            # Convert timestamps to matplotlib date numbers for proper spacing
            from matplotlib.dates import date2num
            x_dates = date2num(df.index)
            
            # Plot line chart (mid-price) using date numbers for x-axis
            self.ax.plot(x_dates, df['close'].values.tolist(), color=self.border_color, 
                        linewidth=2, alpha=0.9, label='Mid Price')
            
            # Format x-axis as datetime
            self.ax.xaxis_date()
            
            # Style the chart
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
            
            # Set title with contract description
            current_price = float(df['close'].iloc[-1])
            title_text = f"{self.title}"
            if contract_description:
                title_text += f" - {contract_description}"
            
            self.title_label.setText(title_text)
            
            # Add current price horizontal line
            self.ax.axhline(y=current_price, color=self.border_color, 
                          linestyle='--', linewidth=1, alpha=0.5)
            
            # Add current price text label on right y-axis
            self.ax.text(1.01, current_price, f'${current_price:.2f}', 
                        transform=self.ax.get_yaxis_transform(),
                        color=self.border_color, fontsize=10, fontweight='bold',
                        va='center', ha='left',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='#0a0a0a', 
                                 edgecolor=self.border_color, linewidth=1))
            
            # Preserve current zoom/pan state if we saved it, otherwise set default view
            if saved_xlim is not None:
                # Restore the user's view from before figure was cleared
                self.ax.set_xlim(saved_xlim)
                self.ax.autoscale(enable=False, axis='x')
            else:
                # First time drawing - set default view
                if len(x_dates) > 100:
                    visible_bars = min(240, len(x_dates))
                    x_range = x_dates[-1] - x_dates[-visible_bars]
                    padding = x_range * 0.02
                    self.ax.set_xlim(x_dates[-visible_bars], x_dates[-1] + padding)
                    self.ax.autoscale(enable=False, axis='x')
                else:
                    x_range = x_dates[-1] - x_dates[0]
                    padding = x_range * 0.02
                    self.ax.set_xlim(x_dates[0], x_dates[-1] + padding)
            
            # No need to call tight_layout - using constrained_layout in Figure constructor
            
            # Redraw canvas - use draw_idle() to avoid blocking UI
            self.canvas.draw_idle()
            
            # Update navigation toolbar to reflect current view
            if hasattr(self, 'nav_toolbar'):
                self.nav_toolbar.push_current()
            
        except Exception as e:
            logger.error(f"Error updating chart {self.title}: {e}", exc_info=True)
            self.draw_empty_chart()


class ProfessionalUnderlyingChart(QWidget):
    """
    Professional candlestick chart for underlying (SPX/XSP) with Z-Score subplot
    Similar to TradeStation multi-panel charts with throttled updates for trading
    """
    
    def __init__(self, title: str, border_color: str = "#FF8C00", parent=None):
        super().__init__(parent)
        self.title = title
        self.border_color = border_color
        self.chart_data = []
        self.last_update_time = 0  # Throttle updates
        self.update_interval = 0.25  # Minimum 250ms between updates (4 FPS)
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
        self.days_combo.setCurrentText("1")
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
    
    def update_chart_throttled(self, price_data, ema_period=9, z_period=30, z_threshold=1.5):
        """Throttled chart update - limits update frequency to prevent UI freezing"""
        import time
        current_time = time.time()
        
        # Check if enough time has passed since last update
        if current_time - self.last_update_time >= self.update_interval:
            # Update immediately
            self.last_update_time = current_time
            self.update_chart(price_data, ema_period, z_period, z_threshold)
        else:
            # Schedule update for later if not already scheduled
            if self.pending_update is None:
                remaining_time = self.update_interval - (current_time - self.last_update_time)
                delay_ms = int(remaining_time * 1000)
                self.pending_update = QTimer.singleShot(
                    delay_ms,
                    lambda: self._execute_pending_update(price_data, ema_period, z_period, z_threshold)
                )
    
    def _execute_pending_update(self, price_data, ema_period=9, z_period=30, z_threshold=1.5):
        """Execute the pending chart update"""
        import time
        self.pending_update = None
        self.last_update_time = time.time()
        self.update_chart(price_data, ema_period, z_period, z_threshold)
    
    def update_chart(self, price_data, ema_period=9, z_period=30, z_threshold=1.5):
        """Update chart with price data, EMA, and Z-Score"""
        if not price_data or len(price_data) < max(ema_period, z_period):
            self.draw_empty_chart()
            return
        
        try:
            # Save current view limits BEFORE clearing figure
            saved_xlim = None
            if hasattr(self, 'price_ax') and self.price_ax is not None:
                try:
                    saved_xlim = self.price_ax.get_xlim()
                except:
                    pass
            
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
            
            # Calculate Z-Score
            df['z_score'] = (df['close'] - df['close'].rolling(z_period).mean()) / df['close'].rolling(z_period).std()
            
            # Clear figure and create subplots
            self.figure.clear()
            gs = self.figure.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
            
            # Price chart (top) - manual candlestick rendering with proper datetime x-axis
            self.price_ax = self.figure.add_subplot(gs[0])
            
            # Convert timestamps to matplotlib date numbers for proper spacing
            from matplotlib.dates import date2num
            x_dates = date2num(df.index)
            
            # Calculate bar width based on time interval (in days)
            if len(x_dates) > 1:
                bar_width = (x_dates[1] - x_dates[0]) * 0.6  # 60% of interval
            else:
                bar_width = 0.0003  # ~30 seconds for single bar
            
            # Plot candlesticks using datetime x-axis
            for i, (timestamp, row) in enumerate(df.iterrows()):
                x = x_dates[i]
                color = '#00ff00' if row['close'] >= row['open'] else '#ff0000'
                
                # Draw high-low line (wick)
                self.price_ax.plot([x, x], [row['low'], row['high']], 
                                  color=color, linewidth=1, alpha=0.8)
                
                # Draw open-close box (body)
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
                self.price_ax.add_patch(rect)
            
            # Add EMA overlay using datetime x-axis
            self.price_ax.plot(x_dates, df['ema'].values.tolist(), color=self.border_color, 
                             linewidth=1.5, label=f'EMA({ema_period})', alpha=0.8)
            
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
                # First time drawing - set default view
                if len(x_dates) > 100:
                    visible_bars = min(240, len(x_dates))
                    x_range = x_dates[-1] - x_dates[-visible_bars]
                    padding = x_range * 0.02
                    self.price_ax.set_xlim(x_dates[-visible_bars], x_dates[-1] + padding)
                    self.price_ax.autoscale(enable=False, axis='x')
                else:
                    x_range = x_dates[-1] - x_dates[0]
                    padding = x_range * 0.02
                    self.price_ax.set_xlim(x_dates[0], x_dates[-1] + padding)
            
            # Update title (price shown on chart now)
            self.title_label.setText(self.title)
            
            # No need to call tight_layout - using constrained_layout in Figure constructor
            # Use draw_idle() to avoid blocking UI thread
            self.canvas.draw_idle()
            
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
        
        # ES offset monitoring timer (check market hours and ES futures state every minute)
        self.offset_monitor_timer = QTimer()
        self.offset_monitor_timer.timeout.connect(self.check_offset_monitoring)
        self.offset_monitor_timer.start(60000)  # Check every minute for responsive market state detection
        
        # ES offset save timer (save offset every 1 minute during market hours)
        self.offset_save_timer = QTimer()
        self.offset_save_timer.timeout.connect(self.save_offset_to_settings)
        self.offset_save_timer.start(60000)  # Save every 60 seconds
        
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
        
        # Log ES offset tracking status at startup
        if self.is_market_hours():
            logger.info("ES offset tracking: ACTIVE (market hours 8:30 AM - 3:00 PM CT)")
        else:
            logger.info("ES offset tracking: INACTIVE (outside market hours) - using saved offset from day session")
        
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
            
            # Calculate duration based on days
            days = int(days_text)
            duration = f"{days} D"
            
            # Create underlying contract
            from ibapi.contract import Contract
            contract = Contract()
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
                contract_key = f"UNDERLYING_{self.instrument['underlying_symbol']}"
            
            self.request_id_map[req_id] = contract_key
            
            # Clear existing data for this chart (both historical and chart data)
            if contract_key in self.historical_data:
                self.historical_data[contract_key] = []
            
            # Also clear chart_data to prevent rendering stale data
            if is_trade_chart:
                self.chart_data['underlying_trade'] = []
            else:
                self.chart_data['underlying'] = []
            
            # Request new data with updated settings
            self.ibkr_client.reqHistoricalData(
                req_id,
                contract,
                "",  # End time (empty = now)
                duration,
                bar_size,
                "TRADES",
                1,  # Use RTH
                1,  # Format date
                True,  # Keep up to date
                []
            )
            
            chart_name = "Trade" if is_trade_chart else "Confirmation"
            logger.info(f"Reloading {chart_name} chart with {interval_text} bars, {days} days")
            self.log_message(f"Reloading {chart_name} chart: {interval_text}, {days} days", "INFO")
            
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
            
            # Calculate duration based on days
            days = int(days_text)
            duration = f"{days} D"
            
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
                1,  # Use RTH
                1,  # Format date
                True,  # Keep up to date
                []
            )
            
            chart_name = "Call" if is_call else "Put"
            logger.info(f"Reloading {chart_name} chart with {interval_text} bars, {days} days")
            self.log_message(f"Reloading {chart_name} chart: {interval_text}, {days} days", "INFO")
            
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
        """Request historical data for the underlying instrument (SPX/XSP)"""
        try:
            from ibapi.contract import Contract
            
            # Create underlying contract
            contract = Contract()
            contract.symbol = self.instrument['underlying_symbol']
            contract.secType = "IND" if self.instrument['underlying_symbol'] == "SPX" else "STK"
            contract.exchange = "CBOE" if self.instrument['underlying_symbol'] == "SPX" else "ARCA"
            contract.currency = "USD"
            
            req_id = self.app_state['next_req_id']
            self.app_state['next_req_id'] += 1
            
            # Store request mapping for chart updates
            contract_key = f"UNDERLYING_{self.instrument['underlying_symbol']}"
            self.request_id_map[req_id] = contract_key
            
            # Request 1 day of 1-minute data for confirmation chart with real-time updates
            self.ibkr_client.reqHistoricalData(
                req_id,
                contract,
                "",  # End time (empty = now)
                "1 D",  # Duration
                "1 min",  # Bar size
                "TRADES",
                1,  # Use RTH
                1,  # Format date
                True,  # Keep up to date - enables real-time bar updates via historicalDataUpdate
                []
            )
            
            logger.info(f"Requested underlying historical data for {contract_key}")
            
            # Request second dataset for trade chart (shorter timeframe)
            req_id_trade = self.app_state['next_req_id']
            self.app_state['next_req_id'] += 1
            
            contract_key_trade = f"UNDERLYING_{self.instrument['underlying_symbol']}_TRADE"
            self.request_id_map[req_id_trade] = contract_key_trade
            
            # Request 4 hours of 30-second data for trade chart with real-time updates
            self.ibkr_client.reqHistoricalData(
                req_id_trade,
                contract,
                "",  # End time (empty = now)
                "14400 S",  # 4 hours in seconds
                "30 secs",  # Bar size
                "TRADES",
                1,  # Use RTH
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
            call_contract_key = f"{self.instrument['symbol']}_{atm_strike}_C_{self.current_expiry}"
            put_contract_key = f"{self.instrument['symbol']}_{atm_strike}_P_{self.current_expiry}"
            
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
            contract.symbol = self.instrument['symbol']
            contract.secType = "OPT"
            contract.exchange = self.instrument['exchange']
            contract.currency = "USD"
            contract.lastTradeDateOrContractMonth = self.current_expiry
            contract.strike = strike
            contract.right = right
            contract.multiplier = str(self.instrument['multiplier'])
            contract.tradingClass = self.instrument['trading_class']
            
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
                1,  # Use RTH
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
                1,  # Use RTH
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
        
        # Top button row - Show Charts button
        top_button_row = QFrame()
        top_button_layout = QHBoxLayout(top_button_row)
        top_button_layout.setContentsMargins(0, 0, 0, 5)
        
        self.show_charts_btn = QPushButton("Show Charts")
        self.show_charts_btn.clicked.connect(self.toggle_chart_window)
        self.show_charts_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 12pt;
                padding: 8px 20px;
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
        top_button_layout.addWidget(self.show_charts_btn)
        top_button_layout.addStretch()
        
        main_layout.addWidget(top_button_row)
        
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
        self.confirm_chart_widget = ProfessionalUnderlyingChart("Confirmation Chart", "#FFA726")
        self.confirm_chart_widget.interval_combo.currentTextChanged.connect(
            lambda: self.on_underlying_settings_changed(self.confirm_chart_widget, is_trade_chart=False)
        )
        self.confirm_chart_widget.days_combo.currentTextChanged.connect(
            lambda: self.on_underlying_settings_changed(self.confirm_chart_widget, is_trade_chart=False)
        )
        
        # Trade Chart (Bottom Right) - Professional underlying with Z-Score
        self.trade_chart_widget = ProfessionalUnderlyingChart("Trade Chart", "#66BB6A")
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
        self.positions_table.setColumnCount(9)
        self.positions_table.setHorizontalHeaderLabels([
            "Contract", "Qty", "Entry", "Current", "P&L", "P&L %", "EntryTime", "TimeSpan", "Action"
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
        panels_layout.setSpacing(5)        # --- PANEL 1: Master Settings (Strategy Control) ---
        self.master_group = QGroupBox("Master Settings")
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
        
        # Target Delta
        self.target_delta_spin = QSpinBox()
        self.target_delta_spin.setRange(10, 50)
        self.target_delta_spin.setSingleStep(10)
        self.target_delta_spin.setValue(self.target_delta)
        self.target_delta_spin.valueChanged.connect(self.on_master_settings_changed)
        master_layout.addRow("Target Delta:", self.target_delta_spin)
        
        # Max Risk
        self.max_risk_spin = QSpinBox()
        self.max_risk_spin.setRange(100, 10000)
        self.max_risk_spin.setSingleStep(50)
        self.max_risk_spin.setValue(self.max_risk)
        self.max_risk_spin.valueChanged.connect(self.on_master_settings_changed)
        master_layout.addRow("Max Risk ($):", self.max_risk_spin)
        
        # Trade Quantity
        self.trade_qty_spin = QSpinBox()
        self.trade_qty_spin.setRange(1, 100)
        self.trade_qty_spin.setValue(self.trade_qty)
        self.trade_qty_spin.valueChanged.connect(self.on_master_settings_changed)
        master_layout.addRow("Trade Quantity:", self.trade_qty_spin)
        
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
        
        master_layout.addRow("Position Sizing:", radio_frame)
        
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
        
        # --- PANEL 6: Reserved for Future Use ---
        future_group = QGroupBox("Reserved for Future Use")
        future_group.setFixedWidth(280)
        future_layout = QVBoxLayout(future_group)
        
        placeholder_label = QLabel(
            "This panel is reserved\n"
            "for future features.\n\n"
            "Chain settings have been\n"
            "moved to the Settings tab."
        )
        placeholder_label.setStyleSheet("color: #888888; font-size: 9pt;")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        future_layout.addWidget(placeholder_label)
        future_layout.addStretch()
        
        panels_layout.addWidget(future_group)
        
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
        
        # Request LIVE market data (type 1 = live, never use delayed data)
        self.ibkr_client.reqMarketDataType(1)
        
        # Use snapshot mode during futures market closed hours (4-5pm CT weekdays, weekends)
        # to get last known price instead of waiting for streaming data
        use_snapshot = self.is_futures_market_closed()
        
        # Subscribe to market data
        self.ibkr_client.reqMktData(req_id, es_contract, "", use_snapshot, False, [])
        mode_str = "snapshot mode" if use_snapshot else "streaming mode"
        self.log_message(f"Subscribed to ES futures {es_contract.lastTradeDateOrContractMonth} ({mode_str}, LIVE data)", "INFO")
    
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
        
        # Update charts based on contract type
        if contract_key.startswith("UNDERLYING_"):
            self.update_underlying_chart_data(contract_key, bar_data)
        elif contract_key.startswith("CHART_"):
            self.update_option_chart_data(contract_key, bar_data)
    
    @pyqtSlot(str)
    def on_historical_complete(self, contract_key: str):
        """Handle historical data complete"""
        if contract_key in self.historical_data:
            bars = self.historical_data[contract_key]
            self.log_message(f"Historical data complete for {contract_key}: {len(bars)} bars", "SUCCESS")
            
            # Update appropriate charts with complete data
            if contract_key.startswith("UNDERLYING_"):
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
            else:
                # This is for the confirmation chart
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
    
    def update_underlying_charts_complete(self, contract_key: str):
        """Update underlying charts when historical data is complete"""
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
                    # Update trade chart with ALL data - throttled for performance
                    self.trade_chart_widget.update_chart_throttled(chart_bars)
                else:
                    # Update confirmation chart with ALL data - throttled for performance
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
            # XSP strikes are in $1 increments, SPX in $5 or $25 increments
            if self.instrument['symbol'] == 'XSP':
                return round(price)  # Round to nearest dollar
            else:  # SPX
                if price < 2000:
                    return round(price / 5) * 5  # $5 increments below 2000
                else:
                    return round(price / 25) * 25  # $25 increments above 2000
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
                
                # Chart Interval/Days Settings
                'call_chart_interval': self.call_chart_widget.interval_combo.currentText(),
                'call_chart_days': self.call_chart_widget.days_combo.currentText(),
                'put_chart_interval': self.put_chart_widget.interval_combo.currentText(),
                'put_chart_days': self.put_chart_widget.days_combo.currentText(),
                'confirm_chart_interval': self.confirm_chart_widget.interval_combo.currentText(),
                'confirm_chart_days': self.confirm_chart_widget.days_combo.currentText(),
                'trade_chart_interval': self.trade_chart_widget.interval_combo.currentText(),
                'trade_chart_days': self.trade_chart_widget.days_combo.currentText(),
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
                
                # Restore Chart Interval/Days Settings
                call_interval = settings.get('call_chart_interval', '15 secs')
                call_days = settings.get('call_chart_days', '1')
                put_interval = settings.get('put_chart_interval', '15 secs')
                put_days = settings.get('put_chart_days', '1')
                confirm_interval = settings.get('confirm_chart_interval', '15 secs')
                confirm_days = settings.get('confirm_chart_days', '1')
                trade_interval = settings.get('trade_chart_interval', '15 secs')
                trade_days = settings.get('trade_chart_days', '1')
                
                # Set combo box values (this will trigger chart reload via signals)
                self.call_chart_widget.interval_combo.setCurrentText(call_interval)
                self.call_chart_widget.days_combo.setCurrentText(call_days)
                self.put_chart_widget.interval_combo.setCurrentText(put_interval)
                self.put_chart_widget.days_combo.setCurrentText(put_days)
                self.confirm_chart_widget.interval_combo.setCurrentText(confirm_interval)
                self.confirm_chart_widget.days_combo.setCurrentText(confirm_days)
                self.trade_chart_widget.interval_combo.setCurrentText(trade_interval)
                self.trade_chart_widget.days_combo.setCurrentText(trade_days)
                
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
