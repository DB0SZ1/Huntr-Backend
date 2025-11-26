"""
Scheduled cleanup task for expired opportunities
Removes unsaved opportunities after 5 days
"""
import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


async def cleanup_expired_opportunities(db: AsyncIOMotorDatabase):
    """
    Delete unsaved opportunities that are older than 5 days
    
    Args:
        db: Database connection
    """
    try:
        # Find all unsaved opportunities that have expired
        cutoff_date = datetime.utcnow()
        
        result = await db.user_opportunities.delete_many({
            "saved": False,
            "applied": False,
            "expires_at": {
                "$exists": True,
                "$lt": cutoff_date
            }
        })
        
        if result.deleted_count > 0:
            logger.info(f"[CLEANUP] Deleted {result.deleted_count} expired opportunities")
        
        return result.deleted_count
    
    except Exception as e:
        logger.error(f"[ERROR] Cleanup failed: {str(e)}", exc_info=True)
        return 0


async def cleanup_inactive_users(db: AsyncIOMotorDatabase):
    """
    Clean up data for deleted/inactive users
    
    Args:
        db: Database connection
    """
    try:
        # Get inactive users (no login for 90 days)
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        inactive_users = await db.users.find(
            {"last_login": {"$lt": cutoff_date}, "is_active": False}
        ).to_list(length=100)
        
        deleted_count = 0
        
        for user in inactive_users:
            user_id = str(user['_id'])
            
            # Delete user's opportunities
            await db.user_opportunities.delete_many({"user_id": user_id})
            
            # Delete user's niches
            await db.niche_configs.delete_many({"user_id": user_id})
            
            # Delete user
            await db.users.delete_one({"_id": user['_id']})
            
            deleted_count += 1
        
        if deleted_count > 0:
            logger.info(f"[CLEANUP] Removed {deleted_count} inactive users and their data")
        
        return deleted_count
    
    except Exception as e:
        logger.error(f"[ERROR] Inactive user cleanup failed: {str(e)}", exc_info=True)
        return 0
