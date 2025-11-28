# User ID Field Fix - Summary

## Problem
The application was throwing a 500 error when starting scans:
```
Error starting scan: 'None' is not a valid ObjectId, it must be a 12-byte input or a 24-character hex string
```

## Root Cause
The `get_current_user()` dependency returns a dict with the key `"id"`, not `"_id"`:
```python
# In app/auth/oauth.py, get_current_user() returns:
return {
    "id": user_id,           # ← This is the key
    "email": user['email'],
    "name": user['name'],
    # ...
}
```

However, the code was trying to access `current_user.get("_id")`, which returned `None`.

## Solution
Updated all endpoints that use `get_current_user()` dependency to use the correct key `"id"`:

### Files Fixed:
1. **app/scan/routes.py** → `/api/scans/start`
   - Changed: `user_id = str(current_user.get("_id"))`
   - To: `user_id = current_user.get("id")`
   - Added validation to ensure user_id exists

2. **app/credits/routes.py** → Multiple endpoints
   - Line 315: Fixed `/api/credits/statement` endpoint
   - Line 389: Fixed `/api/credits/deduct` endpoint
   - Line 448: Fixed `/api/credits/transactions` endpoint
   - All changed from `"_id"` to `"id"`
   - Added validation for user_id

### Code Changes Pattern:
**Before:**
```python
async def some_endpoint(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    try:
        user_id = current_user.get("_id")  # ❌ Returns None
        # ... rest of code
```

**After:**
```python
async def some_endpoint(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    try:
        user_id = current_user.get("id")  # ✅ Returns actual user ID
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in session")
        # ... rest of code
```

## Result
✅ Scan API now properly retrieves user ID from current_user
✅ Credit endpoints now properly access user information
✅ All ObjectId() conversions work correctly
✅ Clear error messages if user_id is missing

## Note
The `get_current_user_id()` dependency (in `app/auth/jwt_handler.py`) returns a string user_id directly and is used in other endpoints. This is the preferred approach when only the user_id is needed (not the full user object).
