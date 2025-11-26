"""
Test tier update after payment
"""
import asyncio
from datetime import datetime
from bson import ObjectId

async def test_tier_update():
    from app.database.connection import get_database
    
    db = await get_database()
    
    # Find a test user
    user = await db.users.find_one({"email": "test@paystack-payment.local"})
    
    if not user:
        print("❌ Test user not found")
        return
    
    user_id = str(user['_id'])
    print(f"\n=== TIER UPDATE TEST ===\n")
    print(f"User: {user['email']}")
    print(f"ID: {user_id}\n")
    
    # Check current tier
    print(f"Current tier in users collection: {user['tier']}")
    
    # Check subscription
    sub = await db.subscriptions.find_one({"user_id": user_id})
    if sub:
        print(f"Subscription tier: {sub['tier']}")
        print(f"Subscription status: {sub['status']}")
        print(f"Period end: {sub.get('current_period_end')}")
    else:
        print("No subscription found")
    
    # Check payment transactions
    payments = await db.payment_transactions.find({
        "user_id": user_id
    }).sort("created_at", -1).limit(3).to_list(length=3)
    
    if payments:
        print(f"\nLast {len(payments)} payments:")
        for payment in payments:
            print(f"  - {payment['tier']}: {payment['status']} ({payment['created_at']})")
    
    print()

if __name__ == "__main__":
    asyncio.run(test_tier_update())
