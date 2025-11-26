"""
Payments API Routes
Subscription management and Paystack integration
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime, timedelta

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id
from config import TIER_LIMITS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.get("/plans")
async def get_subscription_plans(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Get all available subscription plans"""
    try:
        plans = []
        for tier_name, tier_data in TIER_LIMITS.items():
            plans.append({
                "id": tier_name,
                "tier": tier_name,
                "price_ngn": tier_data.get("price_ngn", 0),
                "features": tier_data.get("features", []),
                "max_niches": tier_data.get("max_niches", 0),
                "max_keywords_per_niche": 50,
                "platforms": tier_data.get("platforms", []),
                "monthly_opportunities_limit": tier_data.get("monthly_opportunities_limit", 0),
                "daily_credits": tier_data.get("daily_credits", 0),
                "scan_interval_minutes": tier_data.get("scan_interval_minutes", 0)
            })
        
        return {"plans": plans}
    except Exception as e:
        logger.error(f"Error getting plans: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get subscription plans")


@router.get("/subscription")
async def get_user_subscription(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's current subscription"""
    try:
        subscription = await db.subscriptions.find_one({"user_id": user_id})
        
        if not subscription:
            raise HTTPException(status_code=404, detail="No subscription found")
        
        subscription["_id"] = str(subscription["_id"])
        
        return {"subscription": subscription}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subscription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get subscription")


@router.post("/upgrade")
async def upgrade_subscription(
    tier: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Upgrade user subscription tier"""
    try:
        if tier not in TIER_LIMITS:
            raise HTTPException(status_code=400, detail="Invalid tier")
        
        # Update user tier
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"tier": tier, "updated_at": datetime.utcnow()}}
        )
        
        # Update subscription
        await db.subscriptions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "tier": tier,
                    "status": "active",
                    "current_period_start": datetime.utcnow(),
                    "current_period_end": datetime.utcnow() + timedelta(days=30)
                }
            },
            upsert=True
        )
        
        return {"message": f"Upgraded to {tier}", "tier": tier, "success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upgrading subscription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upgrade subscription")


@router.post("/cancel")
async def cancel_subscription(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Cancel user subscription"""
    try:
        await db.subscriptions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": datetime.utcnow()
                }
            }
        )
        
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"tier": "free"}}
        )
        
        return {"message": "Subscription cancelled", "success": True}
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")
