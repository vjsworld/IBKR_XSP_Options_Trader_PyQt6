# MES Hedging Quick Reference

## At a Glance

### What's Automated Now
- ✅ MES subscription on connect
- ✅ Delta calculation
- ✅ MES contract sizing
- ✅ Hedge order placement (market orders)
- ✅ Automatic hedge closing on position exit
- ✅ Continuous monitoring (if enabled)

### What You Need to Do
1. Enable Vega Strategy
2. (Optional) Enable Auto Delta Hedging
3. Scan and enter trades
4. Watch the magic happen! ✨

## Quick Math

```
XSP Delta → MES Contracts
±5    →  1 MES
±10   →  2 MES
±25   →  5 MES
±50   →  10 MES
±100  →  20 MES
```

**Rule**: Divide delta by 5, round to nearest integer

## Hedge Actions

| Your Delta | Market View | MES Action | Why |
|------------|-------------|------------|-----|
| +50 | Slightly Bullish | SELL 10 MES | Neutralize |
| -30 | Slightly Bearish | BUY 6 MES | Neutralize |
| +5 | Nearly Neutral | SELL 1 MES (or skip) | Fine-tune |
| 0 | Perfect | None | ✅ |

## Button Actions

### 🔍 Scan for Opportunities
- Finds low IV strangles
- Shows total cost and strikes
- Click "Enter Trade" to execute

### 🎯 Enter Trade
- Buys long strangle (put + call)
- **Auto-hedges after 2 seconds**
- Creates position in table

### ⚖️ Hedge Delta Now
- Manual hedge trigger
- Calculates portfolio delta
- Places MES order immediately

### 🔴 Close
- Sells both option legs
- **Auto-closes MES hedge**
- Removes from table

## Auto-Hedge Settings

### Enable Vega Strategy
- **Must be ON** to trade

### Enable Auto Delta Hedging
- **ON**: Monitors every 30 seconds, auto-rehedges
- **OFF**: Manual hedging only (click button)

### Max Delta Threshold
- **5**: Very tight (expensive, more orders)
- **10**: Balanced (recommended)
- **20**: Loose (cheaper, less neutral)

## Reading the Table

### Hedge MES Column
- **-10 MES**: Short 10 contracts (hedging positive delta)
- **+5 MES**: Long 5 contracts (hedging negative delta)
- **None**: No hedge placed yet

### Portfolio Δ
- Shows option delta (before hedge effect)
- Color: 🟢 Green (good) → 🟡 Yellow (ok) → 🔴 Red (hedge now!)

## Typical Workflow

```
1. Connect to IBKR
   ↓ (MES auto-subscribes)
2. Enable Vega Strategy ✅
3. Scan for Opportunities 🔍
   ↓
4. Click "Enter Trade"
   ↓ (Buys put + call)
   ↓ (2 seconds...)
   ↓ (AUTO: Calculates delta)
   ↓ (AUTO: Places MES hedge)
5. Monitor position
   ↓ (If auto-hedge ON: monitors every 30s)
   ↓ (If delta drifts: auto-rehedges)
6. When profit target hit → Click "Close"
   ↓ (Sells put + call)
   ↓ (AUTO: Closes MES hedge)
7. Done! ✅
```

## Cost Example

### Position
- Long 1 XSP 530 Put @ $2.00
- Long 1 XSP 540 Call @ $2.50
- **Total**: $450 ($4.50 × 100)

### Hedge
- Delta: +10
- MES: SELL 2 contracts
- **Commission**: $0.50 ($0.25 × 2)

### Exit
- Sell options: $500 ($5.00 × 100)
- Close MES: 2 contracts
- **Commission**: $0.50 ($0.25 × 2)

### Net
- **Options P&L**: +$50
- **Hedge Cost**: -$1.00
- **Net Profit**: +$49

## Common Scenarios

### Scenario 1: IV Expands Quickly
```
Time    Delta   Action
09:30   +8      SELL 2 MES (initial)
10:15   +12     SELL 1 MES (rehedge)
11:00   -15     BUY 6 MES (delta flipped, rehedge)
11:30   -5      Close (profit target)
        ↓       BUY 1 MES (close hedge)
Result: Slightly over-hedged but captured IV expansion
```

### Scenario 2: Gamma Whipsaw (Auto-Hedge ON)
```
Time    Delta   Action
09:30   +10     SELL 2 MES
09:31   +5      (no action, within threshold)
09:32   +15     SELL 1 MES
09:33   +8      BUY 1 MES (unwound previous)
Result: Auto-monitoring kept delta tight despite whipsaw
```

### Scenario 3: Set-and-Forget (Auto-Hedge ON)
```
09:30   Enter position, hedge -2 MES
        [Walk away, let auto-hedge handle it]
15:00   Return, delta still <10 (rehedged 3x automatically)
15:30   Close position, net hedge -5 MES closed
Result: Hands-off delta neutrality all day
```

## Pro Tips

### 💡 Tip 1: Start Manual
Enable auto-hedge **after** you're comfortable with manual hedging. Learn the mechanics first.

### 💡 Tip 2: Watch the First Few
Don't walk away on your first few trades. Watch how MES orders execute. Verify fills in TWS.

### 💡 Tip 3: Check MES Price
Glance at MES price occasionally. If it's not updating, check connection or resubscribe.

### 💡 Tip 4: Hedge Before News
Major news events? Hedge manually BEFORE the event (delta will whipsaw during).

### 💡 Tip 5: Close End of Day
If holding overnight, consider closing and re-entering next day (avoids overnight gamma risk).

## Troubleshooting Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| "MES not initialized" | Wait 5 seconds after connect, retry |
| Hedge didn't place | Check TWS connection, check order ID |
| Delta not updating | Refresh option chain, wait for greeks |
| Over-hedged | Click hedge button with opposite small order |
| Under-hedged | Click hedge button again |

## Emergency: Manual Hedge

If automation fails:

1. Note your portfolio delta (e.g., +47)
2. Open TWS → Futures
3. Search "MES"
4. **Divide delta by 5**: 47 / 5 = 9.4 → 9 contracts
5. **SELL 9 MES** (if delta positive) or **BUY 9 MES** (if negative)
6. Done!

## Key Log Messages

| Message | Meaning |
|---------|---------|
| "✅ Subscribed to MES futures 202512" | Good! Hedge ready |
| "📊 Calculated hedge: SELL 5 MES" | Auto-calc complete |
| "🛡️ Hedge order #123: SELL 5 MES" | Order submitted |
| "✅ Hedge order placed: SELL 5 MES" | Hedge active |
| "🔴 Closing vega position" | Exit initiated |
| "✓ Hedge closed: BUY 5 MES" | Hedge unwound |

## Settings Cheat Sheet

### Conservative (Tight Delta)
- Max Delta Threshold: **5**
- Auto Hedge: **ON**
- Result: More commissions, tighter neutrality

### Balanced (Recommended)
- Max Delta Threshold: **10**
- Auto Hedge: **ON**
- Result: Good balance of cost and neutrality

### Aggressive (Loose Delta)
- Max Delta Threshold: **20**
- Auto Hedge: **OFF** (manual only)
- Result: Lower costs, less tight neutrality

### Learning Mode
- Max Delta Threshold: **15**
- Auto Hedge: **OFF**
- Result: Manual control, learn the ropes

## Success Checklist

Before your first trade:
- [ ] Connected to IBKR (status shows "CONNECTED")
- [ ] MES subscription confirmed (see log message)
- [ ] Vega Strategy enabled ✅
- [ ] Option chain loaded with deltas
- [ ] Understand hedge direction (SELL for +Δ, BUY for -Δ)
- [ ] TWS open to verify orders
- [ ] Small position size (1 contract to start)

You're ready! 🚀

---

**Remember**: The system is automated but **you are still in control**. Monitor, learn, adjust. Start small and scale as you gain confidence!
