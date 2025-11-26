"""
Quick Server Health Check
Tests the running server without full test suite
"""
import httpx
import asyncio
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def test_server():
    print("\n" + "="*70)
    print(" JOB HUNTER BACKEND - QUICK HEALTH CHECK")
    print(f" Testing: {BASE_URL}")
    print(" Started: " + datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'))
    print("="*70 + "\n")
    
    results = {
        "passed": 0,
        "failed": 0
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        
        # Test 1: Root endpoint
        print("1. Testing root endpoint...")
        try:
            response = await client.get(f"{BASE_URL}/")
            if response.status_code == 200:
                data = response.json()
                print(f"   [OK] Status: {response.status_code}")
                print(f"   [OK] Message: {data.get('message')}")
                results["passed"] += 1
            else:
                print(f"   [FAIL] Status: {response.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"   [FAIL] Error: {str(e)}")
            results["failed"] += 1
        
        # Test 2: Health endpoint
        print("\n2. Testing health endpoint...")
        try:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"   [OK] Status: {response.status_code}")
                print(f"   [OK] Service: {data.get('service')}")
                print(f"   [OK] Version: {data.get('version')}")
                
                # Check database health
                db_status = data.get('database', {}).get('status')
                if db_status == 'healthy':
                    print(f"   [OK] Database: {db_status}")
                    
                    # Show collection counts
                    collections = data.get('database', {}).get('collections', {})
                    if collections:
                        print(f"   [OK] Collections:")
                        for coll, count in collections.items():
                            if count != "error":
                                print(f"        - {coll}: {count} documents")
                else:
                    print(f"   [WARNING] Database: {db_status}")
                
                results["passed"] += 1
            else:
                print(f"   [FAIL] Status: {response.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"   [FAIL] Error: {str(e)}")
            results["failed"] += 1
        
        # Test 3: API docs
        print("\n3. Testing API documentation...")
        try:
            response = await client.get(f"{BASE_URL}/docs")
            if response.status_code == 200:
                print(f"   [OK] Swagger UI available at {BASE_URL}/docs")
                results["passed"] += 1
            else:
                print(f"   [FAIL] Status: {response.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"   [FAIL] Error: {str(e)}")
            results["failed"] += 1
        
        # Test 4: OpenAPI schema
        print("\n4. Testing OpenAPI schema...")
        try:
            response = await client.get(f"{BASE_URL}/openapi.json")
            if response.status_code == 200:
                schema = response.json()
                endpoints = len(schema.get('paths', {}))
                print(f"   [OK] Schema available")
                print(f"   [OK] API endpoints: {endpoints}")
                results["passed"] += 1
            else:
                print(f"   [FAIL] Status: {response.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"   [FAIL] Error: {str(e)}")
            results["failed"] += 1
        
        # Test 5: Auth endpoints exist
        print("\n5. Testing auth endpoints...")
        try:
            # Should return 307 redirect to Google
            response = await client.get(
                f"{BASE_URL}/api/auth/google/login",
                follow_redirects=False
            )
            if response.status_code in [302, 307]:
                location = response.headers.get('location', '')
                if 'accounts.google.com' in location:
                    print(f"   [OK] Google OAuth configured")
                    results["passed"] += 1
                else:
                    print(f"   [FAIL] Unexpected redirect: {location}")
                    results["failed"] += 1
            else:
                print(f"   [FAIL] Status: {response.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"   [FAIL] Error: {str(e)}")
            results["failed"] += 1
        
        # Test 6: Protected endpoint (should fail without auth)
        print("\n6. Testing protected endpoints...")
        try:
            response = await client.get(f"{BASE_URL}/api/auth/me")
            if response.status_code == 401:
                print(f"   [OK] Protected endpoint requires authentication")
                results["passed"] += 1
            else:
                print(f"   [FAIL] Status: {response.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"   [FAIL] Error: {str(e)}")
            results["failed"] += 1
        
        # Test 7: Payment plans endpoint (public)
        print("\n7. Testing payment plans endpoint...")
        try:
            response = await client.get(f"{BASE_URL}/api/payments/plans")
            if response.status_code == 200:
                data = response.json()
                plans = data.get('plans', [])
                print(f"   [OK] Found {len(plans)} subscription plans")
                for plan in plans:
                    print(f"        - {plan['name']}: N{plan['price_ngn']:,}")
                results["passed"] += 1
            else:
                print(f"   [FAIL] Status: {response.status_code}")
                results["failed"] += 1
        except Exception as e:
            print(f"   [FAIL] Error: {str(e)}")
            results["failed"] += 1
    
    # Summary
    total = results["passed"] + results["failed"]
    pass_rate = (results["passed"] / total * 100) if total > 0 else 0
    
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)
    print(f"\nPassed: {results['passed']}/{total}")
    print(f"Failed: {results['failed']}/{total}")
    print(f"Pass Rate: {pass_rate:.1f}%")
    
    if results["failed"] == 0:
        print("\n[OK] ALL TESTS PASSED! Server is fully operational.")
        print("\n" + "="*70)
        print(" NEXT STEPS:")
        print("="*70)
        print("\n1. Open browser: http://localhost:8000/docs")
        print("2. View API documentation and try endpoints")
        print("3. Run full test suite: python test_suite.py")
        print("4. Build your frontend to connect to this API\n")
        return 0
    else:
        print("\n[WARNING] Some tests failed.")
        print("\nServer is running but some features may not work correctly.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(test_server())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n[ERROR] Fatal error: {str(e)}")
        sys.exit(1)