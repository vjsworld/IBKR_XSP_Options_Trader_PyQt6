# SPX 0DTE Options Trading Application - PyQt6 Edition

## Overview
Professional Bloomberg/TWS-style GUI application for automated 0DTE (Zero Days To Expiration) SPX options trading via Interactive Brokers API. Built with modern PyQt6 framework and TradingView lightweight-charts for real-time market data visualization.

## Features

### Core Functionality
- ✅ **Real-time SPX Price Tracking**: Live underlying index price updates
- ✅ **Option Chain Display**: IBKR TWS-style layout with calls/strikes/puts
- ✅ **Real-time Market Data**: Bid/ask/last prices, volume, greeks streaming
- ✅ **TradingView Charts**: Professional candlestick charts for calls and puts
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
- **lightweight-charts**: TradingView charting library for real-time candlesticks
- **IBKR API**: Professional-grade market data and order execution
- **Black-Scholes**: Greeks calculations for options analysis
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
- `PyQt6-WebEngine>=6.6.0` - For chart WebView
- `lightweight-charts>=2.0` - TradingView charts
- `ibapi>=9.81.1` - Interactive Brokers API
- `pandas>=2.0.0` - Data processing
- `numpy>=1.24.0` - Numerical operations
- `scipy>=1.11.0` - Black-Scholes calculations

## Running the Application

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
- **Real-time Updates**: Candlestick charts with TradingView rendering
- **Historical Data**: Automatically loads when option selected
- **Responsive**: Smooth rendering optimized for real-time data

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
- `ChartWidget`: TradingView chart with WebEngineView
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
- **"Chart unavailable"**: Install `pip install lightweight-charts`
- **Empty charts**: Select an option from the option chain first
- **Slow rendering**: Historical data may be limited in paper trading account

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
- ✅ **Professional Charts**: TradingView vs Matplotlib
- ✅ **Responsive UI**: No blocking updates or lag
- ✅ **Native Look**: Platform-native widgets

### Preserved Features
All features from the tkinter version are preserved:
- Manual trading with mid-price chasing ✅
- Real-time position P&L tracking ✅
- IBKR TWS dark color scheme ✅
- Intelligent order management ✅
- Black-Scholes greeks calculations ✅

## Development

### Project Structure
```
IBKR XSP Option Trader1 (PyQt6)/
├── main.py                      # Main application (~1300 lines)
├── requirements.txt             # Python dependencies
├── setup.ps1                    # Setup script
├── copilot-instructions.md      # AI agent instructions
├── settings.json                # User settings (auto-created)
└── .venv/                       # Virtual environment (created by setup)
```

### Code Organization
- **Lines 1-100**: Imports and Black-Scholes calculations
- **Lines 100-200**: Connection state and IBKR signals
- **Lines 200-400**: IBKR wrapper with signal emissions
- **Lines 400-500**: Chart widget with lightweight-charts
- **Lines 500-1300**: MainWindow with all GUI components

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

## Support

### Resources
- **IBKR API Docs**: https://interactivebrokers.github.io/tws-api/
- **PyQt6 Docs**: https://doc.qt.io/qtforpython-6/
- **lightweight-charts**: https://github.com/tradingview/lightweight-charts
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
- **Version**: 2.0 (PyQt6 Edition)
- **Date**: October 24, 2025
- **Author**: VJS World
- **Technology**: PyQt6 + lightweight-charts + IBKR API
