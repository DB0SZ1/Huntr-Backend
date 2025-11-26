"""
Make a user admin by email
Usage: python make_admin.py your@email.com
"""
import asyncio
import sys
from bson import ObjectId
from datetime import datetime

async def make_admin(email: str):
    from app.database.connection import get_database
    
    db = await get_database()
    
    # Find user by email
    user = await db.users.find_one({"email": email})
    
    if not user:
        print(f"❌ User not found: {email}")
        return
    
    user_id = user["_id"]
    
    # Update to admin
    result = await db.users.update_one(
        {"_id": user_id},
        {"$set": {"is_admin": True}}
    )
    
    if result.modified_count > 0:
        print(f"✅ User {email} is now ADMIN")
        user = await db.users.find_one({"_id": user_id})
        print(f"   is_admin: {user.get('is_admin')}")
    else:
        print(f"❌ Failed to update user")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py your@email.com")
        sys.exit(1)
    
    email = sys.argv[1]
    print(f"Making {email} an admin...\n")
    asyncio.run(make_admin(email))
