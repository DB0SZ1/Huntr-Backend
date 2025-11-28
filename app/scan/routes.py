"""
Scan Management Routes
Manually trigger scans (free users) or automatic scheduling (paid tiers)
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import uuid
import asyncio
import time

from app.database.connection import get_database, check_database_health
from app.auth.oauth import get_current_user
from app.credits.manager import CreditManager
from app.credits.routes import initialize_user_credits
from config import TIER_LIMITS, CREDIT_COSTS
from app.jobs.scraper import scrape_platforms_for_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scans", tags=["Scans"])


async def perform_scan_background(
    scan_id: str,
    user_id: str,
    db: AsyncIOMotorDatabase
):
    """
    Background task to perform actual scanning
    Runs asynchronously after scan is created
    
    Args:
        scan_id: The scan ID (string) to track progress
        user_id: The user ID (string) to get tier
        db: Database connection
    """
    try:
        logger.info(f"[SCAN] Background scan task started: {scan_id}")
        
        # Get user's tier to determine which platforms to scan
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"[SCAN] User not found: {user_id}")
            await db.scan_history.update_one(
                {"scan_id": scan_id},
                {"$set": {"status": "failed", "error": "User not found"}}
            )
            return
        
        user_tier = user.get("tier", "free")
        
        # Get platforms for this tier from config
        tier_config = TIER_LIMITS.get(user_tier, TIER_LIMITS.get("free", {}))
        platforms_to_scan = tier_config.get("platforms", ["Twitter/X", "Reddit"])
        
        logger.info(f"[SCAN] Scraping for user {user_id} (tier: {user_tier}) on platforms: {platforms_to_scan}")
        
        # Perform the actual scraping with the platforms list
        results = await scrape_platforms_for_user(
            platforms=platforms_to_scan,
            max_concurrent=3
        )
        
        # Extract opportunities from results
        all_opportunities = results.get("opportunities", [])
        stats = results.get("stats", {})
        
        # APPLY TIER-BASED LIMITS: Free=4, Pro=3, Premium=3
        tier_limits = {
            "free": 4,
            "pro": 3,
            "premium": 3
        }
        max_opps = tier_limits.get(user_tier, 4)
        opportunities = all_opportunities[:max_opps]
        
        logger.info(f"[SCAN] Tier {user_tier}: Limiting {len(all_opportunities)} to {len(opportunities)} opportunities")
        
        # Store opportunities to user_opportunities collection ONLY (single source of truth)
        now = datetime.utcnow()
        stored_count = 0
        for opp in opportunities:
            try:
                # Check if this opportunity already exists for this user
                existing = await db.user_opportunities.find_one({
                    "user_id": user_id,
                    "external_id": opp.get("id")
                })
                
                if not existing:
                    # Store as user opportunity with proper parsing
                    title = opp.get("title", "No title")
                    if isinstance(title, str):
                        # Clean up title - remove newlines and truncate
                        title = title.replace('\n', ' ')[:100]
                    
                    user_opp = {
                        "user_id": user_id,
                        "scan_id": scan_id,
                        "external_id": opp.get("id", f"opp_{int(time.time())}_{stored_count}"),
                        "title": title,
                        "description": opp.get("description", "")[:500],
                        "platform": opp.get("platform", "Unknown"),
                        "url": opp.get("url", ""),
                        "contact": opp.get("contact"),
                        "telegram": opp.get("telegram"),
                        "twitter": opp.get("twitter"),
                        "website": opp.get("website"),
                        "email": opp.get("email"),
                        "timestamp": opp.get("timestamp"),
                        "metadata": opp.get("metadata", {}),
                        "found_at": now,
                        "is_saved": False,
                        "is_applied": False,
                        "notes": "",
                        "match_score": 0
                    }
                    
                    # Check for duplicate before inserting
                    existing = await db.user_opportunities.find_one({
                        "user_id": user_id,
                        "external_id": user_opp.get("external_id")
                    })
                    
                    if not existing:
                        await db.user_opportunities.insert_one(user_opp)
                        stored_count += 1
                    else:
                        logger.debug(f"[SCAN] Skipping duplicate opportunity: {user_opp.get('external_id')}")
            except Exception as e:
                logger.warning(f"[SCAN] Failed to store opportunity: {str(e)}")
        
        logger.info(f"[SCAN] Stored {stored_count} opportunities to user_opportunities for user {user_id}")
        
        # Update scan_history record with results
        await db.scan_history.update_one(
            {"scan_id": scan_id},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": datetime.utcnow(),
                    "opportunities_found": len(opportunities),
                    "platforms_scanned": platforms_to_scan,
                    "results": opportunities,
                    "stats": stats,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Also update scans collection for consistency
        await db.scans.update_one(
            {"_id": ObjectId(scan_id)},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": datetime.utcnow(),
                    "opportunities_found": len(opportunities),
                    "platforms_scanned": platforms_to_scan,
                    "results": opportunities,
                    "stats": stats,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"[SCAN] ✅ Scan completed: {scan_id} - Found {len(opportunities)} opportunities on {len(platforms_to_scan)} platforms")
    
    except Exception as e:
        logger.error(f"[SCAN] ❌ Background scan error for {scan_id}: {str(e)}", exc_info=True)
        try:
            # Update both collections with error status
            error_msg = str(e)
            await db.scan_history.update_one(
                {"scan_id": scan_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": error_msg,
                        "completed_at": datetime.utcnow()
                    }
                }
            )
            await db.scans.update_one(
                {"_id": ObjectId(scan_id)},
                {
                    "$set": {
                        "status": "failed",
                        "error": error_msg,
                        "completed_at": datetime.utcnow()
                    }
                }
            )
        except Exception as err:
            logger.error(f"[SCAN] Failed to update error status: {err}")


@router.post("/start")
async def start_scan(
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db = Depends(get_database)
):
    """Start a scan with proper credit deduction and background scraping"""
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
        last_refill = credit_record.get("last_refill")
        current_credits = credit_record.get("current_credits", 0)
        
        # Determine if we need to reset credits
        needs_reset = False
        
        if last_refill is None:
            # First time setup
            needs_reset = True
        else:
            # Calculate time elapsed since last refill
            time_elapsed = (now - last_refill).total_seconds()
            
            # Reset if more than 24 hours (86400 seconds) have passed
            if time_elapsed >= 86400:
                needs_reset = True
        
        # Also reset if current_credits is 0 and we haven't reset today
        if current_credits == 0 and not needs_reset:
            if last_refill is not None:
                time_elapsed = (now - last_refill).total_seconds()
                # If less than 24 hours but credits are 0, likely used all credits today
                # Don't reset - user has to wait 24 hours
                pass
            else:
                # First time, no last_refill, reset
                needs_reset = True
        
        if needs_reset:
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
            logger.info(f"Credits reset for user {user_id}: {daily_credits} credits (tier: {user_tier})")
            # Get fresh record after reset
            credit_record = await db.user_credits.find_one({"user_id": user_id})
        
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
        
        # ✅ STEP 9: Create scan record in both collections for tracking
        scan_record = {
            "user_id": user_id,
            "status": "running",
            "credits_used": CREDITS_REQUIRED,
            "started_at": now,
            "results": []
        }
        
        result = await db.scans.insert_one(scan_record)
        scan_id = str(result.inserted_id)
        
        # Also store in scan_history for status tracking (with string scan_id)
        await db.scan_history.insert_one({
            "scan_id": scan_id,  # Use string ID for easy lookup
            "user_id": user_id,
            "status": "running",
            "credits_used": CREDITS_REQUIRED,
            "started_at": now,
            "opportunities_found": 0,
            "platforms_scanned": [],
            "results": []
        })
        
        # ✅ STEP 10: Trigger background scraping task
        background_tasks.add_task(
            perform_scan_background,
            scan_id=scan_id,
            user_id=user_id,
            db=db
        )
        
        logger.info(f"Scan started for user {user_id}: {CREDITS_REQUIRED} credits deducted (tier: {user_tier}) - background task queued")
        
        return {
            "success": True,
            "message": "Scan started successfully. Background scraping in progress...",
            "scan_id": str(result.inserted_id),
            "status": "running",
            "credits_deducted": CREDITS_REQUIRED,
            "credits_remaining": new_available,
            "tier": user_tier,
            "daily_credits": daily_credits,
            "note": "Check /api/scans/status/{scan_id} for updates"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting scan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting scan: {str(e)}")


@router.get("/status/{scan_id}")
async def get_scan_status(
    scan_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get status of a scan (only own scans)
    """
    try:
        # Get user_id from current_user dict
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in session")
        
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
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = 20
):
    """
    Get user's scan history (only own scans)
    """
    try:
        # Get user_id from current_user dict
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in session")
        
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