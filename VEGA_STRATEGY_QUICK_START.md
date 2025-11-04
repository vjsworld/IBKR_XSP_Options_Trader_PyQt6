# Vega Delta Neutral Strategy - Quick Start Guide

## What Was Added?

### New Tab: "Vega Strategy"
A complete trading interface for volatility-based trading strategies located between "Trading Dashboard" and "Settings" tabs.

## Quick Start (5 Steps)

### 1. Enable the Strategy
- Go to **Vega Strategy** tab
- Check ✅ **"Enable Vega Strategy"**

### 2. Configure (Optional)
- **Target Vega**: 500 (default) - your desired vega exposure
- **Max Delta Threshold**: 10 (default) - triggers rehedge when exceeded
- **Auto Delta Hedging**: ☐ OFF (manual hedge recommended for learning)

### 3. Scan for Trades
- Click **🔍 Scan for Opportunities**
- Scanner finds low IV opportunities
- Results show in table with strikes, IVs, and total cost

### 4. Enter Trade
- Review scanner results
- Click **Enter Trade** on desired opportunity
- App buys long strangle (put + call)
- Initial delta hedge is calculated
- Position shows in "Active Vega Positions" table

### 5. Manage Position
- Watch **Portfolio Greeks** display (Delta should be near 0)
- Click **⚖️ Hedge Delta Now** when delta drifts
- Click **Close** button when target profit reached

## Portfolio Greeks Display

| Greek | What It Means | What You Want |
|-------|---------------|---------------|
| **Delta** | Directional exposure | Near 0 (green) |
| **Gamma** | Rate of delta change | Higher = more dynamic hedging needed |
| **Vega** | Profit from IV expansion | Higher = more profit potential |
| **Theta** | Daily time decay loss | Lower (but unavoidable for long options) |

## Color Codes

### Delta Label Colors
- 🟢 **Green** (< 5): Excellent - nearly delta neutral
- 🟡 **Yellow** (5-15): Moderate - consider hedging soon
- 🔴 **Red** (> 15): High - hedge immediately

### P&L in Positions Table
- 🟢 **Green**: Profit
- 🔴 **Red**: Loss

## When to Use This Strategy?

### ✅ GOOD Times to Enter
- IV Rank is LOW (< 30)
- Market is calm but expecting an event
- Earnings announcements coming
- Economic data releases expected
- Political/geopolitical uncertainty building

### ❌ BAD Times to Enter
- IV Rank is HIGH (> 50) - already expensive
- Right after a volatility spike (IV likely to contract)
- Too close to expiration (< 2 days)
- No clear catalyst for volatility expansion

## Trade Management Rules

### Delta Hedging Frequency
- **Low volatility day**: Check 2-3 times
- **High volatility day**: Check every hour
- **Auto-hedge enabled**: Every 30 seconds (automatic)

### When to Hedge
- Portfolio Delta exceeds your threshold (default: ±10)
- After a large directional move in underlying
- Before market close if holding overnight

### When to Exit (Take Profit)
- ✅ IV expands 20-50% (e.g., from 15% to 18-22%)
- ✅ Position up 30-50% in value
- ✅ VIX spikes significantly
- ✅ Expected catalyst has passed

### When to Exit (Stop Loss)
- ❌ Position down 30-50% in value
- ❌ IV continues to contract
- ❌ 1-2 days before expiration (gamma risk too high)
- ❌ No volatility catalyst on horizon

## Important Notes

### ⚠️ Manual Hedge Required
The app **calculates** the hedge requirement but does **NOT automatically execute** hedge orders. 

**Why?**: SPX is a cash index (non-tradeable). You need to hedge using:
- SPY ETF (for XSP, use 1/10 size)
- ES futures (for SPX)
- SPX futures

**What to do**: When app says "SELL 50 shares", execute that order manually in TWS or your broker platform.

### 📊 Scanner Logic
Current implementation scans for:
- Long strangle: 2 strikes OTM on each side
- Based on current expiry selected
- Uses real-time market data for pricing

**Future enhancement**: Multi-expiry scanning, true IV Rank calculation

## Example Scenario

```
Step 1: Scan shows opportunity
  - Expiry: Today (0DTE)
  - Put Strike: 535 @ IV 18%
  - Call Strike: 545 @ IV 19%
  - Total Cost: $12.50 ($1,250 total)
  - IV Rank: Low

Step 2: Click "Enter Trade"
  - BUY 1 x 535 PUT
  - BUY 1 x 545 CALL
  - Position Delta: +8.5
  - Hedge needed: SELL 9 shares of SPY

Step 3: Execute hedge manually
  - In TWS: SELL 9 shares SPY at market

Step 4: Monitor
  - 10:00 AM: Delta drifts to -12
  - Click "Hedge Delta Now"
  - App says: BUY 20 shares
  - Execute: BUY 20 shares SPY in TWS

Step 5: Exit
  - 2:00 PM: VIX spikes, IV jumps to 25%
  - Position value: $16.00 (up $3.50 = 28% profit)
  - Click "Close"
  - App sells both put and call
  - Manually close SPY hedge (net ~11 shares long, sell them)
```

## Keyboard Shortcuts

Currently none specific to Vega Strategy tab. Use mouse/click interface.

## Troubleshooting

### "Cannot scan: No expiry selected"
- Switch to **Trading Dashboard** tab
- Select an expiry in the option chain
- Return to **Vega Strategy** tab and scan again

### "Insufficient market data for scan"
- Ensure option chain is loaded with live data
- Check IBKR connection is active
- Try refreshing the chain

### "Position not updating"
- Market data may be delayed
- Check IBKR connection status
- Verify positions are actually filled in TWS

### Delta not color-changing
- Ensure market data is flowing
- Greeks require live market data
- Check positions table shows Greek values

## Advanced Tips

### Optimal Position Sizing
Start with **1 contract** to learn. Scale to:
- 2-5 contracts: Intermediate
- 5-10 contracts: Advanced (requires more capital for hedging)

### Multiple Positions
You can run multiple vega trades simultaneously. Each gets a unique Trade ID (VEGA_timestamp).

### Hedge Tracking
Write down your hedge trades in a separate log to reconcile later. Example:
```
Trade ID: VEGA_1234567890
Initial Hedge: SELL 12 SPY @ 540.00
Adjustment 1: BUY 5 SPY @ 538.50
Adjustment 2: SELL 8 SPY @ 542.00
Net Position: Short 15 SPY @ avg 540.50
```

## Next Steps

1. **Paper trade first**: Use IBKR paper trading account
2. **Learn the Greeks**: Understand delta, gamma, vega, theta deeply
3. **Track your P&L**: Keep a journal of what worked and what didn't
4. **Iterate**: Adjust your threshold and target settings based on experience
5. **Scale gradually**: Don't jump from 1 to 10 contracts immediately

## Support & Documentation

- Full implementation details: `VEGA_DELTA_NEUTRAL_IMPLEMENTATION.md`
- General app instructions: `README.md`
- Copilot instructions: `.github/copilot-instructions.md`

---

**Good luck and trade responsibly!** 🚀📈
