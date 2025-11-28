"""
COMPREHENSIVE TEST SCRIPT FOR SCRAPERS.PY
Tests all scraping modules: Twitter, Telegram, Pump.fun, CoinMarketCap, DexScreener, CoinGecko, Web3.career
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# CRITICAL: Load .env file before importing scrapers
import config  # This loads .env automatically

from modules.scrapers import (
    scrape_twitter_comprehensive,
    scrape_telegram_channels,
    scrape_pumpfun,
    scrape_coinmarketcap_new,
    scrape_dexscreener_enhanced,
    scrape_coingecko_new,
    scrape_web3_jobs,
    extract_telegram,
    extract_email
)

# ============================================================================
# COLORS FOR TERMINAL OUTPUT
# ============================================================================

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_section(title: str):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title:^80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.ENDC}\n")

def print_test(name: str):
    """Print test name"""
    print(f"{Colors.CYAN}▶ {name}{Colors.ENDC}")

def print_pass(msg: str):
    """Print success message"""
    print(f"  {Colors.GREEN}✅ {msg}{Colors.ENDC}")

def print_fail(msg: str):
    """Print failure message"""
    print(f"  {Colors.RED}❌ {msg}{Colors.ENDC}")

def print_warn(msg: str):
    """Print warning message"""
    print(f"  {Colors.YELLOW}⚠️  {msg}{Colors.ENDC}")

def print_info(msg: str):
    """Print info message"""
    print(f"  {Colors.CYAN}ℹ️  {msg}{Colors.ENDC}")

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_tests.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# HELPER VALIDATION FUNCTIONS
# ============================================================================

def validate_opportunity(opp: Dict[str, Any], scraper_name: str) -> tuple[bool, List[str]]:
    """
    Validate that an opportunity has required fields
    Returns: (is_valid, list_of_errors)
    """
    errors = []
    required_fields = ['title', 'description', 'platform', 'url', 'contact']
    
    for field in required_fields:
        if field not in opp:
            errors.append(f"Missing field: {field}")
        elif not opp[field]:
            errors.append(f"Empty field: {field}")
    
    # Validate field types
    if not isinstance(opp.get('title'), str):
        errors.append("Title must be string")
    if not isinstance(opp.get('description'), str):
        errors.append("Description must be string")
    if not isinstance(opp.get('platform'), str):
        errors.append("Platform must be string")
    if not isinstance(opp.get('url'), str):
        errors.append("URL must be string")
    if not isinstance(opp.get('contact'), str):
        errors.append("Contact must be string")
    
    # Validate URL format
    if opp.get('url') and not (opp['url'].startswith('http://') or opp['url'].startswith('https://')):
        errors.append(f"Invalid URL format: {opp['url']}")
    
    # Platform-specific validations
    if opp.get('platform') == 'Twitter/X':
        if 'twitter' not in opp:
            errors.append("Twitter platform missing 'twitter' field")
    
    if opp.get('platform') == 'Telegram':
        if 'telegram' not in opp:
            errors.append("Telegram platform missing 'telegram' field")
    
    return len(errors) == 0, errors

def print_opportunity(opp: Dict[str, Any], idx: int):
    """Pretty print an opportunity"""
    print(f"\n  {Colors.YELLOW}Opportunity #{idx}{Colors.ENDC}")
    print(f"    Title: {opp.get('title', 'N/A')[:70]}...")
    print(f"    Platform: {opp.get('platform', 'N/A')}")
    print(f"    URL: {opp.get('url', 'N/A')[:60]}...")
    print(f"    Contact: {opp.get('contact', 'N/A')[:60]}...")
    if opp.get('metadata'):
        print(f"    Metadata: {str(opp['metadata'])[:60]}...")

# ============================================================================
# TEST 1: TWITTER SCRAPER
# ============================================================================

def test_twitter_scraper():
    """Test Twitter/X scraper"""
    print_section("TEST 1: TWITTER/X SCRAPER")
    print_test("Scraping Twitter/X for opportunities...")
    
    try:
        opportunities = scrape_twitter_comprehensive()
        
        if not opportunities:
            print_warn("No opportunities found (API may not be configured)")
            return {"name": "Twitter", "status": "skipped", "reason": "No results", "count": 0}
        
        print_pass(f"Found {len(opportunities)} opportunities")
        
        # Validate each opportunity
        valid_count = 0
        invalid_count = 0
        
        for idx, opp in enumerate(opportunities[:5], 1):
            is_valid, errors = validate_opportunity(opp, "Twitter")
            
            if is_valid:
                valid_count += 1
                print_info(f"Opportunity #{idx}: ✓ Valid")
                if idx <= 3:
                    print_opportunity(opp, idx)
            else:
                invalid_count += 1
                print_fail(f"Opportunity #{idx}: Invalid")
                for error in errors:
                    print_info(f"  - {error}")
        
        # Check platform field
        if all(opp.get('platform') == 'Twitter/X' for opp in opportunities):
            print_pass("All opportunities have platform='Twitter/X'")
        else:
            print_warn("Some opportunities have incorrect platform field")
        
        print_info(f"Summary: {valid_count} valid, {invalid_count} invalid out of {len(opportunities)} total")
        
        return {
            "name": "Twitter",
            "status": "passed" if valid_count > 0 else "failed",
            "count": len(opportunities),
            "valid": valid_count,
            "invalid": invalid_count
        }
    
    except Exception as e:
        print_fail(f"Twitter scraper error: {str(e)}")
        logger.error(f"Twitter scraper error: {str(e)}", exc_info=True)
        return {"name": "Twitter", "status": "error", "error": str(e), "count": 0}

# ============================================================================
# TEST 2: TELEGRAM SCRAPER
# ============================================================================

def test_telegram_scraper():
    """Test Telegram scraper"""
    print_section("TEST 2: TELEGRAM SCRAPER")
    print_test("Scraping Telegram channels for opportunities...")
    
    try:
        opportunities = scrape_telegram_channels()
        
        if not opportunities:
            print_warn("No opportunities found (API may not be configured)")
            return {"name": "Telegram", "status": "skipped", "reason": "No results", "count": 0}
        
        print_pass(f"Found {len(opportunities)} opportunities")
        
        # Validate each opportunity
        valid_count = 0
        invalid_count = 0
        
        for idx, opp in enumerate(opportunities[:5], 1):
            is_valid, errors = validate_opportunity(opp, "Telegram")
            
            if is_valid:
                valid_count += 1
                print_info(f"Opportunity #{idx}: ✓ Valid")
                if idx <= 3:
                    print_opportunity(opp, idx)
            else:
                invalid_count += 1
                print_fail(f"Opportunity #{idx}: Invalid")
                for error in errors:
                    print_info(f"  - {error}")
        
        # Check for Telegram-specific fields
        has_telegram_field = all('telegram' in opp for opp in opportunities)
        if has_telegram_field:
            print_pass("All opportunities have 'telegram' field")
        else:
            print_warn("Some opportunities missing 'telegram' field")
        
        # Check for channel information in metadata
        has_metadata = all(opp.get('metadata', {}).get('channel') for opp in opportunities)
        if has_metadata:
            print_pass("All opportunities have channel in metadata")
        else:
            print_warn("Some opportunities missing channel in metadata")
        
        print_info(f"Summary: {valid_count} valid, {invalid_count} invalid out of {len(opportunities)} total")
        
        return {
            "name": "Telegram",
            "status": "passed" if valid_count > 0 else "failed",
            "count": len(opportunities),
            "valid": valid_count,
            "invalid": invalid_count
        }
    
    except Exception as e:
        print_fail(f"Telegram scraper error: {str(e)}")
        logger.error(f"Telegram scraper error: {str(e)}", exc_info=True)
        return {"name": "Telegram", "status": "error", "error": str(e), "count": 0}

# ============================================================================
# TEST 3: PUMP.FUN SCRAPER
# ============================================================================

def test_pumpfun_scraper():
    """Test Pump.fun scraper"""
    print_section("TEST 3: PUMP.FUN SCRAPER")
    print_test("Scraping Pump.fun for new token opportunities...")
    
    try:
        opportunities = scrape_pumpfun()
        
        if not opportunities:
            print_warn("No opportunities found (API may not be available)")
            return {"name": "Pump.fun", "status": "skipped", "reason": "No results", "count": 0}
        
        print_pass(f"Found {len(opportunities)} opportunities")
        
        # Validate each opportunity
        valid_count = 0
        invalid_count = 0
        
        for idx, opp in enumerate(opportunities[:5], 1):
            is_valid, errors = validate_opportunity(opp, "Pump.fun")
            
            if is_valid:
                valid_count += 1
                print_info(f"Opportunity #{idx}: ✓ Valid")
                if idx <= 3:
                    print_opportunity(opp, idx)
            else:
                invalid_count += 1
                print_fail(f"Opportunity #{idx}: Invalid")
                for error in errors:
                    print_info(f"  - {error}")
        
        # Check platform field
        if all(opp.get('platform') == 'Pump.fun' for opp in opportunities):
            print_pass("All opportunities have platform='Pump.fun'")
        else:
            print_warn("Some opportunities have incorrect platform field")
        
        # Check for market cap in metadata
        has_market_cap = all(opp.get('metadata', {}).get('market_cap') is not None for opp in opportunities)
        if has_market_cap:
            print_pass("All opportunities have market_cap in metadata")
        else:
            print_warn("Some opportunities missing market_cap in metadata")
        
        # Check age_hours
        has_age = all(opp.get('metadata', {}).get('age_hours') is not None for opp in opportunities)
        if has_age:
            print_pass("All opportunities have age_hours in metadata")
        else:
            print_warn("Some opportunities missing age_hours in metadata")
        
        print_info(f"Summary: {valid_count} valid, {invalid_count} invalid out of {len(opportunities)} total")
        
        return {
            "name": "Pump.fun",
            "status": "passed" if valid_count > 0 else "failed",
            "count": len(opportunities),
            "valid": valid_count,
            "invalid": invalid_count
        }
    
    except Exception as e:
        print_fail(f"Pump.fun scraper error: {str(e)}")
        logger.error(f"Pump.fun scraper error: {str(e)}", exc_info=True)
        return {"name": "Pump.fun", "status": "error", "error": str(e), "count": 0}

# ============================================================================
# TEST 4: COINMARKETCAP SCRAPER
# ============================================================================

def test_coinmarketcap_scraper():
    """Test CoinMarketCap scraper"""
    print_section("TEST 4: COINMARKETCAP SCRAPER")
    print_test("Scraping CoinMarketCap for new listings...")
    
    try:
        opportunities = scrape_coinmarketcap_new()
        
        if not opportunities:
            print_warn("No opportunities found (API may not be configured)")
            return {"name": "CoinMarketCap", "status": "skipped", "reason": "No results", "count": 0}
        
        print_pass(f"Found {len(opportunities)} opportunities")
        
        # Validate each opportunity
        valid_count = 0
        invalid_count = 0
        
        for idx, opp in enumerate(opportunities[:5], 1):
            is_valid, errors = validate_opportunity(opp, "CoinMarketCap")
            
            if is_valid:
                valid_count += 1
                print_info(f"Opportunity #{idx}: ✓ Valid")
                if idx <= 3:
                    print_opportunity(opp, idx)
            else:
                invalid_count += 1
                print_fail(f"Opportunity #{idx}: Invalid")
                for error in errors:
                    print_info(f"  - {error}")
        
        # Check platform field
        if all(opp.get('platform') == 'CoinMarketCap' for opp in opportunities):
            print_pass("All opportunities have platform='CoinMarketCap'")
        else:
            print_warn("Some opportunities have incorrect platform field")
        
        # Check for CMC rank in metadata
        has_rank = all(opp.get('metadata', {}).get('rank') is not None for opp in opportunities)
        if has_rank:
            print_pass("All opportunities have rank in metadata")
        else:
            print_warn("Some opportunities missing rank in metadata")
        
        print_info(f"Summary: {valid_count} valid, {invalid_count} invalid out of {len(opportunities)} total")
        
        return {
            "name": "CoinMarketCap",
            "status": "passed" if valid_count > 0 else "failed",
            "count": len(opportunities),
            "valid": valid_count,
            "invalid": invalid_count
        }
    
    except Exception as e:
        print_fail(f"CoinMarketCap scraper error: {str(e)}")
        logger.error(f"CoinMarketCap scraper error: {str(e)}", exc_info=True)
        return {"name": "CoinMarketCap", "status": "error", "error": str(e), "count": 0}

# ============================================================================
# TEST 5: DEXSCREENER SCRAPER
# ============================================================================

def test_dexscreener_scraper():
    """Test DexScreener scraper"""
    print_section("TEST 5: DEXSCREENER SCRAPER")
    print_test("Scraping DexScreener for new trading pairs...")
    
    try:
        opportunities = scrape_dexscreener_enhanced()
        
        if not opportunities:
            print_warn("No opportunities found (API may not be available)")
            return {"name": "DexScreener", "status": "skipped", "reason": "No results", "count": 0}
        
        print_pass(f"Found {len(opportunities)} opportunities")
        
        # Validate each opportunity
        valid_count = 0
        invalid_count = 0
        
        for idx, opp in enumerate(opportunities[:5], 1):
            is_valid, errors = validate_opportunity(opp, "DexScreener")
            
            if is_valid:
                valid_count += 1
                print_info(f"Opportunity #{idx}: ✓ Valid")
                if idx <= 3:
                    print_opportunity(opp, idx)
            else:
                invalid_count += 1
                print_fail(f"Opportunity #{idx}: Invalid")
                for error in errors:
                    print_info(f"  - {error}")
        
        # Check platform field
        if all(opp.get('platform') == 'DexScreener' for opp in opportunities):
            print_pass("All opportunities have platform='DexScreener'")
        else:
            print_warn("Some opportunities have incorrect platform field")
        
        # Check for liquidity in metadata
        has_liquidity = all(opp.get('metadata', {}).get('liquidity') is not None for opp in opportunities)
        if has_liquidity:
            print_pass("All opportunities have liquidity in metadata")
        else:
            print_warn("Some opportunities missing liquidity in metadata")
        
        # Check for chain info
        has_chain = all(opp.get('metadata', {}).get('chain') for opp in opportunities)
        if has_chain:
            print_pass("All opportunities have chain info in metadata")
        else:
            print_warn("Some opportunities missing chain info in metadata")
        
        print_info(f"Summary: {valid_count} valid, {invalid_count} invalid out of {len(opportunities)} total")
        
        return {
            "name": "DexScreener",
            "status": "passed" if valid_count > 0 else "failed",
            "count": len(opportunities),
            "valid": valid_count,
            "invalid": invalid_count
        }
    
    except Exception as e:
        print_fail(f"DexScreener scraper error: {str(e)}")
        logger.error(f"DexScreener scraper error: {str(e)}", exc_info=True)
        return {"name": "DexScreener", "status": "error", "error": str(e), "count": 0}

# ============================================================================
# TEST 6: COINGECKO SCRAPER
# ============================================================================

def test_coingecko_scraper():
    """Test CoinGecko scraper"""
    print_section("TEST 6: COINGECKO SCRAPER")
    print_test("Scraping CoinGecko for new coins...")
    
    try:
        opportunities = scrape_coingecko_new()
        
        if not opportunities:
            print_warn("No opportunities found (API may not be available)")
            return {"name": "CoinGecko", "status": "skipped", "reason": "No results", "count": 0}
        
        print_pass(f"Found {len(opportunities)} opportunities")
        
        # Validate each opportunity
        valid_count = 0
        invalid_count = 0
        
        for idx, opp in enumerate(opportunities[:5], 1):
            is_valid, errors = validate_opportunity(opp, "CoinGecko")
            
            if is_valid:
                valid_count += 1
                print_info(f"Opportunity #{idx}: ✓ Valid")
                if idx <= 3:
                    print_opportunity(opp, idx)
            else:
                invalid_count += 1
                print_fail(f"Opportunity #{idx}: Invalid")
                for error in errors:
                    print_info(f"  - {error}")
        
        # Check platform field
        if all(opp.get('platform') == 'CoinGecko' for opp in opportunities):
            print_pass("All opportunities have platform='CoinGecko'")
        else:
            print_warn("Some opportunities have incorrect platform field")
        
        # Check for age_days in metadata
        has_age = all(opp.get('metadata', {}).get('age_days') is not None for opp in opportunities)
        if has_age:
            print_pass("All opportunities have age_days in metadata")
        else:
            print_warn("Some opportunities missing age_days in metadata")
        
        print_info(f"Summary: {valid_count} valid, {invalid_count} invalid out of {len(opportunities)} total")
        
        return {
            "name": "CoinGecko",
            "status": "passed" if valid_count > 0 else "failed",
            "count": len(opportunities),
            "valid": valid_count,
            "invalid": invalid_count
        }
    
    except Exception as e:
        print_fail(f"CoinGecko scraper error: {str(e)}")
        logger.error(f"CoinGecko scraper error: {str(e)}", exc_info=True)
        return {"name": "CoinGecko", "status": "error", "error": str(e), "count": 0}

# ============================================================================
# TEST 7: WEB3.CAREER SCRAPER
# ============================================================================

def test_web3_jobs_scraper():
    """Test Web3.career scraper"""
    print_section("TEST 7: WEB3.CAREER SCRAPER")
    print_test("Scraping Web3.career for job opportunities...")
    
    try:
        opportunities = scrape_web3_jobs()
        
        if not opportunities:
            print_warn("No opportunities found (API may not be available)")
            return {"name": "Web3.career", "status": "skipped", "reason": "No results", "count": 0}
        
        print_pass(f"Found {len(opportunities)} opportunities")
        
        # Validate each opportunity
        valid_count = 0
        invalid_count = 0
        
        for idx, opp in enumerate(opportunities[:5], 1):
            is_valid, errors = validate_opportunity(opp, "Web3.career")
            
            if is_valid:
                valid_count += 1
                print_info(f"Opportunity #{idx}: ✓ Valid")
                if idx <= 3:
                    print_opportunity(opp, idx)
            else:
                invalid_count += 1
                print_fail(f"Opportunity #{idx}: Invalid")
                for error in errors:
                    print_info(f"  - {error}")
        
        # Check platform field
        if all(opp.get('platform') == 'Web3.career' for opp in opportunities):
            print_pass("All opportunities have platform='Web3.career'")
        else:
            print_warn("Some opportunities have incorrect platform field")
        
        # Check for company info in metadata
        has_company = all(opp.get('metadata', {}).get('company') for opp in opportunities)
        if has_company:
            print_pass("All opportunities have company info in metadata")
        else:
            print_warn("Some opportunities missing company info in metadata")
        
        print_info(f"Summary: {valid_count} valid, {invalid_count} invalid out of {len(opportunities)} total")
        
        return {
            "name": "Web3.career",
            "status": "passed" if valid_count > 0 else "failed",
            "count": len(opportunities),
            "valid": valid_count,
            "invalid": invalid_count
        }
    
    except Exception as e:
        print_fail(f"Web3.career scraper error: {str(e)}")
        logger.error(f"Web3.career scraper error: {str(e)}", exc_info=True)
        return {"name": "Web3.career", "status": "error", "error": str(e), "count": 0}

# ============================================================================
# TEST 8: HELPER FUNCTIONS
# ============================================================================

def test_helper_functions():
    """Test helper functions like extract_telegram, extract_email"""
    print_section("TEST 8: HELPER FUNCTIONS")
    
    results = {"passed": 0, "failed": 0}
    
    # Test extract_telegram
    print_test("Testing extract_telegram()...")
    
    test_cases = [
        ("Check my telegram t.me/myusername", "https://t.me/myusername"),
        ("Contact: @myusername (telegram)", "https://t.me/myusername"),
        ("TG: @crypto_jobs", "https://t.me/crypto_jobs"),
        ("telegram: web3_developer", "https://t.me/web3_developer"),
        ("no telegram here", None),
    ]
    
    for text, expected in test_cases:
        result = extract_telegram(text, "")
        if result == expected:
            print_pass(f"✓ extract_telegram('{text[:40]}...') = {result}")
            results["passed"] += 1
        else:
            print_fail(f"✗ extract_telegram('{text[:40]}...') = {result}, expected {expected}")
            results["failed"] += 1
    
    # Test extract_email
    print_test("Testing extract_email()...")
    
    email_test_cases = [
        ("Contact me at john@example.com", "john@example.com"),
        ("Email: support@web3.career for info", "support@web3.career"),
        ("no email here", None),
        ("multiple@emails.com and test@test.org", "multiple@emails.com"),
    ]
    
    for text, expected in email_test_cases:
        result = extract_email(text)
        if result == expected:
            print_pass(f"✓ extract_email('{text[:40]}...') = {result}")
            results["passed"] += 1
        else:
            print_fail(f"✗ extract_email('{text[:40]}...') = {result}, expected {expected}")
            results["failed"] += 1
    
    print_info(f"Helper functions: {results['passed']} passed, {results['failed']} failed")
    
    return {
        "name": "Helper Functions",
        "status": "passed" if results["failed"] == 0 else "failed",
        "passed": results["passed"],
        "failed": results["failed"]
    }

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all scraper tests"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "COMPREHENSIVE SCRAPER TEST SUITE - 8 TESTS" + " " * 22 + "║")
    print("║" + " " * 20 + f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " " * 32 + "║")
    print("╚" + "=" * 78 + "╝")
    print(f"{Colors.ENDC}")
    
    results = []
    
    # Run all tests
    results.append(test_twitter_scraper())
    results.append(test_telegram_scraper())
    results.append(test_pumpfun_scraper())
    results.append(test_coinmarketcap_scraper())
    results.append(test_dexscreener_scraper())
    results.append(test_coingecko_scraper())
    results.append(test_web3_jobs_scraper())
    results.append(test_helper_functions())
    
    # Print summary
    print_section("TEST SUMMARY")
    
    print(f"{Colors.BOLD}Results by Scraper:{Colors.ENDC}")
    print(f"{'Scraper':<20} {'Status':<12} {'Count':<8} {'Valid':<8} {'Invalid':<8}")
    print("─" * 60)
    
    total_opportunities = 0
    total_valid = 0
    total_invalid = 0
    passed_tests = 0
    failed_tests = 0
    skipped_tests = 0
    error_tests = 0
    
    for result in results:
        status = result.get("status", "unknown")
        count = result.get("count", 0)
        valid = result.get("valid", 0)
        invalid = result.get("invalid", 0)
        
        status_color = {
            "passed": Colors.GREEN,
            "failed": Colors.RED,
            "error": Colors.RED,
            "skipped": Colors.YELLOW
        }.get(status, Colors.CYAN)
        
        print(f"{result['name']:<20} {status_color}{status:<12}{Colors.ENDC} {count:<8} {valid:<8} {invalid:<8}")
        
        total_opportunities += count
        total_valid += valid
        total_invalid += invalid
        
        if status == "passed":
            passed_tests += 1
        elif status == "failed":
            failed_tests += 1
        elif status == "error":
            error_tests += 1
        elif status == "skipped":
            skipped_tests += 1
    
    print("─" * 60)
    print(f"{'TOTAL':<20} {'':<12} {total_opportunities:<8} {total_valid:<8} {total_invalid:<8}")
    
    # Print detailed summary
    print(f"\n{Colors.BOLD}Test Execution Summary:{Colors.ENDC}")
    print(f"  {Colors.GREEN}✅ Passed: {passed_tests}{Colors.ENDC}")
    print(f"  {Colors.RED}❌ Failed: {failed_tests}{Colors.ENDC}")
    print(f"  {Colors.RED}⚠️  Errors: {error_tests}{Colors.ENDC}")
    print(f"  {Colors.YELLOW}⊘ Skipped: {skipped_tests}{Colors.ENDC}")
    print(f"\n  {Colors.CYAN}Total Opportunities Found: {total_opportunities}{Colors.ENDC}")
    print(f"  {Colors.GREEN}Valid Opportunities: {total_valid}{Colors.ENDC}")
    print(f"  {Colors.RED}Invalid Opportunities: {total_invalid}{Colors.ENDC}")
    
    # Final status
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    if failed_tests == 0 and error_tests == 0:
        print("╔" + "=" * 78 + "╗")
        print("║" + " " * 25 + "✅ ALL TESTS PASSED ✅" + " " * 31 + "║")
        print("╚" + "=" * 78 + "╝")
    else:
        print("╔" + "=" * 78 + "╗")
        print("║" + " " * 20 + "⚠️  SOME TESTS FAILED OR HAD ERRORS ⚠️" + " " * 18 + "║")
        print("╚" + "=" * 78 + "╝")
    print(f"{Colors.ENDC}\n")
    
    # Log detailed results
    logger.info(f"Test Summary: {passed_tests} passed, {failed_tests} failed, {error_tests} errors, {skipped_tests} skipped")
    logger.info(f"Total opportunities found: {total_opportunities}")
    logger.info(f"Valid opportunities: {total_valid}, Invalid: {total_invalid}")

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {str(e)}{Colors.ENDC}")
        logger.error(f"Unexpected error in test runner: {str(e)}", exc_info=True)
