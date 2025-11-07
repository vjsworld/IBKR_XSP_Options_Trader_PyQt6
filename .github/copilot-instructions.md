# Copilot Instructions for IBKR XSP/SPX Option Trader

This document provides instructions for AI coding assistants to effectively contribute to this project. Understanding these guidelines is crucial for making accurate and helpful changes.

## 1. Project Overview

This is a specialized trading application for SPX and XSP options on the Interactive Brokers (IBKR) platform. It is built with Python and uses the PyQt6 framework for the graphical user interface. The application focuses on providing tools for 0DTE (zero days to expiration) option trading, including a real-time option chain, charting, and both manual and automated trading capabilities.

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
4.  **Configuration via `SELECTED_INSTRUMENT`**: At the top of `main.py`, the `SELECTED_INSTRUMENT` variable is used to switch the application's behavior between 'SPX' and 'XSP'. This is a simple but important configuration point.

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

## 5. How to Make Changes

1.  **Identify the Logic**: Since most code is in `main.py`, use text search to find the relevant methods or variables.
2.  **Respect the Threading Model**:
    - If you are adding a new piece of data from the IBKR API (i.e., from a callback in `IBKRWrapper`), you **must** add a new `pyqtSignal` to `IBKRSignals`.
    - Emit this signal from the `IBKRWrapper` method.
    - Create a new slot (a method decorated with `@pyqtSlot(...)`) in `MainWindow` to receive the signal and update the UI or `self.app_state`.
    - **Never directly call a UI update method from `IBKRWrapper` or `IBKRThread`.**
3.  **Use the Central State**: Read from and write to `self.app_state` for managing application state.
4.  **Use the Logging Functions**: Use `self.log_message()` to print status updates to the in-app log. Use the `logger` object for more detailed, file-based logging.
5.  **Follow Naming Conventions**:
    - IBKR callback handlers in `IBKRWrapper` are named `on_*` (e.g., `on_position_update`).
    - `MainWindow` slots that handle signals are also often named `on_*` (e.g., `on_market_data_tick`).
    - Contract keys are strings formatted as `{SYMBOL}_{STRIKE}_{RIGHT}_{EXPIRY}` (e.g., `XSP_535_P_20251103`).
