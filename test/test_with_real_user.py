"""
Test niche creation with a real user
"""
import asyncio
import requests
import json
from datetime import datetime
from app.auth.jwt_handler import create_access_token
from app.database.connection import get_database
from bson import ObjectId

async def main():
    # Step 1: Create a test user in database
    db = await get_database()
    
    test_user = {
        "google_id": "test_user_12345",
        "email": "testuser@example.com",
        "name": "Test User",
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
    
    result = await db.users.insert_one(test_user)
    user_id = str(result.inserted_id)
    
    print(f"✅ Created test user: {user_id}")
    print(f"   Email: {test_user['email']}")
    
    # Step 2: Generate token for this user
    token = create_access_token(user_id)
    print(f"\n✅ Generated JWT token")
    
    # Step 3: Test niche creation
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    payload = {
        "name": "Real User Test Niche",
        "keywords": ["react", "web3", "developer"],
        "platforms": ["Twitter/X", "Reddit"],
        "description": "Test niche with real user",
        "min_confidence": 70
    }
    
    print(f"\n🔄 Creating niche for user {user_id}...")
    
    response = requests.post(
        "http://localhost:8000/api/niches",
        json=payload,
        headers=headers,
        timeout=10
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 201:
        print(f"\n✅ SUCCESS! Niche created!")
        niche_data = response.json()
        print(f"   Niche ID: {niche_data['niche']['_id']}")
        print(f"   Name: {niche_data['niche']['name']}")
    else:
        print(f"\n❌ FAILED: {response.status_code}")
    
    # Cleanup
    await db.users.delete_one({"_id": ObjectId(user_id)})
    print(f"\n✅ Cleaned up test user")

if __name__ == "__main__":
    asyncio.run(main())
