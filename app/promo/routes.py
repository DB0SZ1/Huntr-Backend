"""
Promotional trial management endpoints
CSV import, trial tracking, one-time use per user
"""
import csv
import io
import logging
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId

from app.database.connection import get_database
from app.admin.middleware import require_admin
from app.auth.jwt_handler import get_current_user_id
from app.promo.models import (
    PromoUserModel, PromoTrialModel, PromoImportRequest,
    BatchPromoResult, RedeemPromoRequest, PromoValidationResponse,
    PromoUserStatus
)
from config import TIER_LIMITS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/promo", tags=["Promotions"])


@router.post("/import-csv")
async def import_promo_users(
    file: UploadFile = File(..., description="CSV file with id,whatsapp,email,x_handle,niche,pro_tier_eligible"),
    trial_duration_days: int = Query(14, ge=1, le=90),
    trial_tier: str = Query("pro"),
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Import promotional users from CSV file
    CSV format:
    ```
    id,whatsapp,email,x_handle,niche,pro_tier_eligible,created_at,updated_at
    1,+2347036692250,nuradundu50@gmail.com,@noorhd_3,Developer,1,...
    ```
    
    Each user can redeem trial once by providing their X handle and phone number
    """
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be CSV format")
        
        # Read CSV file
        contents = await file.read()
        csv_text = contents.decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        if not csv_reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV file is empty")
        
        # Process rows
        results = {
            "successful": 0,
            "failed": 0,
            "duplicates": 0,
            "errors": []
        }
        
        processed_count = 0
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                # Extract and validate data
                twitter_handle = row.get('x_handle', '').strip().lstrip('@').lower()
                email = row.get('email', '').strip().lower()
                phone_number = row.get('whatsapp', '').strip()
                
                if not twitter_handle or not email or not phone_number:
                    results["errors"].append({
                        "row": row_num,
                        "error": "Missing required fields (x_handle, email, whatsapp)"
                    })
                    results["failed"] += 1
                    continue
                
                # Handle full URLs like https://x.com/handle
                if 'x.com/' in twitter_handle or 'twitter.com/' in twitter_handle:
                    twitter_handle = twitter_handle.split('/')[-1].split('?')[0]
                
                # Normalize phone number
                phone_normalized = ''.join(c for c in phone_number if c.isdigit() or c == '+')
                
                if len(phone_normalized) < 7:
                    results["errors"].append({
                        "row": row_num,
                        "error": f"Invalid phone number: {phone_number}"
                    })
                    results["failed"] += 1
                    continue
                
                # Check if user already exists in promo list
                existing = await db.promo_users.find_one({
                    "twitter_handle": twitter_handle,
                    "phone_number": phone_normalized
                })
                
                if existing:
                    results["duplicates"] += 1
                    logger.info(f"Promo user already exists: {twitter_handle}")
                    continue
                
                # Create promo user record
                user_record = {
                    "twitter_handle": twitter_handle,
                    "email": email,
                    "phone_number": phone_normalized,
                    "status": PromoUserStatus.AVAILABLE,
                    "trial_tier": trial_tier,
                    "trial_duration_days": trial_duration_days,
                    "created_at": datetime.utcnow(),
                    "redeemed_at": None,
                    "redeemed_by_user_id": None,
                    "redeemed_by_email": None,
                    "expires_at": datetime.utcnow() + timedelta(days=90),  # Redemption valid for 90 days
                    "notes": f"CSV import by {admin_id}"
                }
                
                # Insert promo user
                await db.promo_users.insert_one(user_record)
                
                logger.info(f"[OK] Promo user added: {twitter_handle}")
                results["successful"] += 1
            
            except Exception as e:
                results["errors"].append({
                    "row": row_num,
                    "error": str(e)
                })
                results["failed"] += 1
            
            processed_count += 1
        
        # Create index for faster lookups
        try:
            await db.promo_users.create_index([
                ("twitter_handle", 1),
                ("phone_number", 1)
            ], unique=False)
        except:
            pass
        
        # Log batch result
        await db.admin_actions.insert_one({
            "admin_id": admin_id,
            "action_type": "promo_import_csv",
            "details": {
                "file": file.filename,
                "rows_processed": processed_count,
                "successful": results["successful"],
                "failed": results["failed"],
                "duplicates": results["duplicates"],
                "trial_duration_days": trial_duration_days,
                "trial_tier": trial_tier
            },
            "timestamp": datetime.utcnow()
        })
        
        logger.info(f"[OK] CSV import complete: {results['successful']} users added")
        
        return BatchPromoResult(
            total_processed=processed_count,
            successful=results["successful"],
            failed=results["failed"],
            duplicates=results["duplicates"],
            errors=results["errors"][:50],
            message=f"Processed {processed_count} rows: {results['successful']} successful, {results['failed']} failed, {results['duplicates']} duplicates"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] CSV import failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process CSV file")


@router.post("/validate")
async def validate_promo(
    request: RedeemPromoRequest
) -> PromoValidationResponse:
    """
    Validate promo eligibility
    Check if X handle + phone number combo exists in CSV and hasn't been redeemed
    
    Args:
        request: X handle and phone number
        
    Returns:
        Validation result
    """
    try:
        db = await get_database()
        
        twitter_handle = request.twitter_handle.strip().lstrip('@').lower()
        phone_number = request.phone_number.strip()
        
        # Normalize phone
        phone_normalized = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        
        # Find matching promo user
        promo_user = await db.promo_users.find_one({
            "twitter_handle": twitter_handle,
            "phone_number": phone_normalized
        })
        
        if not promo_user:
            return PromoValidationResponse(
                valid=False,
                message="This X handle and phone number combination is not in our promotional list",
                error="NOT_FOUND"
            )
        
        # Check if already redeemed
        if promo_user['status'] == PromoUserStatus.REDEEMED:
            return PromoValidationResponse(
                valid=False,
                message="This promotional offer has already been redeemed",
                already_used=True,
                error="ALREADY_REDEEMED"
            )
        
        # Check if expired
        if promo_user['status'] == PromoUserStatus.EXPIRED:
            return PromoValidationResponse(
                valid=False,
                message="This promotional offer has expired",
                error="EXPIRED"
            )
        
        # Check expiration date
        if promo_user['expires_at'] < datetime.utcnow():
            await db.promo_users.update_one(
                {"_id": promo_user['_id']},
                {"$set": {"status": PromoUserStatus.EXPIRED}}
            )
            return PromoValidationResponse(
                valid=False,
                message="This promotional offer has expired",
                error="EXPIRED"
            )
        
        # Valid!
        return PromoValidationResponse(
            valid=True,
            message="You are eligible for a promotional trial!",
            tier=promo_user['trial_tier'],
            duration_days=promo_user['trial_duration_days']
        )
    
    except Exception as e:
        logger.error(f"[ERROR] Promo validation failed: {str(e)}")
        return PromoValidationResponse(
            valid=False,
            message="Error validating promotional offer",
            error="VALIDATION_ERROR"
        )


@router.post("/redeem")
async def redeem_promo(
    request: RedeemPromoRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Redeem promo (one-time use per user)
    User can only redeem once with their X handle + phone number
    
    Args:
        request: X handle and phone number to redeem
        user_id: Current user ID
        db: Database connection
        
    Returns:
        Trial information if successful
    """
    try:
        twitter_handle = request.twitter_handle.strip().lstrip('@').lower()
        phone_number = request.phone_number.strip()
        
        # Normalize phone
        phone_normalized = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        
        # Get user
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Find matching promo user
        promo_user = await db.promo_users.find_one({
            "twitter_handle": twitter_handle,
            "phone_number": phone_normalized
        })
        
        if not promo_user:
            raise HTTPException(
                status_code=404,
                detail="This X handle and phone number combination is not in our promotional list"
            )
        
        # ===== CRITICAL: Check if already redeemed =====
        if promo_user['status'] == PromoUserStatus.REDEEMED:
            raise HTTPException(
                status_code=400,
                detail=f"This promotional offer has already been redeemed on {promo_user['redeemed_at'].strftime('%Y-%m-%d')}. Each offer can only be used once."
            )
        
        # Check other statuses
        if promo_user['status'] == PromoUserStatus.EXPIRED:
            raise HTTPException(status_code=400, detail="This promotional offer has expired")
        
        # Check expiration date
        if promo_user['expires_at'] < datetime.utcnow():
            await db.promo_users.update_one(
                {"_id": promo_user['_id']},
                {"$set": {"status": PromoUserStatus.EXPIRED}}
            )
            raise HTTPException(status_code=400, detail="This promotional offer has expired")
        
        # Check if user already has active trial
        existing_trial = await db.promo_trials.find_one({
            "user_id": user_id,
            "trial_status": "active"
        })
        
        if existing_trial:
            raise HTTPException(
                status_code=400,
                detail="You already have an active promotional trial. Wait for it to expire before redeeming another offer."
            )
        
        # ===== MARK AS REDEEMED (CRITICAL) =====
        trial_expires = datetime.utcnow() + timedelta(days=promo_user['trial_duration_days'])
        
        await db.promo_users.update_one(
            {"_id": promo_user['_id']},
            {
                "$set": {
                    "status": PromoUserStatus.REDEEMED,
                    "redeemed_at": datetime.utcnow(),
                    "redeemed_by_user_id": user_id,
                    "redeemed_by_email": user.get('email')
                }
            }
        )
        
        # Create trial record
        trial = {
            "user_id": user_id,
            "email": user.get('email'),
            "twitter_handle": twitter_handle,
            "phone_number": phone_normalized,
            "trial_tier": promo_user['trial_tier'],
            "trial_status": "active",
            "started_at": datetime.utcnow(),
            "expires_at": trial_expires,
            "extended": False,
            "extended_until": None,
            "auto_downgraded": False,
            "downgrade_date": None,
            "original_tier": user.get('tier', 'free'),
            "notes": f"Redeemed from CSV promo list"
        }
        
        await db.promo_trials.insert_one(trial)
        
        # Upgrade user tier immediately
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "tier": promo_user['trial_tier'],
                    "promo_trial_id": trial.get('_id'),
                    "trial_started_at": datetime.utcnow(),
                    "trial_expires_at": trial_expires
                }
            }
        )
        
        logger.info(f"[OK] Promo redeemed: {twitter_handle} ({user_id}). Upgraded to {promo_user['trial_tier']} until {trial_expires.isoformat()}")
        
        return {
            "success": True,
            "message": f"Successfully activated {promo_user['trial_tier'].upper()} tier for {promo_user['trial_duration_days']} days",
            "tier": promo_user['trial_tier'],
            "expires_at": trial_expires.isoformat(),
            "duration_days": promo_user['trial_duration_days']
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Promo redemption failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to redeem promotional offer")


@router.get("/available")
async def get_available_promos(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get all available promo users (not yet redeemed)
    """
    try:
        users = await db.promo_users.find({
            "status": PromoUserStatus.AVAILABLE
        }).to_list(length=1000)
        
        return {
            "total": len(users),
            "available": len(users),
            "users": users
        }
    
    except Exception as e:
        logger.error(f"[ERROR] Failed to get available promos: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve promo list")


@router.get("/redeemed")
async def get_redeemed_promos(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get all redeemed promo users (admin only)
    """
    try:
        users = await db.promo_users.find({
            "status": PromoUserStatus.REDEEMED
        }).sort("redeemed_at", -1).to_list(length=1000)
        
        formatted = []
        for user in users:
            user['_id'] = str(user['_id'])
            formatted.append(user)
        
        return {
            "total": len(formatted),
            "redeemed": len(formatted),
            "users": formatted
        }
    
    except Exception as e:
        logger.error(f"[ERROR] Failed to get redeemed promos: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve redeemed list")


@router.get("/active-trials")
async def get_active_trials(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get all active promotional trials
    """
    try:
        trials = await db.promo_trials.find({
            "trial_status": "active"
        }).sort("started_at", -1).to_list(length=1000)
        
        formatted = []
        for trial in trials:
            trial['_id'] = str(trial['_id'])
            days_remaining = (trial['expires_at'] - datetime.utcnow()).days
            trial['days_remaining'] = max(0, days_remaining)
            formatted.append(trial)
        
        return {
            "total": len(formatted),
            "active": len(formatted),
            "trials": formatted
        }
    
    except Exception as e:
        logger.error(f"[ERROR] Failed to get active trials: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trials")


@router.post("/check-expirations")
async def check_trial_expirations(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Check for expired trials and downgrade users
    Called daily by scheduler
    """
    try:
        now = datetime.utcnow()
        
        # Find expired trials
        expired_trials = await db.promo_trials.find({
            "trial_status": "active",
            "expires_at": {"$lte": now},
            "auto_downgraded": False
        }).to_list(length=1000)
        
        downgraded_count = 0
        
        for trial in expired_trials:
            user_id = trial['user_id']
            
            try:
                await downgrade_user_from_trial(user_id, db)
                
                await db.promo_trials.update_one(
                    {"_id": trial['_id']},
                    {
                        "$set": {
                            "trial_status": "expired",
                            "auto_downgraded": True,
                            "downgrade_date": datetime.utcnow()
                        }
                    }
                )
                
                downgraded_count += 1
                logger.info(f"[OK] Auto-downgraded user {user_id} after trial expiration")
            
            except Exception as e:
                logger.error(f"[ERROR] Failed to downgrade user {user_id}: {str(e)}")
        
        return {
            "message": f"Downgraded {downgraded_count} users",
            "downgraded_count": downgraded_count
        }
    
    except Exception as e:
        logger.error(f"[ERROR] Failed to check expirations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process expirations")


async def downgrade_user_from_trial(user_id: str, db: AsyncIOMotorDatabase):
    """
    Downgrade user from trial tier back to free
    Preserves saved opportunities, deletes extra niches
    """
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            logger.warning(f"User not found for downgrade: {user_id}")
            return
        
        trial = await db.promo_trials.find_one({"user_id": user_id})
        original_tier = trial.get('original_tier', 'free') if trial else 'free'
        
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "tier": original_tier,
                    "trial_ended_at": datetime.utcnow()
                },
                "$unset": {
                    "promo_trial_id": "",
                    "trial_started_at": "",
                    "trial_expires_at": ""
                }
            }
        )
        
        tier_limits = TIER_LIMITS.get(original_tier, TIER_LIMITS['free'])
        max_niches = tier_limits.get('max_niches', 1)
        
        niches = await db.niche_configs.find({"user_id": user_id})\
            .sort("created_at", 1)\
            .to_list(length=100)
        
        if len(niches) > max_niches:
            niches_to_delete = niches[max_niches:]
            niche_ids_to_delete = [niche['_id'] for niche in niches_to_delete]
            
            await db.niche_configs.delete_many({
                "_id": {"$in": niche_ids_to_delete}
            })
            
            logger.info(f"[OK] Deleted {len(niche_ids_to_delete)} extra niches for user {user_id}")
        
        logger.info(f"[OK] Downgraded user {user_id} to {original_tier} tier")
    
    except Exception as e:
        logger.error(f"[ERROR] Error downgrading user {user_id}: {str(e)}", exc_info=True)
        raise
