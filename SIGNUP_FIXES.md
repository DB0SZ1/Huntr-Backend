# Signup Fixes - November 29, 2025

## Issues Fixed

### 1. ✅ E11000 Duplicate Key Error on paystack_subscription_id
**Problem:** MongoDB unique index on `paystack_subscription_id` was rejecting multiple `null` values
**Solution:** Don't include `paystack_subscription_id` field in subscription document when it's null
**File:** `app/auth/traditional.py` (lines 162-175)
**Impact:** Multiple users can now sign up without database constraint errors

### 2. ✅ Verification Email Function
**Status:** Correctly imported from `app.notifications.email.send_verification_email`
**Works With:** New argon2 password hashing

## Changes Made

**app/auth/traditional.py:**
- Removed `paystack_subscription_id: None` from subscription insert
- Added check for existing subscription (prevent duplicates)
- Matches OAuth signup pattern which already had this fix

## Verification

✅ Signup flow now:
1. Creates user in `db.users`
2. Generates email verification token
3. Sends verification email (try/except, doesn't block)
4. Creates subscription without null paystack_subscription_id field
5. Returns user_id and signup confirmation

✅ Password hashing uses argon2 (no 72-byte limit)
✅ No database constraint violations
✅ Email notifications gracefully fail if SMTP not configured

## Deployment Status
🚀 **READY** - All signup issues resolved

