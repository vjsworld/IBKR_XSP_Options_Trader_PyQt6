# Copilot Instructions for IBKR XSP/SPX Option Trader

This document provides instructions for AI coding assistants to effectively contribute to this project. Understanding these guidelines is crucial for making accurate and helpful changes.

## 1. Project Overview

This is a specialized trading application for SPX and XSP options on the Interactive Brokers (IBKR) platform. It is built with Python and uses the PyQt6 framework for the graphical user interface. The application focuses on providing tools for 0DTE (zero days to expiration) option trading, including a real-time option chain, charting, and both manual and automated trading capabilities.

### Key Technologies
- **PyQt6**: Modern GUI framework with native performance and thread safety
- **IBKR API** (`ibapi`): Professional-grade market data and order execution
- **matplotlib/mplfinance**: Industry-standard financial charting
- **TradeStation GlobalDictionary**: COM interface for strategy integration
- **Environment Separation**: Development/production isolation with shared infrastructure

## 2. Core Architecture

The application is almost entirely contained within the monolithic `main.py` file. Understanding its structure is key to making any changes.

### Key Components in `main.py`:

- **`MainWindow(QMainWindow)`**: The main application class. It orchestrates the entire application, including the UI, IBKR connection, data processing, and trading logic.
- **`IBKRThread(QThread)`**: The IBKR API (`ibapi`) runs in a blocking loop. This `QThread` runs that loop in the background to prevent the GUI from freezing.
- **`IBKRWrapper(EWrapper)` & `IBKRClient(EClient)`**: These classes handle the direct interaction with the IBKR API.
    - `IBKRWrapper` receives messages *from* IBKR (e.g., market data, order status, positions) and emits PyQt signals.
    - `IBKRClient` sends requests *to* IBKR (e.g., request market data, place order).
- **`IBKRSignals(QObject)`**: A central class that defines all `pyqtSignal`s used for thread-safe communication from the `IBKRThread` to the `MainWindow` (GUI thread). **All communication from the background thread to the UI must go through these signals.**
- **`ProfessionalChart` & `ProfessionalUnderlyingChart`**: Custom `QWidget` classes that use `matplotlib` and `mplfinance` to render financial charts.
- **`app_state` Dictionary**: A dictionary `self.app_state` within `MainWindow` serves as the central, in-memory state store for the application.

### Architectural Principles:

1.  **Single-File Structure**: Nearly all logic resides in `main.py`.
2.  **Threading Model**: The IBKR API is asynchronous but its Python client uses a blocking `run()` loop. We manage this by running the client in a separate `QThread`.
3.  **Signal/Slot for Thread Safety**: All data flowing from the IBKR API thread to the main GUI thread **must** be sent via a `pyqtSignal` defined in `IBKRSignals`. This is critical to prevent crashes. Slots (handler methods) in `MainWindow` are decorated with `@pyqtSlot(...)` and receive this data to update the UI and application state.
4.  **Configuration via `SELECTED_INSTRUMENT`**: The `SELECTED_INSTRUMENT` variable in `config.py` switches the application between instruments. Set to 'SPX', 'XSP', or an ES futures contract (e.g., 'ESZ5', 'ESH6'). This controls all instrument-specific behavior.

### 2.1. Instrument Configuration

The application supports three distinct trading instrument types with different contract structures:

**Supported Instruments**:
- **SPX**: Full-size S&P 500 Index Options (secType=OPT, $100 multiplier, $5 strikes)
- **XSP**: Mini S&P 500 Index Options (secType=OPT, $100 multiplier, $1 strikes)
- **ES Futures**: E-mini S&P 500 Futures Options (secType=FOP, $50 multiplier, $5 strikes)

**Configuration Location**: `config.py`
```python
# For index options:
SELECTED_INSTRUMENT = 'XSP'   # or 'SPX'

# For ES futures options - use actual futures contract:
SELECTED_INSTRUMENT = 'ESZ5'  # December 2025
SELECTED_INSTRUMENT = 'ESH6'  # March 2026
```

**Auto-Detection**: The application automatically detects ES futures contracts (starts with "ES") and configures FOP parameters.

**CRITICAL Contract Differences**:

| Feature | Index Options (SPX/XSP) | Futures Options (ES_FOP) |
|---------|-------------------------|--------------------------|
| **secType** | `"OPT"` | `"FOP"` |
| **underlying** | Cash-settled index | Futures contract |
| **symbol** | `"SPX"` or `"XSP"` | `"ES"` |
| **tradingClass** | `"SPXW"` or `"XSP"` | `"ES"` |
| **exchange** | `"SMART"` | `"CME"` |
| **expiration** | Daily (YYYYMMDD) | Futures expiry (3rd Friday) |
| **multiplier** | `"100"` | `"50"` |

**Contract Creation**:
- **ALWAYS** use `create_instrument_option_contract(strike, right, expiry)` for new contract creation
- This function automatically handles OPT vs FOP differences based on `self.instrument['sec_type']`
- **NEVER** hardcode `secType`, `tradingClass`, or `exchange` - use `self.instrument` config

**FOP-Specific Requirements**:
- `lastTradeDateOrContractMonth` MUST use futures expiry (e.g., "20251219"), NOT daily expiry
- Options expire with underlying futures, not daily like index options
- `futures_symbol` and `futures_expiry` are set at runtime from `ES_FRONT_MONTH`

**ES Futures Month Codes** (CME convention):
- H=Mar, M=Jun, U=Sep, Z=Dec
- Year: last digit (5=2025, 6=2026)
- Example: ESZ5 = ES December 2025

## 3. Key Workflows & Logic

### 3.1. IBKR Connection

- The connection is initiated in `connect_to_ibkr()`.
- The `IBKRThread` is started, which runs the `self.ibkr_client.run()` loop.
- Connection status is tracked via the `self.connection_state` enum and updated through signals.

### 3.2. Option Chain

- **Building the Chain**: `request_option_chain()` builds the list of strikes to display. It centers the chain around an At-The-Money (ATM) strike.
- **ATM Calculation**:
    - **Primary Method**: `find_atm_strike_by_delta()` finds the strike whose call option has a delta closest to `0.50`. This is the most accurate method during market hours.
    - **Fallback Method**: `get_adjusted_es_price()` is used when the cash index isn't trading. It uses the ES futures price and adjusts it by the `es_to_cash_offset` to estimate the ATM strike.
- **Auto-Recentering**: The chain automatically recenters if the ATM strike drifts too far from the current center of the displayed chain. This logic is in `check_chain_drift_and_recenter()`.

### 3.3. ES-to-Cash Offset

- **Purpose**: The price of ES futures is not identical to the cash index (SPX/XSP). The `es_to_cash_offset` variable tracks this basis difference. It is critical for accurately estimating the ATM strike outside of regular trading hours.
- **Lifecycle**:
    1.  **Live Tracking**: During market hours (8:30 AM - 3:00 PM CT), `update_es_to_cash_offset()` actively calculates and updates the offset.
    2.  **Persistence**: The live offset is periodically saved to `settings.json`.
    3.  **After-Hours Loading**: When the app starts after hours, it loads the last saved offset from `settings.json`.
    4.  **Historical Fallback**: If the app starts after hours and has no saved offset, `calculate_offset_from_historical_close()` will fetch historical data for ES and the cash index to calculate the offset from the previous day's 3:00 PM CT close.

### 3.4. Trading and Order Management

- **Universal Order Function**: `place_order()` is the single, robust function for placing all orders. It contains extensive validation and logging.
- **Mid-Price Chasing**: For manual limit orders, the `update_orders()` function implements an intelligent "chasing" algorithm.
    - It places the order at the mid-price.
    - If the order doesn't fill after a set interval (`give_in_interval`), it "gives in" by one tick (e.g., moves a BUY order closer to the ask) and modifies the order.
    - This process repeats, increasing the chance of a fill while still trying for price improvement.
- **Quick Trading**: `Ctrl+Click` on a bid or ask cell in the option chain triggers an immediate trade.
- **Position Closing**: Clicking the "Close" button on the positions table triggers an immediate exit order, also using the mid-price chasing logic.

## 4. Data Persistence & Environment Separation

### Environment-Aware Architecture
The application supports development/production environment separation with **shared infrastructure philosophy**:

**SHARED COMPONENTS** (Same for both environments):
- **Virtual Environment (`.venv/`)**: One virtual environment with same Python packages
- **TradeStation GlobalDictionary**: Both environments use `'IBKR-TRADER'` dictionary name
- **Core Application Files**: Same `main.py`, `config.py`, and source code

**SEPARATED COMPONENTS** (Different per environment):
- **Settings Files**: `settings_dev.json` vs `settings_prod.json`
- **Position Files**: `positions_dev.json` vs `positions_prod.json` 
- **Log Directories**: `logs_dev/` vs `logs_prod/`
- **Client ID Ranges**: Development (100-199) vs Production (1-99)
- **IBKR Ports**: Development (7497 paper) vs Production (7496 live)

### Environment-Specific Files
- **Settings**: Environment-specific settings files store user-configurable settings like connection details, UI preferences, strategy parameters, and the crucial `es_to_cash_offset`. Loaded by `load_settings()` and saved by `save_settings()` using environment-aware file paths.
- **Positions**: Environment-specific position files store currently open positions. Their primary purpose is to persist the `entryTime` of a position across application restarts, allowing for accurate time-in-trade tracking per environment.

### CRITICAL: Maintain Shared Infrastructure Philosophy
When making changes, always respect the shared infrastructure approach:
- ✅ **DO**: Keep one `.venv/` virtual environment for both dev/prod
- ✅ **DO**: Use same `'IBKR-TRADER'` TradeStation GlobalDictionary name for both
- ✅ **DO**: Separate data files (settings, positions, logs) by environment
- ❌ **DON'T**: Create separate virtual environments or TradeStation dictionaries
- ❌ **DON'T**: Mix development and production data in same files

## 4.5. TradeStation Integration

**Optional External Dependency**: The application integrates with TradeStation via COM interface:

**Key Integration Points:**
- **GlobalDictionary Module**: `import GlobalDictionary` (COM interface to TradeStation)  
- **Dictionary Name**: Both environments use `'IBKR-TRADER'` (shared infrastructure)
- **Graceful Degradation**: Application works fully without TradeStation installed
- **Error Handling**: `TRADESTATION_AVAILABLE` flag controls integration features

**TradeStation Integration Files:**
- `GlobalDictionary.py` - COM wrapper for TradeStation communication
- `TradeStation_Example_Indicator.txt` - Example TradeStation strategy code
- `TS to Python/` directory - TradeStation integration examples and documentation

**If TradeStation is not available**: Application logs warning and disables TradeStation features but continues normal operation.

## 5. Critical Development Workflows

### 5.1. Environment Management
**ALWAYS check current environment before making changes:**
```powershell
python config.py info  # Check current environment and configuration
```

**Primary Environment Control**: Edit the `ENVIRONMENT_OVERRIDE` variable at the top of `config.py`:
- Development directory: `ENVIRONMENT_OVERRIDE = 'development'` 
- Production directory: `ENVIRONMENT_OVERRIDE = 'production'`

**Additional environment commands:**
- `python config.py set dev` - Force development environment (secondary method)
- `python config.py set prod` - Force production environment (secondary method) 
- `python deploy_production.py` - Full production deployment with safety checks

### 5.2. Running the Application
**Development (Recommended):**
```powershell
.\.venv\Scripts\Activate.ps1  # Activate virtual environment
python main.py               # Run in development mode
```
**Prerequisites check:** Ensure IBKR TWS/Gateway is running on correct port (7497 for dev, 7496 for prod)

### 5.3. Debugging and Logging
- **Live application logs**: Check in-app Activity Log panel
- **Detailed logs**: Check `logs_dev/` or `logs_prod/` directories  
- **Log format**: Daily rotation with pattern `YYYY-MM-DD.log`
- **Timezone**: All timestamps use Central Time (America/Chicago)

## 6. How to Make Changes

### 6.1. Code Location and Search
1.  **Identify the Logic**: Since most code is in `main.py` (~11,800 lines), use text search to find the relevant methods or variables.
2.  **Key search patterns**:
    - `def method_name` - Find specific functions
    - `class ClassName` - Find class definitions
    - `contract_key` - Find option contract handling
    - `@pyqtSlot` - Find signal handler methods

### 6.2. Threading Model (CRITICAL)
**All IBKR API callbacks run in background thread - GUI updates MUST use signals:**
1.  Add new `pyqtSignal` to `IBKRSignals` class for any new data from IBKR
2.  Emit the signal from `IBKRWrapper` method (background thread)
3.  Create `@pyqtSlot(...)` decorated method in `MainWindow` to receive signal (GUI thread)
4.  **NEVER directly call UI methods from `IBKRWrapper` or `IBKRThread`**

### 6.3. State Management and Conventions
- **Central State**: Read from and write to `self.app_state` dictionary in `MainWindow`
- **Logging**: Use `self.log_message()` for in-app log, `logger` object for file logs
- **Contract Keys**: Format as `{SYMBOL}_{STRIKE}_{RIGHT}_{EXPIRY}` (e.g., `XSP_535_P_20251103`)
- **Method Naming**: 
  - IBKR callbacks: `on_*` (e.g., `on_position_update`)
  - Signal handlers: `on_*` (e.g., `on_market_data_tick`)
  - Helper methods: descriptive names (e.g., `find_atm_strike_by_delta`)

### 6.4. Instrument Configuration
**CRITICAL**: Change `SELECTED_INSTRUMENT` at top of `main.py` to switch between instruments:
```python
SELECTED_INSTRUMENT = 'XSP'  # Change to 'SPX' for full-size trading
```
This controls all instrument-specific settings, option chains, and trading parameters.
