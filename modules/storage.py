"""
Real MongoDB-based storage and analytics
NO MOCK DATA - Direct MongoDB integration
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
import logging
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)


async def load_sent_jobs(db: AsyncIOMotorDatabase, user_id: str):
    """Load previously sent job IDs from database"""
    try:
        sent_jobs = await db.user_opportunities.find(
            {"user_id": user_id, "sent_at": {"$exists": True}}
        ).to_list(length=10000)
        
        sent_ids = set(job['opportunity_id'] for job in sent_jobs)
        logger.info(f"Loaded {len(sent_ids)} previously sent jobs for user {user_id}")
        return sent_ids
    except Exception as e:
        logger.error(f"Error loading sent jobs: {e}")
        return set()


async def save_opportunity_to_db(
    db: AsyncIOMotorDatabase,
    opp: dict,
    analysis: dict = None,
    sent: bool = False,
    user_id: str = None
):
    """Save opportunity with real analysis to MongoDB"""
    try:
        opportunity_doc = {
            "external_id": opp['id'],
            "title": opp.get('title'),
            "description": opp.get('description', '')[:1000],
            "platform": opp.get('platform'),
            "url": opp.get('url'),
            "contact": opp.get('contact'),
            "telegram": opp.get('telegram'),
            "twitter": opp.get('twitter'),
            "website": opp.get('website'),
            "metadata": opp.get('metadata', {}),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Store in opportunities collection
        result = await db.opportunities.update_one(
            {"external_id": opp['id']},
            {"$set": opportunity_doc},
            upsert=True
        )
        
        opportunity_id = str(result.upserted_id) if result.upserted_id else opp['id']
        
        # If sent, create user-opportunity relationship
        if sent and user_id and analysis:
            await db.user_opportunities.insert_one({
                "user_id": user_id,
                "opportunity_id": opportunity_id,
                "confidence": analysis.get('confidence', 0),
                "ai_analysis": analysis,
                "sent_at": datetime.utcnow(),
                "viewed": False,
                "saved": False,
                "applied": False
            })
            
            logger.info(f"Saved opportunity {opportunity_id} to user {user_id}")
        
        return True
    except Exception as e:
        logger.error(f"Error saving to database: {e}")
        return False


async def save_analytics(
    db: AsyncIOMotorDatabase,
    user_id: str,
    total_found: int,
    total_sent: int,
    avg_confidence: float,
    platforms: list
):
    """Save real analytics to MongoDB"""
    try:
        current_month = datetime.utcnow().strftime("%Y-%m")
        
        analytics_doc = {
            "user_id": user_id,
            "month": current_month,
            "total_found": total_found,
            "total_sent": total_sent,
            "avg_confidence": avg_confidence,
            "top_platforms": platforms,
            "created_at": datetime.utcnow()
        }
        
        await db.analytics.insert_one(analytics_doc)
        logger.info(f"Analytics saved for user {user_id}: {total_sent} sent")
        
        # Update usage tracking
        await db.usage_tracking.update_one(
            {"user_id": user_id, "month": current_month},
            {
                "$inc": {"opportunities_sent": total_sent},
                "$set": {"updated_at": datetime.utcnow()}
            },
            upsert=True
        )
        
    except Exception as e:
        logger.error(f"Error saving analytics: {e}")


async def get_analytics(db: AsyncIOMotorDatabase, user_id: str, days: int = 7):
    """Get real analytics from MongoDB"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Overall stats
        pipeline = [
            {"$match": {"user_id": user_id, "created_at": {"$gte": cutoff_date}}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "total_sent": {"$sum": "$total_sent"},
                    "avg_conf": {"$avg": "$avg_confidence"}
                }
            }
        ]
        
        overall_result = await db.analytics.aggregate(pipeline).to_list(length=1)
        overall = overall_result[0] if overall_result else {"total": 0, "total_sent": 0, "avg_conf": 0}
        
        # Platform breakdown
        platform_pipeline = [
            {"$match": {"user_id": user_id, "created_at": {"$gte": cutoff_date}}},
            {
                "$group": {
                    "_id": {"$arrayElemAt": ["$top_platforms", 0]},
                    "count": {"$sum": "$total_found"}
                }
            },
            {"$sort": {"count": -1}}
        ]
        
        platforms = await db.analytics.aggregate(platform_pipeline).to_list(length=10)
        
        return {
            'overall': overall,
            'platforms': platforms
        }
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return {"overall": {}, "platforms": []}


async def get_recent_opportunities(db: AsyncIOMotorDatabase, user_id: str, limit: int = 20):
    """Get recent real opportunities from MongoDB"""
    try:
        opportunities = await db.user_opportunities.find(
            {"user_id": user_id}
        ).sort("sent_at", -1).limit(limit).to_list(length=limit)
        
        results = []
        for opp in opportunities:
            opportunity = await db.opportunities.find_one(
                {"_id": ObjectId(opp['opportunity_id'])}
            )
            if opportunity:
                results.append({
                    "id": opp['opportunity_id'],
                    "title": opportunity['title'],
                    "platform": opportunity['platform'],
                    "confidence": opp['confidence'],
                    "urgency": opp.get('ai_analysis', {}).get('urgency', 'low'),
                    "created_at": opportunity['created_at'],
                    "sent_at": opp['sent_at']
                })
        
        return results
    except Exception as e:
        logger.error(f"Error getting recent opportunities: {e}")
        return []


async def cleanup_old_records(db: AsyncIOMotorDatabase, days: int = 30):
    """Clean up old records from MongoDB"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await db.opportunities.delete_many(
            {"created_at": {"$lt": cutoff_date}}
        )
        
        deleted = result.deleted_count
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old opportunity records")
        
        return deleted
    except Exception as e:
        logger.error(f"Error cleaning up: {e}")
        return 0