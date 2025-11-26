"""
Admin Dashboard API
Complete admin functionality for monitoring, analytics, and user management
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from bson.objectid import ObjectId

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id
from app.admin.middleware import require_admin
from app.utils.serializers import serialize_documents, serialize_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin Dashboard"])


@router.get("/stats/overview")
async def get_admin_overview(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get admin dashboard overview statistics"""
    try:
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month = (this_month - timedelta(days=1)).replace(day=1)
        
        # Total users
        total_users = await db.users.count_documents({})
        
        # Today's signups
        today_signups = await db.users.count_documents({
            "created_at": {"$gte": today}
        })
        
        # This month's signups
        this_month_signups = await db.users.count_documents({
            "created_at": {"$gte": this_month}
        })
        
        # Last month's signups
        last_month_signups = await db.users.count_documents({
            "created_at": {"$gte": last_month, "$lt": this_month}
        })
        
        # User tiers distribution
        free_users = await db.users.count_documents({"tier": "free"})
        pro_users = await db.users.count_documents({"tier": "pro"})
        premium_users = await db.users.count_documents({"tier": "premium"})
        
        # Revenue calculation
        from config import TIER_LIMITS
        pro_price = TIER_LIMITS.get("pro", {}).get("price_ngn", 0)
        premium_price = TIER_LIMITS.get("premium", {}).get("price_ngn", 0)
        
        monthly_revenue = (pro_users * pro_price) + (premium_users * premium_price)
        
        # Active users (last 7 days)
        seven_days_ago = now - timedelta(days=7)
        active_users = await db.users.count_documents({
            "last_login": {"$gte": seven_days_ago}
        })
        
        # Conversion rate
        conversion_rate = round((pro_users + premium_users) / total_users * 100) if total_users > 0 else 0
        
        return {
            "users": {
                "total": total_users,
                "active_7d": active_users,
                "free": free_users,
                "pro": pro_users,
                "premium": premium_users,
                "conversion_rate": conversion_rate
            },
            "signups": {
                "today": today_signups,
                "this_month": this_month_signups,
                "last_month": last_month_signups
            },
            "revenue": {
                "monthly_revenue_ngn": monthly_revenue,
                "pro_subscriptions": pro_users,
                "premium_subscriptions": premium_users
            },
            "growth": {
                "signups_change": this_month_signups - last_month_signups,
                "user_growth": round(((this_month_signups / last_month_signups - 1) * 100) if last_month_signups > 0 else 0)
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting admin overview: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get overview")


@router.get("/users")
async def list_all_users(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    tier: str = Query(None),
    status: str = Query(None)
):
    """List all users with filtering"""
    try:
        query = {}
        
        if tier:
            query["tier"] = tier
        
        if status == "active":
            query["is_active"] = True
        elif status == "inactive":
            query["is_active"] = False
        
        total = await db.users.count_documents(query)
        
        users = await db.users.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)\
            .to_list(length=limit)
        
        # Serialize ObjectId and ensure _id is always a string
        users = serialize_documents(users)
        
        # Double-check that all users have valid _id
        for user in users:
            if "_id" not in user or not user["_id"] or user["_id"] == "Unknown":
                logger.warning(f"User missing valid _id: {user}")
                user["_id"] = str(user.get("_id", ""))
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "users": users
        }
    
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list users")


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get detailed user information"""
    try:
        # Validate user_id is a valid ObjectId
        if not user_id or user_id == "Unknown" or len(user_id) != 24:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        try:
            user = await db.users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        niches = await db.niche_configs.count_documents({"user_id": user_id})
        opportunities = await db.user_opportunities.count_documents({"user_id": user_id})
        scans = await db.scan_history.count_documents({"user_id": user_id})
        
        # Serialize user
        user = serialize_document(user)
        
        return {
            "user": user,
            "stats": {
                "niches": niches,
                "opportunities": opportunities,
                "scans": scans
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get user details")


@router.put("/users/{user_id}/tier")
async def update_user_tier(
    user_id: str,
    new_tier: str,
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update user subscription tier"""
    try:
        if new_tier not in ["free", "pro", "premium"]:
            raise HTTPException(status_code=400, detail="Invalid tier")
        
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"tier": new_tier, "updated_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Log admin action
        await db.admin_actions.insert_one({
            "admin_id": admin_id,
            "action": "update_user_tier",
            "user_id": user_id,
            "details": {"new_tier": new_tier},
            "timestamp": datetime.utcnow()
        })
        
        return {"message": f"User tier updated to {new_tier}"}
    
    except Exception as e:
        logger.error(f"Error updating user tier: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update user tier")


@router.get("/revenue/breakdown")
async def get_revenue_breakdown(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get revenue breakdown by tier and month"""
    try:
        from config import TIER_LIMITS
        
        pro_price = TIER_LIMITS.get("pro", {}).get("price_ngn", 0)
        premium_price = TIER_LIMITS.get("premium", {}).get("price_ngn", 0)
        
        # Get subscription counts
        pro_count = await db.users.count_documents({"tier": "pro"})
        premium_count = await db.users.count_documents({"tier": "premium"})
        
        # Get monthly revenue
        now = datetime.utcnow()
        this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate from payments (if available)
        monthly_payments = await db.payments.aggregate([
            {"$match": {"status": "successful", "created_at": {"$gte": this_month}}},
            {"$group": {"_id": "$tier", "total": {"$sum": "$amount"}}}
        ]).to_list(length=None)
        
        return {
            "current": {
                "pro_subscriptions": pro_count,
                "premium_subscriptions": premium_count,
                "pro_revenue": pro_count * pro_price,
                "premium_revenue": premium_count * premium_price,
                "total_revenue": (pro_count * pro_price) + (premium_count * premium_price)
            },
            "monthly_payments": monthly_payments or []
        }
    
    except Exception as e:
        logger.error(f"Error getting revenue breakdown: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get revenue breakdown")


@router.get("/activity")
async def get_admin_activity(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = Query(50, ge=1, le=100)
):
    """Get recent admin actions and system activity"""
    try:
        # Admin actions
        admin_actions = await db.admin_actions.find()\
            .sort("timestamp", -1)\
            .limit(limit)\
            .to_list(length=limit)
        
        # Recent signups
        recent_signups = await db.users.find()\
            .sort("created_at", -1)\
            .limit(10)\
            .to_list(length=10)
        
        # System alerts
        system_alerts = await db.system_alerts.find()\
            .sort("timestamp", -1)\
            .limit(10)\
            .to_list(length=10)
        
        # Serialize all documents
        admin_actions = serialize_documents(admin_actions)
        recent_signups = serialize_documents(recent_signups)
        system_alerts = serialize_documents(system_alerts)
        
        return {
            "admin_actions": admin_actions,
            "recent_signups": recent_signups,
            "system_alerts": system_alerts
        }
    
    except Exception as e:
        logger.error(f"Error getting activity: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get activity")


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Suspend/deactivate user account"""
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_active": False}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Log action
        await db.admin_actions.insert_one({
            "admin_id": admin_id,
            "action": "suspend_user",
            "user_id": user_id,
            "timestamp": datetime.utcnow()
        })
        
        return {"message": "User suspended"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suspending user: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to suspend user")


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Reactivate user account"""
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_active": True}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Log action
        await db.admin_actions.insert_one({
            "admin_id": admin_id,
            "action": "activate_user",
            "user_id": user_id,
            "timestamp": datetime.utcnow()
        })
        
        return {"message": "User activated"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating user: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to activate user")