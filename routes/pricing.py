"""
Pricing Routes - Public endpoint for pricing plans
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

router = APIRouter(prefix="/api/pricing", tags=["pricing"])

# Pricing plans data
PRICING_PLANS = {
    "free": {
        "tier": "free",
        "name": "Free",
        "description": "Perfect for getting started with gig hunting",
        "max_niches": 1,
        "scans_per_day": 2,
        "curated_gigs_per_scan": 5,
        "scan_interval_minutes": 0,
        "auto_scan_enabled": False,
        "monthly_opportunities_limit": 50,
        "daily_credits": 10,
        "credit_refill_hour": 0,
        "features": [
            "Create 1 niche",
            "2 scans per day",
            "5 curated gigs per scan",
            "Scam detection",
            "Salary detection",
            "Manual scanning only",
            "Up to 50 opportunities/month",
            "Email notifications"
        ],
        "platforms": ["Twitter/X", "Telegram"],
        "price_ngn": 0,
        "price_usd": 0
    },
    "pro": {
        "tier": "pro",
        "name": "Pro",
        "description": "For serious freelancers ready to scale",
        "max_niches": 5,
        "scans_per_day": 5,
        "curated_gigs_per_scan": 8,
        "scan_interval_minutes": 90,
        "auto_scan_enabled": True,
        "monthly_opportunities_limit": 500,
        "daily_credits": 50,
        "credit_refill_hour": 0,
        "features": [
            "Create up to 5 niches",
            "5 scans per day",
            "8 curated gigs per scan",
            "Advanced scam detection",
            "Salary detection & analysis",
            "Automatic scans every 90 minutes",
            "Up to 500 opportunities/month",
            "CV Analyzer Lite (PDF <5MB)",
            "Email + WhatsApp notifications",
            "Priority support"
        ],
        "platforms": ["Twitter/X", "Web3.career", "Telegram"],
        "price_ngn": 2500,
        "price_usd": 1.50
    },
    "premium": {
        "tier": "premium",
        "name": "Premium",
        "description": "Maximum power for elite professionals",
        "max_niches": 20,
        "scans_per_day": 10,
        "curated_gigs_per_scan": 12,
        "scan_interval_minutes": 30,
        "auto_scan_enabled": True,
        "monthly_opportunities_limit": 5000,
        "daily_credits": 200,
        "credit_refill_hour": 0,
        "features": [
            "Create up to 20 niches",
            "10 scans per day",
            "12 curated gigs per scan",
            "Elite scam detection",
            "Advanced salary detection",
            "Automatic scans every 30 minutes",
            "Up to 5000 opportunities/month",
            "CV Analyzer Premium (PDF <5MB)",
            "Proof of Work Analyzer",
            "All notifications",
            "Priority support",
            "Advanced analytics",
            "Custom alerts"
        ],
        "platforms": [
            "Twitter/X", "Web3.career", "Pump.fun", 
            "DexScreener", "CoinMarketCap", "CoinGecko", "Telegram"
        ],
        "price_ngn": 7500,
        "price_usd": 4.50
    }
}


@router.get("/plans", response_model=Dict[str, Any])
async def get_pricing_plans():
    """
    Get all pricing plans (PUBLIC - No authentication required)
    
    Returns:
        Dict containing all available pricing plans with features and limitations
    """
    return {
        "success": True,
        "data": PRICING_PLANS,
        "plans": list(PRICING_PLANS.keys()),
        "currency": "NGN"
    }


@router.get("/plans/{plan_name}", response_model=Dict[str, Any])
async def get_pricing_plan(plan_name: str):
    """
    Get specific pricing plan details (PUBLIC - No authentication required)
    
    Args:
        plan_name: Name of the plan (free, pro, or premium)
    
    Returns:
        Specific plan details
    
    Raises:
        HTTPException: If plan not found
    """
    plan_name = plan_name.lower()
    
    if plan_name not in PRICING_PLANS:
        raise HTTPException(
            status_code=404,
            detail=f"Plan '{plan_name}' not found. Available plans: {list(PRICING_PLANS.keys())}"
        )
    
    return {
        "success": True,
        "plan": plan_name,
        "data": PRICING_PLANS[plan_name]
    }


@router.get("/comparison", response_model=Dict[str, Any])
async def get_pricing_comparison():
    """
    Get pricing comparison between all plans (PUBLIC - No authentication required)
    
    Returns:
        Comparison matrix of all plans
    """
    return {
        "success": True,
        "plans": PRICING_PLANS,
        "comparison": {
            "features": {
                "free": len(PRICING_PLANS["free"]["features"]),
                "pro": len(PRICING_PLANS["pro"]["features"]),
                "premium": len(PRICING_PLANS["premium"]["features"])
            },
            "price_range": {
                "min": 0,
                "max": 7500,
                "currency": "NGN"
            }
        }
    }