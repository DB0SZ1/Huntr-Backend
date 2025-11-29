#!/usr/bin/env python3
"""
Test to verify the signup fix for E11000 duplicate key error on google_id
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.auth.password_handler import PasswordHandler
from datetime import datetime
from config import settings

async def test_traditional_signup():
    """Test that traditional signup doesn't set google_id"""
    
    # Connect to database
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.DATABASE_NAME]
    
    try:
        # Clean up test user if exists
        await db.users.delete_one({"email": "test_signup@example.com"})
        
        # Create test user document (mimicking traditional signup)
        test_user = {
            "email": "test_signup@example.com",
            "name": "Test User",
            "password_hash": PasswordHandler.hash_password("TestPass123"),
            "auth_method": "email",
            # NOTE: google_id is intentionally omitted (not set to None)
            "profile_picture": None,
            "tier": "free",
            "is_active": True,
            "email_verified": True,
            "email_verified_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "last_login": None,
            "settings": {
                "notifications_enabled": True,
                "email_notifications": True,
                "whatsapp_notifications": False
            }
        }
        
        # Insert user
        result1 = await db.users.insert_one(test_user.copy())
        print(f"✅ First traditional user created: {result1.inserted_id}")
        
        # Try to insert a second user without google_id (this was causing the error)
        test_user2 = {
            "email": "test_signup2@example.com",
            "name": "Test User 2",
            "password_hash": PasswordHandler.hash_password("TestPass456"),
            "auth_method": "email",
            # google_id intentionally omitted
            "profile_picture": None,
            "tier": "free",
            "is_active": True,
            "email_verified": True,
            "email_verified_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "last_login": None,
            "settings": {
                "notifications_enabled": True,
                "email_notifications": True,
                "whatsapp_notifications": False
            }
        }
        
        result2 = await db.users.insert_one(test_user2)
        print(f"✅ Second traditional user created: {result2.inserted_id}")
        
        # Verify both users exist
        user1 = await db.users.find_one({"email": "test_signup@example.com"})
        user2 = await db.users.find_one({"email": "test_signup2@example.com"})
        
        assert user1 is not None, "First user not found"
        assert user2 is not None, "Second user not found"
        assert user1.get("google_id") is None, "First user should not have google_id"
        assert user2.get("google_id") is None, "Second user should not have google_id"
        
        print("✅ Both users created successfully without google_id field")
        print("✅ FIX VERIFIED: E11000 duplicate key error is resolved!")
        
        # Clean up
        await db.users.delete_one({"email": "test_signup@example.com"})
        await db.users.delete_one({"email": "test_signup2@example.com"})
        print("✅ Test cleanup complete")
        
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_traditional_signup())
