# Dual-Instrument Options Trading Application - PyQt6 Edition (SPX/XSP)

## Project Overview
Professional Bloomberg/TWS-style GUI application for automated 0DTE (Zero Days To Expiration) options trading via Interactive Brokers API. **Designed to trade TWO separate instruments** (SPX and XSP) with configurable settings. Modern PyQt6 architecture with TradingView lightweight-charts for real-time market data visualization.

## ⚠️ CRITICAL: Symbol-Agnostic Code Design

### Never Hardcode Symbol Names in Functions/Variables

**The application MUST support multiple instruments** (SPX, XSP, etc.) through configuration, not hardcoding.

**✅ CORRECT - Generic naming:**
```python
# Functions use generic terms
def create_option_contract(self, strike: float, right: str, symbol: str, trading_class: str):
    """Works for ANY symbol (SPX, XSP, etc.)"""
    pass

def subscribe_underlying_price(self, symbol: str, sec_type: str, exchange: str):
    """Generic function for any underlying"""
    pass

# Variables use generic terms
self.underlying_price = 0.0     # ✓ Generic
self.underlying_symbol = "SPX"  # ✓ Configuration
self.option_contracts = []      # ✓ Generic
self.options_symbol = "SPX"     # ✓ Configuration
```

**❌ WRONG - Symbol-specific naming:**
```python
def create_spx_contract():     # ✗ Hardcoded SPX
def subscribe_spx_price():     # ✗ Hardcoded SPX
self.spx_price = 0.0           # ✗ Hardcoded SPX
self.spx_contracts = []        # ✗ Hardcoded SPX
```

### Dual-Instrument Configuration Pattern

Configure instruments at the top of the application:

```python
# ============================================================================
# INSTRUMENT CONFIGURATION - Two separate tradable instruments
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
        'strike_increment': 5.0,
        'tick_size_above_3': 0.10,           # >= $3.00
        'tick_size_below_3': 0.05,           # < $3.00
        'description': 'S&P 500 Index Options (Full size)'
    },
    'XSP': {
        'name': 'XSP',
        'underlying_symbol': 'XSP',          # Mini-SPX symbol
        'options_symbol': 'XSP',
        'options_trading_class': 'XSP',
        'underlying_type': 'STK',            # Stock/ETF type
        'underlying_exchange': 'ARCA',
        'multiplier': '100',
        'strike_increment': 1.0,
        'tick_size_above_3': 0.05,
        'tick_size_below_3': 0.05,
        'description': 'Mini-SPX Options (1/10 size)'
    }
}

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Select instrument via settings or UI
        self.current_instrument = 'SPX'  # Default, or from settings
        self.instrument = INSTRUMENT_CONFIG[self.current_instrument]
        
        # Extract configuration for easy access
        self.underlying_symbol = self.instrument['underlying_symbol']
        self.options_symbol = self.instrument['options_symbol']
        self.trading_class = self.instrument['options_trading_class']
```

### Generic Function Implementation

All functions must accept symbol parameters, never hardcode:

```python
def subscribe_underlying_price(self):
    """Subscribe to underlying price - works for any configured instrument"""
    underlying_contract = Contract()
    underlying_contract.symbol = self.underlying_symbol  # From config
    underlying_contract.secType = self.instrument['underlying_type']
    underlying_contract.currency = "USD"
    underlying_contract.exchange = self.instrument['underlying_exchange']
    
    req_id = self.next_req_id()
    self.app_state['underlying_req_id'] = req_id
    self.ibkr_client.reqMktData(req_id, underlying_contract, "", False, False, [])
    logger.info(f"Subscribed to {self.underlying_symbol} underlying price")

def create_option_contract(self, strike: float, right: str) -> Contract:
    """Create option contract for current instrument"""
    contract = Contract()
    contract.symbol = self.options_symbol  # From config
    contract.secType = "OPT"
    contract.currency = "USD"
    contract.exchange = "SMART"
    contract.tradingClass = self.trading_class  # From config
    contract.strike = strike
    contract.right = right
    contract.lastTradeDateOrContractMonth = self.current_expiry
    contract.multiplier = self.instrument['multiplier']
    return contract

def round_to_tick_size(self, price: float) -> float:
    """Round price to instrument-specific tick size"""
    if price >= 3.00:
        tick_size = self.instrument['tick_size_above_3']
    else:
        tick_size = self.instrument['tick_size_below_3']
    return round(price / tick_size) * tick_size
```

### UI Must Show Current Instrument

```python
# Update window title
self.setWindowTitle(f"{self.instrument['name']} 0DTE Options Trader - PyQt6 Professional Edition")

# Update labels
self.underlying_price_label = QLabel(f"{self.instrument['name']}: Loading...")

# Log messages should include symbol
logger.info(f"Requesting {self.options_symbol} option chain for 0DTE...")
```

## Python Environment (CRITICAL!)

### Virtual Environment: `.venv`
**⚠️ ALWAYS use the virtual environment - NEVER install to root Python!**

- **Location**: `.venv/` folder in project root
- **Python Version**: 3.11+
- **Activation**: 
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **Installing packages**: 
  ```powershell
  .\.venv\Scripts\python.exe -m pip install <package>
  # OR (if venv activated)
  pip install <package>
  ```

### Dependency Management Rules
1. **ALWAYS install to `.venv`**, not global Python
2. **Update `requirements.txt`** after adding new dependencies
3. **Test imports** in venv before committing:
   ```powershell
   .\.venv\Scripts\python.exe -c "import <module>; print('✓ Import successful')"
   ```
4. **VS Code Python interpreter** should point to `.venv\Scripts\python.exe`

### Current Dependencies
- `PyQt6>=6.6.0`: Modern Qt6 framework for Python
- `PyQt6-WebEngine>=6.6.0`: For lightweight-charts WebView integration
- `lightweight-charts-python>=2.0`: TradingView charting library
- `ibapi>=9.81.1`: Interactive Brokers API
- `pandas>=2.0.0`, `numpy>=1.24.0`: Data processing
- `scipy>=1.11.0`: Black-Scholes greeks calculations

**Install all dependencies**: 
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Core Architecture

### PyQt6 Design Patterns

#### Application Structure
```python
QApplication → MainWindow(QMainWindow)
    ├── QTabWidget (main tabs)
    │   ├── TradingTab (QWidget)
    │   │   ├── Option Chain (QTableWidget)
    │   │   ├── Charts Panel (QSplitter)
    │   │   │   ├── Call Chart (ChartWidget with WebEngineView)
    │   │   │   └── Put Chart (ChartWidget with WebEngineView)
    │   │   ├── Positions/Orders (QSplitter)
    │   │   │   ├── Positions (QTableWidget)
    │   │   │   └── Orders (QTableWidget)
    │   │   └── Manual Trading Panel (QFrame)
    │   └── SettingsTab (QWidget)
    └── QStatusBar
```

#### Thread Safety with Signals/Slots
**CRITICAL: All GUI updates MUST use PyQt signals from IBKR thread**

```python
# Define custom signals in MainWindow
class MainWindow(QMainWindow):
    # Custom signals for thread-safe updates
    spx_price_updated = pyqtSignal(float)
    market_data_updated = pyqtSignal(str, dict)  # contract_key, data
    position_updated = pyqtSignal(str, dict)
    order_status_updated = pyqtSignal(int, str, dict)
    log_message_signal = pyqtSignal(str, str)  # message, level
    
    def __init__(self):
        super().__init__()
        # Connect signals to slots
        self.spx_price_updated.connect(self.update_spx_display)
        self.market_data_updated.connect(self.update_option_chain_cell)
        # ... etc

# In IBKRWrapper callbacks (API thread):
def tickPrice(self, reqId, tickType, price, attrib):
    # Emit signal instead of direct GUI update
    if reqId == self.app.spx_req_id and tickType == 4:
        self.app.main_window.spx_price_updated.emit(price)
```

**Never do this:**
```python
# WRONG - Direct GUI update from IBKR thread
def tickPrice(self, reqId, tickType, price, attrib):
    self.app.spx_label.setText(f"SPX: {price:.2f}")  # ❌ CRASH!
```

#### QTimer for Periodic Updates
Replace `root.after()` with `QTimer`:

```python
# Update positions every second
self.position_update_timer = QTimer()
self.position_update_timer.timeout.connect(self.update_positions_display)
self.position_update_timer.start(1000)  # 1000ms = 1 second

# Chart refresh (debounced)
self.chart_update_timer = QTimer()
self.chart_update_timer.setSingleShot(True)  # Debounce mode
self.chart_update_timer.timeout.connect(self._update_chart_now)
```

### Lightweight-Charts Integration

#### Chart Widget Architecture
```python
from PyQt6.QtWebEngineWidgets import QWebEngineView
from lightweight_charts import Chart

class ChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chart = Chart()
        
        # Create WebEngineView to display chart
        self.web_view = QWebEngineView()
        self.web_view.setHtml(self.chart.get_webview_html())
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.web_view)
        layout.setContentsMargins(0, 0, 0, 0)
    
    def update_data(self, bars: list):
        """Update chart with new candlestick data"""
        # Lightweight-charts expects: [{'time': '2023-01-01', 'open': 100, 'high': 101, ...}]
        self.chart.set(bars)
```

#### Real-Time Data Streaming
```python
# Add single candle in real-time
def on_new_bar(self, bar_data):
    self.chart.update({
        'time': bar_data['date'],
        'open': bar_data['open'],
        'high': bar_data['high'],
        'low': bar_data['low'],
        'close': bar_data['close']
    })
```

#### Performance Optimization
- Use `set()` for bulk data loading
- Use `update()` for single-bar updates (real-time)
- Limit visible bars to reduce rendering overhead
- Debounce chart updates with QTimer (100-200ms)

### Dark Theme Styling

#### IBKR TWS Color Scheme (QSS)
```python
DARK_STYLESHEET = """
QMainWindow {
    background-color: #000000;
}

QTableWidget {
    background-color: #000000;
    color: #c8c8c8;
    gridline-color: #1a1a1a;
    selection-background-color: #1a2a3a;
    selection-color: #ffffff;
    border: 1px solid #1a1a1a;
}

QTableWidget::item {
    padding: 5px;
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

QPushButton:pressed {
    background-color: #0a0a0a;
}

/* Success button (green) */
QPushButton[success="true"] {
    background-color: #1a3a1a;
    color: #44ff44;
    border: 1px solid #2a5a2a;
}

/* Danger button (red) */
QPushButton[danger="true"] {
    background-color: #3a1a1a;
    color: #ff4444;
    border: 1px solid #5a2a2a;
}
"""

# Apply stylesheet
app = QApplication(sys.argv)
app.setStyleSheet(DARK_STYLESHEET)
```

#### Dynamic Cell Coloring
```python
def update_option_chain_cell(self, row, col, value, pnl=None):
    item = QTableWidgetItem(str(value))
    
    # Color based on P&L
    if pnl is not None:
        if pnl > 0:
            item.setForeground(QColor("#00ff00"))  # Green
        elif pnl < 0:
            item.setForeground(QColor("#ff0000"))  # Red
    
    # ITM background
    if self.is_itm(row, col):
        item.setBackground(QColor("#0f1a2a"))  # Blue tint
    
    self.option_table.setItem(row, col, item)
```

## Key Data Structures

### Contract Key Format
All options identified by standardized string: `"SPX_{strike}_{right}_{YYYYMMDD}"`
- Example: `"SPX_6740_C_20251024"` (SPX Call at 6740, expiring Oct 24, 2025)
- Used as dictionary keys: `market_data`, `positions`, `historical_data`

### Critical State Dictionaries
- `market_data`: Live bid/ask/last/greeks keyed by contract_key
- `market_data_map`: Maps IBKR reqId → contract_key for callback routing
- `positions`: Active positions with entry, current price, P&L
- `pending_orders`: orderId → (contract_key, action, quantity)
- `manual_orders`: Track manual orders with mid-price chasing

### Connection State Machine
```
DISCONNECTED → CONNECTING → CONNECTED
       ↑ (auto-retry)          ↓ (on error)
       └─────────────────────────┘
```

## SPXW Contract Specifications

### Trading Class: "SPXW"
- **Symbol**: "SPX" (NOT "SPXW")
- **TradingClass**: "SPXW"
- **Exchange**: "SMART"
- **Currency**: "USD"
- **Multiplier**: "100"
- **SecType**: "OPT"

### Expiration Date Handling
- Format: "YYYYMMDD" (e.g., "20251024")
- Monday/Wednesday/Friday expirations for SPX
- User can switch via QComboBox (0 DTE, 1 DTE, etc.)

## Trading Strategy Implementation

### Manual Trading Mode
**Risk-based one-click trading with mid-price chasing**

#### Entry System:
1. BUY CALL/PUT buttons scan chain for max risk ≤ specified amount
2. Place limit order at mid-price (bid+ask)/2
3. Monitor with QTimer every 1 second
4. Auto-adjust price if mid moves (cancel/replace)
5. Continue until filled or cancelled

#### SPX Tick Size Rules:
- Prices ≥ $3.00: Round to $0.10 increments
- Prices < $3.00: Round to $0.05 increments

#### Exit System:
- "Close" button in QTableWidget delegates
- Exit at mid-price with same chasing logic
- Confirmation QMessageBox shows current P&L

### Hourly Straddle Entry (Automated)
1. Triggered at top of hour by QTimer
2. Find cheapest call/put with ask ≤ $0.50
3. Place limit orders at ask price
4. Track in `active_straddles` list

## GUI Components Best Practices

### QTableWidget Optimization
```python
# Disable updates during bulk changes
table.setUpdatesEnabled(False)
for row in range(100):
    # ... update cells
table.setUpdatesEnabled(True)

# Use item delegates for custom rendering
class PriceDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # Custom painting for performance
        pass
```

### QSplitter for Resizable Panels
```python
splitter = QSplitter(Qt.Orientation.Horizontal)
splitter.addWidget(call_chart)
splitter.addWidget(put_chart)
splitter.setSizes([400, 400])  # Equal sizes
splitter.setCollapsible(0, False)  # Prevent collapse
```

### QDialog for Settings
```python
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        
        # Form layout for inputs
        form = QFormLayout()
        self.host_edit = QLineEdit()
        form.addRow("Host:", self.host_edit)
        
        # Button box
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
```

## Settings Persistence

### JSON Configuration
```python
import json
from pathlib import Path

def save_settings(self):
    settings = {
        'host': self.host,
        'port': self.port,
        'client_id': self.client_id,
        # ... all settings
    }
    Path('settings.json').write_text(json.dumps(settings, indent=2))

def load_settings(self):
    if Path('settings.json').exists():
        settings = json.loads(Path('settings.json').read_text())
        self.host = settings.get('host', '127.0.0.1')
        # ... restore all settings
```

## Development Workflows

### Running the Application
```powershell
# Always use virtual environment
.\.venv\Scripts\python.exe main.py

# Or activate first
.\.venv\Scripts\Activate.ps1
python main.py
```

### Debugging Tips
1. **Use Qt Creator Designer** for complex layouts (optional)
2. **Enable Qt warnings**: `export QT_LOGGING_RULES='*.debug=true'`
3. **Check thread affinity**: `QObject.thread()` to verify signals
4. **Profile with cProfile** for performance bottlenecks
5. **Use Qt's built-in debugging**: `QObject.dumpObjectTree()`

### Testing Requirements
1. **IBKR Setup**: TWS or IB Gateway on port 7497 (paper trading)
2. **Market Data**: SPX + SPXW subscriptions
3. **Market Hours**: 9:30 AM - 4:00 PM ET for full functionality
4. **WebEngine**: Ensure PyQt6-WebEngine installed for charts

## Critical Constraints

- **Cross-platform**: PyQt6 works on Windows/Mac/Linux (prefer Windows for IBKR)
- **Real-money risk**: Always test with paper trading first (port 7497)
- **Market hours dependency**: Most functionality requires active market
- **WebEngine dependency**: lightweight-charts requires QWebEngineView

## Performance Optimization

### Chart Rendering
1. Debounce updates with QTimer (100-200ms)
2. Limit visible candles (e.g., last 500 bars)
3. Use `update()` for single bars, not `set()`
4. Disable animations if needed for speed

### Table Updates
1. Use `setUpdatesEnabled(False)` during bulk updates
2. Update only changed cells, not entire rows
3. Consider QAbstractTableModel for large datasets
4. Use item delegates for custom rendering

### Memory Management
1. Clear old historical data periodically
2. Disconnect signals when widgets destroyed
3. Delete unused chart instances
4. Monitor with `gc.collect()` and `objgraph`

## Common PyQt6 Gotchas

1. **Signal/Slot Types**: Must match exactly (`int` vs `float`)
2. **Lambda Connections**: Use `functools.partial` to avoid closure issues
3. **Widget Lifecycle**: Parent widgets delete children automatically
4. **Event Loop**: Don't block main thread with long operations
5. **WebEngine**: Requires separate process, handle crashes gracefully

## Migration from Tkinter

### Key Differences
| Tkinter | PyQt6 |
|---------|-------|
| `root.after()` | `QTimer` |
| `messagebox` | `QMessageBox` |
| `ttk.Treeview` | `QTableWidget` or `QTreeWidget` |
| `tksheet.Sheet` | `QTableWidget` |
| Grid/Pack layout | `QVBoxLayout`, `QHBoxLayout`, `QGridLayout` |
| Thread-safe queue | PyQt signals/slots |
| Matplotlib canvas | lightweight-charts with QWebEngineView |

### Advantages of PyQt6
✅ True thread safety with signals/slots  
✅ Better performance for large datasets  
✅ Native look and feel on all platforms  
✅ Rich widget library (QSplitter, QDockWidget, etc.)  
✅ Professional styling with QSS  
✅ Better WebView integration for TradingView charts  
✅ Active development and long-term support  

## Error Handling

### Exception Hooks
```python
import sys
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

def qt_message_handler(mode, context, message):
    if mode == QtMsgType.QtWarningMsg:
        print(f"Qt Warning: {message}")
    elif mode == QtMsgType.QtCriticalMsg:
        print(f"Qt Critical: {message}")
    elif mode == QtMsgType.QtFatalMsg:
        print(f"Qt Fatal: {message}")

qInstallMessageHandler(qt_message_handler)

def exception_hook(exctype, value, traceback):
    print(f"Unhandled exception: {exctype.__name__}: {value}")
    sys.__excepthook__(exctype, value, traceback)

sys.excepthook = exception_hook
```

## Deployment

### PyInstaller (Optional)
```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name "SPX_Trader" main.py
```

### Dependencies Bundle
Include in distribution:
- `settings.json` (template)
- `README.md` (setup instructions)
- `requirements.txt`
- `.venv` setup script

---

**Remember**: PyQt6 is event-driven. Design around signals/slots, not polling loops. Let Qt handle the threading complexity.
