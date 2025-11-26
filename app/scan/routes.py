"""
Scan Management Routes
Manually trigger scans (free users) or automatic scheduling (paid tiers)
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime
import uuid

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id
from app.credits.manager import CreditManager
from config import TIER_LIMITS, CREDIT_COSTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scans", tags=["Scans"])


@router.post("/start")
async def start_scan(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Start a new scan
    - FREE tier: Manual only (costs 5 credits)
    - PRO/PREMIUM: Manual or automatic
    
    Returns:
        Scan ID and status
    """
    try:
        # Get user
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        tier = user.get("tier", "free")
        
        # Get user's niches
        niches = await db.niche_configs.find({
            "user_id": user_id,
            "is_active": True
        }).to_list(length=100)
        
        if not niches:
            raise HTTPException(
                status_code=400,
                detail="Create at least one niche before scanning"
            )
        
        # ✅ CRITICAL: Check credits
        credit_cost = CREDIT_COSTS.get("scan", 5)
        
        has_credits = await CreditManager.has_sufficient_credits(user_id, credit_cost, db)
        
        if not has_credits:
            return {
                "success": False,
                "message": f"Insufficient credits. This scan requires {credit_cost} credits.",
                "credits_needed": credit_cost,
                "current_credits": await CreditManager.get_balance(user_id, db)
            }
        
        # ✅ Create scan record
        scan_id = str(uuid.uuid4())
        
        scan_record = {
            "scan_id": scan_id,
            "user_id": user_id,
            "tier": tier,
            "status": "processing",
            "niches": [n.get("_id") for n in niches],
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "opportunities_found": 0,
            "platforms_scanned": [],
            "failed_platforms": [],
            "credits_used": credit_cost
        }
        
        await db.scan_history.insert_one(scan_record)
        
        logger.info(f"Scan started: {scan_id} for user {user_id}")
        
        return {
            "success": True,
            "scan_id": scan_id,
            "status": "processing",
            "niches_count": len(niches),
            "credit_cost": credit_cost,
            "message": f"Scan started. Scanning {len(niches)} niche(s) on available platforms..."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting scan: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start scan")


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