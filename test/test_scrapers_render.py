"""
Test both Telegram and Reddit scrapers for Render compatibility
Ensures they work in production environment
"""
import asyncio
import sys
import os

# Load environment variables from .env FIRST
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.scrapers import (
    scrape_telegram_channels,
    scrape_reddit_jobs,
    scrape_telegram_channels_async
)
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_reddit_scraper():
    """Test Reddit scraper - SYNC function"""
    print("\n" + "="*60)
    print("[TEST] TESTING REDDIT SCRAPER")
    print("="*60)
    
    try:
        logger.info("Starting Reddit scraper test...")
        opportunities = scrape_reddit_jobs()
        
        print(f"\n[SUCCESS] Reddit Scraper worked!")
        print(f"   Found: {len(opportunities)} opportunities")
        
        if opportunities:
            print(f"\n   Sample opportunity:")
            opp = opportunities[0]
            print(f"   - Title: {opp.get('title', 'N/A')[:50]}...")
            print(f"   - Platform: {opp.get('platform', 'N/A')}")
            print(f"   - Contact: {opp.get('contact', 'N/A')[:50]}...")
        
        return True, len(opportunities)
    
    except Exception as e:
        print(f"\n[FAILED] Reddit Scraper FAILED")
        print(f"   Error: {str(e)}")
        logger.error(f"Reddit scraper error: {str(e)}", exc_info=True)
        return False, 0


def test_telegram_scraper_sync():
    """Test Telegram scraper - SYNC function directly"""
    print("\n" + "="*60)
    print("[TEST] TESTING TELEGRAM SCRAPER (SYNC)")
    print("="*60)
    
    try:
        logger.info("Starting Telegram scraper test (sync)...")
        opportunities = scrape_telegram_channels()
        
        print(f"\n[SUCCESS] Telegram Scraper (SYNC) worked!")
        print(f"   Found: {len(opportunities)} opportunities")
        
        if opportunities:
            print(f"\n   Sample opportunity:")
            opp = opportunities[0]
            print(f"   - Title: {opp.get('title', 'N/A')[:50]}...")
            print(f"   - Platform: {opp.get('platform', 'N/A')}")
            print(f"   - Contact: {opp.get('contact', 'N/A')[:50]}...")
        
        return True, len(opportunities)
    
    except Exception as e:
        print(f"\n[FAILED] Telegram Scraper (SYNC) FAILED")
        print(f"   Error: {str(e)}")
        logger.error(f"Telegram scraper sync error: {str(e)}", exc_info=True)
        return False, 0


async def test_telegram_scraper_in_thread():
    """Test Telegram scraper running in asyncio.to_thread() - like Render does"""
    print("\n" + "="*60)
    print("[TEST] TESTING TELEGRAM SCRAPER (IN THREAD - LIKE RENDER)")
    print("="*60)
    
    try:
        logger.info("Starting Telegram scraper test (in asyncio.to_thread)...")
        
        # This simulates how the scraper is called in production on Render
        opportunities = await asyncio.to_thread(scrape_telegram_channels)
        
        print(f"\n[SUCCESS] Telegram Scraper (IN THREAD) worked!")
        print(f"   Found: {len(opportunities)} opportunities")
        
        if opportunities:
            print(f"\n   Sample opportunity:")
            opp = opportunities[0]
            print(f"   - Title: {opp.get('title', 'N/A')[:50]}...")
            print(f"   - Platform: {opp.get('platform', 'N/A')}")
            print(f"   - Contact: {opp.get('contact', 'N/A')[:50]}...")
        
        return True, len(opportunities)
    
    except Exception as e:
        print(f"\n[FAILED] Telegram Scraper (IN THREAD) FAILED")
        print(f"   Error: {str(e)}")
        logger.error(f"Telegram scraper in thread error: {str(e)}", exc_info=True)
        return False, 0


async def test_telegram_scraper_async_wrapper():
    """Test Telegram async wrapper"""
    print("\n" + "="*60)
    print("[TEST] TESTING TELEGRAM ASYNC WRAPPER")
    print("="*60)
    
    try:
        logger.info("Starting Telegram async wrapper test...")
        
        # This simulates how the wrapper is called
        opportunities = await asyncio.to_thread(scrape_telegram_channels_async)
        
        print(f"\n[SUCCESS] Telegram Async Wrapper worked!")
        print(f"   Found: {len(opportunities)} opportunities")
        
        if opportunities:
            print(f"\n   Sample opportunity:")
            opp = opportunities[0]
            print(f"   - Title: {opp.get('title', 'N/A')[:50]}...")
            print(f"   - Platform: {opp.get('platform', 'N/A')}")
            print(f"   - Contact: {opp.get('contact', 'N/A')[:50]}...")
        
        return True, len(opportunities)
    
    except Exception as e:
        print(f"\n[FAILED] Telegram Async Wrapper FAILED")
        print(f"   Error: {str(e)}")
        logger.error(f"Telegram async wrapper error: {str(e)}", exc_info=True)
        return False, 0


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("RENDER SCRAPER COMPATIBILITY TESTS")
    print("="*60)
    print("\nThis tests both scrapers in the same way Render would call them")
    print("Environment variables check:")
    print(f"  - TELEGRAM_API_ID: {'SET' if os.getenv('TELEGRAM_API_ID') else 'NOT SET'}")
    print(f"  - TELEGRAM_API_HASH: {'SET' if os.getenv('TELEGRAM_API_HASH') else 'NOT SET'}")
    
    results = []
    
    # Test Reddit (sync)
    success, count = test_reddit_scraper()
    results.append(("Reddit", success, count))
    
    # Test Telegram sync directly
    success, count = test_telegram_scraper_sync()
    results.append(("Telegram (Sync)", success, count))
    
    # Test Telegram in thread (like Render)
    success, count = await test_telegram_scraper_in_thread()
    results.append(("Telegram (In Thread)", success, count))
    
    # Test Telegram async wrapper
    success, count = await test_telegram_scraper_async_wrapper()
    results.append(("Telegram (Async Wrapper)", success, count))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for scraper, success, count in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} - {scraper}: {count} opportunities found")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED! Ready for Render deployment")
    else:
        print("SOME TESTS FAILED - Check logs above")
    print("="*60 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
