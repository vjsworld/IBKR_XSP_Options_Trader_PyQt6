# ⏰ CRITICAL TIMEZONE CONFIGURATION

## 🚨 ABSOLUTE RULE: ALL TIMES ARE CENTRAL TIME (America/Chicago)

### Application-Wide Timezone Standard

**EVERY** time-related operation in this application uses Central Time (CT / America/Chicago):

- ✅ Market hours: 8:30 AM - 3:00 PM CT
- ✅ After-hours trading: 7:15 PM - 8:30 AM CT (0DTE overnight)
- ✅ All chart timestamps display Central Time
- ✅ All position entry/exit times in Central Time
- ✅ All order timestamps in Central Time
- ✅ All log entries in Central Time
- ✅ TradeStation signal processing in Central Time
- ✅ ES offset calculations use 3:00 PM CT market close
- ✅ Option expiry calculations based on Central Time
- ✅ Historical data converted from Eastern to Central Time

### Code Implementation

**Main timezone initialization (line ~2215 in main.py):**
```python
# Set timezone to Central Time (America/Chicago) - ALL TIMES IN THIS APP USE CT
self.local_tz = pytz.timezone('America/Chicago')
logger.info(f"Application timezone set to: {self.local_tz} (Central Time)")
```

**All pytz.timezone() calls use:**
- `pytz.timezone('America/Chicago')` ✅ CORRECT
- `pytz.timezone('US/Central')` ✅ CORRECT (alias for America/Chicago)
- ❌ **NEVER** use 'US/Eastern' or 'America/New_York'

### Why This Matters

1. **Trading Hours**: SPX/XSP options trading hours are based on Central Time (Chicago Mercantile Exchange)
2. **TradeStation Integration**: Time-based contract selection (0DTE vs 1DTE) relies on Central Time
3. **ES Offset Tracking**: Offset calculations must align with market close (3:00 PM CT)
4. **User Location**: Primary user is in Central Time zone
5. **Consistency**: All timestamps, logs, and displays must be consistent

### Historical Data Note

IBKR returns historical data in US/Eastern time. The application automatically converts this to Central Time for display and calculations. This conversion is handled internally - all displayed times are Central Time.

### TradeStation Time-Based Logic

**Critical for signal processing:**
- **0DTE contracts**: 7:15 PM CT - 11:00 AM CT
- **1DTE contracts**: 11:00 AM CT - 4:00 PM CT

This logic is implemented in `get_ts_active_contract_type()` using Central Time.

### Reference Locations in Code

1. **Header comment**: Lines 13-23 (CRITICAL TIMEZONE CONFIGURATION banner)
2. **Import statement**: Line 48 (pytz import with Central Time comment)
3. **Timezone initialization**: Line ~2215 (self.local_tz assignment)
4. **Market hours**: Line ~4451, 4477, 4501 (US/Central timezone)
5. **ES offset tracking**: Line ~7684, 7843, 7868 (US/Central timezone)
6. **TradeStation**: Line ~8207 (America/Chicago timezone)

### Testing Checklist

When verifying timezone correctness:
- [ ] Check log shows "Application timezone set to: America/Chicago (Central Time)"
- [ ] Verify chart timestamps match Central Time
- [ ] Confirm position times are in Central Time
- [ ] Check order timestamps are Central Time
- [ ] Verify ES offset updates at 3:00 PM CT
- [ ] Confirm TradeStation contract switching at 11:00 AM CT

---

**Last Updated**: November 5, 2025  
**Maintained By**: VJS World  
**DO NOT MODIFY THIS CONFIGURATION WITHOUT EXPLICIT USER APPROVAL**
