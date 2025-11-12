# ES Futures Options (FOP) tradingClass Fix

**Date**: November 12, 2025  
**Issue**: Error 200 "No security definition found" for all ES FOP contracts  
**Status**: ✅ RESOLVED

## Problem

ES Futures Options (FOP) contracts were failing with Error 200 when attempting to request market data. The issue affected:
- Main option chain (all 50 contracts)
- TradeStation 0DTE chain (all 22 contracts)
- TradeStation 1DTE chain (all 22 contracts)

Total: 94 contract subscription failures.

## Root Cause

The application was explicitly setting `contract.tradingClass = "ES"` for FOP contracts, but IBKR requires weekly-specific trading classes that vary by expiration date:
- Week 1: `EW1`
- Week 2: `EW2`
- Week 3: `EW3`
- Week 4/5: `EW4`

Setting a generic `"ES"` trading class caused IBKR to reject all contract definitions.

## Solution

**DO NOT set `tradingClass` for FOP contracts.** Instead, leave it unset and let IBKR's API automatically resolve the correct weekly trading class based on:
- `symbol` ("ES")
- `exchange` ("CME")
- `lastTradeDateOrContractMonth` (e.g., "20251112")

### Code Changes

**Before (BROKEN)**:
```python
contract.secType = "FOP"
contract.symbol = "ES"
contract.tradingClass = "ES"  # ❌ This causes Error 200
contract.exchange = "CME"
contract.lastTradeDateOrContractMonth = "20251112"
```

**After (WORKING)**:
```python
contract.secType = "FOP"
contract.symbol = "ES"
# contract.tradingClass is intentionally NOT SET ✅
contract.exchange = "CME"
contract.lastTradeDateOrContractMonth = "20251112"
```

## Learning Source

The fix was discovered by analyzing working example files provided by the user in the `example python files to teach/` folder:
- `example_options_downloader.py` - Shows proper FOP contract creation for NQ/ES
- `optionData.py` - Demonstrates weekly trading class codes (EW1, EW2, etc.)
- `optionData_v0.py` - Additional FOP contract examples

Key insight: These examples **never explicitly set `tradingClass`** for FOP contracts, allowing IBKR to auto-resolve it.

## Verification

After the fix:
```
[DEVELOPMENT] 09:23:47 | INFO  | ✓ main chain: subscribed to 50 contracts (25 strikes × 2)
[DEVELOPMENT] 09:23:50 | INFO  | ✓ ts_0dte chain: subscribed to 22 contracts (11 strikes × 2)
[DEVELOPMENT] 09:23:53 | INFO  | ✓ ts_1dte chain: subscribed to 22 contracts (11 strikes × 2)
[DEVELOPMENT] 09:23:58 | INFO  | ✅ Sequential chain loading complete
```

All 94 contracts now load successfully without Error 200.

## Key Takeaways

1. **FOP vs OPT Contract Differences**:
   - **OPT (Index Options)**: MUST explicitly set `tradingClass` (e.g., "SPXW", "XSP")
   - **FOP (Futures Options)**: MUST NOT set `tradingClass` (let IBKR auto-resolve)

2. **ES Weekly Trading Classes**:
   - ES options use weekly-specific codes that change based on expiration date
   - These codes are: EW1, EW2, EW3, EW4 (and monthly variants)
   - Application cannot hard-code these - must let IBKR resolve dynamically

3. **0DTE Support for ES Options**:
   - ES futures options DO support daily (0DTE) expiration
   - Use YYYYMMDD format for daily options (e.g., "20251112")
   - Use YYYYMM format for monthly options (e.g., "202512")
   - The underlying futures (ESZ5) can have options expiring on any trading day

## Files Modified

- `main.py` - Function `create_instrument_option_contract()` (lines ~7150-7195)
  - Removed `contract.tradingClass = "ES"` assignment
  - Added documentation explaining why tradingClass must NOT be set for FOP
  - Cleaned up debug logging

## Related Documentation

- `INSTRUMENT_SELECTION_GUIDE.md` - Instrument configuration details
- `copilot-instructions.md` - Updated contract creation guidelines
- IBKR API Documentation - FOP Contract Specifications
