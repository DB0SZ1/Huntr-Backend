"""
Enhanced Multi-Tenant Job Scraper
Robust error handling, rate limiting, and monitoring
"""
import asyncio
from typing import List, Dict, Optional
import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict

# Import your EXISTING, WORKING scrapers
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from modules.scrapers import (
    scrape_twitter_comprehensive,
    scrape_telegram_channels,
    scrape_pumpfun,
    scrape_coinmarketcap_new,
    scrape_dexscreener_enhanced,
    scrape_coingecko_new,
    scrape_web3_jobs
)

logger = logging.getLogger(__name__)


# Platform configuration with retry settings
SCRAPER_CONFIG = {
    'Twitter/X': {
        'function': scrape_twitter_comprehensive,
        'timeout': 60,
        'retries': 2,
        'rate_limit_per_hour': 100,
        'requires_api': True
    },
    'Web3.career': {
        'function': scrape_web3_jobs,
        'timeout': 30,
        'retries': 2,
        'rate_limit_per_hour': 200,
        'requires_api': False
    },
    'Pump.fun': {
        'function': scrape_pumpfun,
        'timeout': 30,
        'retries': 2,
        'rate_limit_per_hour': 100,
        'requires_api': False
    },
    'DexScreener': {
        'function': scrape_dexscreener_enhanced,
        'timeout': 45,
        'retries': 2,
        'rate_limit_per_hour': 150,
        'requires_api': False
    },
    'CoinMarketCap': {
        'function': scrape_coinmarketcap_new,
        'timeout': 60,
        'retries': 2,
        'rate_limit_per_hour': 50,
        'requires_api': True
    },
    'CoinGecko': {
        'function': scrape_coingecko_new,
        'timeout': 90,
        'retries': 2,
        'rate_limit_per_hour': 30,
        'requires_api': False
    },
    'Telegram': {
        'function': scrape_telegram_channels,
        'timeout': 120,
        'retries': 1,
        'rate_limit_per_hour': 20,
        'requires_api': True
    }
}


class ScraperMetrics:
    """Track scraper performance and rate limits"""
    
    def __init__(self):
        self.calls_per_platform = defaultdict(list)  # platform -> list of timestamps
        self.errors_per_platform = defaultdict(int)
        self.success_count = defaultdict(int)
        
    def record_call(self, platform: str):
        """Record a scraper call"""
        now = datetime.utcnow()
        self.calls_per_platform[platform].append(now)
        
        # Clean old entries (older than 1 hour)
        hour_ago = now - timedelta(hours=1)
        self.calls_per_platform[platform] = [
            ts for ts in self.calls_per_platform[platform]
            if ts > hour_ago
        ]
    
    def can_scrape(self, platform: str) -> bool:
        """Check if platform can be scraped (rate limit check)"""
        config = SCRAPER_CONFIG.get(platform)
        if not config:
            return False
        
        recent_calls = len(self.calls_per_platform[platform])
        limit = config['rate_limit_per_hour']
        
        return recent_calls < limit
    
    def record_success(self, platform: str):
        """Record successful scrape"""
        self.success_count[platform] += 1
    
    def record_error(self, platform: str):
        """Record scrape error"""
        self.errors_per_platform[platform] += 1
    
    def get_stats(self) -> Dict:
        """Get scraper statistics"""
        return {
            'calls_last_hour': {
                platform: len(timestamps)
                for platform, timestamps in self.calls_per_platform.items()
            },
            'success_count': dict(self.success_count),
            'error_count': dict(self.errors_per_platform)
        }


# Global metrics tracker
metrics = ScraperMetrics()


async def scrape_platform(
    platform: str,
    timeout_override: Optional[int] = None
) -> Dict[str, any]:
    """
    Scrape a single platform with comprehensive error handling
    
    Args:
        platform: Platform name (e.g., "Twitter/X")
        timeout_override: Override default timeout
        
    Returns:
        Dict with 'opportunities', 'success', 'error', 'duration'
    """
    config = SCRAPER_CONFIG.get(platform)
    
    if not config:
        logger.warning(f"No scraper configuration found for platform: {platform}")
        return {
            'platform': platform,
            'opportunities': [],
            'success': False,
            'error': 'Platform not configured',
            'duration': 0
        }
    
    # Check rate limit
    if not metrics.can_scrape(platform):
        logger.warning(f"Rate limit reached for {platform}")
        return {
            'platform': platform,
            'opportunities': [],
            'success': False,
            'error': 'Rate limit exceeded',
            'duration': 0
        }
    
    scraper_func = config['function']
    timeout = timeout_override or config['timeout']
    max_retries = config['retries']
    
    start_time = time.time()
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Scraping {platform} (attempt {attempt}/{max_retries})...")
            
            # Record the call
            metrics.record_call(platform)
            
            # Run scraper in thread pool with timeout
            opportunities = await asyncio.wait_for(
                asyncio.to_thread(scraper_func),
                timeout=timeout
            )
            
            duration = time.time() - start_time
            
            if opportunities:
                logger.info(f"{platform}: Found {len(opportunities)} opportunities in {duration:.2f}s")
                metrics.record_success(platform)
                
                return {
                    'platform': platform,
                    'opportunities': opportunities,
                    'success': True,
                    'error': None,
                    'duration': duration
                }
            else:
                logger.info(f"{platform}: No opportunities found in {duration:.2f}s")
                return {
                    'platform': platform,
                    'opportunities': [],
                    'success': True,
                    'error': None,
                    'duration': duration
                }
        
        except asyncio.TimeoutError:
            error_msg = f"Timeout after {timeout}s"
            logger.error(f"{platform} scrape timeout (attempt {attempt})")
            
            if attempt == max_retries:
                metrics.record_error(platform)
                return {
                    'platform': platform,
                    'opportunities': [],
                    'success': False,
                    'error': error_msg,
                    'duration': time.time() - start_time
                }
            
            # Wait before retry with exponential backoff
            await asyncio.sleep(2 ** attempt)
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"{platform} scrape error (attempt {attempt}): {error_msg}", exc_info=True)
            
            if attempt == max_retries:
                metrics.record_error(platform)
                return {
                    'platform': platform,
                    'opportunities': [],
                    'success': False,
                    'error': error_msg,
                    'duration': time.time() - start_time
                }
            
            await asyncio.sleep(2 ** attempt)
    
    # Should never reach here
    return {
        'platform': platform,
        'opportunities': [],
        'success': False,
        'error': 'Max retries exceeded',
        'duration': time.time() - start_time
    }


async def scrape_platforms_for_user(
    platforms: List[str],
    max_concurrent: int = 3
) -> Dict[str, any]:
    """
    Scrape multiple platforms concurrently with controlled concurrency
    
    Args:
        platforms: List of platform names
        max_concurrent: Maximum concurrent scrapes
        
    Returns:
        Dict with 'opportunities', 'results', 'stats'
    """
    start_time = time.time()
    
    logger.info(f"Starting scrape for {len(platforms)} platforms: {', '.join(platforms)}")
    
    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def scrape_with_semaphore(platform: str):
        async with semaphore:
            return await scrape_platform(platform)
    
    # Scrape all platforms
    tasks = [scrape_with_semaphore(platform) for platform in platforms]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    
    # Aggregate results
    all_opportunities = []
    successful_scrapes = 0
    failed_scrapes = 0
    errors = []
    
    for result in results:
        if result['success']:
            all_opportunities.extend(result['opportunities'])
            successful_scrapes += 1
        else:
            failed_scrapes += 1
            errors.append({
                'platform': result['platform'],
                'error': result['error']
            })
    
    # Deduplicate by external_id (opportunity ID)
    seen_ids = set()
    unique_opportunities = []
    duplicate_count = 0
    
    for opp in all_opportunities:
        opp_id = opp.get('id')
        if opp_id and opp_id not in seen_ids:
            seen_ids.add(opp_id)
            unique_opportunities.append(opp)
        else:
            duplicate_count += 1
    
    total_duration = time.time() - start_time
    
    stats = {
        'total_platforms': len(platforms),
        'successful_scrapes': successful_scrapes,
        'failed_scrapes': failed_scrapes,
        'total_opportunities': len(all_opportunities),
        'unique_opportunities': len(unique_opportunities),
        'duplicates_removed': duplicate_count,
        'duration': round(total_duration, 2),
        'errors': errors
    }
    
    logger.info(
        f"Scrape complete: {successful_scrapes}/{len(platforms)} successful, "
        f"{len(unique_opportunities)} unique opportunities in {total_duration:.2f}s"
    )
    
    return {
        'opportunities': unique_opportunities,
        'results': results,
        'stats': stats
    }


async def store_opportunities_to_db(opportunities: List[Dict], db) -> int:
    """
    Store scraped opportunities to database with deduplication
    
    Args:
        opportunities: List of opportunity dicts
        db: Database connection
        
    Returns:
        Number of new opportunities stored
    """
    stored_count = 0
    
    for opp in opportunities:
        try:
            # FIX: Use 'id' field from scrapers (not 'external_id')
            external_id = opp.get('id')
            
            if not external_id:
                logger.warning("Opportunity missing ID, skipping")
                continue
            
            # Check if already exists
            existing = await db.opportunities.find_one({'external_id': external_id})
            
            if existing:
                # Update times_matched
                await db.opportunities.update_one(
                    {'external_id': external_id},
                    {'$inc': {'times_matched': 1}}
                )
                continue
            
            # Create new opportunity document
            opportunity_doc = {
                'external_id': external_id,  # Store scraper's ID as external_id
                'title': opp.get('title', 'No title'),
                'description': opp.get('description', ''),
                'platform': opp.get('platform', 'Unknown'),
                'url': opp.get('url', ''),
                'contact': opp.get('contact'),
                'telegram': opp.get('telegram'),
                'twitter': opp.get('twitter'),
                'website': opp.get('website'),
                'email': opp.get('email'),
                'timestamp': opp.get('timestamp'),
                'metadata': opp.get('metadata', {}),
                'created_at': datetime.utcnow(),
                'scraped_at': datetime.utcnow(),
                'is_active': True,
                'times_matched': 0
            }
            
            await db.opportunities.insert_one(opportunity_doc)
            stored_count += 1
        
        except Exception as e:
            logger.error(f"Error storing opportunity: {str(e)}", exc_info=True)
    
    if stored_count > 0:
        logger.info(f"Stored {stored_count} new opportunities to database")
    
    return stored_count


def get_scraper_metrics() -> Dict:
    """Get current scraper metrics"""
    return metrics.get_stats()


async def test_platform_scraper(platform: str) -> Dict:
    """
    Test a single platform scraper
    
    Args:
        platform: Platform name
        
    Returns:
        Test result dict
    """
    logger.info(f"Testing {platform} scraper...")
    
    result = await scrape_platform(platform)
    
    return {
        'platform': platform,
        'success': result['success'],
        'opportunities_found': len(result['opportunities']),
        'error': result['error'],
        'duration': result['duration']
    }


async def validate_scraper_setup() -> Dict:
    """
    Validate all scrapers are properly configured
    
    Returns:
        Validation results
    """
    results = {}
    
    for platform, config in SCRAPER_CONFIG.items():
        try:
            scraper_func = config['function']
            
            # Check if function exists
            if not callable(scraper_func):
                results[platform] = {
                    'valid': False,
                    'error': 'Scraper function not callable'
                }
                continue
            
            # Check if requires API key
            if config.get('requires_api'):
                # This would need environment variable checks
                results[platform] = {
                    'valid': True,
                    'note': 'Requires API configuration'
                }
            else:
                results[platform] = {
                    'valid': True,
                    'note': 'No API required'
                }
        
        except Exception as e:
            results[platform] = {
                'valid': False,
                'error': str(e)
            }
    
    return results