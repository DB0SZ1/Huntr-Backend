# TEST SUITE - COMMAND REFERENCE

## 🚀 Quick Commands

### Install Dependencies
```bash
pip install httpx
```

### Start Backend (Terminal 1)
```bash
python main.py
```

### Run Tests (Terminal 2 - after 5 seconds)
```bash
python test_system_comprehensive.py
```

### Run Tests on Production
```bash
# Edit test_system_comprehensive.py line 18:
# BASE_URL = "https://huntr-backend.onrender.com"

python test_system_comprehensive.py
```

---

## 📊 Understanding Output

### Color Codes
```
✅ GREEN  = Test Passed
❌ RED    = Test Failed (needs fixing)
⚠️ YELLOW = Warning (might be ok)
ℹ️ BLUE   = Info (for debugging)
```

### Test Numbers
```
TEST 1-2   : Auth & Profile (Foundations)
TEST 3-4   : Credits (Money System)
TEST 5-7   : Scans (Scraping)
[30 SEC WAIT] <- Background scraping happens here
TEST 8-10  : Opportunities (THE FIX - Retrieve results)
TEST 11-13 : Dashboard & Niches
TEST 14    : Error Handling
```

---

## 📋 Detailed Test List

### TEST 1: AUTHENTICATION
**What:** User signup and login
**Endpoints:** `/api/auth/signup`, `/api/auth/login`
**Expected:** ✅ Users created, tokens acquired

### TEST 2: USER PROFILE
**What:** Get user information
**Endpoints:** `/api/auth/me`
**Expected:** ✅ Returns user email, name, tier

### TEST 3: CREDITS - BALANCE
**What:** Check credit allocation
**Endpoints:** `/api/credits/balance`
**Expected:** ✅ Free=10, Pro=50, Premium=200 credits/day

### TEST 4: CREDITS - REALTIME
**What:** Get fresh balance (no cache)
**Endpoints:** `/api/credits/balance/realtime` ⭐ NEW
**Expected:** ✅ Returns immediate data, cache_expiry=null

### TEST 5: SCANS - START
**What:** Initiate background scan
**Endpoints:** `/api/scans/start`
**Expected:** ✅ Scan created, credits deducted, background task queued

### TEST 6: SCANS - STATUS
**What:** Check scan progress
**Endpoints:** `/api/scans/status/{scan_id}`
**Expected:** ✅ Shows status (running/completed), platforms scanned

### TEST 7: SCANS - HISTORY
**What:** Get all past scans
**Endpoints:** `/api/scans/history`
**Expected:** ✅ Returns list of user's scans

### TEST 8: OPPORTUNITIES - RETRIEVE ⭐ KEY
**What:** Get discovered opportunities
**Endpoints:** `/api/opportunities`
**Expected:** ✅ Returns 10-100+ opportunities from scans

### TEST 9: OPPORTUNITIES - FILTER
**What:** Filter by platform
**Endpoints:** `/api/opportunities?platform=Reddit`
**Expected:** ✅ Returns only selected platform opportunities

### TEST 10: OPPORTUNITIES - SAVE
**What:** Bookmark opportunity
**Endpoints:** `/api/opportunities/{id}` PUT
**Expected:** ✅ Marks opportunity as saved

### TEST 11: DASHBOARD - STATS
**What:** Get dashboard statistics
**Endpoints:** `/api/dashboard/stats`
**Expected:** ✅ Returns scan count, opportunity count, etc

### TEST 12: DASHBOARD - ACTIVITY
**What:** Get activity feed
**Endpoints:** `/api/dashboard/activity`
**Expected:** ✅ Returns recent activities

### TEST 13: NICHES - MANAGEMENT
**What:** Create and list niches
**Endpoints:** `/api/users/niches` POST/GET
**Expected:** ✅ Niche created and retrievable

### TEST 14: ERROR HANDLING
**What:** Test error cases
**Endpoints:** Various (invalid tokens, missing auth, etc)
**Expected:** ✅ Proper 401/404/500 status codes

---

## 🔧 Customization Quick Guide

### Change Backend URL
```python
# Line 18 in test_system_comprehensive.py
BASE_URL = "http://localhost:8000"  # Local
# OR
BASE_URL = "https://huntr-backend.onrender.com"  # Production
```

### Change Test User Emails
```python
# Lines 30-45 in test_system_comprehensive.py
TEST_USERS = {
    "free": {
        "email": "my_test_free@gmail.com",  # Change this
        "password": "MyPassword123!",        # Change this
        "tier": "free"
    }
}
```

### Increase Timeout (for slow connections)
```python
# Line 17 in test_system_comprehensive.py
TIMEOUT = 30.0  # Change to 60.0 for slower connections
```

### Increase Wait Time for Scanning
```python
# Line 281 in test_system_comprehensive.py
for i in range(30, 0, -1):  # Change 30 to 60 for longer wait
```

---

## 📈 Expected Timing

```
TEST 1-2: ~30 seconds (Auth)
TEST 3-4: ~15 seconds (Credits)
TEST 5-7: ~45 seconds (Scans)
WAIT:     ~30 seconds (Background scraping)
TEST 8-10: ~60 seconds (Opportunities)
TEST 11-13: ~45 seconds (Dashboard)
TEST 14: ~30 seconds (Errors)
---
TOTAL: ~3 minutes
```

---

## ✅ What Success Looks Like

### All Tests Pass ✅
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                       ALL TESTS COMPLETED SUCCESSFULLY!                      ║
║                         Finished: 2025-11-28 10:33:12                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Key Indicators of Success
- ✅ 14 tests completed
- ✅ Most show ✅ PASS (green)
- ✅ TEST 8 shows opportunities > 0
- ✅ No ❌ FAIL (red) results
- ✅ Proper HTTP status codes

---

## 🚨 Troubleshooting Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| Connection refused | `python main.py` in terminal 1 |
| Empty opportunities | Increase wait time from 30 to 60 |
| Login fails | Check TEST_USERS credentials |
| Timeout | Increase TIMEOUT from 30 to 60 |
| 422 errors | Check request JSON format |
| 401 errors | Ensure login (TEST 1) passed first |

---

## 📊 Database Queries to Verify

### Count test data created
```javascript
db.users.count({ email: /test_/ })           // Should be 3
db.user_opportunities.count()                 // Should be 50+
db.scans.count()                              // Should be 3
```

### Check opportunities were stored
```javascript
db.user_opportunities.findOne()
// Should show:
// {
//   "user_id": "...",
//   "scan_id": "...",
//   "title": "...",
//   "platform": "Reddit",
//   ...
// }
```

### Verify scan completed
```javascript
db.scans.findOne({ status: "completed" })
// Should show opportunities_found > 0
```

---

## 🎯 Success Checklist

- [ ] Backend running (no errors in terminal)
- [ ] Tests start (see "COMPREHENSIVE SYSTEM TEST" header)
- [ ] TEST 1-2 pass (auth works)
- [ ] TEST 3-4 pass (credits work)
- [ ] TEST 5-7 pass (scans work)
- [ ] 30-second wait completes
- [ ] TEST 8 shows opportunities > 0 ⭐ KEY
- [ ] TEST 8-10 pass (opportunities work)
- [ ] TEST 11-14 pass (dashboard, niches, errors work)
- [ ] Script completes with "ALL TESTS COMPLETED SUCCESSFULLY!"

---

## 🚀 After Tests Pass - Deploy

```bash
# 1. Verify last test
git status
# Should show: app/scan/routes.py modified

# 2. Stage the changes
git add app/scan/routes.py

# 3. Commit with message
git commit -m "feat: save opportunities to user_opportunities collection

- Opportunities from scans now stored in user_opportunities collection
- Linked to user_id for proper API retrieval
- Tested with comprehensive 14-endpoint test suite"

# 4. Push to production
git push origin main

# 5. Wait for Render deployment
# Check email for deployment status

# 6. Verify production
curl https://huntr-backend.onrender.com/api/opportunities \
  -H "Authorization: Bearer YOUR_TOKEN"
# Should return opportunities now!
```

---

## 💡 Tips & Tricks

### Run Only Specific Tests
```python
# Modify run_all_tests() function to call only certain tests
await test_01_authentication()
await test_08_opportunities_retrieve()  # Skip to the interesting one
```

### Capture Output to File
```bash
python test_system_comprehensive.py > test_results.txt 2>&1
```

### Run with Debug Output
```bash
# Add print statements in test functions for debugging
python test_system_comprehensive.py -v
```

### Compare Runs
```bash
# Run once, save output
python test_system_comprehensive.py > run1.txt

# Make changes, run again
python test_system_comprehensive.py > run2.txt

# Compare
diff run1.txt run2.txt
```

---

## 📞 Common Questions

### Q: How long does it take?
**A:** About 2-3 minutes total

### Q: Will it create real test data?
**A:** Yes, 3 test users and ~50-100 opportunities

### Q: Can I delete test data?
**A:** Yes, see cleanup queries in TEST_SCRIPT_GUIDE.md

### Q: What if a test fails?
**A:** Check the error message, fix the backend, re-run

### Q: Does it test production?
**A:** Change BASE_URL to production URL and it will

### Q: Can I run multiple times?
**A:** Yes, it will create duplicate data each time

### Q: Does it need internet?
**A:** Yes, for scraping Twitter/Reddit

### Q: What if Twitter rate limits?
**A:** Normal, Reddit will still work (see logs)

---

## 🎓 Learning Resources

### Inside the Script
- See line numbers for which endpoint each test calls
- Comments explain what each test validates
- Response structures shown in print statements

### Documentation Files
- **TEST_SCRIPT_GUIDE.md** - Detailed explanation of each test
- **QUICK_TEST_REFERENCE.md** - Fast lookup reference
- **TEST_SUITE_SUMMARY.md** - Complete overview

---

## 📝 Notes

- Test script creates real data in database
- Safe to delete after testing
- No production data affected (uses separate test users)
- All operations logged to console
- Can be run multiple times

---

## Final Command

Run this after backend is started:

```bash
python test_system_comprehensive.py
```

That's it! Watch the tests run and see your system tested thoroughly. 🚀

---

## Success Message

When you see this, you're good to go:

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                       ALL TESTS COMPLETED SUCCESSFULLY!                      ║
║                         Finished: [TIME]                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

**Then deploy!** ✅
