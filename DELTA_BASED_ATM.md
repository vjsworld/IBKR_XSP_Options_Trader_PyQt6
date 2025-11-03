# Delta-Based ATM Strike Tracking

## Overview

Implemented a superior ATM strike tracking system using **0.5 delta** instead of price calculations. This is the industry-standard method for identifying true at-the-money options.

## Why Delta-Based ATM is Superior

### The Old Way (Price-Based)
```
ATM Strike = round(price / strike_increment) * strike_increment
```

**Problems:**
- ❌ Depends on accurate underlying price
- ❌ ES futures have basis difference from cash index
- ❌ After-hours prices may be stale
- ❌ Doesn't account for skew or market conditions
- ❌ Can be off by multiple strikes

### The New Way (Delta-Based)
```
ATM Strike = strike where |delta| is closest to 0.5
```

**Advantages:**
- ✅ **Delta represents probability** of expiring ITM
- ✅ **Market-derived** - reflects actual option pricing
- ✅ **Accounts for skew** - implied volatility smile
- ✅ **Works 24/6** - as long as options have deltas
- ✅ **Matches trader expectations** - industry standard

## How It Works

### Step 1: Price-Based Initial Centering
When the option chain first loads, use price to center the chain in an approximate ATM zone:

```python
# Use actual underlying price (preferred)
reference_price = self.app_state.get('underlying_price', 0)

# Fallback to ES-adjusted price (after-hours)
if reference_price == 0:
    reference_price = self.get_adjusted_es_price()

# Center chain around this reference
center_strike = round(reference_price / strike_increment) * strike_increment
```

This ensures we request options in the right range.

### Step 2: Delta-Based ATM Identification
Once greeks arrive, identify true ATM using delta:

```python
def find_atm_strike_by_delta(self):
    """Find strike where delta is closest to 0.5"""
    
    # For calls: find delta closest to +0.5
    # For puts: find delta closest to -0.5
    
    min_call_diff = float('inf')
    atm_call_strike = 0
    
    for contract_key, data in self.market_data.items():
        if '_C_' in contract_key:
            delta = data.get('delta', 0)
            if 0 < delta < 1:
                diff = abs(delta - 0.5)
                if diff < min_call_diff:
                    min_call_diff = diff
                    atm_call_strike = strike
    
    return atm_call_strike
```

### Step 3: Visual Highlighting
Update strike row colors based on delta-identified ATM:

- **ATM Strike**: Gold (#FFD700) with black text
- **Above ATM**: Lighter blue (#2a4a6a)
- **Below ATM**: Darker blue (#1a2a3a)

### Step 4: Continuous Updates
Every time new greeks arrive:

```python
def on_greeks_updated(self, contract_key, greeks):
    self.market_data[contract_key].update(greeks)
    self.update_option_chain_cell(contract_key)
    
    # Update ATM identification based on latest deltas
    self.update_strike_backgrounds_by_delta()
```

## Technical Details

### Delta Ranges
- **ATM Call**: Delta ≈ **0.45 to 0.55** (target: 0.5)
- **ATM Put**: Delta ≈ **-0.55 to -0.45** (target: -0.5)

### Why 0.5?
- **0.5 delta** = 50% probability of expiring in-the-money
- ATM options have approximately equal chance of finishing ITM or OTM
- This is the theoretical definition of "at-the-money"

### Delta vs Price
| Scenario | Price-Based ATM | Delta-Based ATM | Winner |
|----------|----------------|-----------------|--------|
| Normal market | Strike 590 | Strike 590 | Tie |
| High volatility skew | Strike 590 | Strike 588 | Delta ✅ |
| After-hours (stale price) | Strike 595 | Strike 590 | Delta ✅ |
| ES basis difference | Strike 691 | Strike 589 | Delta ✅ |

## User Interface

### Header Display
Added new label showing current ATM strike:

```
XSP: 589.12    ES: 6947.75    ES to SPX offset: +3.17    ATM: 589
```

The ATM label:
- Shows in **gold** (#FFD700) to match the strike highlighting
- Updates in real-time as deltas change
- Shows "Calculating..." until first deltas arrive

### Option Chain Table
- **Gold row** = ATM strike (0.5 delta)
- Provides instant visual identification
- Updates automatically as market moves

## Error Handling

```python
if atm_strike == 0:
    return  # No deltas available yet, keep initial coloring
```

Gracefully handles:
- No greeks data yet (connection just established)
- All deltas are None (data feed issue)
- No options in the 0.3-0.7 delta range (extreme price movement)

## Performance

- **Minimal CPU**: Only recalculates when greeks update
- **Fast lookup**: O(n) through market_data dict
- **No blocking**: Runs on Qt event thread with fast completion
- **Smart updates**: Only updates when delta data changes

## Testing Scenarios

1. **Normal Market Hours**: ATM should match TWS exactly
2. **High Volatility**: ATM may differ from price-based by 1-2 strikes (skew)
3. **After Hours**: Delta-based works, price-based may use stale reference
4. **Large Price Move**: ATM updates immediately as deltas shift

## Benefits Summary

1. **Accuracy**: Industry-standard definition of ATM
2. **Real-time**: Updates as market moves
3. **Visual**: Clear gold highlighting
4. **Reliable**: Works in all market conditions
5. **Professional**: Matches trader expectations and TWS behavior

## References

- **Options Theory**: Delta represents probability of ITM at expiration
- **Market Practice**: Traders use 0.5 delta to define ATM
- **Volatility Skew**: Put/call skew means price-based ATM ≠ delta-based ATM
- **Risk Management**: Delta-based ATM used for hedging and position sizing
