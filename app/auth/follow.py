"""
Twitter Follow Modal Management
Tracks if users have followed the official account
"""
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime
from pydantic import BaseModel
import logging

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth/follow", tags=["Follow"])


class FollowStatusResponse(BaseModel):
    """Response for follow status"""
    has_followed: bool
    should_show_modal: bool
    twitter_url: str
    message: str


class MarkFollowedRequest(BaseModel):
    """Request to mark user as followed"""
    followed: bool = True


@router.get("/status")
async def get_follow_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> FollowStatusResponse:
    """
    Get user's follow status
    Shows modal on first login or if user hasn't followed yet
    
    Args:
        user_id: Current user ID
        db: Database connection
        
    Returns:
        Follow status and whether to show modal
    """
    try:
        # Get user
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user has followed
        has_followed = user.get('twitter_follow_status', {}).get('has_followed', False)
        follow_prompted_at = user.get('twitter_follow_status', {}).get('prompted_at')
        
        # Determine if we should show modal
        # Show if: never followed AND (never prompted OR prompted more than 7 days ago)
        should_show = False
        
        if not has_followed:
            if not follow_prompted_at:
                # First time - always show
                should_show = True
            else:
                # Check if 7 days have passed since last prompt
                from datetime import timedelta
                days_since_prompt = (datetime.utcnow() - follow_prompted_at).days
                if days_since_prompt >= 7:
                    should_show = True
        
        logger.info(
            f"Follow status check for user {user_id}: "
            f"has_followed={has_followed}, should_show={should_show}"
        )
        
        return FollowStatusResponse(
            has_followed=has_followed,
            should_show_modal=should_show,
            twitter_url="https://x.com/db0sz1",
            message="Follow @db0sz1 to get exclusive updates and opportunities!"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting follow status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get follow status")


@router.post("/mark-followed")
async def mark_user_followed(
    request: MarkFollowedRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Mark user as having followed the Twitter account
    Called after user completes the follow action
    
    Args:
        request: Follow status request
        user_id: Current user ID
        db: Database connection
        
    Returns:
        Confirmation
    """
    try:
        # Update user follow status
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "twitter_follow_status": {
                        "has_followed": request.followed,
                        "marked_at": datetime.utcnow(),
                        "prompted_at": datetime.utcnow()
                    }
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"User {user_id} marked as followed: {request.followed}")
        
        return {
            "success": True,
            "message": "Thank you for following! You'll get exclusive updates.",
            "has_followed": request.followed
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking user followed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update follow status")


@router.post("/dismiss-modal")
async def dismiss_follow_modal(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Dismiss the follow modal (user chose not to follow for now)
    Will show again after 7 days
    
    Args:
        user_id: Current user ID
        db: Database connection
        
    Returns:
        Confirmation
    """
    try:
        # Update user - record that we prompted them
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "twitter_follow_status.prompted_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"User {user_id} dismissed follow modal")
        
        return {
            "success": True,
            "message": "Modal dismissed. We'll remind you in 7 days."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dismissing modal: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to dismiss modal")
