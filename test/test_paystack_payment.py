"""
Test Paystack payment initialization
Complete flow: Create user -> Get token -> Initialize payment
"""
import asyncio
import httpx
from datetime import datetime
from bson import ObjectId

BASE_URL = "http://localhost:8000"
TIMEOUT = 120.0  # Increased from 30s to 120s for Paystack API calls

async def test_payment():
    print("\n" + "="*70)
    print(" PAYSTACK PAYMENT TEST")
    print("="*70 + "\n")
    
    try:
        # Step 1: Import and setup
        from app.auth.jwt_handler import create_access_token
        from app.database.connection import get_database
        from config import TIER_LIMITS
        
        print("Step 1: Connecting to database...")
        db = await get_database()
        print("  ✅ Database connected\n")
        
        # Step 2: Create or get test user
        print("Step 2: Creating/verifying test user in database...")
        
        test_email = "test@paystack-payment.local"
        test_user = await db.users.find_one({"email": test_email})
        
        if not test_user:
            print("  → User not found, creating new test user...")
            
            new_user = {
                "google_id": "test_google_id_paystack",
                "email": test_email,
                "name": "Paystack Test User",
                "profile_picture": None,
                "tier": "free",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "last_login": datetime.utcnow(),
                "settings": {
                    "notifications_enabled": True,
                    "email_notifications": True,
                    "whatsapp_notifications": False
                }
            }
            
            result = await db.users.insert_one(new_user)
            test_user_id = str(result.inserted_id)
            print(f"  ✅ User created: {test_user_id}\n")
            
            # Create free subscription
            await db.subscriptions.insert_one({
                "user_id": test_user_id,
                "tier": "free",
                "status": "active",
                "payment_method": None,
                "created_at": datetime.utcnow()
            })
            
            # Create usage tracking
            await db.usage_tracking.insert_one({
                "user_id": test_user_id,
                "month": datetime.utcnow().strftime("%Y-%m"),
                "opportunities_sent": 0,
                "scans_completed": 0
            })
        else:
            test_user_id = str(test_user['_id'])
            print(f"  ✅ Existing user found: {test_user_id}\n")
        
        # Step 3: Create access token
        print("Step 3: Generating access token...")
        mock_token = create_access_token(test_user_id)
        print(f"  ✅ Token generated")
        print(f"     Preview: {mock_token[:50]}...\n")
        
        headers = {
            "Authorization": f"Bearer {mock_token}",
            "Content-Type": "application/json"
        }
        
        # Step 4: Test payment initialization with extended timeout
        print("Step 4: Initializing Paystack payment...")
        print("  ⏳ Calling Paystack API (this may take up to 60 seconds)...\n")
        
        payload = {"tier": "pro"}
        
        # Use extended timeout for this call
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                response = await client.post(
                    f"{BASE_URL}/api/payments/initialize",
                    json=payload,
                    headers=headers
                )
                
                print(f"  ✅ Response received")
                print(f"  Status: {response.status_code}\n")
                
                data = response.json()
                
                if response.status_code == 200:
                    print(f"  ✅ SUCCESS! Payment initialized\n")
                    print(f"  Response:")
                    print(f"    - Authorization URL: {data.get('authorization_url', 'N/A')[:80]}...")
                    print(f"    - Reference: {data.get('reference', 'N/A')}")
                    print(f"    - Access Code: {data.get('access_code', 'N/A')}")
                    
                    print(f"\n  📊 Next Steps:")
                    print(f"    1. Visit the authorization URL in your browser")
                    print(f"    2. Complete payment on Paystack")
                    print(f"    3. You'll be redirected back with payment status")
                    
                    return True
                
                else:
                    print(f"  ❌ Error: {response.status_code}\n")
                    print(f"  Response:")
                    import json
                    print(json.dumps(data, indent=2))
                    
                    if response.status_code == 404:
                        print(f"\n  💡 Troubleshooting:")
                        print(f"    - User was just created, verify tier is 'free'")
                        print(f"    - Can only upgrade FROM 'free' TO 'pro' or 'premium'")
                    
                    elif response.status_code == 400:
                        print(f"\n  💡 Troubleshooting:")
                        print(f"    - Check if user is already on pro/premium tier")
                        print(f"    - Try different tier: 'pro' or 'premium'")
                    
                    elif response.status_code == 401:
                        print(f"\n  💡 Troubleshooting:")
                        print(f"    - Token may be invalid or expired")
                        print(f"    - User may be inactive")
                    
                    return False
            
            except httpx.TimeoutException:
                print(f"\n  ❌ REQUEST TIMEOUT\n")
                print(f"  The request took longer than {TIMEOUT} seconds.")
                print(f"\n  This could mean:")
                print(f"    1. Backend server is slow or unresponsive")
                print(f"    2. Network connection to Paystack is slow")
                print(f"    3. Paystack API is experiencing issues")
                print(f"\n  Troubleshooting:")
                print(f"    1. Check if backend is still running: python main.py")
                print(f"    2. Try again in a moment")
                print(f"    3. Check Paystack API status: https://status.paystack.com/")
                return False
            
            except httpx.ConnectError as e:
                print(f"\n  ❌ CONNECTION ERROR\n")
                print(f"  Could not connect to backend at {BASE_URL}")
                print(f"\n  Make sure:")
                print(f"    1. Backend is running: python main.py")
                print(f"    2. Backend is at {BASE_URL}")
                print(f"    3. No firewall blocking port 8000")
                return False
    
    except Exception as e:
        print(f"\n  ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_payment())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n\nFatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
