"""
Opportunities Management
User-specific opportunity tracking and management
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime
from typing import List, Optional

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/opportunities", tags=["Opportunities"])


@router.get("")
async def get_user_opportunities(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    platform: str = Query(None),
    saved_only: bool = Query(False)
):
    """Get opportunities for current user - applies tier limits to control access"""
    try:
        # Get user tier
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Apply tier-based limits
        tier_limits = {
            "free": 5,
            "pro": 8,
            "premium": 12
        }
        user_tier = user.get("tier", "free")
        max_opportunities = tier_limits.get(user_tier, 5)
        
        # Query for opportunities
        query = {
            "user_id": user_id,
            "platform": {"$exists": True, "$ne": "Unknown"},
            "title": {"$exists": True, "$ne": ""}
        }
        
        if platform:
            query["platform"] = platform
        
        if saved_only:
            query["is_saved"] = True
        
        # Count total but limit query to tier max
        total_count = await db.user_opportunities.count_documents(query)
        total = min(total_count, max_opportunities)  # Cap at tier limit
        
        opportunities = await db.user_opportunities.find(query)\
            .sort("found_at", -1)\
            .skip(skip)\
            .limit(min(limit, max_opportunities - skip))\
            .to_list(length=min(limit, max_opportunities))
        
        # Parse and clean up opportunities for display
        parsed_opps = []
        for opp in opportunities:
            opp["_id"] = str(opp["_id"])
            
            # Clean title - remove newlines, truncate
            title = opp.get("title", "No title")
            if isinstance(title, str):
                title = title.replace('\n', ' ').replace('\r', '').strip()[:100]
            opp["title"] = title
            
            # Ensure platform is set
            if not opp.get("platform") or opp["platform"] == "Unknown":
                opp["platform"] = "Opportunity"
            
            # Format for display card
            time_ago = ""
            if opp.get("found_at"):
                from datetime import datetime, timedelta
                found = opp["found_at"]
                now = datetime.utcnow()
                diff = now - found
                
                if diff.total_seconds() < 60:
                    time_ago = "just now"
                elif diff.total_seconds() < 3600:
                    mins = int(diff.total_seconds() / 60)
                    time_ago = f"{mins}m ago"
                elif diff.total_seconds() < 86400:
                    hours = int(diff.total_seconds() / 3600)
                    time_ago = f"{hours}h ago"
                else:
                    days = int(diff.days)
                    time_ago = f"{days}d ago"
            
            opp["time_ago"] = time_ago
            parsed_opps.append(opp)
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "tier": user_tier,
            "tier_limit": max_opportunities,
            "pagination": {"total": total, "skip": skip, "limit": limit},
            "opportunities": parsed_opps
        }
    except Exception as e:
        logger.error(f"Error fetching opportunities for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch opportunities")


@router.get("/{opportunity_id}")
async def get_opportunity_details(
    opportunity_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get details of a specific opportunity"""
    try:
        opportunity = await db.user_opportunities.find_one({
            "_id": ObjectId(opportunity_id),
            "user_id": user_id
        })
        
        if not opportunity:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        opportunity["_id"] = str(opportunity["_id"])
        
        return {"opportunity": opportunity}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get opportunity")


@router.post("/{opportunity_id}/save")
async def save_opportunity(
    opportunity_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Save/bookmark an opportunity"""
    try:
        result = await db.user_opportunities.update_one(
            {"_id": ObjectId(opportunity_id), "user_id": user_id},
            {"$set": {"is_saved": True, "saved_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        return {"message": "Opportunity saved"}
    except Exception as e:
        logger.error(f"Error saving opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save opportunity")


@router.post("/{opportunity_id}/apply")
async def mark_applied(
    opportunity_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Mark opportunity as applied"""
    try:
        result = await db.user_opportunities.update_one(
            {"_id": ObjectId(opportunity_id), "user_id": user_id},
            {"$set": {"applied": True, "applied_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        return {"message": "Marked as applied"}
    except Exception as e:
        logger.error(f"Error marking as applied: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to mark as applied")


@router.delete("/{opportunity_id}")
async def delete_opportunity(
    opportunity_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete an opportunity from user's list"""
    try:
        result = await db.user_opportunities.delete_one({
            "_id": ObjectId(opportunity_id),
            "user_id": user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        return {"message": "Opportunity deleted"}
    except Exception as e:
        logger.error(f"Error deleting opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete opportunity")


@router.get("/stats/summary")
async def get_opportunity_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get summary statistics for user's opportunities"""
    try:
        total = await db.user_opportunities.count_documents({"user_id": user_id})
        saved = await db.user_opportunities.count_documents({"user_id": user_id, "is_saved": True})
        applied = await db.user_opportunities.count_documents({"user_id": user_id, "applied": True})
        
        return {
            "total_opportunities": total,
            "saved": saved,
            "applied": applied,
            "pending": total - applied
        }
    except Exception as e:
        logger.error(f"Error getting opportunity stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")


@router.get("/platforms/available")
async def get_available_platforms(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get available platforms for user's tier"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        from config import TIER_LIMITS
        tier = user.get("tier", "free")
        platforms = TIER_LIMITS.get(tier, {}).get("platforms", [])
        
        return {
            "tier": tier,
            "platforms": platforms,
            "count": len(platforms)
        }
    except Exception as e:
        logger.error(f"Error getting available platforms: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get platforms")