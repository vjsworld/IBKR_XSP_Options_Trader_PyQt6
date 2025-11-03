# ATM Strike Calculation Fix

## Problem Identified

The application was showing **different ATM strikes than TWS** because it was using **ES futures / 10** instead of the **actual XSP index price** for centering the option chain.

### Example from your screenshot:
- **TWS**: Shows ATM around **589** (based on actual XSP index)
- **Your App**: Shows ATM around **691** (based on ES futures/10 ~6947.75/10 = 694.78)

## Root Cause

XSP options are based on the **XSP INDEX** (symbol: XSP, type: IND), NOT ES futures divided by 10.

While it's true that:
- ES futures / 10 ≈ SPX cash index / 10
- And XSP = SPX / 10

The **ES futures have a basis/spread difference** from the cash index, especially:
1. During after-hours when the XSP index isn't updating
2. Near futures expiration dates
3. During periods of market stress

## The Fix

Changed `request_option_chain()` to use **PRIORITY PRICING**:

### Priority 1: Actual Underlying Index (CORRECT)
```python
underlying_price = self.app_state.get('underlying_price', 0)
if underlying_price > 0:
    reference_price = underlying_price  # XSP or SPX index
```

This uses the actual XSP index price that TWS uses for ATM calculation.

### Priority 2: ES Futures Fallback (APPROXIMATE)
```python
else:
    # After-hours fallback when XSP index not available
    adjusted_es_price = self.get_adjusted_es_price()
    reference_price = adjusted_es_price
    logger.warning("Using ES-derived price - may not match TWS")
```

This fallback is only used when the actual index isn't available (after-hours).

## Why This Matters

**During Regular Market Hours (8:30 AM - 4:00 PM CT)**:
- XSP index: **589.XX** (actual, what options trade on)
- ES futures/10: **691.XX** (approximate, has basis difference)
- **Difference**: ~102 points = 102 strikes off!

This caused:
- Wrong ATM strike highlighting
- Option chain centered on wrong strikes
- Confusion when comparing to TWS

## Technical Details

### XSP Index vs ES Futures
- **XSP Index** (IND/CBOE): Official index, trades 9:30 AM - 4:00 PM ET
  - This is what XSP options are settled against
  - Symbol: XSP, SecType: IND, Exchange: CBOE
  
- **ES Futures** (FUT/CME): Futures contract, trades 23/6
  - Symbol: ES, SecType: FUT, Exchange: CME
  - Has basis difference from SPX/XSP index
  - Used for after-hours approximation only

### The Basis Difference
ES futures typically trade at a **premium or discount** to the cash index due to:
1. **Cost of carry** (dividends vs interest rates)
2. **Time to expiration**
3. **Supply/demand dynamics**

This basis can be **0.1% to 0.5%** or more, which translates to:
- SPX: 6000 * 0.3% = 18 points
- XSP: 600 * 0.3% = 1.8 points

## Testing

To verify the fix works:
1. **During market hours**: App should now show same ATM as TWS (using XSP index)
2. **After hours**: App will show warning that it's using ES-derived price
3. **Check logs**: Will say either "Using actual XSP index price" or "Using FALLBACK ES-derived price"

## Migration Notes

The ES-to-cash offset calculation is still used but only as a fallback. The offset helps adjust ES futures to approximate the cash index when the real index isn't available.

## References

- CBOE XSP Product Specs: XSP options are based on XSP Index (1/10 of SPX)
- CME ES Futures: Trade 23/6 but have basis difference from SPX
- IB API: Subscribe to symbol="XSP", secType="IND", exchange="CBOE" for actual index
