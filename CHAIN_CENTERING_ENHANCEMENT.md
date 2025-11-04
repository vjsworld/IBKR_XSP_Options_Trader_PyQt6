# Chain Centering Enhancement - Delta-Based Calibration

## Problem Description

During large overnight market moves (e.g., >1% futures drop in premarket), the option chain would load off-center because:

1. **Initial Load**: Chain centered using ES futures adjusted for cash offset
2. **ES Offset Limitation**: The ES-to-cash offset is calculated during previous day's market hours (8:30 AM - 3:00 PM CT)
3. **Large Overnight Moves**: When futures gap significantly overnight, the saved offset becomes inaccurate
4. **Result**: Chain loads with ATM estimate far from true ATM (identified by 0.5 delta options)

### Example Scenario
- Previous close: SPX 5800, ES offset = +0.50
- Overnight gap: ES drops to 5720 (equivalent to SPX ~5720)
- App uses saved offset: 5720 + 0.50 = 5720.50
- True ATM from deltas: 5715 (5+ strikes off!)
- User opens app to a badly off-center chain

## Solution Implemented

### Core Enhancement: Initial Delta Calibration

The app now performs a **two-phase chain centering process**:

#### Phase 1: Initial Load with Approximation
```
1. Connect to IBKR
2. Get ES futures price (available 23/6)
3. Apply saved ES-to-cash offset
4. Load chain centered on approximated ATM
5. Set delta_calibration_done = False
```

#### Phase 2: Automatic Delta-Based Recalibration
```
1. Option deltas start populating from IBKR
2. find_atm_strike_by_delta() detects true ATM (0.5 delta)
3. check_chain_drift_and_recenter() evaluates drift
4. IF drift >= 2 strikes AND delta_calibration_done = False:
   → Immediately recenter chain on true ATM
   → Set delta_calibration_done = True
   → Log: "Initial ATM calibration complete"
5. ELSE IF drift < 2 strikes:
   → Mark calibration complete
   → Continue with normal operation
```

#### Phase 3: Ongoing Drift Monitoring
```
1. As market moves, ATM strike changes
2. check_chain_drift_and_recenter() monitors drift
3. IF drift >= chain_drift_threshold (default: 5 strikes):
   → Recenter chain
   → Reset delta_calibration_done = False
4. Repeat Phase 2 for new chain
```

## Code Changes

### 1. Added Calibration Flag (line ~2072)
```python
self.delta_calibration_done = False  # Track if we've done initial delta-based recenter after chain load
```

### 2. Reset Flag on New Chain Load (line ~5345)
```python
# Clear recentering flags now that chain is loaded
self.is_recentering_chain = False
self.delta_calibration_done = False  # Reset calibration flag for new chain
```

### 3. Enhanced Drift Detection Logic (line ~5493)
```python
def check_chain_drift_and_recenter(self, atm_strike: float):
    """
    Check if the delta-based ATM strike has drifted from the chain center.
    Auto-recenter the chain if drift exceeds the configured threshold.
    
    Special handling for initial calibration:
    - On first ATM detection after chain load, if ATM is off-center by 2+ strikes,
      immediately recenter (don't wait for full drift threshold)
    - This handles large overnight moves where ES offset approximation is inaccurate
    """
    # ... existing checks ...
    
    # Calculate drift in number of strikes
    strike_increment = self.instrument['strike_increment']
    drift_strikes = abs(atm_strike - self.last_chain_center_strike) / strike_increment
    
    # Check if this is initial calibration
    is_initial_calibration = not self.delta_calibration_done
    initial_calibration_threshold = 2  # Recenter immediately if off by 2+ strikes
    
    if is_initial_calibration and drift_strikes >= initial_calibration_threshold:
        # Immediate recenter on initial detection
        should_recenter = True
        self.delta_calibration_done = True
    elif drift_strikes >= self.chain_drift_threshold:
        # Normal drift threshold exceeded
        should_recenter = True
    else:
        # If calibration check passed, mark as done
        if is_initial_calibration:
            self.delta_calibration_done = True
```

## User Experience

### Before Enhancement
1. User opens app during volatile premarket (large gap down)
2. Chain loads centered on ES offset approximation (e.g., 5720)
3. True ATM from deltas is 5715 (5 strikes off)
4. User must manually wait for drift threshold (5 strikes) to trigger recenter
5. In this example, drift is exactly at threshold - barely triggers recenter
6. Delayed and confusing user experience

### After Enhancement
1. User opens app during volatile premarket (large gap down)
2. Chain loads centered on ES offset approximation (5720) - **same as before**
3. Deltas populate from IBKR (2-5 seconds)
4. True ATM detected at 5715 (5 strikes off)
5. **AUTOMATIC IMMEDIATE RECENTER** (initial calibration threshold: 2 strikes)
6. New chain loads centered on 5715 (true ATM)
7. Log message: "✅ Initial ATM calibration complete"
8. Smooth, automatic user experience

### During Normal Market Hours
1. Chain loads using actual underlying price (XSP/SPX index)
2. Deltas populate
3. ATM detected at same strike as chain center (0-1 strike drift)
4. Calibration passes: "✅ Initial ATM calibration complete (0.5 strikes off - within tolerance)"
5. No unnecessary recentering
6. Normal drift monitoring continues

## Configuration

### Initial Calibration Threshold
- **Default**: 2 strikes
- **Location**: `check_chain_drift_and_recenter()` method
- **Purpose**: Trigger immediate recenter on first ATM detection if off-center
- **Rationale**: 
  - 2 strikes = Noticeable but not excessive
  - Prevents unnecessary recenters for small discrepancies
  - Ensures proper centering for large gaps

### Normal Drift Threshold
- **Default**: 5 strikes (user-configurable in settings)
- **Location**: `self.chain_drift_threshold`
- **Purpose**: Trigger recenter during normal trading as ATM moves
- **Setting**: Adjustable in Settings → Chain Drift Threshold

## Technical Details

### Thread Safety
- All chain operations run on main GUI thread
- Delta updates trigger via `pyqtSignal` from IBKR thread
- `is_recentering_chain` flag prevents concurrent recenters
- 10-second throttle prevents rapid recenter loops

### ATM Detection Algorithm
```python
def find_atm_strike_by_delta(self):
    """Find ATM strike using 0.5 delta"""
    best_call_strike = 0
    best_call_delta_diff = float('inf')
    
    for contract_key, greeks in self.market_data.items():
        if '_C_' in contract_key:  # Call option
            delta = greeks.get('delta', 0)
            if delta > 0:  # Valid call delta
                delta_diff = abs(delta - 0.5)
                if delta_diff < best_call_delta_diff:
                    best_call_delta_diff = delta_diff
                    strike = float(contract_key.split('_')[1])
                    best_call_strike = strike
    
    return best_call_strike
```

### Chain Centering Algorithm
```python
def request_option_chain(self):
    """Build and subscribe to option chain"""
    # 1. Determine reference price
    if underlying_price > 0:
        reference_price = underlying_price  # PRIORITY 1: Actual index
    else:
        reference_price = get_adjusted_es_price()  # FALLBACK: ES + offset
    
    # 2. Round to nearest strike increment
    strike_increment = self.instrument['strike_increment']
    center_strike = round(reference_price / strike_increment) * strike_increment
    
    # 3. Track center for drift detection
    self.last_chain_center_strike = center_strike
    
    # 4. Build strike range
    strikes = []
    current_strike = center_strike - (self.strikes_below * strike_increment)
    end_strike = center_strike + (self.strikes_above * strike_increment)
    
    # 5. Subscribe to market data for each strike (calls and puts)
    # ...
```

## Testing Scenarios

### Scenario 1: Large Overnight Gap (Primary Use Case)
- **Setup**: Saved ES offset = +0.50, overnight gap down 80 points
- **Expected**: 
  1. Chain loads with ES approximation (off by ~8 strikes)
  2. Deltas populate in 2-5 seconds
  3. ATM detected (off by 8 strikes > 2 threshold)
  4. **IMMEDIATE RECENTER**
  5. Log: "🎯 Initial ATM calibration: True ATM at X, chain centered at Y (8.0 strikes off) - RECENTERING IMMEDIATELY"
  6. New chain loads centered on true ATM
  7. Log: "✅ Initial ATM calibration complete"

### Scenario 2: Normal Market Hours (No Gap)
- **Setup**: Actual underlying price available, no overnight gap
- **Expected**:
  1. Chain loads with actual underlying price
  2. Deltas populate
  3. ATM detected (same as center, 0 drift)
  4. **NO RECENTER** (drift < 2 threshold)
  5. Log: "✅ Initial ATM calibration complete: ATM at X, chain centered at X (0.0 strikes off - within tolerance)"

### Scenario 3: Small Overnight Gap (< 2 strikes)
- **Setup**: Saved ES offset slightly off, 1 strike drift
- **Expected**:
  1. Chain loads with ES approximation (off by 1 strike)
  2. Deltas populate
  3. ATM detected (1 strike off < 2 threshold)
  4. **NO RECENTER** (within tolerance)
  5. Log: "✅ Initial ATM calibration complete: ATM at X, chain centered at Y (1.0 strikes off - within tolerance)"

### Scenario 4: Continued Drift During Trading
- **Setup**: Market continues to move after initial calibration
- **Expected**:
  1. Initial calibration completes
  2. Market moves, ATM drifts to 5 strikes from center
  3. Normal drift threshold (5 strikes) exceeded
  4. **RECENTER** (normal drift logic)
  5. Log: "🎯 ATM drifted 5 strikes from center... - AUTO-RECENTERING"
  6. New chain loads, `delta_calibration_done = False`
  7. Repeat initial calibration for new chain

## Benefits

1. **Accuracy**: Chain always centers on true ATM (0.5 delta), not approximation
2. **Speed**: Automatic recenter within seconds of chain load
3. **Reliability**: Handles large overnight gaps gracefully
4. **User Experience**: No manual intervention required
5. **Logging**: Clear visibility into calibration process
6. **Flexibility**: Separate thresholds for initial vs. ongoing drift

## Future Enhancements (Optional)

1. **Configurable Initial Threshold**: Make 2-strike threshold user-adjustable in settings
2. **Smart Threshold Adjustment**: Dynamically adjust threshold based on market volatility
3. **Pre-Load Delta Estimates**: Use ES offset + historical volatility to pre-estimate deltas
4. **Multi-Phase Calibration**: Implement tiered approach (rough → fine → confirmed)

## Related Files

- `main.py` - Main application logic
- `DELTA_BASED_ATM.md` - Original delta-based ATM detection documentation
- `ATM_STRIKE_FIX.md` - Previous ATM calculation fixes
- `settings.json` - Stores ES offset and user preferences

## Version History

- **2025-11-03**: Initial implementation of delta-based calibration enhancement
- **Previous**: Delta-based ATM detection (always-on)
- **Previous**: ES-to-cash offset tracking (live + historical)
- **Previous**: Chain drift monitoring (normal threshold)
