# Order Chasing Error Fix - "Error 105: Order Mismatch"

**Date**: November 12, 2025  
**Issue**: Order chasing repeatedly failing with "Error 105: Order being modified does not match original order"  
**Status**: ✅ FIXED

## Problem

When order chasing was enabled, the `update_orders()` function was attempting to modify orders but consistently receiving Error 105 from IBKR. The error pattern showed:

```
[ERROR] Error 105: Order being modified does not match original order.
```

This repeated every 3 seconds as the chase logic tried to adjust the limit price.

## Root Cause

The `update_orders()` function was **recreating the contract from scratch** instead of using the original contract object:

**Before (BROKEN)**:
```python
# Parse contract key to recreate contract
parts = contract_key.split('_')
if len(parts) == 4:
    symbol, strike_str, right, expiry = parts
    trading_class = "SPXW" if symbol == "SPX" else "XSP"
    
    # Create NEW contract (WRONG!)
    contract = self.create_option_contract(
        strike=float(strike_str),
        right=right,
        symbol=symbol,
        trading_class=trading_class,
        expiry=expiry
    )
```

**Problems with this approach**:
1. ❌ Recreated contract didn't match original exactly
2. ❌ Hardcoded trading class logic (`"SPXW" if symbol == "SPX" else "XSP"`)
3. ❌ Didn't work for ES/MES futures options (FOP)
4. ❌ Lost contract-specific attributes set during original order placement
5. ❌ IBKR rejected as "order mismatch"

## Solution

Use the **stored contract object** that was saved when the order was originally placed:

**After (FIXED)**:
```python
# Use the stored contract object (don't recreate it - causes "Error 105: order mismatch")
contract = order_info['contract']
```

The contract object is already stored in `chasing_orders` dictionary at order placement:
```python
self.chasing_orders[order_id] = {
    'contract_key': contract_key,
    'contract': contract,  # ← Original contract stored here
    'action': action,
    'quantity': quantity,
    # ... other tracking fields
}
```

## Benefits of Fix

1. ✅ **Exact Contract Match**: Uses the same contract object IBKR knows about
2. ✅ **Works for All Instruments**: SPX, XSP, ES, MES all work correctly
3. ✅ **Simpler Code**: Removed 10+ lines of unnecessary parsing logic
4. ✅ **More Reliable**: No parsing errors or attribute mismatches
5. ✅ **Faster**: No contract recreation overhead

## Technical Details

### IBKR Order Modification Requirements

When modifying an order via `placeOrder(orderId, contract, order)`:
- The `contract` parameter must **exactly match** the original contract
- Even minor differences (missing attributes, different object references) cause Error 105
- The contract is already stored and should be reused

### Order Chasing Flow

1. **Order Placement** (`place_order()` function):
   - Create contract using `create_instrument_option_contract()`
   - Store contract in `chasing_orders[order_id]['contract']`
   
2. **Order Monitoring** (`update_orders()` function - runs every 1 second):
   - Calculate new price based on mid-price + give-in ticks
   - **Use stored contract object** (not recreated)
   - Call `placeOrder(order_id, contract, order)` to modify
   
3. **Price Adjustment Logic**:
   - X_ticks starts at 0 (order at pure mid)
   - Every 3 seconds: X_ticks += 1
   - BUY: price = mid + (X_ticks × tick_size) → creeps toward ask
   - SELL: price = mid - (X_ticks × tick_size) → creeps toward bid

## Testing

**Before Fix**:
```
[ERROR] Error 105: Order being modified does not match original order.
[ERROR] Error 105: Order being modified does not match original order.
[ERROR] Error 105: Order being modified does not match original order.
(repeated continuously)
```

**After Fix**:
```
[INFO] Order #75: Time-based give-in (every 3.0s) → X_ticks=1 | $19.50 - (1 × $0.25) = $19.25
[INFO] ✓ Order #75 updated to $19.25 (X_ticks=1)
[INFO] Order #75: Time-based give-in (every 3.0s) → X_ticks=2 | $19.50 - (2 × $0.25) = $19.00
[INFO] ✓ Order #75 updated to $19.00 (X_ticks=2)
(successful modifications)
```

## Files Modified

**main.py** (line ~8591-8635):
- Removed contract recreation logic (15 lines)
- Replaced with single line: `contract = order_info['contract']`
- Simplified error handling

## Code Location

**Function**: `update_orders()` in `main.py`  
**Line**: ~8594 (after fix)  
**Section**: Order Chasing Logic

## Related Components

This fix affects:
- ✅ Manual order chasing (Ctrl+Click orders)
- ✅ Quick trading button orders
- ✅ Position closing orders
- ✅ All instruments (SPX, XSP, ES, MES)
- ✅ Both buy and sell orders

## Prevention

**Best Practice**: When storing order information, always include the contract object:
```python
order_tracking[order_id] = {
    'contract': contract,  # Store the exact contract object
    'contract_key': contract_key,  # For display/lookup
    # ... other fields
}
```

**Why**: The contract object contains all IBKR-specific attributes, serialization formats, and internal state. Recreating it risks subtle mismatches.

## Conclusion

This was a simple but critical fix. The order chasing logic was fundamentally sound, but the contract recreation step broke the IBKR order modification API contract. By using the stored contract object, order modifications now work reliably for all instruments and order types.

**Result**: Order chasing now works as designed! 🎉
