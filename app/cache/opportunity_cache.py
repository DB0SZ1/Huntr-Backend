"""
Opportunity Caching System
Caches all scraped opportunities to avoid re-scraping and hitting rate limits
Reuses cached opportunities for multiple users
"""
import logging
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Optional
import hashlib
import json

logger = logging.getLogger(__name__)


class OpportunityCacheManager:
    """Manages opportunity caching to reduce scraping overhead"""
    
    # Cache validity: 4 hours (refresh if older)
    CACHE_TTL_MINUTES = 240
    
    @staticmethod
    def _generate_opportunity_hash(opp: Dict) -> str:
        """Generate unique hash for an opportunity based on core fields"""
        key_str = f"{opp.get('title', '')}{opp.get('platform', '')}{opp.get('url', '')}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    @staticmethod
    async def get_or_scrape_opportunities(
        db: AsyncIOMotorDatabase,
        platforms: List[str],
        scraper_function,
        force_refresh: bool = False
    ) -> Dict:
        """
        Get opportunities from cache if fresh, otherwise scrape and cache
        
        Args:
            db: Database connection
            platforms: List of platforms to scrape
            scraper_function: Function to call for scraping
            force_refresh: Force re-scrape even if cache is fresh
            
        Returns:
            Dict with opportunities and stats
        """
        
        # Check if we have fresh cached opportunities for ALL platforms
        if not force_refresh:
            cached = await OpportunityCacheManager.get_cached_opportunities(
                db, 
                platforms
            )
            if cached:
                logger.info(f"[CACHE] ✅ Using {len(cached['opportunities'])} cached opportunities")
                return {
                    "opportunities": cached['opportunities'],
                    "stats": {
                        "source": "cache",
                        "cached_at": cached['cached_at'],
                        "platforms": platforms
                    }
                }
        
        # Cache miss or forced refresh - scrape
        logger.info(f"[CACHE] 📡 Cache miss/refresh - scraping {len(platforms)} platforms...")
        results = await scraper_function(platforms=platforms)
        
        # Store in cache
        if results.get("opportunities"):
            await OpportunityCacheManager.cache_opportunities(
                db,
                results["opportunities"],
                platforms
            )
            logger.info(f"[CACHE] 💾 Cached {len(results['opportunities'])} opportunities")
        
        return results
    
    @staticmethod
    async def get_cached_opportunities(
        db: AsyncIOMotorDatabase,
        platforms: List[str]
    ) -> Optional[Dict]:
        """
        Get fresh cached opportunities for the given platforms
        
        Returns:
            Dict with opportunities if cache is fresh, None otherwise
        """
        try:
            # Get cached opportunities for all requested platforms
            cache_collection = db.opportunity_cache
            
            cutoff_time = datetime.utcnow() - timedelta(
                minutes=OpportunityCacheManager.CACHE_TTL_MINUTES
            )
            
            # Get opportunities cached after cutoff
            cached_opps = await cache_collection.find({
                "platform": {"$in": platforms},
                "cached_at": {"$gte": cutoff_time}
            }).to_list(length=1000)
            
            if not cached_opps:
                logger.info(f"[CACHE] ❌ No fresh cache for platforms: {platforms}")
                return None
            
            # Extract opportunity data
            opportunities = [
                opp.get("opportunity_data", opp) for opp in cached_opps
            ]
            
            # Check coverage: do we have results from ALL requested platforms?
            platforms_in_cache = set(opp.get("platform") for opp in opportunities)
            requested_platforms = set(platforms)
            
            missing_platforms = requested_platforms - platforms_in_cache
            if missing_platforms:
                logger.warning(
                    f"[CACHE] ⚠️  Missing platforms in cache: {missing_platforms}"
                )
                return None  # Don't use partial cache
            
            return {
                "opportunities": opportunities,
                "cached_at": cached_opps[0].get("cached_at"),
                "platform_count": len(platforms_in_cache)
            }
            
        except Exception as e:
            logger.error(f"[CACHE] Error retrieving cached opportunities: {str(e)}")
            return None
    
    @staticmethod
    async def cache_opportunities(
        db: AsyncIOMotorDatabase,
        opportunities: List[Dict],
        platforms: List[str]
    ) -> int:
        """
        Cache scraped opportunities for future reuse
        
        Args:
            db: Database connection
            opportunities: List of opportunity dicts
            platforms: List of platforms these came from
            
        Returns:
            Number of opportunities cached
        """
        try:
            cache_collection = db.opportunity_cache
            now = datetime.utcnow()
            cached_count = 0
            
            for opp in opportunities:
                try:
                    # Create cache entry with unique key
                    cache_key = OpportunityCacheManager._generate_opportunity_hash(opp)
                    
                    cache_entry = {
                        "cache_key": cache_key,
                        "platform": opp.get("platform", "Unknown"),
                        "opportunity_data": opp,
                        "cached_at": now,
                        "expires_at": now + timedelta(
                            minutes=OpportunityCacheManager.CACHE_TTL_MINUTES
                        ),
                        "used_count": 0,  # Track how many users got this from cache
                        "last_used": now
                    }
                    
                    # Upsert: update if exists, insert if not
                    await cache_collection.update_one(
                        {"cache_key": cache_key},
                        {
                            "$set": cache_entry,
                            "$inc": {"version": 1}
                        },
                        upsert=True
                    )
                    cached_count += 1
                    
                except Exception as e:
                    logger.warning(f"[CACHE] Failed to cache opportunity: {str(e)}")
                    continue
            
            logger.info(f"[CACHE] Cached {cached_count}/{len(opportunities)} opportunities")
            return cached_count
            
        except Exception as e:
            logger.error(f"[CACHE] Error caching opportunities: {str(e)}")
            return 0
    
    @staticmethod
    async def cleanup_expired_cache(db: AsyncIOMotorDatabase) -> int:
        """
        Remove expired cache entries
        Runs periodically to keep database clean
        
        Returns:
            Number of entries deleted
        """
        try:
            cache_collection = db.opportunity_cache
            now = datetime.utcnow()
            
            result = await cache_collection.delete_many({
                "expires_at": {"$lt": now}
            })
            
            logger.info(f"[CACHE] Cleaned up {result.deleted_count} expired entries")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"[CACHE] Error cleaning cache: {str(e)}")
            return 0
    
    @staticmethod
    async def get_cache_stats(db: AsyncIOMotorDatabase) -> Dict:
        """
        Get cache statistics for monitoring
        
        Returns:
            Dict with cache stats
        """
        try:
            cache_collection = db.opportunity_cache
            now = datetime.utcnow()
            
            total = await cache_collection.count_documents({})
            fresh = await cache_collection.count_documents({
                "expires_at": {"$gte": now}
            })
            expired = total - fresh
            
            # Most used opportunities
            top_opps = await cache_collection.find().sort(
                "used_count", -1
            ).limit(5).to_list(5)
            
            return {
                "total_cached": total,
                "fresh_entries": fresh,
                "expired_entries": expired,
                "cache_hit_rate": f"{(fresh/total*100) if total > 0 else 0:.1f}%",
                "top_cached": [
                    {
                        "title": opp.get("opportunity_data", {}).get("title", "Unknown"),
                        "platform": opp.get("platform", "Unknown"),
                        "used_count": opp.get("used_count", 0)
                    }
                    for opp in top_opps
                ]
            }
            
        except Exception as e:
            logger.error(f"[CACHE] Error getting cache stats: {str(e)}")
            return {
                "error": str(e),
                "total_cached": 0
            }
