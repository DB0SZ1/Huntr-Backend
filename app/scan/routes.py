"""
Scan Management Routes
Manually trigger scans (free users) or automatic scheduling (paid tiers)
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import uuid

from app.database.connection import get_database
from app.auth.oauth import get_current_user
from app.credits.manager import CreditManager
from app.credits.routes import initialize_user_credits
from config import TIER_LIMITS, CREDIT_COSTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scans", tags=["Scans"])


@router.post("/start")
async def start_scan(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Start a scan with proper credit deduction based on user tier"""
    try:
        # Get user_id from current_user (key is "id", not "_id")
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in session")
        
        CREDITS_REQUIRED = 5
        
        # ✅ STEP 1: Initialize credits if not exists (using tier-based values from config)
        await initialize_user_credits(db, user_id)
        
        
        # ✅ STEP 2: Get user and determine tier
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_tier = user.get("tier", "free")
        daily_credits = TIER_LIMITS.get(user_tier, {}).get("daily_credits", 10)
        
        # ✅ STEP 3: Get or create credit record with daily reset
        credit_record = await db.user_credits.find_one({"user_id": user_id})
        
        if not credit_record:
            raise HTTPException(
                status_code=400,
                detail="Credit record not initialized"
            )
        
        # ✅ STEP 4: Check if daily reset is needed
        now = datetime.utcnow()
        last_refill = credit_record.get("last_refill", now)
        
        # Reset if more than 24 hours have passed
        if (now - last_refill).days >= 1 or (now - last_refill).total_seconds() >= 86400:
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
            credit_record = await db.user_credits.find_one({"user_id": user_id})
            logger.info(f"Credits reset for user {user_id}: {daily_credits} credits (tier: {user_tier})")
        
        # ✅ STEP 5: Get current available credits
        available_credits = credit_record.get("current_credits", 0)
        
        # ✅ STEP 6: Check if sufficient credits
        if available_credits < CREDITS_REQUIRED:
            next_refill = credit_record.get("next_refill", now + timedelta(days=1))
            hours_until = max(0, round((next_refill - now).total_seconds() / 3600))
            
            return {
                "success": False,
                "error": "insufficient_credits",
                "message": f"Insufficient credits. This scan requires {CREDITS_REQUIRED} credits.",
                "credits_needed": CREDITS_REQUIRED,
                "credits_available": available_credits,
                "credits_per_day": daily_credits,
                "next_refill_in_hours": hours_until
            }
        
        # ✅ STEP 7: Deduct credits
        new_available = available_credits - CREDITS_REQUIRED
        daily_used = credit_record.get("daily_credits_used", 0) + CREDITS_REQUIRED
        total_used = credit_record.get("total_credits_used", 0) + CREDITS_REQUIRED
        
        await db.user_credits.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "current_credits": new_available,
                    "daily_credits_used": daily_used,
                    "total_credits_used": total_used,
                    "updated_at": now
                }
            }
        )
        
        # ✅ STEP 8: Log transaction
        await db.credit_transactions.insert_one({
            "user_id": user_id,
            "amount": CREDITS_REQUIRED,
            "operation_type": "scan_started",
            "timestamp": now,
            "remaining_credits": new_available,
            "tier": user_tier
        })
        
        # ✅ STEP 9: Create scan record
        scan_record = {
            "user_id": user_id,
            "status": "running",
            "credits_used": CREDITS_REQUIRED,
            "started_at": now,
            "results": []
        }
        
        result = await db.scans.insert_one(scan_record)
        
        logger.info(f"Scan started for user {user_id}: {CREDITS_REQUIRED} credits deducted (tier: {user_tier})")
        
        return {
            "success": True,
            "message": "Scan started successfully",
            "scan_id": str(result.inserted_id),
            "credits_deducted": CREDITS_REQUIRED,
            "credits_remaining": new_available,
            "tier": user_tier,
            "daily_credits": daily_credits
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting scan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting scan: {str(e)}")


@router.get("/status/{scan_id}")
async def get_scan_status(
    scan_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get status of a scan (only own scans)
    """
    try:
        scan = await db.scan_history.find_one({
            "scan_id": scan_id,
            "user_id": user_id  # ✅ Only own scans
        })
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        return {
            "scan_id": scan.get("scan_id"),
            "status": scan.get("status"),
            "started_at": scan.get("started_at").isoformat(),
            "completed_at": scan.get("completed_at").isoformat() if scan.get("completed_at") else None,
            "opportunities_found": scan.get("opportunities_found", 0),
            "platforms_scanned": scan.get("platforms_scanned", []),
            "credits_used": scan.get("credits_used", 0)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scan status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get scan status")


@router.get("/history")
async def get_scan_history(
    user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = 20
):
    """
    Get user's scan history (only own scans)
    """
    try:
        scans = await db.scan_history.find({
            "user_id": user_id  # ✅ Only own scans
        }).sort("started_at", -1).limit(limit).to_list(length=limit)
        
        for scan in scans:
            scan["_id"] = str(scan["_id"])
        
        return {
            "total": len(scans),
            "scans": scans
        }
    
    except Exception as e:
        logger.error(f"Error getting scan history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get scan history")