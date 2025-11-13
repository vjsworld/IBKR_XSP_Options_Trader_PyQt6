# Market Data Subscription Reference Counting System

## CRITICAL: Preventing Duplicate Subscription Bug

This document describes a **RECURRING BUG** that has been fixed multiple times. **READ THIS BEFORE MODIFYING SUBSCRIPTION LOGIC.**

---

## The Problem: Duplicate Market Data Streams

### Symptom
Option chain cells flicker between two different values rapidly (e.g., bid price shows 11 → 15 → 11 → 15).

### Root Cause
**Multiple chains with the same expiry date create DUPLICATE SUBSCRIPTIONS to the same contract.**

When main chain and ts_0dte chain both use 0DTE expiry:
- Both need market data for `XSP_585_C_20251113`
- System tries to share subscription via `_subscribed_contracts` dictionary
- **BUG:** When one chain is canceled/recentered, it deletes the shared subscription
- Other chain doesn't know subscription was deleted
- Other chain re-subscribes with a NEW req_id for the SAME contract
- **Result:** TWO req_ids sending conflicting data to the same cell → flickering

---

## The Bug Flow (Before Fix)

```
1. Main chain loads:
   - Subscribes to XSP_585_C_20251113
   - Creates req_id 1000
   - Stores in _subscribed_contracts['XSP_585_C_20251113'] = 1000
   - Adds req_id 1000 to active_req_ids['main']

2. TS 0DTE chain loads (same expiry):
   - Checks _subscribed_contracts for XSP_585_C_20251113
   - Finds req_id 1000 (already subscribed!)
   - Reuses req_id 1000 (good!)
   - Adds req_id 1000 to active_req_ids['ts_0dte'] (PROBLEM!)

3. Something triggers ts_0dte chain cancel:
   - Calls cancel_chain_subscriptions('ts_0dte')
   - Loops through active_req_ids['ts_0dte'] (includes req_id 1000)
   - Calls ibkr_client.cancelMktData(1000)
   - Deletes from _subscribed_contracts
   - Deletes from market_data_map

4. Main chain still thinks it owns req_id 1000:
   - Has req_id 1000 in active_req_ids['main']
   - But subscription is CANCELED
   - No data coming in

5. Main chain gets new data request or recenter:
   - Checks _subscribed_contracts for XSP_585_C_20251113
   - NOT FOUND (was deleted by ts_0dte cancel!)
   - Creates NEW subscription with req_id 1001
   - Now have TWO req_ids for same contract (old ghost + new)

6. IBKR sends data to BOTH req_ids:
   - Data arrives with slightly different timing
   - Cell updates from req_id 1000 data
   - Cell updates from req_id 1001 data
   - FLICKERING: 11 → 15 → 11 → 15
```

---

## The Solution: Reference Counting

### Core Concept
**Never cancel a subscription if ANY chain is still using it.**

### Implementation

#### 1. Reference Count Dictionary
```python
self._subscription_refcount = {}  # {req_id: set(chain_types)}
```

Tracks which chains (main, ts_0dte, ts_1dte) are using each req_id.

**Example:**
```python
{
    1000: {'main', 'ts_0dte'},      # Shared subscription
    1001: {'main'},                  # Main only
    2000: {'ts_1dte'}                # TS 1DTE only
}
```

#### 2. Subscription Creation
When subscribing (NEW or REUSED):
```python
if call_key in self._subscribed_contracts:
    # REUSING existing subscription
    existing_req_id = self._subscribed_contracts[call_key]
    
    # Add this chain to the reference count
    if existing_req_id not in self._subscription_refcount:
        self._subscription_refcount[existing_req_id] = set()
    self._subscription_refcount[existing_req_id].add(chain_type)
    
else:
    # NEW subscription
    new_req_id = self.get_next_request_id(chain_type)
    
    # Initialize reference count with this chain
    self._subscription_refcount[new_req_id] = {chain_type}
    
    self.ibkr_client.reqMktData(new_req_id, contract, ...)
```

#### 3. Subscription Cancellation
When canceling a chain's subscriptions:
```python
for req_id in self.active_req_ids[chain_type]:
    if req_id in self._subscription_refcount:
        # Remove this chain from reference count
        self._subscription_refcount[req_id].discard(chain_type)
        
        # Only cancel if NO chains are using it
        if len(self._subscription_refcount[req_id]) == 0:
            self.ibkr_client.cancelMktData(req_id)
            del self._subscription_refcount[req_id]
            del self._subscribed_contracts[contract_key]
            # Actually canceled
        else:
            # Still used by other chains - KEEP IT
            logger.debug(f"Keeping req_id {req_id} - still used by: {refcount}")
```

---

## Code Locations (main.py)

### Initialization (~Line 3204)
```python
self._subscribed_contracts = {}      # {contract_key: req_id}
self._subscription_refcount = {}     # {req_id: set(chain_types)}
```

### Subscription Logic (~Line 6560)
```python
# In build_single_chain() when subscribing to strikes
if call_key in self._subscribed_contracts:
    # Reuse + add to refcount
else:
    # New + initialize refcount
```

### Cancellation Logic (~Line 6330)
```python
# In cancel_chain_subscriptions()
# Check refcount before actually canceling
```

---

## Testing & Verification

### How to Test
1. Start app, let all 3 chains load
2. Watch Activity Log for subscription messages
3. Look for: "Reusing XSP_585_C_20251113 - reqId=1000 (used by: main, ts_0dte)"
4. Trigger a recenter (price drift)
5. Watch for: "Keeping reqId=1000 - still used by: main"
6. Verify NO flickering in option chain cells

### Log Messages to Look For

**Good (Reference Counting Working):**
```
✓ main chain: 40 new subscriptions, 0 reused (20 strikes × 2)
✓ ts_0dte chain: 0 new subscriptions, 24 reused (12 strikes × 2)
  Actually canceled: 0, kept (shared): 24
```

**Bad (Bug Present):**
```
New subscription: XSP_585_C_20251113 with reqId=1000
New subscription: XSP_585_C_20251113 with reqId=1001  ← DUPLICATE!
```

---

## Common Scenarios

### Scenario 1: Main + TS 0DTE (Same Expiry)
- Main loads first: Creates 40 subscriptions (20 strikes × 2)
- TS 0DTE loads: Reuses all 24 overlapping subscriptions (12 strikes × 2)
- Refcount: 24 req_ids have {'main', 'ts_0dte'}
- Cancel ts_0dte: 24 subscriptions kept (main still using)
- Cancel main: Now all 24 can be canceled

### Scenario 2: All 3 Chains (Different Expiries)
- Main: 0DTE expiry → 40 subscriptions
- TS 0DTE: 0DTE expiry → Reuses 24 from main
- TS 1DTE: 1DTE expiry → Creates 24 NEW subscriptions (different expiry)
- Total: 64 subscriptions (40 main + 24 ts_1dte, with 24 shared)

### Scenario 3: Recentering Main Chain
- Cancel main subscriptions
- Check refcount: 24 shared with ts_0dte → KEEP
- Rebuild main chain at new center
- Subscribe to new strikes → NEW req_ids
- Subscribe to overlapping strikes → Reuse from ts_0dte

---

## CRITICAL RULES

### ✅ DO:
1. **Always update refcount when subscribing OR reusing**
2. **Always check refcount before canceling**
3. **Use set() for refcount values** (allows multiple chains)
4. **Add chain_type to refcount in BOTH new and reuse cases**
5. **Log which chains are sharing subscriptions** (helps debugging)

### ❌ DON'T:
1. **Never cancel without checking refcount**
2. **Never assume a req_id is exclusive to one chain**
3. **Never delete from _subscribed_contracts if refcount > 0**
4. **Never use same req_id range for different chains** (1000-1999 main, 2000-2999 ts_0dte, 3000-3999 ts_1dte)
5. **Never skip refcount update when reusing subscription**

---

## Why This Bug Keeps Recurring

### Root Psychological Issue
**It seems like the subscription tracking is working** because:
- `_subscribed_contracts` prevents duplicate `reqMktData()` calls ✓
- Chains correctly "share" subscriptions ✓
- No errors in logs ✓

**BUT the cancellation logic doesn't account for sharing:**
- When chain A cancels, it destroys shared subscriptions
- Chain B doesn't know its subscriptions were destroyed
- Chain B re-subscribes with new req_id
- Now have two data streams for same contract

### Key Insight
**Preventing duplicate `reqMktData()` is NOT enough.**
**Must also prevent premature `cancelMktData()` of shared subscriptions.**

---

## Related Files
- `main.py` - All subscription logic
- `FLICKERING_FIX_COMPREHENSIVE.md` - Previous fix (in-place cell updates)
- `FOP_TRADING_CLASS_FIX.md` - FOP contract specifics

---

## Version History
- **Nov 13, 2025**: Implemented reference counting system to fix duplicate streams
- **Earlier**: Multiple attempts to fix via subscription deduplication (insufficient)

---

## Emergency Recovery

If this bug reappears:

### Quick Check
1. Search logs for: "New subscription: XSP_XXX_X_YYYYMMDD with reqId="
2. If same contract appears twice with different req_ids → Bug is back
3. Check if `_subscription_refcount` is being updated correctly

### Quick Fix
1. Verify `_subscription_refcount` exists and is initialized
2. Verify it's updated when subscribing AND reusing
3. Verify `cancel_chain_subscriptions()` checks refcount before canceling
4. Add aggressive logging to see refcount state

### Nuclear Option
If all else fails:
```python
# In cancel_chain_subscriptions(), add this safeguard:
contract_key = self.app_state['market_data_map'].get(req_id)
if contract_key and contract_key in self._subscribed_contracts:
    if self._subscribed_contracts[contract_key] == req_id:
        # This req_id is the canonical one for this contract
        # Check if ANY other chain has it in their active_req_ids
        is_shared = any(
            req_id in self.active_req_ids[other_chain]
            for other_chain in ['main', 'ts_0dte', 'ts_1dte']
            if other_chain != chain_type
        )
        if is_shared:
            logger.warning(f"Refusing to cancel shared reqId={req_id}")
            continue  # Skip cancellation
```

---

## Summary

**The reference counting system ensures that market data subscriptions are only canceled when ALL chains using them have released them.** This prevents the catastrophic bug where one chain's cleanup breaks another chain's data flow, causing duplicate subscriptions and flickering values.

**NEVER modify subscription logic without understanding and preserving this reference counting mechanism.**
