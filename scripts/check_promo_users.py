"""
Check how many promo users are in database
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.job_hunter
    
    total = await db.promo_users.count_documents({})
    available = await db.promo_users.count_documents({"status": "available"})
    redeemed = await db.promo_users.count_documents({"status": "redeemed"})
    
    print(f"Total promo users:    {total}")
    print(f"Available:            {available}")
    print(f"Redeemed:             {redeemed}")
    
    # Show first 5
    users = await db.promo_users.find({}).limit(5).to_list(5)
    print(f"\nFirst 5 users:")
    for user in users:
        print(f"  - @{user['twitter_handle']} ({user['email']})")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check())
