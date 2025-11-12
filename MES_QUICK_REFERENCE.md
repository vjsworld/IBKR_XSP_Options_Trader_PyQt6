# MES Trading Quick Reference

## What is MES?

**MES** (Micro E-mini S&P 500) is a futures contract that's 1/10th the size of ES:
- **ES**: $50 per point
- **MES**: $5 per point (1/10 of ES)

## Quick Setup

### Switch to MES Trading

1. Open `config.py`
2. Change line 50:
   ```python
   SELECTED_INSTRUMENT = 'MES'  # Change from 'ES'
   ```
3. Save and restart the application

### Select Contract Month

In `config.py` around line 75:
```python
MES_FRONT_MONTH = 'MESZ5'  # December 2025
```

**Month Codes**:
- H = March
- M = June  
- U = September
- Z = December

**Examples**:
- `MESZ5` = MES December 2025
- `MESH6` = MES March 2026
- `MESM6` = MES June 2026

## Contract Specifications

### MES Options
| Property | Value |
|----------|-------|
| **Multiplier** | $5 per point |
| **Strike Increment** | 5 points (5800, 5805, 5810...) |
| **Tick Size ≥$3.00** | $0.25 |
| **Tick Size <$3.00** | $0.05 |
| **Exchange** | CME |
| **Contract Type** | FOP (Futures Options) |
| **Expiry** | Daily (0DTE supported) + Monthly |

## Trading Examples

### Contract Value Calculation
**Formula**: Option Price × Multiplier = Total Risk

| Option Price | ES Value ($50) | MES Value ($5) |
|--------------|----------------|----------------|
| $10.00 | $500 | **$50** |
| $15.00 | $750 | **$75** |
| $20.00 | $1,000 | **$100** |
| $25.00 | $1,250 | **$125** |
| $30.00 | $1,500 | **$150** |

### Position Sizing Examples

**Example 1**: $18.00 MES Call Option
- **Per Contract Risk**: $18.00 × 5 = $90
- **10 Contracts**: $90 × 10 = $900 total risk

**Example 2**: Maximum $500 Risk Allocation
- **Option Price**: $15.00
- **Contract Value**: $15.00 × 5 = $75
- **Max Contracts**: $500 ÷ $75 = 6 contracts
- **Actual Risk**: 6 × $75 = $450

### P&L Calculation

**Formula**: (Exit Price - Entry Price) × Quantity × 5

**Example Trade**:
- Entry: $18.00 × 10 contracts
- Exit: $22.00 × 10 contracts  
- P&L: ($22 - $18) × 10 × 5 = **$200 profit**

## Comparison Table

| Feature | SPX | XSP | ES | **MES** |
|---------|-----|-----|-------|---------|
| **Multiplier** | $100 | $100 | $50 | **$5** |
| **Type** | Index Options | Index Options | Futures Options | **Futures Options** |
| **Ideal For** | Large accounts | Small accounts | Medium accounts | **Micro accounts** |
| **Min Capital** | ~$5,000+ | ~$500+ | ~$2,500+ | **~$250+** |
| **Example Risk** | $20 option = $2,000 | $20 option = $2,000 | $20 option = $1,000 | **$20 option = $100** |

## When to Use MES vs ES

### Use MES When:
- ✅ Testing new strategies (lower risk)
- ✅ Smaller account size (<$10k)
- ✅ Learning futures options
- ✅ Fine-tuning position sizes
- ✅ Reducing overnight exposure

### Use ES When:
- ✅ Larger account size (>$25k)
- ✅ Scaling proven strategies
- ✅ Better liquidity needed
- ✅ Lower transaction costs per dollar traded

## Tick Size Rules

Both ES and MES follow the same tick size rules:

**Option Price ≥ $3.00**: $0.25 tick
- Valid prices: $3.00, $3.25, $3.50, $3.75, $4.00...

**Option Price < $3.00**: $0.05 tick
- Valid prices: $0.05, $0.10, $0.15, $0.20, $0.25... $2.95

## Keyboard Shortcuts

Same shortcuts work for MES as other instruments:
- **Ctrl+Click** bid/ask: Quick trade
- **F5**: Refresh chain
- **Ctrl+R**: Recenter chain
- **Ctrl+O**: Open order panel

## Verification Checklist

After switching to MES, verify:
- [ ] Window title shows "MES [Month] [Year] Futures Options"
- [ ] Header shows correct contract (e.g., "Contract: MESZ5")
- [ ] ES-to-cash offset label is hidden (not needed for FOP)
- [ ] Option chain displays with 5-point strikes
- [ ] Position P&L uses $5 multiplier
- [ ] Order confirmations show correct contract values

## Common Questions

**Q: Can I trade both ES and MES in the same app?**  
A: Not simultaneously. Switch `SELECTED_INSTRUMENT` in config.py and restart.

**Q: Do MES options have the same expiration dates as ES?**  
A: Yes! Both support daily (0DTE) and monthly expirations.

**Q: Is liquidity good for MES options?**  
A: MES is very liquid, but ES typically has tighter spreads. For small positions (<10 contracts), MES works great.

**Q: Can I use the same strategies?**  
A: Yes! All strategies (vega, delta-neutral, iron condors, etc.) work identically with MES.

**Q: What about TradeStation integration?**  
A: Works the same way - TradeStation strategies can trade MES just like ES or SPX/XSP.

## Risk Warning

⚠️ **Important**: While MES has lower dollar risk per contract, futures options can still:
- Expire worthless (100% loss)
- Move rapidly (high volatility)
- Have overnight gap risk
- Require futures knowledge

Start small and understand futures options before trading size!

## Support Files

- **Full Implementation Details**: `MES_SUPPORT_IMPLEMENTATION.md`
- **Configuration File**: `config.py`
- **Main Application**: `main.py`

## Quick Test

Test configuration without running the app:
```bash
python config.py info
```

Should show:
```
📈 Instrument: MES
📊 MES Contract: MESZ5
   Expiry: Dec 2025 (20251219)
```

---

**Ready to trade MES?** Just change `SELECTED_INSTRUMENT = 'MES'` in `config.py` and restart! 🚀
