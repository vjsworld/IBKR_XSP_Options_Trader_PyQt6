# Chain Oscillation Fix (November 4, 2025)

## Problem Description

The option chain was oscillating between two center strikes:
- **6775** (correct ATM strike detected via 0.5 delta)
- **6700** (incorrect ES offset approximation)

This caused the chain to constantly reload, flickering between these two centers.

## Root Cause

There were **TWO competing auto-recenter mechanisms** running simultaneously:

### 1. Delta-Based Recenter (Correct) ✅
Located in `check_chain_drift_and_recenter()` (lines 5720-5779):
- Runs every 1 second (throttled)
- Detects true ATM strike via 0.5 delta
- Calls `request_option_chain(force_center_strike=6775)` to recenter on detected ATM

### 2. ES-Based Recenter (Problematic) ❌
Located in `auto_refresh_option_chain()` (lines 7314-7334):
- Runs constantly in the auto-refresh loop
- Uses ES offset approximation to calculate center strike
- Calls `request_option_chain()` WITHOUT `force_center_strike`
- This causes chain to recalculate center from ES offset → 6700

## The Oscillation Loop

```
1. Chain loads at 6700 (ES offset approximation)
   ↓
2. Delta-based recenter: ATM detected at 6775
   ↓
3. Calls request_option_chain(force_center_strike=6775)
   ↓
4. Chain loads at 6775 (correct!)
   ↓
5. ES-based recenter: Calculates center from ES → 6700
   ↓
6. Calls request_option_chain() [no force_center_strike]
   ↓
7. Chain loads at 6700 (wrong!)
   ↓
8. BACK TO STEP 2 → INFINITE LOOP
```

## Solution

**Disable ES-based auto-recenter after delta calibration is complete.**

The ES-based recenter is only needed during the initial phase before we have live delta data. Once delta calibration is done (`self.delta_calibration_done = True`), the delta-based recenter is far more accurate and should be the sole authority for drift detection.

### Code Change (Line 7316)

**BEFORE:**
```python
if self.connection_state == ConnectionState.CONNECTED and self.chain_refresh_interval > 0:
```

**AFTER:**
```python
if (self.connection_state == ConnectionState.CONNECTED and 
    self.chain_refresh_interval > 0 and 
    not self.delta_calibration_done):  # ✅ ONLY run before delta calibration
```

## Result

After this fix:
1. Chain loads at 6700 (ES offset approximation)
2. Delta-based recenter detects true ATM at 6775
3. Chain recenters to 6775 using `force_center_strike`
4. `delta_calibration_done` is set to `True`
5. ES-based recenter is now **disabled**
6. Only delta-based recenter runs (checking actual 0.5 delta strikes)
7. **No more oscillation!** ✅

## Timeline

- **November 3, 2025**: Initial implementation of `force_center_strike` parameter
- **November 4, 2025**: Discovered oscillation bug caused by competing recenter mechanisms
- **November 4, 2025**: Fixed by disabling ES-based recenter after delta calibration complete

## Related Files

- `CHAIN_RECENTERING_FIX.md` - Documents the initial `force_center_strike` implementation
- `DELTA_BASED_ATM.md` - Documents the delta-based ATM detection system
