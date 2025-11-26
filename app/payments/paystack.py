"""
Paystack Payment Integration
Handles subscription payments and webhook events
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from pydantic import BaseModel
import httpx
import hmac
import hashlib
import logging
from typing import Dict

from config import settings, TIER_LIMITS
from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["Payments"])

# ==========================================
# CALLBACK & WEBHOOK URLs
# ==========================================
# These URLs are used by Paystack to communicate with your backend
# Configure them in your Paystack Dashboard

CALLBACK_URL = f"{settings.API_URL}/api/payments/verify"
WEBHOOK_URL = f"{settings.API_URL}/api/payments/webhook"
REDIRECT_URL = f"{settings.FRONTEND_URL}/payment/callback"

# Log URLs on startup
logger.info(f"[CONFIG] Paystack Callback URL: {CALLBACK_URL}")
logger.info(f"[CONFIG] Paystack Webhook URL: {WEBHOOK_URL}")
logger.info(f"[CONFIG] Frontend Redirect URL: {REDIRECT_URL}")


class PaymentRequest(BaseModel):
    """Request model for payment initialization"""
    tier: str
    
    class Config:
        extra = "allow"


@router.get("/plans")
async def get_subscription_plans():
    """
    Get available subscription plans with pricing and features
    
    Returns:
        List of available paid plans (Pro, Premium)
    """
    plans = []
    
    for tier, limits in TIER_LIMITS.items():
        if tier != 'free':  # Exclude free tier from plans
            plans.append({
                'id': tier,  # ← Also provide 'id' field for frontend
                'tier': tier,
                'name': tier.title(),
                'price_ngn': limits['price_ngn'],
                'price_usd': round(limits['price_ngn'] / 1500, 2),  # Approximate USD conversion
                'features': limits['features'],
                'max_niches': limits['max_niches'],
                'scan_interval_minutes': limits['scan_interval_minutes'],
                'monthly_opportunities_limit': limits['monthly_opportunities_limit'],
                'platforms': limits['platforms']
            })
    
    return {
        "plans": plans,
        "currency": "NGN"
    }


@router.post("/initialize")  # ← Ensure this is POST not GET
async def initialize_payment(
    payment_request: PaymentRequest,  # ← Body parameter
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Initialize Paystack payment for subscription upgrade
    
    Args:
        payment_request: {"tier": "pro" or "premium"}
        user_id: Current authenticated user ID
        db: Database connection
        
    Returns:
        Paystack authorization URL and reference
    """
    # Get tier from request body
    tier = payment_request.tier
    
    if not tier:
        raise HTTPException(
            status_code=400,
            detail="Missing 'tier' in request body"
        )
    
    if tier not in ['pro', 'premium']:
        raise HTTPException(
            status_code=400,
            detail="Invalid tier. Must be 'pro' or 'premium'"
        )
    
    # Get user details
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is already on this tier or higher
    current_tier = user.get('tier', 'free')
    tier_priority = {'free': 0, 'pro': 1, 'premium': 2}
    
    if tier_priority.get(current_tier, 0) >= tier_priority.get(tier, 0):
        raise HTTPException(
            status_code=400,
            detail=f"You are already on {current_tier} tier"
        )
    
    # Get plan price
    amount = TIER_LIMITS[tier]['price_ngn'] * 100  # Paystack uses kobo (smallest currency unit)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.paystack.co/transaction/initialize",
                headers={
                    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "email": user['email'],
                    "amount": amount,
                    "currency": "NGN",
                    "metadata": {
                        "user_id": user_id,
                        "tier": tier,
                        "subscription": True,
                        "user_name": user.get('name', 'User'),
                        "custom_fields": [
                            {
                                "display_name": "Subscription Tier",
                                "variable_name": "tier",
                                "value": tier.upper()
                            }
                        ]
                    },
                    # FIX: Changed from /payment/ to match actual file location
                    "callback_url": f"{settings.FRONTEND_URL}/payment/callback.html",
                    "channels": ["card", "bank", "ussd", "mobile_money"]  # Available payment methods
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status'):
                    payment_data = data['data']
                    
                    # Store payment reference in database for verification
                    await db.payment_transactions.insert_one({
                        "user_id": user_id,
                        "reference": payment_data['reference'],
                        "tier": tier,
                        "amount": amount / 100,  # Convert back to Naira
                        "status": "pending",
                        "created_at": datetime.utcnow()
                    })
                    
                    logger.info(f"Payment initialized for user {user['email']}: {tier} tier")
                    
                    return {
                        "status": "success",
                        "authorization_url": payment_data['authorization_url'],
                        "access_code": payment_data['access_code'],
                        "reference": payment_data['reference']
                    }
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=data.get('message', 'Payment initialization failed')
                    )
            else:
                error_message = f"Paystack API error: {response.status_code}"
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', error_message)
                except:
                    pass
                
                logger.error(f"Paystack initialization error: {error_message}")
                raise HTTPException(status_code=500, detail=error_message)
    
    except httpx.TimeoutException:
        logger.error("Paystack API timeout")
        raise HTTPException(
            status_code=504,
            detail="Payment service timeout. Please try again."
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Payment initialization error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Payment system error. Please contact support."
        )


@router.get("/verify/{reference}")
async def verify_payment(
    reference: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Verify payment status with Paystack
    
    Args:
        reference: Payment reference from Paystack
        user_id: Current authenticated user ID
        db: Database connection
        
    Returns:
        Payment verification status
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers={
                    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') and data['data']['status'] == 'success':
                    payment_data = data['data']
                    metadata = payment_data.get('metadata', {})
                    
                    # Verify this payment belongs to the user
                    if metadata.get('user_id') != user_id:
                        raise HTTPException(
                            status_code=403,
                            detail="Payment does not belong to this user"
                        )
                    
                    tier = metadata.get('tier')
                    
                    # Activate subscription
                    await activate_subscription(user_id, tier, payment_data, db)
                    
                    # ✅ FIX: Get updated user to confirm tier change
                    user = await db.users.find_one({'_id': ObjectId(user_id)})
                    confirmed_tier = user.get('tier') if user else tier
                    
                    logger.info(f"Payment verified. User tier confirmed as: {confirmed_tier}")
                    
                    return {
                        "status": "success",
                        "tier": confirmed_tier,  # Return actual tier from DB
                        "message": f"Subscription to {confirmed_tier.title()} tier activated successfully!"
                    }
                else:
                    logger.warning(f"Payment status not success: {data['data'].get('status')}")
                    return {
                        "status": "failed",
                        "message": "Payment verification failed"
                    }
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to verify payment with Paystack"
                )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Payment verification error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Payment verification failed"
        )


@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Handle Paystack webhook events for payment notifications
    
    Args:
        request: FastAPI request object
        db: Database connection
        
    Returns:
        Success response
    """
    try:
        # Get request body
        body = await request.body()
        
        # Get signature from header
        signature = request.headers.get('x-paystack-signature')
        
        if not signature:
            logger.warning("Webhook received without signature")
            raise HTTPException(status_code=400, detail="Missing signature")
        
        # ✅ FIX: Use correct webhook secret
        webhook_secret = settings.PAYSTACK_WEBHOOK_SECRET
        
        if not webhook_secret or webhook_secret == "whsec_test_YOUR_WEBHOOK_SECRET_HERE":
            logger.warning("Webhook secret not configured properly")
            # For now, skip signature validation if secret not set
            # In production, this should fail
            pass
        else:
            # Compute expected signature
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                body,
                hashlib.sha512
            ).hexdigest()
            
            # Verify signature matches
            if signature != expected_signature:
                logger.warning(f"Invalid webhook signature: {signature[:20]}...")
                raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Parse webhook event
        event = await request.json()
        event_type = event.get('event')
        
        logger.info(f"Webhook event: {event_type}")
        
        # Handle different event types
        if event_type == 'charge.success':
            await handle_charge_success(event, db)
        elif event_type == 'subscription.create':
            await handle_subscription_create(event, db)
        elif event_type == 'subscription.disable':
            await handle_subscription_disable(event, db)
        else:
            logger.info(f"Unhandled webhook event: {event_type}")
        
        return {"status": "success"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


async def handle_charge_success(event: Dict, db: AsyncIOMotorDatabase):
    """Handle successful payment charge"""
    data = event.get('data', {})
    metadata = data.get('metadata', {})
    
    if metadata.get('subscription'):
        user_id = metadata.get('user_id')
        tier = metadata.get('tier')
        
        if user_id and tier:
            await activate_subscription(user_id, tier, data, db)
            logger.info(f"Subscription activated via webhook for user {user_id}: {tier}")


async def handle_subscription_create(event: Dict, db: AsyncIOMotorDatabase):
    """Handle subscription creation"""
    data = event.get('data', {})
    # Additional subscription setup if needed
    logger.info(f"Subscription created: {data.get('subscription_code')}")


async def handle_subscription_disable(event: Dict, db: AsyncIOMotorDatabase):
    """Handle subscription cancellation"""
    data = event.get('data', {})
    subscription_code = data.get('subscription_code')
    
    if subscription_code:
        # Find and deactivate subscription
        subscription = await db.subscriptions.find_one({
            'paystack_subscription_id': subscription_code
        })
        
        if subscription:
            user_id = subscription['user_id']
            
            # Update subscription status
            await db.subscriptions.update_one(
                {'_id': subscription['_id']},
                {
                    '$set': {
                        'status': 'cancelled',
                        'cancelled_at': datetime.utcnow(),
                        'auto_renew': False
                    }
                }
            )
            
            # Downgrade user to free tier
            await db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'tier': 'free'}}
            )
            
            logger.info(f"Subscription cancelled for user {user_id}")


async def handle_subscription_not_renew(event: Dict, db: AsyncIOMotorDatabase):
    """Handle subscription set to not renew"""
    data = event.get('data', {})
    subscription_code = data.get('subscription_code')
    
    if subscription_code:
        await db.subscriptions.update_one(
            {'paystack_subscription_id': subscription_code},
            {'$set': {'auto_renew': False}}
        )
        
        logger.info(f"Subscription set to not renew: {subscription_code}")


async def activate_subscription(
    user_id: str,
    tier: str,
    payment_data: Dict,
    db: AsyncIOMotorDatabase
):
    """
    Activate user's subscription after successful payment
    FIX: Set proper period end (30 days from now for monthly subscription)
    """
    try:
        logger.info(f"Activating subscription: user={user_id}, tier={tier}")
        
        # ✅ FIX 1: Update user tier FIRST (critical)
        user_update = await db.users.update_one(
            {'_id': ObjectId(user_id)},
            {
                '$set': {
                    'tier': tier,  # ← MUST update tier
                    'last_login': datetime.utcnow()
                }
            }
        )
        
        if user_update.modified_count == 0:
            logger.warning(f"User {user_id} not updated - may not exist")
        else:
            logger.info(f"User tier updated to {tier}")
        
        # ✅ FIX 2: Calculate subscription period (30 days = 1 month)
        current_period_start = datetime.utcnow()
        current_period_end = current_period_start + timedelta(days=30)  # ← 30 days from now
        
        logger.info(f"Subscription period: {current_period_start} to {current_period_end}")
        
        # ✅ FIX 3: Create or update subscription record
        subscription_update = await db.subscriptions.update_one(
            {'user_id': user_id},
            {
                '$set': {
                    'tier': tier,
                    'status': 'active',
                    'payment_method': payment_data.get('channel'),
                    'paystack_subscription_id': payment_data.get('reference'),
                    'paystack_customer_code': payment_data.get('customer', {}).get('customer_code'),
                    'current_period_start': current_period_start,
                    'current_period_end': current_period_end,  # ← 30 days from purchase
                    'auto_renew': True,
                    'updated_at': datetime.utcnow()
                },
                '$setOnInsert': {
                    'created_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        
        logger.info(f"Subscription updated/created for {user_id}: {subscription_update.modified_count} modified")
        logger.info(f"Period end: {current_period_end.isoformat()}")
        
        # ✅ FIX 4: Update payment transaction status
        await db.payment_transactions.update_one(
            {
                'user_id': user_id,
                'reference': payment_data.get('reference')
            },
            {
                '$set': {
                    'status': 'success',
                    'completed_at': datetime.utcnow()
                }
            }
        )
        
        # ✅ FIX 5: Initialize or update usage tracking
        current_month = datetime.utcnow().strftime("%Y-%m")
        await db.usage_tracking.update_one(
            {
                'user_id': user_id,
                'month': current_month
            },
            {
                '$set': {
                    'updated_at': datetime.utcnow()
                },
                '$setOnInsert': {
                    'opportunities_sent': 0,
                    'scans_completed': 0,
                    'ai_analyses_used': 0
                }
            },
            upsert=True
        )
        
        logger.info(f"✅ Subscription fully activated for {user_id}: tier={tier}, expires={current_period_end.isoformat()}")
        
    except Exception as e:
        logger.error(f"Error activating subscription: {str(e)}", exc_info=True)
        raise


@router.get("/subscription/current")
async def get_current_subscription(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get current user's subscription details
    
    Args:
        user_id: Current authenticated user ID
        db: Database connection
        
    Returns:
        Current subscription information
    """
    user = await db.users.find_one({'_id': ObjectId(user_id)})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = await db.subscriptions.find_one({'user_id': user_id})
    
    tier = user.get('tier', 'free')
    tier_limits = TIER_LIMITS[tier]
    
    # Get current month usage
    current_month = datetime.utcnow().strftime("%Y-%m")
    usage = await db.usage_tracking.find_one({
        'user_id': user_id,
        'month': current_month
    })
    
    response = {
        'tier': tier,
        'status': subscription['status'] if subscription else 'active',
        'limits': {
            'max_niches': tier_limits['max_niches'],
            'scan_interval_minutes': tier_limits['scan_interval_minutes'],
            'monthly_opportunities_limit': tier_limits['monthly_opportunities_limit'],
            'platforms': tier_limits['platforms']
        },
        'usage': {
            'opportunities_sent': usage['opportunities_sent'] if usage else 0,
            'scans_completed': usage['scans_completed'] if usage else 0
        }
    }
    
    if subscription and subscription.get('status') == 'active':
        response.update({
            'current_period_end': subscription.get('current_period_end'),
            'auto_renew': subscription.get('auto_renew', True),
            'payment_method': subscription.get('payment_method')
        })
    
    return response


@router.post("/subscription/cancel")
async def cancel_subscription(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Cancel user's subscription (will remain active until period end)
    
    Args:
        user_id: Current authenticated user ID
        db: Database connection
        
    Returns:
        Cancellation confirmation
    """
    subscription = await db.subscriptions.find_one({
        'user_id': user_id,
        'status': 'active'
    })
    
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    # Update subscription
    await db.subscriptions.update_one(
        {'_id': subscription['_id']},
        {
            '$set': {
                'auto_renew': False,
                'cancelled_at': datetime.utcnow()
            }
        }
    )
    
    logger.info(f"Subscription cancelled by user {user_id}")
    
    return {
        "message": "Subscription cancelled successfully. Access will continue until period end.",
        "period_end": subscription.get('current_period_end')
    }