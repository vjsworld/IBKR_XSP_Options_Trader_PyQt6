# Dual-Instrument Options Trading Application - PyQt6 Edition (SPX/XSP)

## Project Overview
Professional Bloomberg/TWS-style GUI application for automated 0DTE (Zero Days To Expiration) options trading via Interactive Brokers API. **Designed to trade TWO separate instruments** (SPX and XSP) with configurable settings. Modern PyQt6 architecture with **matplotlib/mplfinance** for professional TradingView-style candlestick visualization.

## ⚙️ Instrument Selection (How to Switch Between SPX and XSP)

**The instrument selection is at the very top of `main.py` for easy access:**

```python
# ============================================================================
# ⚙️ TRADING INSTRUMENT SELECTION - CHANGE THIS TO SWITCH INSTRUMENTS
# ============================================================================
# Set this to either 'SPX' (full-size S&P 500) or 'XSP' (mini 1/10 size)
# This controls which instrument the application will trade
SELECTED_INSTRUMENT = 'SPX'  # Change to 'XSP' for mini-SPX trading
# ============================================================================
```

**To switch instruments:**
1. Open `main.py`
2. Go to line ~19 (right after the module docstring and imports)
3. Change `SELECTED_INSTRUMENT = 'SPX'` to `SELECTED_INSTRUMENT = 'XSP'` (or vice versa)
4. Restart the application

**The application will automatically:**
- Use the correct symbol, trading class, and exchange
- Apply correct tick sizes and strike increments
- Update window title and all labels
- Log the selected instrument on startup

**Key Differences:**
- **SPX**: Full-size S&P 500 Index, $5 strike increments, tick sizes: ≥$3.00→$0.10, <$3.00→$0.05
- **XSP**: Mini-SPX (1/10 size), $1 strike increments, tick size: $0.05 always

**Implementation Pattern:**
```python
# In MainWindow.__init__():
self.trading_instrument = SELECTED_INSTRUMENT  # From top of file
self.instrument = INSTRUMENT_CONFIG[self.trading_instrument]

# All functions use self.instrument configuration:
contract.symbol = self.instrument['options_symbol']
contract.tradingClass = self.instrument['options_trading_class']
tick_size = self.instrument['tick_size_above_3'] if price >= 3.0 else self.instrument['tick_size_below_3']
```

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
- `PyQt6-WebEngine>=6.6.0`: For web content rendering (optional)
- `matplotlib>=3.8.0`: Industry-standard plotting library
- `mplfinance>=0.12.10`: Specialized financial charting for candlesticks
- `ibapi>=9.81.1`: Interactive Brokers API
- `pandas>=2.0.0`, `numpy>=1.24.0`: Data processing

**Install all dependencies**: 
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### ⚠️ CRITICAL: Greeks Calculation - DO NOT Use Black-Scholes

**✅ CORRECT - Use IBKR's model-based greeks:**
```python
# Greeks are automatically provided by IBKR via tickOptionComputation callback
def tickOptionComputation(self, reqId, tickType, tickAttrib, 
                          impliedVol, delta, optPrice, pvDividend,
                          gamma, vega, theta, undPrice):
    """
    IBKR provides model-based greeks calculated using bid/ask mid-price.
    This is MORE ACCURATE than custom Black-Scholes calculations.
    
    tickType 13 = MODEL_OPTION (computed greeks)
    - delta: Position delta
    - gamma: Gamma (rate of change of delta)
    - theta: Theta (time decay per day)
    - vega: Vega (sensitivity to volatility per 1%)
    - impliedVol: Implied volatility
    """
    if tickType == 13:  # MODEL_OPTION
        contract_key = self.app.market_data_map.get(reqId)
        if contract_key:
            self.app.market_data[contract_key].update({
                'delta': delta,
                'gamma': gamma,
                'theta': theta,
                'vega': vega,
                'iv': impliedVol
            })
            # Emit signal for GUI update
            self.app.main_window.market_data_updated.emit(contract_key, 
                                                          self.app.market_data[contract_key])
```

**❌ WRONG - Do NOT implement Black-Scholes:**
```python
# ✗ DO NOT DO THIS - Removed from codebase
from scipy.stats import norm  # ✗ Dependency removed

def calculate_greeks(spot, strike, tte, vol, rate):  # ✗ Function removed
    """
    This approach is LESS ACCURATE than IBKR's model-based greeks because:
    1. IBKR uses actual bid/ask mid-price (real market conditions)
    2. IBKR's model accounts for dividends, rates, early exercise
    3. Custom Black-Scholes requires manual volatility/rate inputs
    4. Adds unnecessary scipy dependency
    """
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol**2) * tte) / (vol * math.sqrt(tte))
    d2 = d1 - vol * math.sqrt(tte)
    # ... ✗ Don't implement this
```

**Why IBKR's greeks are superior:**
1. ✅ **Real-time accuracy**: Calculated from actual bid/ask mid-price
2. ✅ **Professional model**: Uses IBKR's institutional-grade pricing
3. ✅ **Market conditions**: Accounts for dividends, interest rates, early exercise
4. ✅ **No manual inputs**: No need to estimate volatility or risk-free rate
5. ✅ **Simpler code**: Eliminates 60+ lines of Black-Scholes calculations
6. ✅ **Fewer dependencies**: Removes scipy requirement

**Implementation notes:**
- Subscribe to market data with `reqMktData()` for each option contract
- Greeks arrive automatically via `tickOptionComputation` callback
- Update GUI using PyQt signals from the callback (thread-safe)
- Store greeks in `market_data[contract_key]` dictionary
- No calculation code needed - IBKR does all the work

## Core Architecture

### PyQt6 Design Patterns

#### Application Structure
```python
QApplication → MainWindow(QMainWindow)
    ├── QTabWidget (main tabs)
    │   ├── TradingTab (QWidget)
    │   │   ├── Option Chain (QTableWidget)
    │   │   ├── Charts Panel (QSplitter)
    │   │   │   ├── Call Chart (ChartWidget with matplotlib/mplfinance)
    │   │   │   └── Put Chart (ChartWidget with matplotlib/mplfinance)
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

### matplotlib/mplfinance Integration (Professional Candlestick Charts)

#### Chart Widget Architecture
**We use matplotlib with mplfinance for professional TradingView-style charts:**

```python
import matplotlib
matplotlib.use('QtAgg')  # Qt backend for PyQt6 integration

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import mplfinance as mpf
import pandas as pd

class ChartWidget(QWidget):
    """Professional candlestick chart using matplotlib/mplfinance"""
    
    def __init__(self, title="Chart", parent=None):
        super().__init__(parent)
        self.title = title
        self.bars = []
        self.setup_ui()
    
    def setup_ui(self):
        """Setup matplotlib figure with TradingView dark theme"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QLabel(self.title)
        header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(header)
        
        # Create matplotlib figure with dark background
        self.figure = Figure(figsize=(8, 6), facecolor='#131722')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111, facecolor='#1e222d')
        
        # TradingView-style theme
        self.ax.tick_params(colors='#787b86', which='both')
        self.ax.spines['bottom'].set_color('#2a2e39')
        self.ax.spines['top'].set_color('#2a2e39')
        self.ax.spines['left'].set_color('#2a2e39')
        self.ax.spines['right'].set_color('#2a2e39')
        
        layout.addWidget(self.canvas)
    
    def update_data(self, bars: list):
        """Update chart with candlestick data using mplfinance"""
        if not bars:
            return
        
        self.bars = bars
        self.ax.clear()
        
        # Convert bars to pandas DataFrame
        data = []
        for bar in bars:
            date_str = bar['date']
            data.append({
                'Date': pd.to_datetime(date_str, format='%Y%m%d'),
                'Open': float(bar['open']),
                'High': float(bar['high']),
                'Low': float(bar['low']),
                'Close': float(bar['close']),
                'Volume': int(bar.get('volume', 0))
            })
        
        df = pd.DataFrame(data)
        df.set_index('Date', inplace=True)
        
        # Create TradingView-style market colors
        mc = mpf.make_marketcolors(
            up='#26a69a',      # Teal green (bullish)
            down='#ef5350',    # Red (bearish)
            edge='inherit',
            wick='inherit',
            volume='in',
            alpha=1.0
        )
        
        # Create style with dark theme
        s = mpf.make_mpf_style(
            marketcolors=mc,
            gridcolor='#2a2e39',
            gridstyle='-',
            y_on_right=False,
            facecolor='#1e222d',
            figcolor='#131722',
            edgecolor='#2a2e39',
            rc={'axes.labelcolor': '#787b86',
                'xtick.color': '#787b86',
                'ytick.color': '#787b86'}
        )
        
        # Plot candlesticks directly on our axes
        mpf.plot(df, type='candle', style=s, ax=self.ax, 
                 volume=False, show_nontrading=False)
        
        self.canvas.draw()
    
    def add_bar(self, bar: dict):
        """Add single bar for real-time updates"""
        self.bars.append(bar)
        # Keep only last 200 bars for performance
        if len(self.bars) > 200:
            self.bars = self.bars[-200:]
        self.update_data(self.bars)
```

#### Key Advantages Over PyQt6-Charts

✅ **Simpler Code**: 160 lines vs 250+ lines (36% reduction)  
✅ **Industry Standard**: matplotlib is the most widely-used Python plotting library  
✅ **Professional Styling**: Built-in TradingView dark theme  
✅ **Better Display**: Actual candlesticks instead of buggy dots  
✅ **Proven Reliability**: mplfinance is specialized for financial charts  
✅ **Easier Maintenance**: Well-documented with large community support  

#### Real-Time Data Streaming
```python
# Add single candle in real-time
def on_new_bar(self, bar_data):
    """bar_data format: {'date': '20251027', 'open': 100, 'high': 101, 'low': 99, 'close': 100.5}"""
    self.chart_widget.add_bar(bar_data)
```

#### Performance Optimization
- Limit visible bars to last 200 for smooth rendering
- Use `self.ax.clear()` before updates
- `canvas.draw()` only after data changes
- Disable animations (matplotlib default)

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

### Universal Order Chasing System
**⚠️ CRITICAL: ALL orders MUST use the same mid-price chasing with "give in" logic**

**Design Principle**: Every order - whether manual entry, automated entry, or exit - MUST use the unified `place_order()` function with `enable_chasing=True`. No special cases or separate logic paths.

#### Unified Order Flow (for ALL orders):
1. **Order Placement**: All orders call `place_order(contract_key, action, quantity, limit_price, enable_chasing=True)`
2. **Initial Limit Price**: Set to current mid-price (bid+ask)/2 rounded to tick size
3. **Order Tracking**: Added to `self.chasing_orders` dictionary with tracking info
4. **Continuous Monitoring**: `update_orders()` timer runs every 1 second for all chasing orders
5. **Auto-Adjustment**: Price updates if:
   - Mid-price moves ≥ $0.05 (recalculate: current_mid ± X_ticks)
   - Every 10 seconds without fill → increment X_ticks, recalculate price
6. **"Give In" Logic** (applies to ALL orders):
   - X_ticks starts at 0 (initial order at pure mid)
   - After 10 sec: X_ticks = 1 → price = mid ± (1 × tick_size)
   - After 20 sec: X_ticks = 2 → price = mid ± (2 × tick_size)
   - After 30 sec: X_ticks = 3 → price = mid ± (3 × tick_size)
   - For BUY: price = mid + X_ticks (creeping toward ask)
   - For SELL: price = mid - X_ticks (creeping toward bid)
   - Uses instrument tick size rules (SPX: ≥$3.00→$0.10, <$3.00→$0.05)

#### Order Types (all use same system):
- **Manual Entry Orders** (BUY CALL/PUT buttons): `place_order()` with chasing enabled
- **Automated Entry Orders** (hourly straddles, etc.): `place_order()` with chasing enabled
- **Exit Orders** (Close button): `place_order()` with chasing enabled
- **Any Future Order Type**: MUST use `place_order()` with chasing enabled

#### Implementation Pattern:
```python
# ✅ CORRECT - All order types use unified function
def manual_buy_call(self):
    """Manual call entry - uses unified chasing"""
    contract_key, mid_price = self.find_option_by_max_risk("C", max_risk)
    self.place_order(contract_key, "BUY", 1, mid_price, enable_chasing=True)

def manual_close_position(self, contract_key):
    """Exit order - uses same unified chasing"""
    mid_price = self.calculate_mid_price(contract_key)
    self.place_order(contract_key, "SELL", qty, mid_price, enable_chasing=True)

def hourly_straddle_entry(self):
    """Automated entry - uses same unified chasing"""
    call_key, call_price = self.find_cheapest_option("C")
    self.place_order(call_key, "BUY", 1, call_price, enable_chasing=True)

# ❌ WRONG - Don't create separate order placement logic
def place_exit_order(self, ...):  # ✗ Don't create separate functions
    # Special exit logic here...  # ✗ No special cases!
```

#### Order Tracking Structure:
```python
# All chasing orders stored in self.chasing_orders
self.chasing_orders[order_id] = {
    'contract_key': contract_key,
    'contract': contract,
    'action': action,  # "BUY" or "SELL"
    'quantity': quantity,
    'initial_mid': limit_price,
    'last_mid': limit_price,
    'last_price': limit_price,  # Actual order price (mid ± X_ticks)
    'give_in_count': 0,  # Increments every 10 seconds
    'attempts': 1,
    'timestamp': datetime.now(),  # Reset on each price update
    'order': order
}
```

#### Why This Matters:
1. **Consistency**: All orders get filled using the same proven strategy
2. **Simplicity**: One code path = easier to maintain and debug
3. **Reliability**: Exit orders get same aggressive filling as entry orders
4. **Fairness**: No order type is disadvantaged or gets special treatment
5. **Testability**: Single system to test and verify

**Never create custom order placement logic for specific order types!**

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
4. **matplotlib**: Ensure matplotlib and mplfinance installed for charts

## Critical Constraints

- **Cross-platform**: PyQt6 works on Windows/Mac/Linux (prefer Windows for IBKR)
- **Real-money risk**: Always test with paper trading first (port 7497)
- **Market hours dependency**: Most functionality requires active market
- **matplotlib charts**: Professional TradingView-style candlesticks with mplfinance

## Performance Optimization

### Chart Rendering
1. Update only when data changes (matplotlib handles efficiently)
2. Limit visible candles to last 200 bars for performance
3. Use `ax.clear()` before updates, then `canvas.draw()`
4. Consider debouncing with QTimer if needed (100-200ms)

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
| Matplotlib canvas | matplotlib with `FigureCanvasQTAgg` + mplfinance |

### Advantages of PyQt6 + matplotlib
✅ True thread safety with signals/slots  
✅ Better performance for large datasets  
✅ Native look and feel on all platforms  
✅ Rich widget library (QSplitter, QDockWidget, etc.)  
✅ Professional styling with QSS  
✅ Industry-standard charting with matplotlib/mplfinance  
✅ TradingView-style charts out of the box  
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
