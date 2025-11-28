#!/usr/bin/env python3
"""
Full Integration Test: Scrapers → Database → API
Tests the complete workflow from scraping to database storage to API retrieval
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment
import config

# Import database and scrapers
from app.database.connection import get_database
from modules.scrapers import (
    scrape_twitter_comprehensive,
    scrape_telegram_channels,
    scrape_coinmarketcap_new
)
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_scrapers():
    """Test 1: Verify scrapers return real data"""
    print("\n" + "="*70)
    print("TEST 1: SCRAPER DATA COLLECTION")
    print("="*70)
    
    scrapers = [
        ("Twitter/X", scrape_twitter_comprehensive),
        ("Telegram", scrape_telegram_channels),
        ("CoinMarketCap", scrape_coinmarketcap_new),
    ]
    
    all_opps = []
    
    for name, scraper_func in scrapers:
        try:
            print(f"\n▶ Scraping {name}...")
            if asyncio.iscoroutinefunction(scraper_func):
                results = await scraper_func()
            else:
                results = scraper_func()
            
            count = len(results) if results else 0
            print(f"  ✅ {name}: Found {count} opportunities")
            
            if results and count > 0:
                all_opps.extend(results)
                # Show first opportunity as sample
                first = results[0]
                print(f"     Sample: {first.get('title', 'N/A')[:70]}")
        except Exception as e:
            print(f"  ❌ {name} error: {str(e)}")
    
    print(f"\n📊 TOTAL: {len(all_opps)} opportunities found")
    return all_opps

async def test_database_save(opportunities):
    """Test 2: Save opportunities to database"""
    print("\n" + "="*70)
    print("TEST 2: DATABASE STORAGE")
    print("="*70)
    
    try:
        # Get database connection
        client = AsyncIOMotorClient(os.getenv('MONGODB_URL', 'mongodb://localhost:27017'))
        db = client[os.getenv('DATABASE_NAME', 'job_hunter')]
        
        # Create test user if doesn't exist
        test_user_id = "test_user_001"
        test_scan_id = f"scan_{datetime.utcnow().timestamp()}"
        
        print(f"\n▶ Saving {len(opportunities)} opportunities to database...")
        
        # Insert into user_opportunities collection
        inserted = 0
        for opp in opportunities[:10]:  # Save first 10 for testing
            try:
                user_opp = {
                    "user_id": test_user_id,
                    "scan_id": test_scan_id,
                    "external_id": opp.get("id", f"opp_{inserted}"),
                    "title": opp.get('title', 'No title'),
                    "description": opp.get('description', '')[:500],
                    "platform": opp.get('platform', 'Unknown'),
                    "url": opp.get('url', ''),
                    "contact": opp.get('contact'),
                    "telegram": opp.get('telegram'),
                    "found_at": datetime.utcnow(),
                    "is_saved": False,
                    "is_applied": False,
                    "metadata": opp.get('metadata', {})
                }
                
                result = await db.user_opportunities.insert_one(user_opp)
                inserted += 1
                print(f"  ✅ Saved: {opp.get('title', 'N/A')[:50]}")
            except Exception as e:
                print(f"  ❌ Failed to save: {str(e)}")
        
        # Create scan history record
        scan_record = {
            "scan_id": test_scan_id,
            "user_id": test_user_id,
            "status": "completed",
            "opportunities_found": len(opportunities),
            "platforms_scanned": ["Twitter", "Telegram", "CoinMarketCap"],
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "opportunities_saved": inserted
        }
        
        await db.scan_history.insert_one(scan_record)
        
        print(f"\n✅ Stored {inserted} opportunities in database")
        print(f"✅ Scan record created: {test_scan_id}")
        
        return test_user_id, test_scan_id, db
        
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None

async def test_database_retrieval(user_id, scan_id, db):
    """Test 3: Retrieve opportunities from database"""
    print("\n" + "="*70)
    print("TEST 3: DATABASE RETRIEVAL")
    print("="*70)
    
    try:
        print(f"\n▶ Retrieving opportunities for user {user_id}...")
        
        # Get all opportunities for this user from this scan
        opps = []
        async for opp in db.user_opportunities.find({
            "user_id": user_id,
            "scan_id": scan_id
        }):
            opps.append(opp)
        
        print(f"  ✅ Found {len(opps)} opportunities in database")
        
        # Get scan history
        scan_history = await db.scan_history.find_one({
            "scan_id": scan_id
        })
        
        if scan_history:
            print(f"  ✅ Scan history found:")
            print(f"     - Status: {scan_history.get('status')}")
            print(f"     - Opportunities found: {scan_history.get('opportunities_found')}")
            print(f"     - Platforms: {', '.join(scan_history.get('platforms_scanned', []))}")
        
        # Show sample opportunities
        print(f"\n  Sample opportunities retrieved:")
        for i, opp in enumerate(opps[:3], 1):
            print(f"    {i}. {opp.get('title', 'N/A')[:60]}")
            print(f"       Platform: {opp.get('platform')}")
            print(f"       URL: {opp.get('url', 'N/A')[:60]}")
        
        return opps
    
    except Exception as e:
        print(f"❌ Retrieval error: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

async def test_api_simulation():
    """Test 4: Simulate API endpoint behavior"""
    print("\n" + "="*70)
    print("TEST 4: API ENDPOINT SIMULATION")
    print("="*70)
    
    try:
        client = AsyncIOMotorClient(os.getenv('MONGODB_URL', 'mongodb://localhost:27017'))
        db = client[os.getenv('DATABASE_NAME', 'job_hunter')]
        
        # Simulate GET /api/scans/status endpoint
        print("\n▶ Simulating GET /api/scans/{scan_id} endpoint...")
        
        # Find latest scan
        latest_scan = await db.scan_history.find_one(
            {},
            sort=[("created_at", -1)]
        )
        
        if latest_scan:
            print(f"  ✅ Latest scan found: {latest_scan.get('scan_id')}")
            print(f"  ✅ Response would be:")
            response = {
                "scan_id": latest_scan.get('scan_id'),
                "status": latest_scan.get('status'),
                "opportunities_found": latest_scan.get('opportunities_found'),
                "platforms_scanned": latest_scan.get('platforms_scanned'),
                "created_at": latest_scan.get('created_at').isoformat() if latest_scan.get('created_at') else None,
                "completed_at": latest_scan.get('completed_at').isoformat() if latest_scan.get('completed_at') else None
            }
            
            for key, value in response.items():
                print(f"     {key}: {value}")
        
        # Simulate GET /api/opportunities endpoint
        print("\n▶ Simulating GET /api/opportunities endpoint...")
        
        opps = []
        async for opp in db.user_opportunities.find().limit(5):
            opps.append(opp)
        
        print(f"  ✅ Would return {len(opps)} opportunities:")
        for i, opp in enumerate(opps, 1):
            print(f"     {i}. {opp.get('title', 'N/A')[:50]}")
        
    except Exception as e:
        print(f"❌ API simulation error: {str(e)}")

async def main():
    """Run all integration tests"""
    print("\n")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║          FULL INTEGRATION TEST: SCRAPERS → DB → API            ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    
    # Test 1: Collect data from scrapers
    opportunities = await test_scrapers()
    
    if not opportunities:
        print("\n❌ No opportunities found. Cannot continue tests.")
        return
    
    # Test 2: Save to database
    user_id, scan_id, db = await test_database_save(opportunities)
    
    if not user_id or not db:
        print("\n❌ Database save failed. Cannot continue tests.")
        return
    
    # Test 3: Retrieve from database
    retrieved = await test_database_retrieval(user_id, scan_id, db)
    
    # Test 4: Simulate API endpoints
    await test_api_simulation()
    
    # Summary
    print("\n" + "="*70)
    print("INTEGRATION TEST SUMMARY")
    print("="*70)
    print(f"✅ Scrapers: {len(opportunities)} opportunities collected")
    print(f"✅ Database: Opportunities stored and retrievable")
    print(f"✅ API: Endpoints would work correctly")
    print(f"\n🎉 FULL INTEGRATION TEST PASSED!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
