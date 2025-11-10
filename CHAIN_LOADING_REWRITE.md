# Option Chain Loading System Rewrite
## November 10, 2025

## Problem Statement
The current chain loading system is overly complex with multiple competing functions, ES-based fallbacks, delta scanning, and race conditions causing incorrect ATM strike detection and duplicate request ID errors.

## Root Issues Identified
1. **Multiple ATM Calculation Paths**: ES adjustments, delta scanning, price-based calculations all competing
2. **Duplicate Request IDs**: No centralized ID management, ranges overlap
3. **Complex Initialization**: Multiple functions doing similar things (build_main_chain_only, build_ts_chains_after_main_complete, request_option_chain, request_ts_chain, etc.)
4. **Unnecessary Fallbacks**: ES futures calculations when underlying price is directly available
5. **Non-sequential Loading**: All chains trying to load simultaneously causing race conditions

## Solution Design

### 1. Single Source of Truth for ATM Strike
```python
def calculate_atm_strike(self) -> float:
    """
    Calculate ATM strike using ONLY the underlying price.
    No ES adjustments, no delta scanning, no fallbacks.
    Simply round to nearest strike interval.
    """
    price = self.app_state.get('underlying_price', 0)
    if price == 0:
        return 0
    interval = self.instrument['strike_increment']
    return round(price / interval) * interval
```

### 2. Centralized Request ID Manager
```python
class RequestIDManager:
    """
    Centralized request ID allocation to prevent duplicates.
    
    ID Ranges:
    - 1-999: Underlying/ES market data
    - 1000-1999: Main option chain
    - 2000-2999: TradeStation 0DTE chain
    - 3000-3999: TradeStation 1DTE chain
    - 5000+: Orders, historical data, other
    """
```

### 3. Sequential Chain Loader
```python
def load_all_chains(self):
    """
    Load chains sequentially with proper state management:
    1. Wait for underlying price (with timeout)
    2. Load main chain
    3. Wait for main chain completion
    4. Load TS 0DTE chain
    5. Wait for TS 0DTE completion  
    6. Load TS 1DTE chain
    """
```

### 4. Unified Chain Building Function
```python
def build_option_chain(self, chain_type: str, atm_strike: float, 
                      strikes_above: int, strikes_below: int):
    """
    Single function to build any chain type.
    
    Args:
        chain_type: 'MAIN', 'TS_0DTE', or 'TS_1DTE'
        atm_strike: The ATM strike to center on
        strikes_above: Number of strikes above ATM (from UI settings)
        strikes_below: Number of strikes below ATM (from UI settings)
    """
```

### 5. Drift Detection and Auto-Recenter
```python
def monitor_chain_drift(self):
    """
    Monitor current ATM vs chain center.
    If drift exceeds threshold, trigger sequential recenter of all chains.
    Uses same unified loader as initial load.
    """
```

### 6. Error Handling
- Error 200 (No security definition): Log and skip that strike, continue loading
- Duplicate ID errors: Prevented by centralized ID manager
- Missing underlying price: Wait with timeout, show clear message

## Implementation Plan
1. Create RequestIDManager class
2. Create simplified calculate_atm_strike() 
3. Create unified build_option_chain() function
4. Create sequential load_all_chains() orchestrator
5. Create drift monitoring system
6. Delete obsolete functions
7. Test thoroughly with live market data

## Functions to DELETE
- `build_main_chain_only()` - Replaced by unified loader
- `build_ts_chains_after_main_complete()` - Replaced by sequential loader
- `calculate_master_atm_strike()` - Replaced by simple calculate_atm_strike()
- `find_atm_strike_by_delta()` - No longer needed
- `get_adjusted_es_price()` - No longer needed
- `update_es_to_cash_offset()` - No longer needed
- `request_ts_chain_forced_center()` - Replaced by unified loader
- `complete_atm_scan_and_build_chain()` - No longer needed
- Any other complex ATM scanning functions

## Functions to KEEP (Simplified)
- `subscribe_underlying_price()` - Essential for real-time price
- `request_option_chain()` - Refactored to use unified loader
- `check_chain_drift_and_recenter()` - Refactored for drift monitoring
- `initialize_option_chain_table()` - UI table setup
- `initialize_ts_chain_table()` - UI table setup

## Expected Benefits
1. **Correctness**: ATM strike always matches underlying price during market hours
2. **Reliability**: No duplicate request IDs
3. **Simplicity**: One clear path for chain loading
4. **Maintainability**: Easy to understand and modify
5. **Performance**: Sequential loading prevents overwhelm IBKR API limits
