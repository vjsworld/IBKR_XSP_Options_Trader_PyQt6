# SPX 0DTE Options Trading Application - PyQt6 Edition

## Overview
Professional Bloomberg/TWS-style GUI application for automated 0DTE (Zero Days To Expiration) SPX options trading via Interactive Brokers API. Built with modern PyQt6 framework and **matplotlib/mplfinance** for professional TradingView-style candlestick charts.

## Features

### Core Functionality
- ✅ **Real-time SPX Price Tracking**: Live underlying index price updates
- ✅ **Option Chain Display**: IBKR TWS-style layout with calls/strikes/puts
- ✅ **Real-time Market Data**: Bid/ask/last prices, volume, greeks streaming
- ✅ **Professional Charts**: matplotlib/mplfinance candlestick charts with TradingView theme
- ✅ **Position Management**: Real-time P&L tracking with entry/exit management
- ✅ **Order Management**: Live order status with intelligent execution
- ✅ **Manual Trading**: One-click BUY CALL/PUT with risk-based sizing
- ✅ **Dark Theme**: IBKR TWS color scheme for professional appearance

### Trading Features
- **Manual Trading Mode**: Risk-based position sizing with mid-price chasing
- **Intelligent Order Management**: Auto-adjusts limit prices to improve fills
- **Position Tracking**: Real-time P&L with color-coded profit/loss
- **Flexible Expiration**: Switch between 0DTE, 1DTE, or any available expiry
- **Customizable Strikes**: Adjustable strike range around SPX price

### Technology Stack
- **PyQt6**: Modern Qt6 framework for native performance and thread safety
- **matplotlib/mplfinance**: Industry-standard charting for professional candlestick charts
- **IBKR API**: Professional-grade market data and order execution
- **Signal/Slot Architecture**: Thread-safe GUI updates from API callbacks

## Installation

### Prerequisites
- Python 3.11 or higher
- Interactive Brokers TWS or IB Gateway installed and configured
- Windows, macOS, or Linux (Windows recommended for IBKR)
- Market data subscriptions: SPX + SPXW options

### Setup Steps

1. **Clone or download this project**
   ```powershell
   cd "d:\Dropbox\VRB Share\IBKR XSP Option Trader1 (PyQt6)"
   ```

2. **Run the setup script** (PowerShell)
   ```powershell
   .\setup.ps1
   ```
   
   This will:
   - Create virtual environment (`.venv`)
   - Install all dependencies from `requirements.txt`
   - Verify installation

3. **Manual installation** (alternative)
   ```powershell
   # Create virtual environment
   python -m venv .venv
   
   # Activate virtual environment
   .\.venv\Scripts\Activate.ps1
   
   # Install dependencies
   pip install -r requirements.txt
   ```

### Dependencies
The application requires:
- `PyQt6>=6.6.0` - GUI framework
- `matplotlib>=3.8.0` - Industry-standard plotting library
- `mplfinance>=0.12.10` - Financial charting (candlesticks)
- `ibapi>=9.81.1` - Interactive Brokers API
- `pandas>=2.0.0` - Data processing
- `numpy>=1.24.0` - Numerical operations

## Running the Application

### Instrument Configuration

The application supports trading on three types of instruments:
- **XSP**: Mini S&P 500 Index Options ($100 multiplier, $1 strike increments)
- **SPX**: Full-size S&P 500 Index Options ($100 multiplier, $5 strike increments)
- **ES Futures**: E-mini S&P 500 Futures Options (FOP, $50 multiplier, $5 strike increments)

**To select an instrument**, edit `config.py`:

```python
# For index options:
SELECTED_INSTRUMENT = 'XSP'   # or 'SPX'

# For ES futures options - use the actual futures contract:
SELECTED_INSTRUMENT = 'ESZ5'  # December 2025
SELECTED_INSTRUMENT = 'ESH6'  # March 2026
SELECTED_INSTRUMENT = 'ESM6'  # June 2026
```

#### ES Futures Options (FOP) Configuration

For ES Futures Options, specify the **actual futures contract symbol** in `SELECTED_INSTRUMENT`:

**ES Futures Contract Naming** (CME convention):
- **Month Codes**: H=Mar, M=Jun, U=Sep, Z=Dec (quarterly contracts)
- **Year**: Last digit (5=2025, 6=2026, etc.)
- **Format**: ES + Month Code + Year Digit
- **Examples**: 
  - `ESZ5` = ES December 2025 (current front month)
  - `ESH6` = ES March 2026
  - `ESM6` = ES June 2026
  - `ESU6` = ES September 2026

**The application will automatically**:
- Detect that you're trading futures options (starts with "ES")
- Parse the contract month and year
- Calculate the 3rd Friday expiry date
- Configure FOP-specific parameters (CME exchange, $50 multiplier, etc.)

**CRITICAL DIFFERENCES - FOP vs Index Options**:

| Feature | Index Options (SPX/XSP) | Futures Options (ES) |
|---------|-------------------------|----------------------|
| **Security Type** | OPT (index options) | FOP (futures options) |
| **Underlying** | Cash-settled index | Futures contract (ESZ5, ESH6, etc.) |
| **Symbol** | "SPX" or "XSP" | "ES" |
| **Trading Class** | "SPXW" or "XSP" | "ES" |
| **Exchange** | SMART | CME |
| **Expiration** | Daily (0DTE, 1DTE, etc.) | Futures contract expiry (3rd Friday) |
| **Strike Intervals** | SPX: $5, XSP: $1 | ES: $5 |
| **Multiplier** | $100 per point | $50 per point |
| **Tick Sizes** | SPX: $0.05/$0.10, XSP: $0.01 | ES: $0.05/$0.25 |

**Important**: ES options expire with the underlying futures contract (quarterly cycle), NOT daily like cash-settled index options. The application automatically uses the correct expiration date from the futures contract symbol.

**Rollover**: When approaching futures expiration (typically 8 days before), change `SELECTED_INSTRUMENT` in `config.py` to the next front month contract (e.g., ESZ5 → ESH6).

### Start TWS or IB Gateway
1. Launch Interactive Brokers TWS or IB Gateway
2. Configure API settings:
   - Enable ActiveX and Socket Clients
   - Socket Port: **7497** (paper trading) or 7496 (live)
   - Master API Client ID: Leave blank or set to 0
   - Read-Only API: Unchecked (for order placement)
3. Ensure you're logged into paper trading account for testing

### Launch the Application

**Option 1: With virtual environment activated**
```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

**Option 2: Direct execution**
```powershell
.\.venv\Scripts\python.exe main.py
```

**Option 3: VS Code**
1. Open folder in VS Code
2. Set Python interpreter to `.venv\Scripts\python.exe`
3. Press F5 or run `main.py`

### First Run
1. Application will auto-connect to IBKR after 2 seconds
2. Check the Activity Log for connection status
3. Once connected, SPX price will appear in the header
4. Option chain will populate automatically
5. Click any option to view its chart

## Usage Guide

### Navigation
- **Trading Dashboard Tab**: Main trading interface with option chain, charts, positions, orders
- **Settings Tab**: Configure connection parameters and strategy settings

### Option Chain
- **Layout**: Calls on left | Strike (center) | Puts on right
- **Columns**: Imp Vol, Delta, Theta, Vega, Gamma, Volume, CHANGE %, Last, Ask, Bid
- **Color Coding**: ITM options have blue background tint
- **Click**: Select any option to view historical chart

### Charts
- **Dual Panel**: Call chart (left) | Put chart (right)
- **TradingView Style**: Professional dark theme with matplotlib/mplfinance
- **Real-time Updates**: Candlestick charts with smooth rendering
- **Historical Data**: Automatically loads when option selected
- **Performance Optimized**: Last 200 bars for smooth updates

### Manual Trading
1. **Set Max Risk**: Enter maximum risk per contract (e.g., 500 = $5.00)
2. **Click BUY CALL or BUY PUT**: Scans chain for option ≤ max risk
3. **Order Placed**: Limit order at mid-price (bid+ask)/2
4. **Intelligent Chasing**: Auto-adjusts price every 1 second if market moves
5. **Monitor**: Track order status in Active Orders table

### Position Management
- **Real-time P&L**: Updates every second with current mid-price
- **Color Coding**: Green = profit, Red = loss
- **Close Button**: One-click exit at current mid-price
- **Confirmation**: Shows current P&L before closing

### Settings
- **Connection**: Host, port, client ID
- **Strike Range**: Number of strikes above/below SPX
- **Auto-save**: Settings persist to `settings.json`

## Architecture

### CRITICAL: Strike Type Convention (FLOAT Only)

**⚠️ IB API REQUIREMENT**: All strikes MUST be typed as `float`, never `int`.

IBKR's API sends strike prices as floating-point numbers (e.g., `684.0`, `685.0`) even for whole-number strikes. Our application MUST maintain this convention throughout the codebase to prevent contract key mismatches that cause data overwriting bugs.

**Contract Key Format** (CORRECT):
```python
contract_key = f"XSP_{strike}_C_{expiry}"  # strike is FLOAT
# Example: "XSP_684.0_C_20251111"
```

**Contract Key Format** (WRONG - DO NOT USE):
```python
strike_int = int(strike)  # ❌ NEVER convert to int
contract_key = f"XSP_{strike_int}_C_{expiry}"
# Example: "XSP_684_C_20251111"  # ❌ Mismatches IBKR data
```

**Why This Matters**:
When a strike is converted to `int`, contract keys won't match IBKR's float-based data:
- IBKR sends: `"XSP_684.0_P_20251111"` (float strike)
- If we use: `"XSP_684_P_20251111"` (int strike)
- Result: **Data lookup fails**, creates separate dictionary entry
- Consequence: Bid/ask prices get **overwritten** between contracts

**Rules for Developers**:
1. ✅ **Always** use `float` type for strike variables
2. ✅ **Never** call `int(strike)` when building contract keys
3. ✅ Use `{strike:.1f}` or `{strike:.2f}` in logging for clarity
4. ✅ Compare strikes with tolerance: `abs(strike1 - strike2) < 0.01`
5. ❌ **Never** use `{strike:.0f}` (hides the float nature)
6. ❌ **Never** create "strike_int" variables for contract keys

**Key Locations** (already fixed in codebase):
- Contract key generation in chain loading (lines ~5565, ~5581)
- TradeStation automation entry (lines ~10425-10428)
- Straddle strategy (lines ~12519-12587)
- Option chain cell updates (line ~7252)
- TS chain cell updates (lines ~10871-10872)

**Testing Strike Types**:
```python
# Verify contract key format
assert isinstance(strike, float), "Strike must be float"
assert "_" in contract_key and "." in contract_key.split("_")[1], "Strike must include decimal"
```

See `copilot-instructions.md` for AI agent guidance on maintaining this convention.

### Thread Safety
All GUI updates use PyQt6 signals/slots for thread safety:
```
IBKR API Thread → Signals → Main Thread (GUI)
```

### Key Components
- `MainWindow`: Main application window with tabs
- `IBKRWrapper`: Handles IBKR API callbacks (data in)
- `IBKRClient`: Sends IBKR API requests (commands out)
- `IBKRSignals`: Qt signals for thread-safe GUI updates
- `ChartWidget`: matplotlib/mplfinance candlestick chart (in chart_widget_matplotlib.py)
- `QTableWidget`: Option chain, positions, orders display

### Data Flow
1. **Market Data**: IBKR → Wrapper → Signal → GUI update
2. **Orders**: GUI → Client → IBKR → Wrapper → Signal → GUI update
3. **Positions**: IBKR → Wrapper → Signal → P&L calc → GUI update

## Configuration

### Connection Settings
Edit in Settings tab or `settings.json`:
```json
{
  "host": "127.0.0.1",
  "port": 7497,
  "client_id": 1,
  "strikes_above": 20,
  "strikes_below": 20
}
```

### Paper Trading vs Live
- **Paper Trading**: Port 7497 (default, recommended for testing)
- **Live Trading**: Port 7496 (**⚠️ USE WITH EXTREME CAUTION**)

## Troubleshooting

### Connection Issues
- **"Status: Disconnected"**: Check TWS/IB Gateway is running and API enabled
- **"Client ID already in use"**: Close other connections or change client ID
- **"Data server not ready"**: Wait for "✓ Data server connection confirmed" message

### Chart Issues
- **"Chart unavailable"**: Verify `pip install matplotlib mplfinance`
- **Empty charts**: Select an option from the option chain first
- **Slow rendering**: Limit to last 200 bars (automatically done)

### Order Issues
- **"Order rejected"**: Check TWS API settings allow order placement
- **Silent rejection**: Verify account is set correctly (last in managed accounts list)
- **Price out of range**: Mid-price may not match SPX tick size rules

### Market Data Issues
- **No bid/ask prices**: Ensure SPX + SPXW data subscriptions are active
- **No greeks**: Wait for MODEL_OPTION tick (uses bid/ask mid-point)
- **No historical data**: Paper accounts have limited historical data access

## Migrating from Tkinter Version

### Key Differences
- ✅ **Better Performance**: PyQt6 native rendering vs tkinter
- ✅ **True Thread Safety**: Signals/slots vs queue polling
- ✅ **Professional Charts**: matplotlib/mplfinance TradingView-style
- ✅ **Responsive UI**: No blocking updates or lag
- ✅ **Native Look**: Platform-native widgets
- ✅ **Simpler Code**: 160-line chart widget vs 250+ lines

### Preserved Features
All features from the tkinter version are preserved:
- Manual trading with mid-price chasing ✅
- Real-time position P&L tracking ✅
- IBKR TWS dark color scheme ✅
- Intelligent order management ✅
- IBKR model-based greeks (more accurate than Black-Scholes) ✅

## Development

### Project Structure
```
IBKR XSP Option Trader1 (PyQt6)/
├── main.py                      # Main application (~1850 lines)
├── chart_widget_matplotlib.py   # Chart widget with matplotlib/mplfinance (160 lines)
├── requirements.txt             # Python dependencies
├── setup.ps1                    # Setup script
├── copilot-instructions.md      # AI agent instructions
├── settings.json                # User settings (auto-created)
└── .venv/                       # Virtual environment (created by setup)
```

### Code Organization
- **chart_widget_matplotlib.py**: ChartWidget class with matplotlib/mplfinance (160 lines)
- **main.py Lines 1-100**: Imports and configuration
- **main.py Lines 100-200**: Connection state and IBKR signals
- **main.py Lines 200-400**: IBKR wrapper with signal emissions
- **main.py Lines 450-460**: Import ChartWidget from chart_widget_matplotlib
- **main.py Lines 460-1850**: MainWindow with all GUI components

### Extending the Application
1. **Add new signals**: Define in `IBKRSignals` class
2. **New IBKR callbacks**: Add to `IBKRWrapper`, emit signals
3. **New GUI components**: Add to `MainWindow.setup_ui()`
4. **Connect signals**: Add to `MainWindow.connect_signals()`

## Safety and Disclaimers

### ⚠️ IMPORTANT WARNINGS
- **Paper Trading First**: ALWAYS test with paper trading (port 7497)
- **Real Money Risk**: Live trading involves real financial risk
- **No Warranties**: Use at your own risk - software provided AS-IS
- **Market Data**: Ensure proper subscriptions to avoid violations
- **0DTE Options**: Highly volatile, can expire worthless quickly

### Risk Management
- Start with small position sizes
- Use max risk limits appropriately
- Monitor positions actively during market hours
- Understand options expiration mechanics
- Have a clear exit strategy

## Environment Separation

### Development vs Production
The application supports automatic environment detection for safe development and live trading:

**🔧 SHARED INFRASTRUCTURE** (Optimal approach):
- **Virtual Environment**: One `.venv/` for both environments (same dependencies)
- **TradeStation Dictionary**: Both use `'IBKR-TRADER'` (no strategy changes needed)
- **Core Code**: Same application files with environment-aware configuration

**🔄 SEPARATED COMPONENTS** (Safety isolation):
- **Client IDs**: Dev (100-199) vs Prod (1-99) - zero conflicts
- **Ports**: Dev (7497 paper) vs Prod (7496 live) 
- **Files**: `settings_dev.json` vs `settings_prod.json`
- **Logs**: `logs_dev/` vs `logs_prod/` directories

### Quick Environment Commands
```bash
# Check current environment
python config.py info

# Deploy to production (when ready)
python deploy_production.py
```

**📚 Complete Guide**: See `ENVIRONMENT_GUIDE.md` for detailed setup instructions.

## Support

### Resources
- **IBKR API Docs**: https://interactivebrokers.github.io/tws-api/
- **PyQt6 Docs**: https://doc.qt.io/qtforpython-6/
- **matplotlib**: https://matplotlib.org/
- **mplfinance**: https://github.com/matplotlib/mplfinance
- **Environment Guide**: See `ENVIRONMENT_GUIDE.md`
- **Architecture Decisions**: See `ADR_SHARED_INFRASTRUCTURE.md`
- **Copilot Instructions**: See `copilot-instructions.md`

### Common Questions
- **Q: Why PyQt6 instead of tkinter?**
  - A: Better performance, true thread safety, professional charts, native widgets

- **Q: Can I use this with other brokers?**
  - A: No, this is specifically designed for Interactive Brokers API

- **Q: Does this work with stocks or futures?**
  - A: Designed for SPX options, but could be adapted for other instruments

- **Q: Is historical data available in paper trading?**
  - A: Limited - paper accounts have restricted historical data access

## License
This software is provided for educational purposes. Use at your own risk.

## Version
- **Version**: 2.0 (PyQt6 Edition with matplotlib/mplfinance)
- **Date**: October 27, 2025
- **Author**: VJS World
- **Technology**: PyQt6 + matplotlib/mplfinance + IBKR API
