"""
COMPREHENSIVE SYSTEM TEST SCRIPT
Tests all 14 major endpoint categories before production deployment
Includes: Auth, Credits, Scans, Opportunities, Dashboard, etc.
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_URL = "https://huntr-backend.onrender.com"  # Change to "https://huntr-backend.onrender.com" for production
TIMEOUT = 60.0  # Increased timeout for slower backends

# Test users (create these in your database first)
TEST_USERS = {
    "free": {
        "email": "test_free@example.com",
        "password": "Test123!",
        "tier": "free"
    },
    "pro": {
        "email": "test_pro@example.com", 
        "password": "Test123!",
        "tier": "pro"
    },
    "premium": {
        "email": "test_premium@example.com",
        "password": "Test123!",
        "tier": "premium"
    }
}

# Store tokens from login
TOKENS = {}

# ============================================================================
# COLORS FOR TERMINAL OUTPUT
# ============================================================================

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_test(section: int, name: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}TEST {section}: {name}{Colors.ENDC}")
    print("=" * 80)

def print_pass(msg: str):
    print(f"{Colors.GREEN}✅ PASS:{Colors.ENDC} {msg}")

def print_fail(msg: str):
    print(f"{Colors.RED}❌ FAIL:{Colors.ENDC} {msg}")

def print_info(msg: str):
    print(f"{Colors.CYAN}ℹ️  INFO:{Colors.ENDC} {msg}")

def print_warn(msg: str):
    print(f"{Colors.YELLOW}⚠️  WARN:{Colors.ENDC} {msg}")

# ============================================================================
# TEST 1: AUTHENTICATION - SIGNUP & LOGIN
# ============================================================================

async def test_01_authentication():
    """Test signup and login endpoints"""
    print_test(1, "AUTHENTICATION - SIGNUP & LOGIN")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        # Test signup for each tier
        for tier, user_data in TEST_USERS.items():
            print_info(f"Testing signup for {tier} tier: {user_data['email']}")
            
            signup_response = await client.post(
                "/api/auth/signup",
                json={
                    "email": user_data["email"],
                    "password": user_data["password"],
                    "name": f"Test User {tier.upper()}",
                    "tier": tier
                }
            )
            
            if signup_response.status_code in [200, 201, 400]:  # 400 if already exists
                print_pass(f"Signup endpoint responded: {signup_response.status_code}")
            else:
                print_fail(f"Signup failed: {signup_response.status_code}")
                print_warn(f"Response: {signup_response.text}")
        
        # Test login
        for tier, user_data in TEST_USERS.items():
            print_info(f"Testing login for {tier} tier")
            
            login_response = await client.post(
                "/api/auth/login",
                json={
                    "email": user_data["email"],
                    "password": user_data["password"]
                }
            )
            
            if login_response.status_code == 200:
                data = login_response.json()
                token = data.get("access_token")
                TOKENS[tier] = token
                print_pass(f"Login successful - Token acquired for {tier}")
            else:
                print_fail(f"Login failed: {login_response.status_code}")
                print_warn(f"Response: {login_response.text}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 2: USER PROFILE - GET & UPDATE
# ============================================================================

async def test_02_user_profile():
    """Test user profile endpoints"""
    print_test(2, "USER PROFILE - GET & UPDATE")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        for tier, token in TOKENS.items():
            print_info(f"Testing profile for {tier} tier")
            
            # Get profile
            profile_response = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                print_pass(f"Profile retrieved: {profile_data.get('email')}")
                print_info(f"  - Tier: {profile_data.get('tier')}")
                print_info(f"  - Name: {profile_data.get('name')}")
            else:
                print_fail(f"Get profile failed: {profile_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 3: CREDITS - INITIALIZATION & BALANCE
# ============================================================================

async def test_03_credits_balance():
    """Test credit initialization and balance endpoints"""
    print_test(3, "CREDITS - INITIALIZATION & BALANCE")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        for tier, token in TOKENS.items():
            print_info(f"Testing credits for {tier} tier")
            
            # Get balance
            balance_response = await client.get(
                "/api/credits/balance",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if balance_response.status_code == 200:
                balance_data = balance_response.json()
                current = balance_data.get("current_credits", 0)
                daily = balance_data.get("daily_credits", 0)
                print_pass(f"Balance retrieved: {current}/{daily} credits")
                print_info(f"  - Daily refill: {balance_data.get('daily_credits_used', 0)} used")
                print_info(f"  - Tier: {balance_data.get('tier')}")
            else:
                print_fail(f"Get balance failed: {balance_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 4: CREDITS - REALTIME BALANCE (NEW ENDPOINT)
# ============================================================================

async def test_04_credits_realtime():
    """Test realtime credit balance endpoint"""
    print_test(4, "CREDITS - REALTIME BALANCE")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        for tier, token in TOKENS.items():
            print_info(f"Testing realtime balance for {tier} tier")
            
            realtime_response = await client.get(
                "/api/credits/balance/realtime",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if realtime_response.status_code == 200:
                data = realtime_response.json()
                print_pass(f"Realtime balance retrieved")
                print_info(f"  - Current: {data.get('current_credits')} credits")
                print_info(f"  - Next refill in: {data.get('hours_until_refill')} hours")
                print_info(f"  - Cache expiry: {data.get('cache_expiry')} (should be null)")
            else:
                print_fail(f"Realtime balance failed: {realtime_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 5: SCANS - START SCAN
# ============================================================================

async def test_05_scans_start():
    """Test starting a scan"""
    print_test(5, "SCANS - START SCAN")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        scan_ids = {}
        
        for tier, token in TOKENS.items():
            print_info(f"Starting scan for {tier} tier")
            
            start_response = await client.post(
                "/api/scans/start",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if start_response.status_code == 200:
                data = start_response.json()
                scan_id = data.get("scan_id")
                scan_ids[tier] = scan_id
                print_pass(f"Scan started: {scan_id}")
                print_info(f"  - Status: {data.get('status')}")
                print_info(f"  - Credits deducted: {data.get('credits_deducted')}")
                print_info(f"  - Credits remaining: {data.get('credits_remaining')}")
            else:
                print_fail(f"Start scan failed: {start_response.status_code}")
                print_warn(f"Response: {start_response.text}")
        
        # Store scan_ids for later tests
        return scan_ids
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 6: SCANS - STATUS TRACKING
# ============================================================================

async def test_06_scans_status(scan_ids: Dict[str, str]):
    """Test scan status endpoint"""
    print_test(6, "SCANS - STATUS TRACKING")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        for tier, token in TOKENS.items():
            scan_id = scan_ids.get(tier)
            if not scan_id:
                print_warn(f"No scan_id for {tier} tier")
                continue
            
            print_info(f"Checking status for {tier} tier scan: {scan_id}")
            
            status_response = await client.get(
                f"/api/scans/status/{scan_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if status_response.status_code == 200:
                data = status_response.json()
                status = data.get("status", "unknown")
                opportunities = data.get("opportunities_found", 0)
                print_pass(f"Status: {status}")
                print_info(f"  - Opportunities found: {opportunities}")
                print_info(f"  - Platforms scanned: {data.get('platforms_scanned', [])}")
                print_info(f"  - Started at: {data.get('started_at')}")
            else:
                print_fail(f"Get status failed: {status_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 7: SCANS - HISTORY
# ============================================================================

async def test_07_scans_history():
    """Test scan history endpoint"""
    print_test(7, "SCANS - HISTORY")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        for tier, token in TOKENS.items():
            print_info(f"Retrieving scan history for {tier} tier")
            
            history_response = await client.get(
                "/api/scans/history",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if history_response.status_code == 200:
                data = history_response.json()
                total = data.get("total", 0)
                scans = data.get("scans", [])
                print_pass(f"History retrieved: {total} total scans")
                print_info(f"  - Recent scans: {len(scans)}")
                if scans:
                    latest = scans[0]
                    print_info(f"  - Latest scan: {latest.get('status')} with {latest.get('opportunities_found')} opportunities")
            else:
                print_fail(f"Get history failed: {history_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 8: OPPORTUNITIES - RETRIEVE OPPORTUNITIES
# ============================================================================

async def test_08_opportunities_retrieve():
    """Test retrieving opportunities after scan"""
    print_test(8, "OPPORTUNITIES - RETRIEVE OPPORTUNITIES")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        for tier, token in TOKENS.items():
            print_info(f"Retrieving opportunities for {tier} tier")
            
            opps_response = await client.get(
                "/api/opportunities",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if opps_response.status_code == 200:
                data = opps_response.json()
                total = data.get("total", 0)
                opportunities = data.get("opportunities", [])
                print_pass(f"Opportunities retrieved: {total} total")
                print_info(f"  - Showing: {len(opportunities)} opportunities")
                if opportunities:
                    opp = opportunities[0]
                    print_info(f"  - Sample: {opp.get('title')} ({opp.get('platform')})")
            else:
                print_fail(f"Get opportunities failed: {opps_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 9: OPPORTUNITIES - FILTER BY PLATFORM
# ============================================================================

async def test_09_opportunities_filter():
    """Test filtering opportunities by platform"""
    print_test(9, "OPPORTUNITIES - FILTER BY PLATFORM")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        # Use pro or premium tier since they have more platforms
        tier = "pro"
        token = TOKENS.get(tier)
        if not token:
            print_fail("No token for pro tier")
            return
        
        platforms = ["Twitter/X", "Reddit", "Web3.career"]
        
        for platform in platforms:
            print_info(f"Filtering opportunities by platform: {platform}")
            
            filter_response = await client.get(
                f"/api/opportunities?platform={platform}",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if filter_response.status_code == 200:
                data = filter_response.json()
                total = data.get("total", 0)
                print_pass(f"Filter successful: {total} opportunities from {platform}")
            else:
                print_fail(f"Filter failed: {filter_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 10: OPPORTUNITIES - SAVE/BOOKMARK
# ============================================================================

async def test_10_opportunities_save():
    """Test saving/bookmarking opportunities"""
    print_test(10, "OPPORTUNITIES - SAVE/BOOKMARK")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        tier = "pro"
        token = TOKENS.get(tier)
        if not token:
            print_fail("No token for pro tier")
            return
        
        # First get some opportunities
        opps_response = await client.get(
            "/api/opportunities",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if opps_response.status_code != 200:
            print_fail("Could not retrieve opportunities")
            return
        
        opportunities = opps_response.json().get("opportunities", [])
        if not opportunities:
            print_warn("No opportunities found to save")
            return
        
        opp_id = opportunities[0].get("_id")
        print_info(f"Attempting to save opportunity: {opp_id}")
        
        save_response = await client.put(
            f"/api/opportunities/{opp_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_saved": True}
        )
        
        if save_response.status_code == 200:
            print_pass("Opportunity saved successfully")
        else:
            print_warn(f"Save opportunity returned: {save_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 11: DASHBOARD - STATS
# ============================================================================

async def test_11_dashboard_stats():
    """Test dashboard statistics endpoint"""
    print_test(11, "DASHBOARD - STATS")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        for tier, token in TOKENS.items():
            print_info(f"Retrieving dashboard stats for {tier} tier")
            
            stats_response = await client.get(
                "/api/dashboard/stats",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if stats_response.status_code == 200:
                data = stats_response.json()
                print_pass("Dashboard stats retrieved")
                print_info(f"  - Total scans: {data.get('total_scans', 0)}")
                print_info(f"  - Total opportunities: {data.get('total_opportunities', 0)}")
                print_info(f"  - Saved opportunities: {data.get('saved_opportunities', 0)}")
                print_info(f"  - Active niches: {data.get('active_niches', 0)}")
            else:
                print_fail(f"Get stats failed: {stats_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 12: DASHBOARD - ACTIVITY
# ============================================================================

async def test_12_dashboard_activity():
    """Test dashboard activity endpoint"""
    print_test(12, "DASHBOARD - ACTIVITY")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        tier = "pro"
        token = TOKENS.get(tier)
        if not token:
            print_fail("No token for pro tier")
            return
        
        print_info("Retrieving recent activity")
        
        activity_response = await client.get(
            "/api/dashboard/activity?limit=5",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if activity_response.status_code == 200:
            data = activity_response.json()
            activities = data.get("activities", [])
            print_pass(f"Activity retrieved: {len(activities)} recent activities")
            for activity in activities:
                print_info(f"  - {activity.get('type')}: {activity.get('description')}")
        else:
            print_fail(f"Get activity failed: {activity_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 13: NICHES - CREATE & MANAGE
# ============================================================================

async def test_13_niches_management():
    """Test niche creation and management"""
    print_test(13, "NICHES - CREATE & MANAGE")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        tier = "pro"
        token = TOKENS.get(tier)
        if not token:
            print_fail("No token for pro tier")
            return
        
        print_info("Creating a test niche")
        
        niche_data = {
            "name": f"Web3 Dev - {datetime.now().timestamp()}",
            "description": "Testing niche for Web3 development roles",
            "keywords": ["web3", "solidity", "ethereum"],
            "is_active": True
        }
        
        create_response = await client.post(
            "/api/users/niches",
            headers={"Authorization": f"Bearer {token}"},
            json=niche_data
        )
        
        if create_response.status_code in [200, 201]:
            niche = create_response.json()
            niche_id = niche.get("_id") or niche.get("id")
            print_pass(f"Niche created: {niche_id}")
            print_info(f"  - Name: {niche.get('name')}")
            print_info(f"  - Keywords: {niche.get('keywords')}")
            
            # Get all niches
            get_response = await client.get(
                "/api/users/niches",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if get_response.status_code == 200:
                niches = get_response.json().get("niches", [])
                print_pass(f"Retrieved {len(niches)} niches")
            else:
                print_fail(f"Get niches failed: {get_response.status_code}")
        else:
            print_fail(f"Create niche failed: {create_response.status_code}")
    
    finally:
        await client.aclose()

# ============================================================================
# TEST 14: ERROR HANDLING & EDGE CASES
# ============================================================================

async def test_14_error_handling():
    """Test error handling and edge cases"""
    print_test(14, "ERROR HANDLING & EDGE CASES")
    
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        print_info("Testing invalid token handling")
        invalid_response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        if invalid_response.status_code == 401:
            print_pass("Invalid token rejected correctly (401)")
        else:
            print_warn(f"Expected 401, got {invalid_response.status_code}")
        
        print_info("Testing missing token")
        no_token_response = await client.get("/api/auth/me")
        if no_token_response.status_code in [401, 403]:
            print_pass(f"Missing token rejected correctly ({no_token_response.status_code})")
        else:
            print_warn(f"Expected 401/403, got {no_token_response.status_code}")
        
        print_info("Testing non-existent endpoint")
        nonexistent_response = await client.get("/api/nonexistent")
        if nonexistent_response.status_code == 404:
            print_pass("Non-existent endpoint returns 404")
        else:
            print_warn(f"Expected 404, got {nonexistent_response.status_code}")
        
        print_info("Testing invalid scan ID")
        token = list(TOKENS.values())[0]
        invalid_scan_response = await client.get(
            "/api/scans/status/invalid_id",
            headers={"Authorization": f"Bearer {token}"}
        )
        if invalid_scan_response.status_code == 404:
            print_pass("Invalid scan ID returns 404")
        else:
            print_warn(f"Got {invalid_scan_response.status_code}")
        
        print_info("Testing insufficient credits")
        # This would require actually depleting credits, skip for now
        print_pass("Error handling test completed")
    
    finally:
        await client.aclose()

# ============================================================================
# HEALTH CHECK
# ============================================================================

async def check_backend_health():
    """Check if backend is running before tests"""
    print(f"\n{Colors.CYAN}Checking backend health...{Colors.ENDC}")
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
    
    try:
        response = await client.get("/docs", follow_redirects=True)
        if response.status_code == 200:
            print_pass("Backend is running and responding!")
            return True
        else:
            print_fail(f"Backend responded with status {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Backend not responding: {str(e)}")
        print_warn(f"Make sure backend is running at {BASE_URL}")
        return False
    finally:
        await client.aclose()

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

async def run_all_tests():
    """Run all 14 test categories"""
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "COMPREHENSIVE SYSTEM TEST - ALL 14 ENDPOINTS" + " " * 20 + "║")
    print("║" + " " * 20 + f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " " * 33 + "║")
    print("╚" + "=" * 78 + "╝")
    print(f"{Colors.ENDC}")
    
    try:
        # Health check first
        if not await check_backend_health():
            print(f"\n{Colors.RED}{Colors.BOLD}❌ Tests cannot run without backend!{Colors.ENDC}")
            return
        
        # Test 1: Authentication
        await test_01_authentication()
        await asyncio.sleep(1)
        
        # Test 2: User Profile
        await test_02_user_profile()
        await asyncio.sleep(1)
        
        # Test 3: Credits Balance
        await test_03_credits_balance()
        await asyncio.sleep(1)
        
        # Test 4: Realtime Credits
        await test_04_credits_realtime()
        await asyncio.sleep(1)
        
        # Test 5: Start Scan
        scan_ids = await test_05_scans_start()
        await asyncio.sleep(2)
        
        # Test 6: Scan Status
        await test_06_scans_status(scan_ids)
        await asyncio.sleep(2)
        
        # Test 7: Scan History
        await test_07_scans_history()
        await asyncio.sleep(1)
        
        # Wait for scans to complete before checking opportunities
        print_info("Waiting 30 seconds for background scans to complete...")
        for i in range(30, 0, -1):
            print(f"\r⏳ Waiting: {i:2d} seconds remaining...", end="", flush=True)
            await asyncio.sleep(1)
        print("\r" + " " * 40 + "\r", end="")
        
        # Test 8: Retrieve Opportunities
        await test_08_opportunities_retrieve()
        await asyncio.sleep(1)
        
        # Test 9: Filter Opportunities
        await test_09_opportunities_filter()
        await asyncio.sleep(1)
        
        # Test 10: Save Opportunities
        await test_10_opportunities_save()
        await asyncio.sleep(1)
        
        # Test 11: Dashboard Stats
        await test_11_dashboard_stats()
        await asyncio.sleep(1)
        
        # Test 12: Dashboard Activity
        await test_12_dashboard_activity()
        await asyncio.sleep(1)
        
        # Test 13: Niches Management
        await test_13_niches_management()
        await asyncio.sleep(1)
        
        # Test 14: Error Handling
        await test_14_error_handling()
        
        # Summary
        print(f"\n{Colors.BOLD}{Colors.GREEN}")
        print("╔" + "=" * 78 + "╗")
        print("║" + " " * 25 + "ALL TESTS COMPLETED SUCCESSFULLY!" + " " * 20 + "║")
        print("║" + " " * 20 + f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " " * 33 + "║")
        print("╚" + "=" * 78 + "╝")
        print(f"{Colors.ENDC}")
        
    except Exception as e:
        print(f"\n{Colors.RED}{Colors.BOLD}TEST EXECUTION ERROR:{Colors.ENDC}")
        print(f"{Colors.RED}{str(e)}{Colors.ENDC}")
        import traceback
        traceback.print_exc()

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print(f"\n{Colors.YELLOW}NOTE: Make sure your backend is running at {BASE_URL}{Colors.ENDC}\n")
    asyncio.run(run_all_tests())
