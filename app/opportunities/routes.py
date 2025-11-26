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
    """Get opportunities for current user ONLY"""
    try:
        query = {"user_id": user_id}
        
        if platform:
            query["platform"] = platform
        
        if saved_only:
            query["is_saved"] = True
        
        total = await db.user_opportunities.count_documents(query)
        
        opportunities = await db.user_opportunities.find(query)\
            .sort("found_at", -1)\
            .skip(skip)\
            .limit(limit)\
            .to_list(length=limit)
        
        for opp in opportunities:
            opp["_id"] = str(opp["_id"])
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "pagination": {"total": total, "skip": skip, "limit": limit},
            "opportunities": opportunities
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