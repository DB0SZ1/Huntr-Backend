"""
Scan Services - Real scraper integration with credit management
NO MOCK DATA - Uses actual scrapers from modules/
"""
import logging
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId

from app.credits.manager import CreditManager
from config import TIER_LIMITS, CREDIT_COSTS

# Import scrapers from modules (not app.scraper)
from modules.scrapers import (
    scrape_twitter_comprehensive,
    scrape_reddit_jobs,
    scrape_web3_jobs,
    scrape_pumpfun,
    scrape_dexscreener_enhanced,
    scrape_coinmarketcap_new,
    scrape_coingecko_new,
    scrape_telegram_channels
)

logger = logging.getLogger(__name__)

# Store active scans (in production, use Redis)
active_scans = {}


async def execute_scan_with_credits(
    scan_id: str,
    user_id: str,
    user_tier: str,
    db: AsyncIOMotorDatabase,
    credits_needed: int
):
    """
    Execute scan with real scrapers and credit deduction
    Uses modules/scrapers.py (synchronous) wrapped in async
    
    Args:
        scan_id: Unique scan identifier
        user_id: User performing scan
        user_tier: User's subscription tier
        db: Database connection
        credits_needed: Credits required for this scan
    """
    try:
        logger.info(f"[SCAN] Starting scan {scan_id} for user {user_id}")
        
        # Update scan status
        active_scans[scan_id]['status'] = 'deducting_credits'
        active_scans[scan_id]['progress'] = 5
        
        # Deduct credits BEFORE scanning
        deducted = await CreditManager.deduct_credits(
            user_id,
            credits_needed,
            'scan',
            db
        )
        
        if not deducted:
            logger.error(f"[FAIL] Could not deduct credits for scan {scan_id}")
            active_scans[scan_id]['status'] = 'failed'
            active_scans[scan_id]['error'] = 'Credit deduction failed'
            return
        
        logger.info(f"[OK] Deducted {credits_needed} credits from user {user_id}")
        active_scans[scan_id]['progress'] = 10
        
        # Get user's active niches
        niches = await db.niche_configs.find({
            "user_id": user_id,
            "is_active": True
        }).to_list(length=100)
        
        if not niches:
            logger.warning(f"[WARN] No active niches for user {user_id}")
            active_scans[scan_id]['status'] = 'completed'
            active_scans[scan_id]['opportunities_found'] = 0
            active_scans[scan_id]['progress'] = 100
            return
        
        # Get tier limits and available platforms
        tier_limits = TIER_LIMITS.get(user_tier, TIER_LIMITS['free'])
        platforms = tier_limits.get('platforms', [])
        
        total_opportunities = 0
        scanned_platforms = []
        failed_platforms = []
        
        logger.info(f"[SCAN] Platforms to scan: {platforms}")
        logger.info(f"[SCAN] Niches to match: {[n.get('name') for n in niches]}")
        
        # Scan each platform
        for idx, platform in enumerate(platforms):
            try:
                active_scans[scan_id]['current_platform'] = platform
                active_scans[scan_id]['status'] = f'scanning_{platform.lower()}'
                progress = 10 + (idx * (80 // len(platforms))) if platforms else 50
                active_scans[scan_id]['progress'] = progress
                
                logger.info(f"[SCAN] Starting {platform} scraper...")
                
                # Execute real scraper (wrapped in thread pool for async)
                opportunities = await asyncio.to_thread(
                    scan_platform,
                    platform,
                    niches,
                    user_id
                )
                
                if opportunities:
                    total_opportunities += len(opportunities)
                    scanned_platforms.append({
                        'platform': platform,
                        'count': len(opportunities)
                    })
                    logger.info(
                        f"[OK] {platform}: found {len(opportunities)} opportunities"
                    )
                else:
                    logger.info(f"[OK] {platform}: no opportunities found")
                    scanned_platforms.append({
                        'platform': platform,
                        'count': 0
                    })
            
            except Exception as e:
                logger.error(f"[ERROR] Error scanning {platform}: {str(e)}")
                failed_platforms.append(platform)
                continue
        
        # Update scan completion
        active_scans[scan_id]['status'] = 'completed'
        active_scans[scan_id]['progress'] = 100
        active_scans[scan_id]['platforms_scanned'] = scanned_platforms
        active_scans[scan_id]['opportunities_found'] = total_opportunities
        active_scans[scan_id]['completed_at'] = datetime.utcnow().isoformat()
        
        # Log scan result to database
        await db.scan_history.insert_one({
            "scan_id": scan_id,
            "user_id": user_id,
            "tier": user_tier,
            "platforms_scanned": scanned_platforms,
            "failed_platforms": failed_platforms,
            "opportunities_found": total_opportunities,
            "credits_used": credits_needed,
            "started_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "status": "completed"
        })
        
        logger.info(
            f"[OK] Scan {scan_id} completed: {total_opportunities} total opportunities "
            f"from {len(scanned_platforms)} platforms, {len(failed_platforms)} failed"
        )
    
    except Exception as e:
        logger.error(f"[FAIL] Scan {scan_id} failed: {str(e)}", exc_info=True)
        active_scans[scan_id]['status'] = 'failed'
        active_scans[scan_id]['error'] = str(e)
        active_scans[scan_id]['progress'] = 0
        
        # Log failed scan
        try:
            await db.scan_history.insert_one({
                "scan_id": scan_id,
                "user_id": user_id,
                "tier": user_tier,
                "status": "failed",
                "error": str(e),
                "credits_used": credits_needed,
                "started_at": datetime.utcnow()
            })
        except Exception as db_err:
            logger.error(f"Failed to log scan error: {str(db_err)}")


def scan_platform(
    platform: str,
    niches: list,
    user_id: str
) -> list:
    """
    Scan specific platform using real scrapers (SYNCHRONOUS)
    Called via asyncio.to_thread() to avoid blocking
    
    Args:
        platform: Platform name
        niches: User's niche configurations
        user_id: User ID
        
    Returns:
        List of found opportunities
    """
    opportunities = []
    
    try:
        # Call appropriate scraper based on platform
        # These are synchronous functions from modules/scrapers.py
        
        if platform == 'Twitter/X':
            opportunities = scrape_twitter_comprehensive() or []
        
        elif platform == 'Reddit':
            opportunities = scrape_reddit_jobs() or []
        
        elif platform == 'Web3.career':
            opportunities = scrape_web3_jobs() or []
        
        elif platform == 'Pump.fun':
            opportunities = scrape_pumpfun() or []
        
        elif platform == 'DexScreener':
            opportunities = scrape_dexscreener_enhanced() or []
        
        elif platform == 'CoinMarketCap':
            opportunities = scrape_coinmarketcap_new() or []
        
        elif platform == 'CoinGecko':
            opportunities = scrape_coingecko_new() or []
        
        elif platform == 'Telegram':
            opportunities = scrape_telegram_channels() or []
        
        else:
            logger.warning(f"Unknown platform: {platform}")
            return []
        
        # Add metadata to opportunities
        if opportunities:
            for opp in opportunities:
                opp['user_id'] = user_id
                opp['platform'] = platform
                opp['found_at'] = datetime.utcnow().isoformat()
        
        return opportunities
    
    except Exception as e:
        logger.error(f"Error scanning {platform}: {str(e)}", exc_info=True)
        return []
