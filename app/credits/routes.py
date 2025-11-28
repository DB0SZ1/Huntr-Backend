"""
Credits Management
Daily credit allocation and tracking for users
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime, timedelta

from app.database.connection import get_database
from app.auth.oauth import get_current_user
from app.auth.jwt_handler import get_current_user_id
from app.credits.manager import CreditManager
from config import TIER_LIMITS, CREDIT_COSTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/credits", tags=["Credits"])


async def initialize_user_credits(db, user_id: str):
    """
    Initialize credits for a new user based on their tier from TIER_LIMITS config
    Creates user_credits record with tier-based daily allocation
    Also repairs broken records (e.g., 0 current_credits)
    """
    try:
        # Get user's tier from database
        try:
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            user_tier = user.get("tier", "free") if user else "free"
        except:
            user_tier = "free"
        
        # Get daily credits from TIER_LIMITS config
        daily_credits = TIER_LIMITS.get(user_tier, {}).get("daily_credits", 10)
        
        # Check if user_credits already exists
        existing = await db.user_credits.find_one({"user_id": user_id})
        
        if existing:
            # Record exists - check if it needs repair
            current_credits = existing.get("current_credits", 0)
            
            # If current_credits is 0 and it's never been set properly, repair it
            if current_credits == 0 and existing.get("daily_credits") != daily_credits:
                # Tier changed or corrupted record - repair it
                now = datetime.utcnow()
                await db.user_credits.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "current_credits": daily_credits,
                            "daily_credits": daily_credits,
                            "daily_credits_used": 0,
                            "last_refill": now,
                            "next_refill": now + timedelta(days=1),
                            "tier": user_tier,
                            "updated_at": now
                        }
                    }
                )
                logger.info(f"Repaired credit record for user {user_id} (tier: {user_tier}, daily: {daily_credits})")
            elif current_credits == 0 and not existing.get("last_refill"):
                # No last_refill set - initialize it
                now = datetime.utcnow()
                await db.user_credits.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "current_credits": daily_credits,
                            "daily_credits": daily_credits,
                            "daily_credits_used": 0,
                            "last_refill": now,
                            "next_refill": now + timedelta(days=1),
                            "tier": user_tier,
                            "updated_at": now
                        }
                    }
                )
                logger.info(f"Fixed uninitialized credit record for user {user_id} (tier: {user_tier}, daily: {daily_credits})")
            
            return  # Already exists (and potentially fixed)
        
        # Create new record
        now = datetime.utcnow()
        await db.user_credits.insert_one({
            "user_id": user_id,
            "current_credits": daily_credits,
            "daily_credits": daily_credits,
            "daily_credits_used": 0,
            "last_refill": now,
            "next_refill": now + timedelta(days=1),
            "total_credits_used": 0,
            "total_credits_purchased": 0,
            "tier": user_tier,
            "created_at": now,
            "updated_at": now,
            "transactions": []
        })
        logger.info(f"Initialized credits for user {user_id} (tier: {user_tier}, daily: {daily_credits})")
    
    except Exception as e:
        logger.error(f"Failed to initialize credits for user {user_id}: {str(e)}")
        raise Exception(f"Failed to initialize credits: {str(e)}")


@router.get("/balance")
async def get_credit_balance(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's current credit balance"""
    try:
        # Initialize if doesn't exist
        await initialize_user_credits(db, user_id)
        
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
            
            # Calculate time elapsed since last refill (in seconds)
            time_elapsed = (now - last_refill).total_seconds()
            
            # Reset if more than 24 hours (86400 seconds) have passed
            if time_elapsed >= 86400:
                await db.user_credits.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "current_credits": daily_credits,
                        "daily_credits": daily_credits,
                        "daily_credits_used": 0,
                        "last_refill": now,
                        "next_refill": now + timedelta(days=1),
                        "tier": tier,
                        "updated_at": now
                    }}
                )
                # Get fresh record after reset
                credit_record = await db.user_credits.find_one({"user_id": user_id})
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
            
            # Calculate time elapsed since last refill (in seconds)
            time_elapsed = (now - last_refill).total_seconds()
            
            # Reset if more than 24 hours (86400 seconds) have passed
            if time_elapsed >= 86400:
                await db.user_credits.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "current_credits": daily_credits,
                        "daily_credits": daily_credits,
                        "daily_credits_used": 0,
                        "last_refill": now,
                        "next_refill": now + timedelta(days=1),
                        "tier": tier,
                        "updated_at": now
                    }}
                )
                # Get fresh record after reset
                credit_record = await db.user_credits.find_one({"user_id": user_id})
        
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


@router.get("/summary")
async def get_credits_summary(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get comprehensive credit summary with proper calculation"""
    try:
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in session")
        
        # Fetch user credit record
        credit_record = await db.user_credits.find_one({"user_id": user_id})
        
        if not credit_record:
            # Initialize credit record
            credit_record = {
                "user_id": user_id,
                "tier": current_user.get("tier", "free"),
                "daily_credits_total": 50 if current_user.get("tier") == "pro" else 10,
                "daily_credits_used": 0,
                "total_credits_purchased": 0,
                "total_credits_used": 0,
                "last_refill_date": datetime.utcnow(),
                "next_refill_time": datetime.utcnow() + timedelta(days=1),
                "credit_transactions": []
            }
            await db.user_credits.insert_one(credit_record)
        
        # Check if daily reset needed
        now = datetime.utcnow()
        last_refill = credit_record.get("last_refill_date", now)
        
        if now >= last_refill + timedelta(days=1):
            # Reset daily credits
            daily_total = 50 if current_user.get("tier") == "pro" else 10
            credit_record["daily_credits_used"] = 0
            credit_record["last_refill_date"] = now
            credit_record["next_refill_time"] = now + timedelta(days=1)
            
            await db.user_credits.update_one(
                {"user_id": user_id},
                {"$set": {
                    "daily_credits_used": 0,
                    "last_refill_date": now,
                    "next_refill_time": now + timedelta(days=1)
                }}
            )
        
        daily_total = credit_record.get("daily_credits_total", 10)
        daily_used = credit_record.get("daily_credits_used", 0)
        daily_remaining = max(0, daily_total - daily_used)
        
        return {
            "data": {
                "daily_credits_total": daily_total,
                "daily_credits_remaining": daily_remaining,
                "daily_credits_used": daily_used,
                "total_credits_used": credit_record.get("total_credits_used", 0),
                "total_credits_purchased": credit_record.get("total_credits_purchased", 0),
                "tier": current_user.get("tier", "free"),
                "last_refill_date": credit_record.get("last_refill_date"),
                "next_refill_time": credit_record.get("next_refill_time"),
                "hours_until_next_refill": round((credit_record.get("next_refill_time", now) - now).total_seconds() / 3600)
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching credits: {str(e)}")


@router.post("/deduct")
async def deduct_credits(
    amount: int,
    operation_type: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Deduct credits with transaction logging
    Used internally by scan, search, etc.
    """
    try:
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in session")
        
        # Get current credits
        credit_record = await db.user_credits.find_one({"user_id": user_id})
        
        if not credit_record:
            raise HTTPException(status_code=400, detail="Credit record not found")
        
        daily_used = credit_record.get("daily_credits_used", 0)
        daily_total = credit_record.get("daily_credits_total", 10)
        
        if daily_used + amount > daily_total:
            remaining = daily_total - daily_used
            return {
                "success": False,
                "message": f"Insufficient credits. Required: {amount}, Available: {remaining}",
                "credits_needed": amount,
                "current_credits": remaining
            }
        
        # Deduct credits
        new_daily_used = daily_used + amount
        total_used = credit_record.get("total_credits_used", 0) + amount
        
        await db.user_credits.update_one(
            {"user_id": user_id},
            {"$set": {
                "daily_credits_used": new_daily_used,
                "total_credits_used": total_used
            }}
        )
        
        # Log transaction
        await db.credit_transactions.insert_one({
            "user_id": user_id,
            "amount": amount,
            "operation_type": operation_type,
            "timestamp": datetime.utcnow(),
            "remaining_daily": daily_total - new_daily_used
        })
        
        return {
            "success": True,
            "message": f"{amount} credits deducted",
            "credits_deducted": amount,
            "daily_credits_remaining": daily_total - new_daily_used
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deducting credits: {str(e)}")


@router.get("/transactions")
async def get_credit_transactions(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get credit transaction history"""
    try:
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in session")
        
        transactions = await db.credit_transactions.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(50).to_list(None)
        
        return {
            "data": transactions,
            "total": len(transactions)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching transactions: {str(e)}")
