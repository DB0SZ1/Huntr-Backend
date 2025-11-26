"""
Setup Admin User
Promotes an existing user to admin status
"""
import asyncio
from bson import ObjectId
from datetime import datetime

async def setup_admin():
    from app.database.connection import get_database
    
    db = await get_database()
    
    # Your admin email
    admin_email = "db0szempire@gmail.com"
    
    print("\n" + "="*70)
    print(" ADMIN USER SETUP")
    print("="*70 + "\n")
    
    # Find user
    user = await db.users.find_one({"email": admin_email})
    
    if not user:
        print(f"❌ User not found: {admin_email}")
        print("\nMake sure to log in first to create your account.")
        return
    
    user_id = str(user["_id"])
    print(f"✅ User found:")
    print(f"   Name: {user.get('name')}")
    print(f"   Email: {user.get('email')}")
    print(f"   ID: {user_id}")
    print(f"   Current admin: {user.get('settings', {}).get('is_admin', False)}\n")
    
    # Promote to admin
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "settings.is_admin": True,
                "promoted_at": datetime.utcnow(),
                "promoted_by": "system"
            }
        }
    )
    
    if result.modified_count > 0:
        print(f"✅ User promoted to admin!")
        print(f"\nYou can now:")
        print(f"   • Manage other users")
        print(f"   • View system statistics")
        print(f"   • Update user tiers")
        print(f"\nAdmin endpoints available at:")
        print(f"   GET  /api/admin/users")
        print(f"   POST /api/admin/promote-user")
        print(f"   PUT  /api/admin/users/{{user_id}}")
        print(f"   GET  /api/admin/stats")
    else:
        print(f"❌ Failed to promote user")
    
    print()

if __name__ == "__main__":
    asyncio.run(setup_admin())
