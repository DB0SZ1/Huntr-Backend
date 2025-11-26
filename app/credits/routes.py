"""
Credits Management
Daily credit allocation and tracking for users
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime, timedelta

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id
from app.credits.manager import CreditManager
from config import TIER_LIMITS, CREDIT_COSTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/credits", tags=["Credits"])


@router.get("/balance")
async def get_credit_balance(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's current credit balance"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        tier = user.get("tier", "free")
        daily_credits = TIER_LIMITS.get(tier, {}).get("daily_credits", 10)
        
        credit_record = await db.user_credits.find_one({"user_id": user_id})
        
        if not credit_record:
            credit_record = {
                "user_id": user_id,
                "current_credits": daily_credits,
                "daily_credits": daily_credits,
                "last_refill": datetime.utcnow(),
                "total_credits_used": 0,
                "total_credits_purchased": 0
            }
            await db.user_credits.insert_one(credit_record)
        else:
            last_refill = credit_record.get("last_refill", datetime.utcnow())
            now = datetime.utcnow()
            
            if (now - last_refill).days >= 1:
                await db.user_credits.update_one(
                    {"user_id": user_id},
                    {"$set": {"current_credits": daily_credits, "last_refill": now}}
                )
                credit_record["current_credits"] = daily_credits
                credit_record["last_refill"] = now
                logger.info(f"Credits refilled for user {user_id}: {daily_credits}")
        
        last_refill = credit_record.get("last_refill", datetime.utcnow())
        now = datetime.utcnow()
        next_refill = last_refill + timedelta(days=1)
        
        return {
            "current_credits": credit_record.get("current_credits", daily_credits),
            "daily_credits": daily_credits,
            "tier": tier,
            "total_used": credit_record.get("total_credits_used", 0),
            "total_purchased": credit_record.get("total_credits_purchased", 0),
            "next_refill": next_refill.isoformat(),
            "hours_until_refill": max(0, round((next_refill - now).total_seconds() / 3600))
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting credit balance: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get credit balance")


@router.get("/summary")
async def get_credit_summary(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get comprehensive credit summary"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        tier = user.get("tier", "free")
        daily_credits = TIER_LIMITS.get(tier, {}).get("daily_credits", 10)
        
        credit_record = await db.user_credits.find_one({"user_id": user_id})
        
        if not credit_record:
            credit_record = {
                "current_credits": daily_credits,
                "daily_credits": daily_credits,
                "last_refill": datetime.utcnow(),
                "total_credits_used": 0,
                "total_credits_purchased": 0
            }
            await db.user_credits.insert_one({**credit_record, "user_id": user_id})
        else:
            last_refill = credit_record.get("last_refill", datetime.utcnow())
            now = datetime.utcnow()
            
            if (now - last_refill).days >= 1:
                await db.user_credits.update_one(
                    {"user_id": user_id},
                    {"$set": {"current_credits": daily_credits, "last_refill": now}}
                )
                credit_record["current_credits"] = daily_credits
                credit_record["last_refill"] = now
        
        last_refill = credit_record.get("last_refill", datetime.utcnow())
        now = datetime.utcnow()
        next_refill = last_refill + timedelta(days=1)
        hours_until = max(0, round((next_refill - now).total_seconds() / 3600))
        
        return {
            "data": {
                "daily_credits_total": daily_credits,
                "daily_credits_remaining": credit_record.get("current_credits", daily_credits),
                "daily_credits_used": daily_credits - credit_record.get("current_credits", daily_credits),
                "total_credits_used": credit_record.get("total_credits_used", 0),
                "total_credits_purchased": credit_record.get("total_credits_purchased", 0),
                "tier": tier,
                "last_refill_date": last_refill.isoformat(),
                "next_refill_time": next_refill.isoformat(),
                "hours_until_next_refill": hours_until
            }
        }
    except Exception as e:
        logger.error(f"Error getting credit summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get credit summary")


@router.get("/history")
async def get_credit_history(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """Get user's credit transaction history"""
    try:
        total = await db.credit_usage.count_documents({"user_id": user_id})
        
        usage = await db.credit_usage.find({"user_id": user_id})\
            .sort("timestamp", -1)\
            .skip(skip)\
            .limit(limit)\
            .to_list(length=limit)
        
        for item in usage:
            item["_id"] = str(item["_id"])
        
        return {
            "data": {
                "transactions": usage,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
    except Exception as e:
        logger.error(f"Error fetching credit history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch credit history")


@router.post("/purchase")
async def purchase_credits(
    amount: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Purchase additional credits"""
    try:
        if amount < 50:
            raise HTTPException(status_code=400, detail="Minimum purchase is 50 credits")
        
        price_ngn = amount * 100
        
        return {
            "amount": amount,
            "price_ngn": price_ngn,
            "payment_url": f"/api/payments/initiate?amount={price_ngn}&type=credits&credits={amount}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error purchasing credits: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process credit purchase")


@router.get("/tier-limits")
async def get_tier_limits(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get tier limits comparison"""
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        current_tier = user.get("tier", "free")
        
        tier_info = {}
        for tier_name, tier_data in TIER_LIMITS.items():
            tier_info[tier_name] = {
                "name": tier_name.upper(),
                "price_ngn": tier_data.get("price_ngn", 0),
                "daily_credits": tier_data.get("daily_credits", 0),
                "max_niches": tier_data.get("max_niches", 0),
                "scan_interval_minutes": tier_data.get("scan_interval_minutes", 0),
                "auto_scan_enabled": tier_data.get("auto_scan_enabled", False),
                "monthly_opportunities_limit": tier_data.get("monthly_opportunities_limit", 0),
                "features": tier_data.get("features", []),
                "platforms": tier_data.get("platforms", []),
                "is_current": tier_name == current_tier
            }
        
        return {
            "data": tier_info,
            "current_tier": current_tier
        }
    except Exception as e:
        logger.error(f"Error getting tier limits: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get tier limits")


@router.get("/check/scan")
async def check_credits_for_scan(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Check if user has enough credits for scan"""
    try:
        scan_cost = CREDIT_COSTS.get("scan", 5)
        
        balance = await CreditManager.get_balance(user_id, db)
        has_enough = balance >= scan_cost
        
        return {
            "data": {
                "has_enough_credits": has_enough,
                "current_balance": balance,
                "required_credits": scan_cost,
                "deficit": max(0, scan_cost - balance) if not has_enough else 0,
                "message": "Ready to scan" if has_enough else f"Need {scan_cost - balance} more credits"
            }
        }
    except Exception as e:
        logger.error(f"Error checking credits: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check credits")
