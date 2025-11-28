"""
Opportunity Caching and Cleanup Service
Caches opportunities by niche to avoid repeated API calls
Auto-deletes unsaved opportunities after tier-specific days
"""

import logging
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from config import TIER_LIMITS

logger = logging.getLogger(__name__)


async def cache_opportunities_by_niche(
    db: AsyncIOMotorDatabase,
    niche: str,
    opportunities: list,
    ttl_hours: int = 24
):
    """
    Cache opportunities by niche to avoid repeated API calls
    
    Args:
        db: Database connection
        niche: Niche name (e.g., "web3", "crypto", "defi")
        opportunities: List of opportunities from scraper
        ttl_hours: Time to live in hours (default 24)
    """
    try:
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=ttl_hours)
        
        cache_record = {
            "niche": niche,
            "opportunities": opportunities,
            "created_at": now,
            "expires_at": expires_at,
            "count": len(opportunities)
        }
        
        # Upsert cache record
        await db.opportunity_cache.update_one(
            {"niche": niche},
            {"$set": cache_record},
            upsert=True
        )
        
        logger.info(f"[CACHE] Cached {len(opportunities)} opportunities for niche '{niche}' (expires in {ttl_hours}h)")
        
    except Exception as e:
        logger.error(f"[CACHE] Error caching opportunities: {str(e)}")


async def get_cached_opportunities(
    db: AsyncIOMotorDatabase,
    niche: str
):
    """
    Retrieve cached opportunities for a niche if not expired
    
    Args:
        db: Database connection
        niche: Niche name
        
    Returns:
        Cached opportunities list or None if expired/not found
    """
    try:
        now = datetime.utcnow()
        
        cache_record = await db.opportunity_cache.find_one({
            "niche": niche,
            "expires_at": {"$gt": now}
        })
        
        if cache_record:
            logger.info(f"[CACHE] Retrieved {cache_record['count']} cached opportunities for niche '{niche}'")
            return cache_record.get("opportunities", [])
        
        return None
    
    except Exception as e:
        logger.error(f"[CACHE] Error retrieving cached opportunities: {str(e)}")
        return None


async def cleanup_expired_opportunities(db: AsyncIOMotorDatabase):
    """
    Delete unsaved opportunities based on tier retention policy
    Free: 3 days
    Pro: 7 days
    Premium: 30 days
    """
    try:
        now = datetime.utcnow()
        
        # Get all users with their tiers
        users = await db.users.find({}).to_list(length=None)
        
        deleted_total = 0
        
        for user in users:
            user_id = str(user.get("_id"))
            tier = user.get("tier", "free")
            
            # Get retention days for tier
            retention_days = {
                "free": 3,
                "pro": 7,
                "premium": 30
            }.get(tier, 3)
            
            cutoff_date = now - timedelta(days=retention_days)
            
            # Delete unsaved opportunities older than retention period
            result = await db.user_opportunities.delete_many({
                "user_id": user_id,
                "is_saved": False,
                "found_at": {"$lt": cutoff_date}
            })
            
            if result.deleted_count > 0:
                logger.info(f"[CLEANUP] User {user_id} ({tier}): Deleted {result.deleted_count} expired opportunities")
                deleted_total += result.deleted_count
        
        logger.info(f"[CLEANUP] Total opportunities cleaned up: {deleted_total}")
        return deleted_total
    
    except Exception as e:
        logger.error(f"[CLEANUP] Error in cleanup task: {str(e)}")
        return 0


async def get_niche_for_user(db: AsyncIOMotorDatabase, user_id: str):
    """Get user's active niches"""
    try:
        niches = await db.niche_configs.find({
            "user_id": user_id,
            "is_active": True
        }).to_list(length=100)
        
        return [n.get("niche") for n in niches] if niches else ["general"]
    
    except Exception as e:
        logger.error(f"Error getting niches for user {user_id}: {str(e)}")
        return ["general"]
