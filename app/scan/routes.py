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
from config import TIER_LIMITS, CREDIT_COSTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scans", tags=["Scans"])


@router.post("/start")
async def start_scan(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Start a scan with proper credit deduction"""
    try:
        user_id = current_user.get("_id")
        CREDITS_REQUIRED = 5
        
        # ✅ STEP 1: Get current credit balance
        credit_record = await db.user_credits.find_one({"user_id": user_id})
        
        if not credit_record:
            raise HTTPException(status_code=400, detail="Credit record not initialized")
        
        # ✅ STEP 2: Check daily reset
        now = datetime.utcnow()
        last_refill = credit_record.get("last_refill_date", now)
        
        if now >= last_refill + timedelta(days=1):
            daily_total = 50 if current_user.get("tier") == "pro" else 10
            await db.user_credits.update_one(
                {"user_id": user_id},
                {"$set": {
                    "daily_credits_used": 0,
                    "daily_credits_total": daily_total,
                    "last_refill_date": now,
                    "next_refill_time": now + timedelta(days=1)
                }}
            )
            credit_record = await db.user_credits.find_one({"user_id": user_id})
        
        # ✅ STEP 3: Calculate available credits
        daily_total = credit_record.get("daily_credits_total", 10)
        daily_used = credit_record.get("daily_credits_used", 0)
        available_credits = daily_total - daily_used
        
        # ✅ STEP 4: Check if sufficient
        if available_credits < CREDITS_REQUIRED:
            return {
                "success": False,
                "message": f"Insufficient credits. This scan requires {CREDITS_REQUIRED} credits.",
                "credits_needed": CREDITS_REQUIRED,
                "current_credits": available_credits  # ← FIX: Use calculated available credits
            }
        
        # ✅ STEP 5: Deduct credits
        new_daily_used = daily_used + CREDITS_REQUIRED
        total_used = credit_record.get("total_credits_used", 0) + CREDITS_REQUIRED
        
        await db.user_credits.update_one(
            {"user_id": user_id},
            {"$set": {
                "daily_credits_used": new_daily_used,
                "total_credits_used": total_used
            }}
        )
        
        # ✅ STEP 6: Log transaction
        await db.credit_transactions.insert_one({
            "user_id": user_id,
            "amount": CREDITS_REQUIRED,
            "operation_type": "scan_started",
            "timestamp": now,
            "remaining_daily": daily_total - new_daily_used
        })
        
        # Create scan record
        scan_record = {
            "user_id": user_id,
            "status": "running",
            "credits_used": CREDITS_REQUIRED,
            "started_at": now,
            "results": []
        }
        
        result = await db.scans.insert_one(scan_record)
        
        return {
            "success": True,
            "message": "Scan started",
            "scan_id": str(result.inserted_id),
            "credits_deducted": CREDITS_REQUIRED,
            "credits_remaining": daily_total - new_daily_used
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting scan: {str(e)}")


@router.get("/status/{scan_id}")
async def get_scan_status(
    scan_id: str,
    user_id: str = Depends(get_current_user_id),
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
    user_id: str = Depends(get_current_user_id),
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