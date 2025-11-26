"""
Reports Module
Generate reports for analytics and business intelligence
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta

from app.database.connection import get_database
from app.admin.middleware import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/signups")
async def get_signups_report(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
    days: int = Query(30, ge=1, le=365)
):
    """
    Get signups report for last N days
    """
    try:
        now = datetime.utcnow()
        start_date = now - timedelta(days=days)
        
        # Get signups by day
        signups = await db.users.aggregate([
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]).to_list(length=None)
        
        return {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": now.isoformat(),
            "signups_by_day": signups,
            "total_signups": sum(s["count"] for s in signups)
        }
    
    except Exception as e:
        logger.error(f"Error generating signups report: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/revenue")
async def get_revenue_report(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
    months: int = Query(3, ge=1, le=12)
):
    """
    Get revenue report for last N months
    """
    try:
        from config import TIER_LIMITS
        
        now = datetime.utcnow()
        start_date = now - timedelta(days=30*months)
        
        # Get tier distribution
        free_count = await db.users.count_documents({"tier": "free"})
        pro_count = await db.users.count_documents({"tier": "pro"})
        premium_count = await db.users.count_documents({"tier": "premium"})
        
        pro_price = TIER_LIMITS.get("pro", {}).get("price_ngn", 0)
        premium_price = TIER_LIMITS.get("premium", {}).get("price_ngn", 0)
        
        # Calculate revenue
        monthly_revenue = (pro_count * pro_price) + (premium_count * premium_price)
        
        return {
            "period_months": months,
            "users": {
                "free": free_count,
                "pro": pro_count,
                "premium": premium_count,
                "total": free_count + pro_count + premium_count
            },
            "revenue": {
                "monthly_revenue_ngn": monthly_revenue,
                "pro_revenue": pro_count * pro_price,
                "premium_revenue": premium_count * premium_price,
                "conversion_rate": round(((pro_count + premium_count) / (free_count + pro_count + premium_count) * 100) if (free_count + pro_count + premium_count) > 0 else 0, 2)
            }
        }
    
    except Exception as e:
        logger.error(f"Error generating revenue report: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/engagement")
async def get_engagement_report(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get user engagement report
    """
    try:
        now = datetime.utcnow()
        
        # Active users (last 7 days)
        week_ago = now - timedelta(days=7)
        active_7d = await db.users.count_documents({"last_login": {"$gte": week_ago}})
        
        # Active users (last 30 days)
        month_ago = now - timedelta(days=30)
        active_30d = await db.users.count_documents({"last_login": {"$gte": month_ago}})
        
        total_users = await db.users.count_documents({})
        
        # Total scans
        total_scans = await db.scan_history.count_documents({})
        
        # Total opportunities discovered
        total_opportunities = await db.user_opportunities.count_documents({})
        
        return {
            "users": {
                "total": total_users,
                "active_7d": active_7d,
                "active_30d": active_30d,
                "engagement_7d": round((active_7d / total_users * 100) if total_users > 0 else 0, 2),
                "engagement_30d": round((active_30d / total_users * 100) if total_users > 0 else 0, 2)
            },
            "activity": {
                "total_scans": total_scans,
                "total_opportunities": total_opportunities,
                "avg_opportunities_per_user": round((total_opportunities / total_users) if total_users > 0 else 0, 2)
            }
        }
    
    except Exception as e:
        logger.error(f"Error generating engagement report: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/platform-stats")
async def get_platform_stats(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get statistics by platform
    """
    try:
        # Opportunities by platform
        platform_stats = await db.user_opportunities.aggregate([
            {"$group": {
                "_id": "$platform",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]).to_list(length=None)
        
        # Scans by platform
        scan_stats = await db.scan_history.aggregate([
            {"$unwind": "$platforms_scanned"},
            {"$group": {
                "_id": "$platforms_scanned.platform",
                "scan_count": {"$sum": 1},
                "avg_opportunities": {"$avg": "$platforms_scanned.count"}
            }},
            {"$sort": {"scan_count": -1}}
        ]).to_list(length=None)
        
        return {
            "opportunities_by_platform": platform_stats,
            "scans_by_platform": scan_stats
        }
    
    except Exception as e:
        logger.error(f"Error generating platform stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate report")