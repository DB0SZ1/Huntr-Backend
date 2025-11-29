"""
Traditional Email/Password Authentication
Signup, login, password reset, email verification
"""
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime, timedelta
from bson import ObjectId
import logging
import re

from app.database.connection import get_database
from app.auth.jwt_handler import create_access_token, create_refresh_token, get_current_user_id
from app.auth.password_handler import PasswordHandler
from app.notifications.email import send_verification_email, send_password_reset_email
from config import settings, TIER_LIMITS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class SignupRequest(BaseModel):
    """User signup request"""
    email: EmailStr
    password: str
    name: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    @validator('name')
    def validate_name(cls, v):
        if len(v) < 2:
            raise ValueError('Name must be at least 2 characters long')
        return v


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    """Email verification request"""
    token: str


class ForgotPasswordRequest(BaseModel):
    """Password reset request"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Password reset with token"""
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v


class ChangePasswordRequest(BaseModel):
    """Change password for authenticated user"""
    old_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v


@router.post("/signup")
async def signup(
    data: SignupRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Traditional signup with email and password
    Sends verification email
    """
    try:
        # Check if user already exists
        existing_user = await db.users.find_one({"email": data.email})
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = PasswordHandler.hash_password(data.password)
        
        # Create new user
        new_user = {
            "email": data.email,
            "name": data.name,
            "password_hash": hashed_password,
            "auth_method": "email",  # Track auth method
            "google_id": None,
            "profile_picture": None,
            "tier": "free",
            "is_active": True,
            "email_verified": False,
            "email_verified_at": None,
            "created_at": datetime.utcnow(),
            "last_login": None,
            "settings": {
                "notifications_enabled": True,
                "email_notifications": True,
                "whatsapp_notifications": False
            }
        }
        
        result = await db.users.insert_one(new_user)
        user_id = str(result.inserted_id)
        
        # Generate verification token
        verification_token = PasswordHandler.generate_verification_token(data.email)
        
        # Store token in database
        await db.email_tokens.insert_one({
            "user_id": user_id,
            "email": data.email,
            "token": verification_token,
            "type": "verification",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=1)
        })
        
        # Send verification email
        try:
            await send_verification_email(data.email, data.name, verification_token)
            email_sent = True
        except Exception as e:
            logger.warning(f"Failed to send verification email: {str(e)}")
            email_sent = False
        
        # Create default free subscription - only if one doesn't exist
        existing_subscription = await db.subscriptions.find_one({"user_id": user_id})
        if not existing_subscription:
            subscription_doc = {
                "user_id": user_id,
                "tier": "free",
                "status": "active",
                "payment_method": None,
                "current_period_start": datetime.utcnow(),
                "current_period_end": datetime.utcnow() + timedelta(days=365),
                "created_at": datetime.utcnow()
            }
            # Only include paystack_subscription_id if it has a value
            # This avoids unique index constraint violations on null values
            await db.subscriptions.insert_one(subscription_doc)
        
        logger.info(f"New user registered: {data.email} (ID: {user_id})")
        
        return {
            "message": "Signup successful",
            "user_id": user_id,
            "email_verification_sent": email_sent,
            "next_step": "Verify your email to activate your account"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(status_code=500, detail="Signup failed")


@router.post("/login")
async def login(
    data: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Traditional login with email and password
    Returns JWT tokens
    """
    try:
        # Find user by email
        user = await db.users.find_one({"email": data.email})
        
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        # Check if user has password (might be OAuth-only)
        if not user.get('password_hash'):
            raise HTTPException(
                status_code=400,
                detail="This email is registered with Google OAuth. Use Google to login."
            )
        
        # Verify password
        if not PasswordHandler.verify_password(data.password, user['password_hash']):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        # Check if email is verified
        if not user.get('email_verified', False):
            raise HTTPException(
                status_code=403,
                detail="Please verify your email first"
            )
        
        if not user.get('is_active', True):
            raise HTTPException(
                status_code=403,
                detail="Account is disabled"
            )
        
        user_id = str(user['_id'])
        
        # Update last login
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        # Generate tokens
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)
        
        logger.info(f"User logged in: {data.email} (ID: {user_id})")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": user['email'],
                "name": user['name'],
                "profile_picture": user.get('profile_picture'),
                "tier": user['tier']
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/verify-email")
async def verify_email(
    data: VerifyEmailRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Verify user email with token
    """
    try:
        # Verify token
        email = PasswordHandler.verify_email_token(data.token)
        
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired verification token"
            )
        
        # Find user and update
        user = await db.users.find_one({"email": email})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.get('email_verified'):
            return {"message": "Email already verified"}
        
        # Update user
        await db.users.update_one(
            {"_id": user['_id']},
            {
                "$set": {
                    "email_verified": True,
                    "email_verified_at": datetime.utcnow()
                }
            }
        )
        
        # Delete token
        await db.email_tokens.delete_one({
            "type": "verification",
            "email": email
        })
        
        logger.info(f"Email verified: {email}")
        
        return {"message": "Email verified successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        raise HTTPException(status_code=500, detail="Email verification failed")


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Request password reset
    Sends reset email
    """
    try:
        # Find user
        user = await db.users.find_one({"email": data.email})
        
        if not user:
            # Don't reveal if email exists (security)
            return {"message": "If email exists, reset link will be sent"}
        
        if not user.get('password_hash'):
            return {"message": "This account uses Google OAuth. Use Google to reset password."}
        
        # Generate reset token
        reset_token = PasswordHandler.generate_password_reset_token(data.email)
        
        # Store token
        await db.email_tokens.insert_one({
            "user_id": str(user['_id']),
            "email": data.email,
            "token": reset_token,
            "type": "password_reset",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=1)
        })
        
        # Send reset email
        try:
            await send_password_reset_email(data.email, user['name'], reset_token)
            sent = True
        except Exception as e:
            logger.warning(f"Failed to send reset email: {str(e)}")
            sent = False
        
        logger.info(f"Password reset requested for: {data.email}")
        
        return {
            "message": "If email exists, reset link will be sent",
            "email_sent": sent
        }
    
    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        raise HTTPException(status_code=500, detail="Password reset request failed")


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Reset password with token
    """
    try:
        # Verify token
        email = PasswordHandler.verify_password_reset_token(data.token)
        
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired reset token"
            )
        
        # Find user
        user = await db.users.find_one({"email": email})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Hash new password
        hashed_password = PasswordHandler.hash_password(data.new_password)
        
        # Update password
        await db.users.update_one(
            {"_id": user['_id']},
            {"$set": {"password_hash": hashed_password}}
        )
        
        # Delete token
        await db.email_tokens.delete_one({
            "type": "password_reset",
            "email": email
        })
        
        logger.info(f"Password reset: {email}")
        
        return {"message": "Password reset successful"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(status_code=500, detail="Password reset failed")


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Change password for authenticated user
    """
    try:
        # Find user
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not user.get('password_hash'):
            raise HTTPException(
                status_code=400,
                detail="Account uses OAuth. Cannot change password."
            )
        
        # Verify old password
        if not PasswordHandler.verify_password(data.old_password, user['password_hash']):
            raise HTTPException(
                status_code=401,
                detail="Current password is incorrect"
            )
        
        # Hash new password
        hashed_password = PasswordHandler.hash_password(data.new_password)
        
        # Update password
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password_hash": hashed_password}}
        )
        
        logger.info(f"Password changed for user: {user_id}")
        
        return {"message": "Password changed successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        raise HTTPException(status_code=500, detail="Password change failed")
