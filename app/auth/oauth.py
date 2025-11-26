"""
Google OAuth Authentication
Real OAuth flow with user creation/login
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from config import settings
from app.database.connection import get_database
from app.auth.jwt_handler import create_access_token, create_refresh_token, verify_token, get_current_user_id
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Initialize OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'prompt': 'select_account'
    }
)


@router.get("/google/login")
async def google_login(request: Request):
    """
    Initiate Google OAuth flow
    Redirects user to Google's consent screen
    """
    try:
        redirect_uri = f"{settings.API_URL}/api/auth/google/callback"
        logger.info(f"Initiating OAuth with redirect_uri: {redirect_uri}")
        
        return await oauth.google.authorize_redirect(request, redirect_uri)
    
    except Exception as e:
        logger.error(f"OAuth initiation error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initiate authentication"
        )


@router.get("/google/callback")
async def google_callback(request: Request):
    """
    Handle Google OAuth callback
    Creates user if new, generates JWT tokens
    """
    db = await get_database()
    
    try:
        # Exchange authorization code for tokens
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if not user_info:
            raise HTTPException(
                status_code=400,
                detail="Failed to retrieve user information from Google"
            )
        
        logger.info(f"OAuth successful for email: {user_info['email']}")
        
        # Check if user exists
        user = await db.users.find_one({"google_id": user_info['sub']})
        
        if not user:
            # Create new user
            new_user = {
                "google_id": user_info['sub'],
                "email": user_info['email'],
                "name": user_info.get('name', 'User'),
                "profile_picture": user_info.get('picture'),
                "tier": "free",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "last_login": datetime.utcnow(),
                "settings": {
                    "notifications_enabled": True,
                    "email_notifications": True,
                    "whatsapp_notifications": False  # User needs to configure
                }
            }
            
            result = await db.users.insert_one(new_user)
            user_id = str(result.inserted_id)
            
            # Create default free subscription
            await db.subscriptions.insert_one({
                "user_id": user_id,
                "tier": "free",
                "status": "active",
                "payment_method": None,
                "paystack_subscription_id": None,
                "current_period_start": datetime.utcnow(),
                "current_period_end": datetime.utcnow() + timedelta(days=365),
                "created_at": datetime.utcnow()
            })
            
            # Initialize usage tracking for current month
            await db.usage_tracking.insert_one({
                "user_id": user_id,
                "month": datetime.utcnow().strftime("%Y-%m"),
                "opportunities_sent": 0,
                "scans_completed": 0,
                "ai_analyses_used": 0,
                "notifications_sent": 0
            })
            
            logger.info(f"New user created: {user_info['email']} (ID: {user_id})")
        
        else:
            # Existing user - update last login
            user_id = str(user['_id'])
            
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "last_login": datetime.utcnow(),
                        "profile_picture": user_info.get('picture')  # Update profile pic
                    }
                }
            )
            
            logger.info(f"Existing user logged in: {user_info['email']} (ID: {user_id})")
        
        # Generate JWT tokens
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)
        
        # Redirect to frontend with tokens
        # CHANGED: Point to auth_callback.html instead of auth/callback
        frontend_redirect = (
            f"{settings.FRONTEND_URL}/auth_callback.html"
            f"?access_token={access_token}"
            f"&refresh_token={refresh_token}"
        )
        
        return RedirectResponse(url=frontend_redirect)
    
    except OAuthError as e:
        logger.error(f"OAuth error: {str(e)}")
        # Redirect to frontend with error
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?message=oauth_failed"
        )
    
    except Exception as e:
        logger.error(f"Callback error: {str(e)}", exc_info=True)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?message=internal_error"
        )


@router.post("/refresh")
async def refresh_access_token(refresh_token: str):
    """
    Refresh access token using refresh token
    """
    try:
        # Verify refresh token
        payload = verify_token(refresh_token, token_type="refresh")
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Verify user still exists and is active
        db = await get_database()
        user = await db.users.find_one({
            "_id": ObjectId(user_id),
            "is_active": True
        })
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        # Generate new access token
        new_access_token = create_access_token(user_id)
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=401, detail="Failed to refresh token")


@router.get("/me")
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get current authenticated user's information
    Requires valid JWT token in Authorization header
    """
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get subscription info
        subscription = await db.subscriptions.find_one({"user_id": user_id})
        
        # Get usage stats for current month
        current_month = datetime.utcnow().strftime("%Y-%m")
        usage = await db.usage_tracking.find_one({
            "user_id": user_id,
            "month": current_month
        })
        
        # Count active niches
        active_niches_count = await db.niche_configs.count_documents({
            "user_id": user_id,
            "is_active": True
        })
        
        return {
            "id": user_id,
            "email": user['email'],
            "name": user['name'],
            "profile_picture": user.get('profile_picture'),
            "tier": user['tier'],
            "is_admin": user.get('is_admin', False),
            "is_active": user.get('is_active', True),
            "subscription": {
                "status": subscription['status'] if subscription else None,
                "current_period_end": subscription['current_period_end'].isoformat() if subscription else None
            },
            "usage": {
                "opportunities_sent": usage['opportunities_sent'] if usage else 0,
                "scans_completed": usage['scans_completed'] if usage else 0
            },
            "active_niches": active_niches_count,
            "settings": user.get('settings', {}),
            "created_at": user['created_at'].isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch user information")


@router.post("/logout")
async def logout():
    """
    Logout endpoint (client-side token removal)
    """
    return {"message": "Logged out successfully"}

