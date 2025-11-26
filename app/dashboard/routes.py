"""
User Dashboard
Personal statistics and overview
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime, timedelta

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id
from app.credits.manager import CreditManager
from config import TIER_LIMITS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/overview")
async def get_dashboard_overview(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's dashboard overview"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        credits = await CreditManager.get_full_balance(user_id, db)
        total_opportunities = await db.user_opportunities.count_documents({"user_id": user_id})
        saved_opportunities = await db.user_opportunities.count_documents({"user_id": user_id, "is_saved": True})
        niches = await db.niche_configs.count_documents({"user_id": user_id, "is_active": True})
        
        recent_scans = await db.scan_history.find({"user_id": user_id}).sort("started_at", -1).limit(5).to_list(length=5)
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        week_opportunities = await db.user_opportunities.count_documents({"user_id": user_id, "found_at": {"$gte": week_ago}})
        
        return {
            "user": {
                "id": user_id,
                "name": user.get("name"),
                "email": user.get("email"),
                "tier": user.get("tier", "free"),
                "joined": user.get("created_at").isoformat()
            },
            "credits": credits,
            "statistics": {
                "total_opportunities": total_opportunities,
                "saved_opportunities": saved_opportunities,
                "active_niches": niches,
                "this_week_opportunities": week_opportunities
            },
            "recent_scans": recent_scans,
            "progress": {
                "tier": user.get("tier", "free"),
                "opportunities_found": total_opportunities,
                "niches_configured": niches
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard overview: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard overview")


@router.get("/stats")
async def get_dashboard_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get detailed dashboard statistics"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        platform_stats = await db.user_opportunities.aggregate([
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$platform", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]).to_list(length=None)
        
        this_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_scans = await db.scan_history.count_documents({"user_id": user_id, "started_at": {"$gte": this_month}})
        
        avg_confidence = await db.user_opportunities.aggregate([
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": None, "avg": {"$avg": "$match_data.confidence"}}}
        ]).to_list(length=1)
        
        avg_conf = round(avg_confidence[0]['avg']) if avg_confidence and avg_confidence[0]['avg'] is not None else 0
        
        return {
            "tier": user.get("tier", "free"),
            "platform_distribution": platform_stats,
            "monthly_scans": month_scans,
            "average_confidence": avg_conf,
            "total_opportunities": await db.user_opportunities.count_documents({"user_id": user_id})
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")


@router.get("/activity")
async def get_dashboard_activity(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = Query(20, ge=1, le=100)
):
    """Get user's recent activity"""
    try:
        # Get recent scans
        scans = await db.scan_history.find({"user_id": user_id})\
            .sort("started_at", -1)\
            .limit(limit)\
            .to_list(length=limit)
        
        # Get recent saved opportunities
        saved_opps = await db.user_opportunities.find({"user_id": user_id, "is_saved": True})\
            .sort("saved_at", -1)\
            .limit(limit)\
            .to_list(length=limit)
        
        # Get recent applied opportunities
        applied_opps = await db.user_opportunities.find({"user_id": user_id, "applied": True})\
            .sort("applied_at", -1)\
            .limit(limit)\
            .to_list(length=limit)
        
        # Combine and sort by timestamp
        activities = []
        
        for scan in scans:
            activities.append({
                "type": "scan",
                "action": f"Scan completed with {scan.get('opportunities_found', 0)} opportunities",
                "timestamp": scan.get("completed_at", scan.get("started_at")).isoformat(),
                "details": {
                    "scan_id": scan.get("scan_id"),
                    "opportunities_found": scan.get("opportunities_found", 0),
                    "status": scan.get("status")
                }
            })
        
        for opp in saved_opps:
            activities.append({
                "type": "saved",
                "action": f"Saved opportunity: {opp.get('title', 'N/A')[:50]}",
                "timestamp": opp.get("saved_at").isoformat(),
                "details": {
                    "opportunity_id": str(opp.get("_id")),
                    "title": opp.get("title"),
                    "platform": opp.get("platform")
                }
            })
        
        for opp in applied_opps:
            activities.append({
                "type": "applied",
                "action": f"Applied to: {opp.get('title', 'N/A')[:50]}",
                "timestamp": opp.get("applied_at").isoformat(),
                "details": {
                    "opportunity_id": str(opp.get("_id")),
                    "title": opp.get("title"),
                    "platform": opp.get("platform")
                }
            })
        
        # Sort by timestamp descending
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "data": {
                "activities": activities[:limit],
                "total": len(activities)
            }
        }
    except Exception as e:
        logger.error(f"Error getting activity: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get activity")


@router.get("/keywords")
async def get_top_keywords(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(30, ge=1, le=90)
):
    """Get top performing keywords for user's opportunities"""
    try:
        # Get date range
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Extract keywords from opportunities and count them
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "found_at": {"$gte": start_date}
            }},
            {"$project": {
                "keywords": {
                    "$split": [{"$toLower": "$title"}, " "]
                },
                "platform": 1,
                "match_data": 1
            }},
            {"$unwind": "$keywords"},
            {"$match": {
                "keywords": {"$regex": "^[a-z0-9]{3,}$"}  # Only words 3+ chars, alphanumeric
            }},
            {"$group": {
                "_id": "$keywords",
                "count": {"$sum": 1},
                "avg_confidence": {"$avg": "$match_data.confidence"},
                "platforms": {"$push": "$platform"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        
        keywords = await db.user_opportunities.aggregate(pipeline).to_list(length=limit)
        
        # Format response
        formatted_keywords = []
        for kw in keywords:
            # Get unique platforms
            platforms = list(set(kw.get("platforms", [])))
            
            formatted_keywords.append({
                "keyword": kw.get("_id"),
                "count": kw.get("count", 0),
                "avg_confidence": round(kw.get("avg_confidence", 0), 2) if kw.get("avg_confidence") is not None else 0,
                "platforms": platforms,
                "platform_count": len(platforms)
            })
        
        return {
            "data": {
                "keywords": formatted_keywords,
                "period_days": days,
                "total_keywords": len(formatted_keywords)
            }
        }
    except Exception as e:
        logger.error(f"Error getting keywords: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get keywords")


@router.get("/keywords/trending")
async def get_trending_keywords(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = Query(10, ge=1, le=50)
):
    """Get trending keywords across all user opportunities"""
    try:
        # Get trending keywords (most recent first)
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$sort": {"found_at": -1}},
            {"$limit": 100},  # Look at last 100 opportunities
            {"$project": {
                "keywords": {
                    "$split": [{"$toLower": "$title"}, " "]
                },
                "confidence": "$match_data.confidence",
                "found_at": 1
            }},
            {"$unwind": "$keywords"},
            {"$match": {
                "keywords": {"$regex": "^[a-z0-9]{3,}$"}
            }},
            {"$group": {
                "_id": "$keywords",
                "count": {"$sum": 1},
                "avg_confidence": {"$avg": "$confidence"},
                "first_seen": {"$max": "$found_at"}
            }},
            {"$sort": {"first_seen": -1, "count": -1}},
            {"$limit": limit}
        ]
        
        trending = await db.user_opportunities.aggregate(pipeline).to_list(length=limit)
        
        formatted = []
        for item in trending:
            formatted.append({
                "keyword": item.get("_id"),
                "count": item.get("count", 0),
                "avg_confidence": round(item.get("avg_confidence", 0), 2) if item.get("avg_confidence") is not None else 0,
                "first_seen": item.get("first_seen").isoformat() if item.get("first_seen") else None
            })
        
        return {
            "data": {
                "trending_keywords": formatted,
                "total": len(formatted)
            }
        }
    except Exception as e:
        logger.error(f"Error getting trending keywords: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get trending keywords")


@router.get("/config/pricing")
async def get_pricing_config(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Get pricing and tier information"""
    try:
        plans = []
        for tier_name, tier_data in TIER_LIMITS.items():
            plans.append({
                "tier": tier_name,
                "price_ngn": tier_data.get("price_ngn", 0),
                "features": tier_data.get("features", []),
                "max_niches": tier_data.get("max_niches", 0),
                "platforms": tier_data.get("platforms", []),
                "monthly_opportunities_limit": tier_data.get("monthly_opportunities_limit", 0),
                "daily_credits": tier_data.get("daily_credits", 0),
                "scan_interval_minutes": tier_data.get("scan_interval_minutes", 0)
            })
        
        return {"plans": plans}
    except Exception as e:
        logger.error(f"Error getting pricing config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get pricing")


@router.get("/settings")
async def get_user_settings(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user settings"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "email": user.get("email"),
            "name": user.get("name"),
            "tier": user.get("tier"),
            "notifications": user.get("settings", {}).get("notifications_enabled", True),
            "email_notifications": user.get("settings", {}).get("email_notifications", True),
            "whatsapp_notifications": user.get("settings", {}).get("whatsapp_notifications", False)
        }
    except Exception as e:
        logger.error(f"Error getting settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get settings")


@router.put("/settings")
async def update_user_settings(
    settings_update: dict,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update user settings"""
    try:
        allowed_fields = ["notifications_enabled", "email_notifications", "whatsapp_notifications", "name"]
        
        update_data = {}
        for field in allowed_fields:
            if field in settings_update:
                if field == "name":
                    update_data["name"] = settings_update[field]
                else:
                    update_data[f"settings.{field}"] = settings_update[field]
        
        if update_data:
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
        
        return {"message": "Settings updated successfully"}
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.get("/usage")
async def get_usage_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's monthly usage statistics"""
    try:
        current_month = datetime.utcnow().strftime("%Y-%m")
        usage = await db.usage_tracking.find_one({
            "user_id": user_id,
            "month": current_month
        })
        
        if not usage:
            usage = {
                "opportunities_sent": 0,
                "scans_completed": 0,
                "ai_analyses_used": 0,
                "notifications_sent": 0
            }
        
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        tier = user.get("tier", "free") if user else "free"
        tier_limits = TIER_LIMITS.get(tier, {})
        monthly_limit = tier_limits.get("monthly_opportunities_limit", 50)
        
        return {
            "month": current_month,
            "usage": usage,
            "limits": {
                "monthly_opportunities": monthly_limit,
                "daily_credits": tier_limits.get("daily_credits", 10)
            },
            "remaining": max(0, monthly_limit - usage.get("opportunities_sent", 0)) if monthly_limit > 0 else -1
        }
    except Exception as e:
        logger.error(f"Error getting usage stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get usage statistics")


@router.post("/email-preferences")
async def update_email_preferences(
    preferences: dict,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update user's email notification preferences"""
    try:
        # Valid preferences
        valid_prefs = {
            "email_digest_frequency": ["never", "daily", "weekly", "all"],
            "urgent_alerts_enabled": [True, False],
            "weekly_top_gigs": [True, False],
            "platform_specific": [True, False]
        }
        
        # Validate and update
        update_data = {}
        for key, value in preferences.items():
            if key not in valid_prefs:
                continue
            
            if key == "email_digest_frequency":
                if value in valid_prefs[key]:
                    update_data[f"settings.{key}"] = value
            else:
                if isinstance(value, bool):
                    update_data[f"settings.{key}"] = value
        
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            logger.info(f"Email preferences updated for user {user_id}")
            return {"message": "Email preferences updated"}
        else:
            return {"message": "No changes made"}
    
    except Exception as e:
        logger.error(f"Error updating email preferences: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")


@router.get("/email-preferences")
async def get_email_preferences(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's email notification preferences"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        settings = user.get('settings', {})
        
        return {
            "email_digest_frequency": settings.get("email_digest_frequency", "daily"),
            "urgent_alerts_enabled": settings.get("urgent_alerts_enabled", True),
            "weekly_top_gigs": settings.get("weekly_top_gigs", True),
            "platform_specific": settings.get("platform_specific", False)
        }
    
    except Exception as e:
        logger.error(f"Error getting email preferences: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get preferences")