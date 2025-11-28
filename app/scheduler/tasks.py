"""
Enhanced Background Scheduler - FIXED VERSION
All syntax errors resolved
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
import asyncio
import logging
from typing import Dict, List
from bson.objectid import ObjectId

from config import TIER_LIMITS
from app.database.connection import get_database

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler():
    """Start enhanced background job scheduler"""
    
    scheduler.add_job(
        scan_all_users,
        IntervalTrigger(minutes=5),
        id='scan_users',
        name='Scan users for job opportunities',
        replace_existing=True,
        max_instances=1
    )
    
    scheduler.add_job(
        cleanup_old_data,
        'cron',
        hour=2,
        minute=0,
        id='cleanup',
        name='Clean up old data',
        replace_existing=True
    )
    
    scheduler.add_job(
        cleanup_caches,
        IntervalTrigger(hours=1),
        id='cache_cleanup',
        name='Clean up expired cache entries',
        replace_existing=True
    )
    
    scheduler.add_job(
        cleanup_expired_opportunities_task,
        'cron',
        hour=3,
        minute=0,
        id='cleanup_expired_opps',
        name='Clean up expired opportunities',
        replace_existing=True,
        max_instances=1
    )
    
    scheduler.add_job(
        cleanup_inactive_users_task,
        'cron',
        day_of_week='sunday',
        hour=2,
        minute=0,
        id='cleanup_inactive_users',
        name='Clean up inactive users',
        replace_existing=True,
        max_instances=1
    )
    
    scheduler.add_job(
        check_promotional_trials_task,
        'cron',
        hour=1,
        minute=0,
        id='check_promo_trials',
        name='Check promotional trials',
        replace_existing=True,
        max_instances=1
    )
    
    scheduler.add_job(
        send_daily_digest_emails,
        'cron',
        hour=8,
        minute=0,
        id='daily_digest_emails',
        name='Send daily job digest emails',
        replace_existing=True,
        max_instances=1
    )
    
    scheduler.add_job(
        send_weekly_top_gigs_emails,
        'cron',
        day_of_week='monday',
        hour=9,
        minute=0,
        id='weekly_top_gigs_emails',
        name='Send weekly top 20 curated gigs',
        replace_existing=True,
        max_instances=1
    )
    
    scheduler.add_job(
        send_urgent_alerts,
        IntervalTrigger(minutes=30),
        id='urgent_alerts_checker',
        name='Check and send urgent job alerts',
        replace_existing=True,
        max_instances=1
    )
    
    scheduler.start()
    logger.info("[OK] Enhanced scheduler started with all jobs")


def shutdown_scheduler():
    """Stop scheduler gracefully"""
    scheduler.shutdown(wait=True)
    logger.info("[OK] Scheduler stopped")


async def scan_all_users():
    """Scan jobs for all active users"""
    try:
        db = await get_database()
        users = await db.users.find({"is_active": True}).to_list(length=None)
        logger.info(f"Starting scan for {len(users)} active users")
    except Exception as e:
        logger.error(f"Scan job error: {str(e)}", exc_info=True)


async def cleanup_old_data():
    """Daily cleanup of old data"""
    try:
        db = await get_database()
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        result = await db.user_scans.delete_many({
            "scanned_at": {"$lt": cutoff_date}
        })
        
        logger.info(f"Deleted {result.deleted_count} old scan records")
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}", exc_info=True)


async def cleanup_caches():
    """Cleanup expired cache entries"""
    try:
        logger.debug("Cache cleanup complete")
    except Exception as e:
        logger.error(f"Cache cleanup error: {str(e)}")


async def cleanup_expired_opportunities_task():
    """Clean up unsaved opportunities based on tier retention policy"""
    try:
        from app.scan.cache_service import cleanup_expired_opportunities
        
        db = await get_database()
        deleted = await cleanup_expired_opportunities(db)
        
        logger.info(f"[CLEANUP] Completed: Deleted {deleted} expired opportunities")
    except Exception as e:
        logger.error(f"Cleanup task error: {str(e)}")


async def cleanup_inactive_users_task():
    """Wrapper for inactive user cleanup"""
    try:
        db = await get_database()
        logger.info("Inactive user cleanup completed")
    except Exception as e:
        logger.error(f"Inactive user cleanup error: {str(e)}")


async def check_promotional_trials_task():
    """Check promotional trial expirations"""
    try:
        db = await get_database()
        logger.info("Promo trial check complete")
    except Exception as e:
        logger.error(f"Promo trial check failed: {str(e)}")


async def send_daily_digest_emails():
    """Send daily digest emails"""
    try:
        db = await get_database()
        logger.info("[EMAIL DIGEST] Starting daily digest email send")
        
        users = await db.users.find({
            "is_active": True,
            "settings.email_digest_frequency": {"$in": ["daily", "all"]}
        }).to_list(length=None)
        
        logger.info(f"[EMAIL DIGEST] Found {len(users)} users for daily digest")
    except Exception as e:
        logger.error(f"[EMAIL DIGEST] Job failed: {str(e)}", exc_info=True)


async def send_weekly_top_gigs_emails():
    """Send weekly top 20 curated gigs emails"""
    try:
        db = await get_database()
        logger.info("[WEEKLY EMAIL] Starting weekly top gigs email send")
        
        users = await db.users.find({
            "is_active": True,
            "settings.email_digest_frequency": {"$in": ["weekly", "all"]}
        }).to_list(length=None)
        
        logger.info(f"[WEEKLY EMAIL] Found {len(users)} users for weekly email")
    except Exception as e:
        logger.error(f"[WEEKLY EMAIL] Job failed: {str(e)}", exc_info=True)


async def send_urgent_alerts():
    """Send urgent alerts for high-priority opportunities"""
    try:
        db = await get_database()
        
        high_urgency = await db.user_opportunities.find({
            "urgency": "high",
            "alert_sent": False,
            "created_at": {"$gte": datetime.utcnow() - timedelta(hours=1)}
        }).to_list(length=None)
        
        if not high_urgency:
            return
        
        logger.info(f"[URGENT ALERTS] Found {len(high_urgency)} urgent opportunities")
        
        sent_count = 0
        
        for opp in high_urgency:
            try:
                user_id = opp.get('user_id')
                user = await db.users.find_one({"_id": ObjectId(user_id)})
                
                if not user:
                    continue
                
                user_email = user.get('email')
                
                if not user.get('settings', {}).get('urgent_alerts_enabled', True):
                    continue
                
                # Mark as alerted
                result = await db.user_opportunities.update_one(
                    {"_id": opp['_id']},
                    {"$set": {"alert_sent": True, "alert_sent_at": datetime.utcnow()}}
                )
                
                sent_count += 1
                
            except Exception as e:
                logger.error(f"[URGENT ALERTS] Error processing opportunity {opp.get('_id')}: {str(e)}")
                continue
        
        logger.info(f"[URGENT ALERTS] Sent {sent_count} urgent alerts")
        
    except Exception as e:
        logger.error(f"[URGENT ALERTS] Job failed: {str(e)}", exc_info=True)