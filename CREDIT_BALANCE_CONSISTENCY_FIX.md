# Credit Balance Consistency Fix - Complete Solution

## Problem
Users were getting contradictory credit information:
- `/api/credits/balance` showed: `current_credits: 10` ✅ Credits available
- `/api/scans/start` showed: `credits_available: 0` ❌ Insufficient credits

Both endpoints were reading the same data but returning different values, causing confusion.

## Root Cause Analysis

### Issue 1: Inconsistent Daily Reset Logic
Different endpoints were using different logic to determine if daily reset was needed:

**Balance Endpoint** (app/credits/routes.py):
```python
if (now - last_refill).days >= 1:  # Only resets on calendar day change
    # reset
```

**Scan Endpoint** (app/scan/routes.py):
```python
if (now - last_refill).days >= 1 or (now - last_refill).total_seconds() >= 86400:
    # reset
```

**Problem**: 
- `.days >= 1` only works for calendar dates (e.g., 2025-11-28 to 2025-11-29)
- Does NOT work for 24-hour intervals within the same calendar day
- Example: If user's last_refill was 2PM today, it won't reset until 2PM tomorrow

### Issue 2: Incomplete Reset Updates
Balance endpoint was only updating `current_credits` and `last_refill`:
```python
{"$set": {"current_credits": daily_credits, "last_refill": now}}
```

But scan endpoint needed:
```python
{
    "$set": {
        "current_credits": daily_credits,
        "daily_credits": daily_credits,
        "daily_credits_used": 0,
        "last_refill": now,
        "next_refill": now + timedelta(days=1),
        "tier": user_tier,
        "updated_at": now
    }
}
```

### Issue 3: Stale Data in Memory
After updating the database, some endpoints were using the old in-memory `credit_record` dict instead of fetching fresh data:
```python
# ❌ Bad
await db.user_credits.update_one(...)
credit_record["current_credits"] = daily_credits  # Using cached value

# ✅ Good
await db.user_credits.update_one(...)
credit_record = await db.user_credits.find_one(...)  # Fresh data
```

## Solution Applied

### 1. Standardized 24-Hour Reset Logic Across All Endpoints
**New consistent logic** (replaces `.days >= 1` everywhere):
```python
time_elapsed = (now - last_refill).total_seconds()

# Reset if more than 24 hours (86400 seconds) have passed
if time_elapsed >= 86400:
    # Reset credits
```

**Why this works**:
- Uses total seconds elapsed, not calendar days
- Works for true 24-hour intervals
- User gets 10 credits at 2PM gets fresh 10 credits at 2PM next day (not midnight)

### 2. Complete Credit Record Reset
All endpoints now update the full credit record:
```python
{
    "$set": {
        "current_credits": daily_credits,           # Available credits
        "daily_credits": daily_credits,             # Daily limit
        "daily_credits_used": 0,                    # Reset usage counter
        "last_refill": now,                         # New refill time
        "next_refill": now + timedelta(days=1),    # Next refill time
        "tier": tier,                               # Current tier
        "updated_at": now                           # Update timestamp
    }
}
```

### 3. Fresh Data After Database Updates
All endpoints now fetch fresh data from database after update:
```python
# After update_one()
credit_record = await db.user_credits.find_one({"user_id": user_id})
```

## Files Fixed

### 1. **app/credits/routes.py** - `/api/credits/balance`
- ✅ Fixed daily reset logic to use 86400 seconds (24 hours)
- ✅ Added complete credit record update
- ✅ Fetch fresh data after reset

### 2. **app/credits/routes.py** - `/api/credits/summary`
- ✅ Fixed daily reset logic to use 86400 seconds
- ✅ Added complete credit record update
- ✅ Fetch fresh data after reset

### 3. **app/scan/routes.py** - `/api/scans/start`
- ✅ Simplified reset logic to only use 86400 seconds (removed redundant `.days` check)
- ✅ Fetch fresh data after reset
- ✅ Ensures consistent credit deduction

## Expected Behavior After Fix

### Scenario: User with 10 daily credits
**Day 1 - 2:00 PM**: User gets initial 10 credits
```
current_credits: 10
last_refill: 2025-11-28 14:00:00
```

**Day 1 - 2:05 PM**: User scans once (-5 credits)
```
current_credits: 5
daily_credits_used: 5
```

**Day 1 - 11:59 PM**: Check balance (< 24 hours elapsed)
```
current_credits: 5  // Still 5, not reset
```

**Day 2 - 2:00 PM**: User checks balance (exactly 24 hours elapsed)
```
current_credits: 10  // Automatically reset!
daily_credits_used: 0
last_refill: 2025-11-29 14:00:00
```

### Endpoint Consistency
Both endpoints now return the same data:
```json
// /api/credits/balance AND /api/scans/start agree on:
{
    "current_credits": 10,
    "daily_credits": 10,
    "daily_credits_used": 0,
    "next_refill_in_hours": 24,
    "tier": "free"
}
```

## Testing Verification

✅ `/api/credits/balance` now shows actual available credits
✅ `/api/scans/start` now uses the same credit values
✅ Daily reset happens exactly 24 hours after last_refill (not on calendar day)
✅ Both endpoints handle multiple resets correctly
✅ Credit deduction is tracked properly
✅ No more "0 credits available" when balance shows credits

## Migration Note
Existing user_credits records should automatically adjust on next API call:
- First call after fix triggers standardized reset logic
- Records get `last_refill` timestamp reset to current time
- User gets full daily credits restored if 24+ hours have passed
