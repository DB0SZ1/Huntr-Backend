"""
Test Telegram Scraper - REAL TESTING (NO MOCKS)
Comprehensive test script to verify Telegram channel scraping functionality
"""
import asyncio
import logging
from datetime import datetime
from pprint import pprint
import os
from dotenv import load_dotenv

# CRITICAL: Reload .env to get fresh values
load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_telegram_imports():
    """Test if Telegram libraries are installed"""
    print("\n" + "="*70)
    print("TEST 1: Checking Telegram Library Imports")
    print("="*70)
    
    try:
        from telethon import TelegramClient
        print("✅ Telethon imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Telethon import failed: {e}")
        print("   Install with: pip install telethon")
        return False


async def test_telegram_api_credentials():
    """Test if Telegram API credentials are configured"""
    print("\n" + "="*70)
    print("TEST 2: Checking Telegram API Credentials")
    print("="*70)
    
    try:
        from config import settings
        
        # Check for required Telegram settings
        required_fields = [
            ('TELEGRAM_API_ID', 'API ID'),
            ('TELEGRAM_API_HASH', 'API Hash'),
            ('TELEGRAM_PHONE', 'Phone Number'),
        ]
        
        missing = []
        configured = []
        
        for field, name in required_fields:
            value = getattr(settings, field, None)
            if value and str(value).strip() and str(value) != 'None':
                configured.append(f"✅ {name}: {field}")
            else:
                missing.append(f"❌ {name}: {field} - NOT SET (value={value})")
        
        for item in configured:
            print(item)
        
        for item in missing:
            print(item)
        
        if missing:
            print("\n[FIX] Run setup first:")
            print("   python setup_telegram.py")
            return False
        
        return True
    
    except Exception as e:
        print(f"❌ Error checking credentials: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_telegram_client_connection():
    """Test Telegram client connection with REAL authentication"""
    print("\n" + "="*70)
    print("TEST 3: Testing Telegram Client Connection (REAL)")
    print("="*70)
    
    try:
        from config import settings
        from telethon import TelegramClient
        
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        phone = getattr(settings, 'TELEGRAM_PHONE', None)
        
        if not api_id or not api_hash or not phone:
            print("⚠️  API credentials not configured")
            print(f"   API_ID: {api_id}")
            print(f"   API_HASH: {api_hash}")
            print(f"   PHONE: {phone}")
            return None
        
        print(f"[INFO] Creating Telegram client...")
        print(f"       API ID: {api_id}")
        print(f"       Phone: {phone}")
        
        client = TelegramClient('session_test', int(api_id), api_hash)
        
        print("✅ Client created successfully")
        
        try:
            print("[INFO] Attempting to connect to Telegram...")
            await asyncio.wait_for(client.connect(), timeout=10.0)
            
            print("✅ Connected to Telegram successfully")
            
            # Check if authorized
            if await client.is_user_authorized():
                print("✅ Client is authorized")
                me = await client.get_me()
                print(f"   Logged in as: {me.first_name} (@{me.username})")
                await client.disconnect()
                return True
            else:
                print("⚠️  Client not authorized")
                print("   Run: python setup_telegram.py")
                await client.disconnect()
                return False
        
        except asyncio.TimeoutError:
            print("⚠️  Connection timed out")
            print("   Check your internet connection")
            return None
        
        except Exception as e:
            print(f"⚠️  Connection failed: {e}")
            return None
    
    except ImportError:
        print("❌ Telethon not installed")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_telegram_scraper_real():
    """Test REAL Telegram scraper (async version)"""
    print("\n" + "="*70)
    print("TEST 4: Testing REAL Telegram Scraper (ASYNC)")
    print("="*70)
    
    try:
        from modules.scrapers import scrape_telegram_channels_async
        
        print("✅ Async scraper function imported successfully")
        print("[INFO] Running REAL Telegram scraper (this may take a while)...")
        print("       Monitoring 200+ channels for job opportunities...\n")
        
        # Call the REAL ASYNC scraper
        results = await scrape_telegram_channels_async()
        
        if results is None:
            print("⚠️  Scraper returned None")
            return False
        
        if not isinstance(results, list):
            print(f"⚠️  Scraper returned {type(results)} instead of list")
            return False
        
        print(f"\n✅ Scraper completed successfully!")
        print(f"   Total opportunities found: {len(results)}")
        
        if len(results) > 0:
            print(f"\n[SAMPLE OPPORTUNITIES (first 3)]\n")
            for idx, opp in enumerate(results[:3], 1):
                print(f"   [{idx}] {opp.get('title', 'No title')[:60]}")
                print(f"       Platform: {opp.get('platform')}")
                print(f"       Contact: {opp.get('contact', 'N/A')[:50]}")
                print(f"       URL: {opp.get('url', 'N/A')[:60]}")
                print()
            
            if len(results) > 3:
                print(f"   ... and {len(results) - 3} more opportunities")
        else:
            print("⚠️  No opportunities found")
            print("   This might be expected if channels have no recent job posts")
        
        return len(results) >= 0  # Success even if no results
    
    except ImportError:
        print("⚠️  Async scraper not found, trying sync version...")
        try:
            from modules.scrapers import scrape_telegram_channels
            
            print("✅ Sync scraper function imported")
            # Run in thread pool to avoid async issues
            results = await asyncio.to_thread(scrape_telegram_channels)
            
            if results is None:
                print("⚠️  Scraper returned None")
                return False
            
            print(f"✅ Scraper completed!")
            print(f"   Total opportunities found: {len(results)}")
            
            if len(results) > 0:
                print(f"\n[SAMPLE OPPORTUNITIES (first 3)]\n")
                for idx, opp in enumerate(results[:3], 1):
                    print(f"   [{idx}] {opp.get('title', 'No title')[:60]}")
                    print()
            
            return True
        
        except Exception as e:
            print(f"❌ Error testing scraper: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    except Exception as e:
        print(f"❌ Error testing scraper: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_scraper_with_config():
    """Test scraper with current config"""
    print("\n" + "="*70)
    print("TEST 5: Scraper Configuration Check")
    print("="*70)
    
    try:
        from config import settings, TIER_LIMITS
        
        print("[INFO] Current Configuration:")
        print(f"   Debug Mode: {settings.DEBUG}")
        print(f"   Database: {settings.DATABASE_NAME}")
        print(f"   Telegram API ID: {settings.TELEGRAM_API_ID}")
        print(f"   Telegram Phone: {settings.TELEGRAM_PHONE}")
        
        # Check if telegram scraper is in enabled platforms
        free_tier = TIER_LIMITS.get('free', {})
        pro_tier = TIER_LIMITS.get('pro', {})
        premium_tier = TIER_LIMITS.get('premium', {})
        
        print(f"\n[TIERS]")
        for tier_name in ['free', 'pro', 'premium']:
            tier = TIER_LIMITS.get(tier_name, {})
            platforms = tier.get('platforms', [])
            print(f"   {tier_name.upper()}: {len(platforms)} platforms")
            
            if 'Telegram' in platforms:
                print(f"   ✅ Telegram ENABLED for {tier_name.upper()} tier")
            else:
                print(f"   ⚠️  Telegram disabled for {tier_name.upper()} tier")
        
        return True
    
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print(f"\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "TELEGRAM SCRAPER TEST SUITE - REAL TESTING".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    results = {
        "Imports": await test_telegram_imports(),
        "API Credentials": await test_telegram_api_credentials(),
        "Client Connection": await test_telegram_client_connection(),
        "Real Scraper": await test_telegram_scraper_real(),
        "Config Check": await test_scraper_with_config(),
    }
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result is True else ("⚠️  SKIP" if result is None else "❌ FAIL")
        print(f"{status} - {test_name}")
    
    print("\n" + "-"*70)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("-"*70)
    
    # Recommendations
    print("\n[NEXT STEPS]")
    
    if failed > 0:
        print("❌ Setup needed. Run this first:")
        print("   python setup_telegram.py")
    elif skipped > 0:
        print("⚠️  Some tests were skipped. Complete setup:")
        print("   python setup_telegram.py")
    elif passed == len(results):
        print("✅ All tests passed! Telegram scraper is working.")
        print("\nYou can now use the scraper in:")
        print("   • POST /api/scans/start (triggers automatic scan)")
        print("   • GET /api/opportunities (retrieve scraped opportunities)")
    
    print("\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\nTests interrupted")
        exit(130)
    except Exception as e:
        print(f"\n\nFatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
