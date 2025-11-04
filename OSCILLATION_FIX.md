# Chain Oscillation Fix (November 4, 2025)

## Problem Description

The option chain was oscillating between two center strikes:
- **678** (ES offset approximation)
- **685** (correct ATM strike detected via 0.5 delta)

This caused the chain to constantly reload every few seconds, cycling between these two centers.

## Root Cause (v1 - Partially Fixed)

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

## Root Cause (v2 - Complete Fix)

The first fix (disabling ES-based recenter after calibration) was **incomplete**. The issue was that every time the chain loaded, `delta_calibration_done` was reset to `False` on line 5528. This caused:

```
1. Chain loads at 678 (ES offset)
2. Delta-based recenter: ATM detected at 685
3. Calls request_option_chain(force_center_strike=685)
4. New chain loads at 685
5. ❌ delta_calibration_done reset to False (line 5528)
6. ES-based recenter re-enabled (checks `not delta_calibration_done`)
7. ES-based recenter: Calculates center from ES → 678
8. Calls request_option_chain() [no force_center_strike]
9. Chain loads at 678
10. BACK TO STEP 2 → INFINITE LOOP
```

The flag was being reset on **every chain load**, not just manual requests. This re-enabled the ES-based recenter after every delta-based recenter!

## Solution (v2 - Complete)

**Only reset `delta_calibration_done = False` for manual chain requests, NOT for delta-based recenters.**

### Changes Made:

1. **Line 5380-5388** (inside `request_option_chain()`):
   ```python
   # Reset delta calibration flag ONLY for manual chain requests
   if force_center_strike is None:
       self.delta_calibration_done = False  # Manual request → allow calibration
   else:
       # Delta-based recenter → keep calibration flag
   ```

2. **Lines 5528-5533** (after chain loads):
   ```python
   # REMOVED: self.delta_calibration_done = False
   # Do NOT reset flag here - it's now handled at the START of request_option_chain()
   ```

### Result:

- **Manual chain request** (user changes expiry, clicks refresh):
  - `force_center_strike = None`
  - `delta_calibration_done` reset to `False`
  - ES-based recenter enabled initially
  - Delta-based recenter performs initial calibration
  - ES-based recenter disabled after calibration

- **Delta-based recenter** (automatic drift correction):
  - `force_center_strike = 685` (detected ATM)
  - `delta_calibration_done` **kept as `True`**
  - New chain loads
  - ES-based recenter stays **disabled**
  - **No oscillation!** ✅

## Timeline

- **November 3, 2025**: Initial implementation of `force_center_strike` parameter
- **November 4, 2025 (8:00 AM)**: Discovered oscillation bug caused by competing recenter mechanisms
- **November 4, 2025 (8:00 AM)**: v1 fix - Disabled ES-based recenter after delta calibration (incomplete)
- **November 4, 2025 (8:30 AM)**: Oscillation continued - discovered flag reset issue
- **November 4, 2025 (8:30 AM)**: v2 fix - Only reset flag for manual requests (complete fix)

## Related Files

- `CHAIN_RECENTERING_FIX.md` - Documents the initial `force_center_strike` implementation
- `DELTA_BASED_ATM.md` - Documents the delta-based ATM detection system
