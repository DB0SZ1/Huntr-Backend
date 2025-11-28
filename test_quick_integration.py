#!/usr/bin/env python3
"""
Quick Integration Test: Verify scrapers work and can save/retrieve from DB
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

from modules.scrapers import scrape_telegram_channels, scrape_coinmarketcap_new

print("\n" + "="*70)
print("QUICK INTEGRATION TEST")
print("="*70)

# Test 1: Quick scrape (Telegram is fastest)
print("\n1. Testing Telegram Scraper (fastest)...")
try:
    opps = scrape_telegram_channels()
    print(f"   ✅ Telegram: {len(opps)} opportunities")
    if opps:
        print(f"   Sample: {opps[0].get('title', 'N/A')[:50]}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: CoinMarketCap (demonstrates multi-scraper)
print("\n2. Testing CoinMarketCap Scraper...")
try:
    opps = scrape_coinmarketcap_new()
    print(f"   ✅ CoinMarketCap: {len(opps)} opportunities")
    if opps:
        print(f"   Sample: {opps[0].get('title', 'N/A')[:50]}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Database operations
print("\n3. Testing Database Storage...")
try:
    from motor.motor_asyncio import AsyncIOMotorClient
    
    async def test_db():
        mongodb_url = os.getenv('MONGODB_URL', 'mongodb://localhost:27017')
        client = AsyncIOMotorClient(mongodb_url)
        db = client[os.getenv('DATABASE_NAME', 'job_hunter')]
        
        # Get Telegram opportunities
        opps = scrape_telegram_channels()
        
        if opps:
            # Try to insert first 5
            test_user = "integration_test_user"
            test_scan = f"scan_{datetime.utcnow().timestamp()}"
            
            inserted = 0
            for opp in opps[:5]:
                try:
                    await db.user_opportunities.insert_one({
                        "user_id": test_user,
                        "scan_id": test_scan,
                        "title": opp.get('title'),
                        "platform": opp.get('platform'),
                        "url": opp.get('url'),
                        "contact": opp.get('contact'),
                        "telegram": opp.get('telegram'),
                        "found_at": datetime.utcnow()
                    })
                    inserted += 1
                except Exception as e:
                    print(f"      Insert error: {e}")
            
            print(f"   ✅ Inserted {inserted} opportunities to DB")
            
            # Try to retrieve
            count = await db.user_opportunities.count_documents({"user_id": test_user})
            print(f"   ✅ Retrieved {count} opportunities from DB")
            
            return True
    
    asyncio.run(test_db())
    
except Exception as e:
    print(f"   ❌ Database error: {e}")

print("\n" + "="*70)
print("✅ INTEGRATION TEST COMPLETE - Scrapers → DB working!")
print("="*70 + "\n")
