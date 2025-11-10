# ATM Highlighting and Chain Centering Fixes

## Issues Identified and Fixed

### Issue 1: Missing Initial ATM Highlighting ❌➡️✅

**Problem**: Option chains loaded without the yellow ATM strike highlighting initially. The highlighting would only appear after market data ticks updated the chain.

**Root Cause**: `update_strike_backgrounds_by_delta()` was only called during market data updates (`on_market_data_tick`), not during initial chain loading.

**Fix Applied**:
```python
# In request_option_chain() - Added initial ATM highlighting call
QTimer.singleShot(1500, self.update_strike_backgrounds_by_delta)
```

This ensures ATM highlighting appears 1.5 seconds after chain load, allowing initial market data to flow.

### Issue 2: No Fallback for Missing Delta Data ❌➡️✅

**Problem**: When delta data wasn't available yet (during initial chain load), `find_atm_strike_by_delta()` returned 0, causing `update_strike_backgrounds_by_delta()` to exit early with no highlighting.

**Root Cause**: The function was too strict - requiring delta-based ATM before any highlighting could occur.

**Fix Applied**:
```python
# In update_strike_backgrounds_by_delta() - Added fallback for initial highlighting
if atm_strike == 0:
    if hasattr(self, 'last_chain_center_strike') and self.last_chain_center_strike:
        atm_strike = self.last_chain_center_strike
        logger.debug(f"Using chain center strike {atm_strike} for initial ATM highlighting")
    else:
        return  # No ATM or center strike available yet
```

This provides initial ATM highlighting using the chain center strike until real delta data arrives.

### Issue 3: ATM Label Not Updated Initially ❌➡️✅

**Problem**: The ATM label in the header wasn't being updated during initial chain load.

**Fix Applied**: Enhanced ATM label to show estimated vs confirmed ATM:
```python
# Show if this is delta-confirmed or estimated from chain center
delta_atm = self.find_atm_strike_by_delta()
if delta_atm > 0:
    # True delta-based ATM
    self.atm_strike_label.setText(f"ATM: {atm_strike:.0f}")
    self.atm_strike_label.setStyleSheet("color: #FFD700;")  # Gold
else:
    # Estimated ATM (using chain center)
    self.atm_strike_label.setText(f"ATM: ~{atm_strike:.0f}")
    self.atm_strike_label.setStyleSheet("color: #FFA500;")  # Orange
```

## How the Fixed System Works

### Phase 1: Chain Loading (First 2 seconds)
1. User connects or clicks "Load Chain"
2. `request_option_chain()` calculates center strike using:
   - **Priority 1**: Actual underlying price (XSP/SPX index)
   - **Fallback**: ES futures + saved offset
3. Chain loads with strikes centered around calculated price
4. `QTimer.singleShot(1500, update_strike_backgrounds_by_delta)` scheduled
5. Initial market data requests sent to IBKR

### Phase 2: Initial Highlighting (1.5-3 seconds)
1. Timer fires `update_strike_backgrounds_by_delta()`
2. `find_atm_strike_by_delta()` tries to find true ATM using deltas
3. **If delta data available**: Use true ATM (gold label: "ATM: 589")
4. **If no delta data yet**: Use chain center as fallback (orange label: "ATM: ~589")
5. Strike backgrounds colored: Gold=ATM, Light Blue=Above, Dark Blue=Below
6. User sees properly highlighted chain within 2-3 seconds

### Phase 3: Delta Calibration (3-10 seconds)
1. More option greeks data arrives from IBKR
2. `find_atm_strike_by_delta()` identifies true 0.5 delta strike
3. `check_chain_drift_and_recenter()` compares true ATM to chain center
4. **If drift >= 2 strikes**: Auto-recenter chain immediately
5. **If drift < 2 strikes**: Mark calibration complete
6. Label updates to gold "ATM: 589" (confirmed by delta)

### Phase 4: Ongoing Monitoring
1. As market moves, ATM strike changes based on deltas
2. Backgrounds update automatically (throttled to 1/second)
3. **If drift >= 5 strikes**: Auto-recenter chain
4. System maintains proper ATM highlighting continuously

## Expected User Experience After Fixes

### Normal Startup (Market Hours)
1. **0-2 seconds**: Chain loads, no highlighting yet
2. **2-3 seconds**: Yellow ATM highlighting appears (may be estimated)
3. **3-5 seconds**: ATM label confirms with gold color
4. **Result**: Properly centered and highlighted chain

### Volatile Market (Large Overnight Gap)
1. **0-2 seconds**: Chain loads centered on ES estimate
2. **2-3 seconds**: Yellow highlighting on estimated ATM
3. **3-5 seconds**: True ATM detected, significantly different
4. **5-7 seconds**: Chain automatically recenters on true ATM
5. **Result**: Initially off-center, but quickly corrects

### After-Hours Startup
1. **0-2 seconds**: Chain loads using ES + saved offset
2. **2-3 seconds**: Orange "ATM: ~589" (estimated)
3. **3-10 seconds**: Deltas arrive, confirms or corrects
4. **Result**: Best available ATM highlighting

## Remaining Potential Issues

### 1. Underlying Price Data Timing
**Possible Problem**: XSP index data may not be available immediately on connection.
**Check**: Look for "Loading..." in underlying price label
**Solution**: ES fallback should handle this

### 2. Market Data Subscription Issues
**Possible Problem**: Option greeks data not arriving due to subscription issues
**Check**: Look in logs for "Requested market data for XSP_XXX_C_" messages
**Solution**: Verify IBKR connection and data subscriptions

### 3. Delta Calculation Logic
**Possible Problem**: Delta-based ATM finding may not be working correctly
**Check**: Look for "✅ ATM strike identified by CALL delta" in logs
**Solution**: Debug `find_atm_strike_by_delta()` function

### 4. Chain Center Strike Calculation
**Possible Problem**: Initial chain centering calculation may be wrong
**Check**: Compare chain center to expected ATM based on current prices
**Solution**: Debug `calculate_initial_atm_strike()` function

## Testing the Fixes

### Test 1: Fresh Connection
1. Start app and connect to IBKR
2. **Expect**: Chain loads and shows yellow ATM within 3 seconds
3. **Check logs**: Should see initial highlighting timer and ATM detection

### Test 2: Manual Chain Refresh
1. Click "Refresh Chains" button
2. **Expect**: Chain reloads with immediate proper highlighting
3. **Check**: ATM should match current underlying price

### Test 3: Large Price Movement
1. Wait for significant market movement (>1% SPX)
2. **Expect**: ATM highlighting shifts automatically
3. **Check**: If movement >5 strikes, chain should auto-recenter

## Log Messages to Monitor

### Successful Operation
```
[Chain Init] Using XSP spot price $589.12
Chain centered at strike 589 (Reference: $589.12)
Subscribed to 42 option contracts
✅ ATM strike identified by CALL delta: 589.0 (delta diff: 0.0234)
✅ Initial calibration complete: ATM at 589, center at 589 (0.0 strikes off - OK)
```

### Problem Indicators
```
ERROR: No underlying price available
WARNING: Using ES-derived price - may not match TWS  
No ATM strike found by delta - waiting for greeks data
🚨 Initial calibration triggered on TS chain! (should not happen for main chain)
```

The system should now provide consistent, immediate ATM highlighting that matches TWS behavior.