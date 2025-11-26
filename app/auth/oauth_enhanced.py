"""
Enhanced Auth Routes
Additional profile and onboarding endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id
from cryptography.fernet import Fernet
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class ProfileUpdateRequest(BaseModel):
    """Request model for profile updates"""
    name: Optional[str] = None
    whatsapp_number: Optional[str] = None
    email_notifications: Optional[bool] = None
    whatsapp_notifications: Optional[bool] = None
    timezone: Optional[str] = None


class OnboardingDataRequest(BaseModel):
    """Request model for onboarding data"""
    profile_type: str
    other_niche: Optional[str] = None
    interests: List[str]
    work_preferences: List[str]
    whatsapp_number: str
    email: Optional[str] = None
    enable_notifications: bool = True
    enable_daily_digest: bool = True


class TwilioConfigRequest(BaseModel):
    """Request model for Twilio configuration"""
    account_sid: str
    auth_token: str
    whatsapp_number: str


@router.put("/profile")
async def update_profile(
    data: ProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Update user profile settings
    """
    try:
        update_data = {}
        
        if data.name:
            update_data["name"] = data.name
        
        # Update settings
        if any([
            data.whatsapp_number is not None,
            data.email_notifications is not None,
            data.whatsapp_notifications is not None,
            data.timezone is not None
        ]):
            settings_update = {}
            
            if data.email_notifications is not None:
                settings_update["settings.email_notifications"] = data.email_notifications
            
            if data.whatsapp_notifications is not None:
                settings_update["settings.whatsapp_notifications"] = data.whatsapp_notifications
            
            if data.timezone is not None:
                settings_update["settings.timezone"] = data.timezone
            
            update_data.update(settings_update)
        
        if data.whatsapp_number:
            update_data["settings.whatsapp_number"] = data.whatsapp_number
        
        if not update_data:
            return {"message": "No changes to update"}
        
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"Profile updated for user {user_id}")
        
        return {"message": "Profile updated successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update profile")


@router.post("/onboarding")
async def save_onboarding_data(
    data: OnboardingDataRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Save complete onboarding data and create default niche
    """
    try:
        # Update user profile with onboarding data
        update_data = {
            "settings.profile_type": data.profile_type,
            "settings.interests": data.interests,
            "settings.work_preferences": data.work_preferences,
            "settings.whatsapp_number": data.whatsapp_number,
            "settings.notifications_enabled": data.enable_notifications,
            "settings.email_notifications": data.enable_notifications,
            "settings.whatsapp_notifications": data.enable_notifications,
            "onboarding_completed": True,
            "onboarding_completed_at": datetime.utcnow()
        }
        
        if data.other_niche:
            update_data["settings.other_niche"] = data.other_niche
        
        if data.email:
            update_data["settings.secondary_email"] = data.email
        
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        
        # Create default niche based on profile type
        niche_name = data.other_niche if data.profile_type == "other" else f"{data.profile_type.title()} Jobs"
        
        # Generate keywords from interests and profile type
        keywords = [data.profile_type.lower()]
        if data.other_niche:
            keywords.append(data.other_niche.lower())
        keywords.extend([interest.lower() for interest in data.interests[:5]])
        
        # Determine platforms based on user tier
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        from config import TIER_LIMITS
        platforms = TIER_LIMITS[user['tier']]['platforms']
        
        # Create default niche
        niche_data = {
            "user_id": user_id,
            "name": niche_name,
            "description": f"Opportunities matching {niche_name}",
            "keywords": list(set(keywords)),  # Remove duplicates
            "excluded_keywords": [],
            "platforms": platforms,
            "min_confidence": 60,
            "is_active": True,
            "priority": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "total_matches": 0
        }
        
        await db.niche_configs.insert_one(niche_data)
        
        logger.info(f"Onboarding completed for user {user_id}")
        
        return {
            "message": "Onboarding completed successfully",
            "niche_created": True
        }
    
    except Exception as e:
        logger.error(f"Error saving onboarding data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save onboarding data")


@router.post("/twilio-config")
async def save_twilio_config(
    data: TwilioConfigRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Save encrypted Twilio credentials for user
    """
    try:
        # Encrypt credentials
        encryption_key = settings.ENCRYPTION_KEY.encode()
        fernet = Fernet(encryption_key)
        
        credentials = {
            "account_sid": data.account_sid,
            "auth_token": data.auth_token,
            "whatsapp_number": data.whatsapp_number
        }
        
        import json
        credentials_json = json.dumps(credentials)
        encrypted_credentials = fernet.encrypt(credentials_json.encode()).decode()
        
        # Save to database
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"encrypted_twilio_credentials": encrypted_credentials}}
        )
        
        logger.info(f"Twilio credentials saved for user {user_id}")
        
        return {"message": "Twilio configuration saved successfully"}
    
    except Exception as e:
        logger.error(f"Error saving Twilio config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save Twilio configuration")


@router.get("/onboarding-status")
async def check_onboarding_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Check if user has completed onboarding
    """
    try:
        user = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"onboarding_completed": 1}
        )
        
        return {
            "completed": user.get('onboarding_completed', False)
        }
    
    except Exception as e:
        logger.error(f"Error checking onboarding status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check onboarding status")