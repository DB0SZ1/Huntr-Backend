"""
Admin Analytics and Data Aggregation
Helper functions for calculating platform statistics
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


async def calculate_growth_percentage(
    db: AsyncIOMotorDatabase,
    collection_name: str,
    date_field: str,
    days: int = 30
) -> float:
    """
    Calculate growth percentage over period
    
    Args:
        db: Database connection
        collection_name: Name of collection to analyze
        date_field: Field containing date
        days: Number of days to compare
        
    Returns:
        Growth percentage
    """
    try:
        now = datetime.utcnow()
        period_start = now - timedelta(days=days)
        previous_period_start = period_start - timedelta(days=days)
        
        # Current period count
        current_count = await db[collection_name].count_documents({
            date_field: {"$gte": period_start}
        })
        
        # Previous period count
        previous_count = await db[collection_name].count_documents({
            date_field: {
                "$gte": previous_period_start,
                "$lt": period_start
            }
        })
        
        if previous_count == 0:
            return 100.0 if current_count > 0 else 0.0
        
        growth = ((current_count - previous_count) / previous_count) * 100
        return round(growth, 2)
    
    except Exception as e:
        logger.error(f"Error calculating growth: {str(e)}")
        return 0.0


async def aggregate_revenue_by_month(
    db: AsyncIOMotorDatabase,
    months: int = 6
) -> List[Dict[str, Any]]:
    """
    Aggregate revenue by month
    
    Args:
        db: Database connection
        months: Number of months to include
        
    Returns:
        List of monthly revenue data
    """
    try:
        from config import TIER_LIMITS
        
        pipeline = [
            {
                "$match": {
                    "status": "active",
                    "tier": {"$in": ["pro", "premium"]}
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$current_period_start"},
                        "month": {"$month": "$current_period_start"}
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id.year": -1, "_id.month": -1}},
            {"$limit": months}
        ]
        
        results = await db.subscriptions.aggregate(pipeline).to_list(length=months)
        
        # Calculate revenue based on tier prices
        monthly_data = []
        for result in results:
            # Estimate revenue (this is simplified - you'd need actual payment records)
            month_str = f"{result['_id']['year']}-{result['_id']['month']:02d}"
            monthly_data.append({
                "month": month_str,
                "subscriptions": result['count'],
                "estimated_revenue": result['count'] * 29999  # Simplified average
            })
        
        return monthly_data
    
    except Exception as e:
        logger.error(f"Error aggregating revenue: {str(e)}")
        return []


async def calculate_user_retention(
    db: AsyncIOMotorDatabase,
    days: int = 30
) -> float:
    """
    Calculate user retention rate
    
    Args:
        db: Database connection
        days: Period to analyze
        
    Returns:
        Retention percentage
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Users created before cutoff
        total_users = await db.users.count_documents({
            "created_at": {"$lt": cutoff_date}
        })
        
        if total_users == 0:
            return 0.0
        
        # Active users (logged in within last 7 days)
        active_cutoff = datetime.utcnow() - timedelta(days=7)
        active_users = await db.users.count_documents({
            "created_at": {"$lt": cutoff_date},
            "last_login": {"$gte": active_cutoff}
        })
        
        retention = (active_users / total_users) * 100
        return round(retention, 2)
    
    except Exception as e:
        logger.error(f"Error calculating retention: {str(e)}")
        return 0.0


async def get_platform_statistics(
    db: AsyncIOMotorDatabase
) -> Dict[str, Any]:
    """
    Get comprehensive platform statistics
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary of platform stats
    """
    try:
        from config import TIER_LIMITS
        
        # User counts by tier
        total_users = await db.users.count_documents({"is_active": True})
        free_users = await db.users.count_documents({"tier": "free", "is_active": True})
        pro_users = await db.users.count_documents({"tier": "pro", "is_active": True})
        premium_users = await db.users.count_documents({"tier": "premium", "is_active": True})
        
        # Revenue calculation
        monthly_revenue = (pro_users * TIER_LIMITS['pro']['price_ngn']) + \
                         (premium_users * TIER_LIMITS['premium']['price_ngn'])
        
        # Opportunities
        total_opportunities = await db.opportunities.count_documents({})
        opportunities_this_week = await db.opportunities.count_documents({
            "created_at": {"$gte": datetime.utcnow() - timedelta(days=7)}
        })
        
        # Active niches
        total_niches = await db.niche_configs.count_documents({"is_active": True})
        
        # Conversion rate (free to paid)
        conversion_rate = 0.0
        if total_users > 0:
            paid_users = pro_users + premium_users
            conversion_rate = (paid_users / total_users) * 100
        
        return {
            "total_users": total_users,
            "user_breakdown": {
                "free": free_users,
                "pro": pro_users,
                "premium": premium_users
            },
            "monthly_revenue": monthly_revenue,
            "total_opportunities": total_opportunities,
            "opportunities_this_week": opportunities_this_week,
            "total_niches": total_niches,
            "conversion_rate": round(conversion_rate, 2),
            "average_opportunities_per_user": round(total_opportunities / total_users, 2) if total_users > 0 else 0
        }
    
    except Exception as e:
        logger.error(f"Error getting platform statistics: {str(e)}")
        return {}


async def get_top_niches(
    db: AsyncIOMotorDatabase,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get top performing niches
    
    Args:
        db: Database connection
        limit: Number of niches to return
        
    Returns:
        List of top niches with stats
    """
    try:
        pipeline = [
            {"$match": {"is_active": True}},
            {
                "$group": {
                    "_id": "$name",
                    "count": {"$sum": 1},
                    "total_matches": {"$sum": "$total_matches"}
                }
            },
            {"$sort": {"total_matches": -1}},
            {"$limit": limit}
        ]
        
        results = await db.niche_configs.aggregate(pipeline).to_list(length=limit)
        
        return [
            {
                "name": result['_id'],
                "users": result['count'],
                "matches": result['total_matches']
            }
            for result in results
        ]
    
    except Exception as e:
        logger.error(f"Error getting top niches: {str(e)}")
        return []


async def get_platform_usage_stats(
    db: AsyncIOMotorDatabase
) -> Dict[str, int]:
    """
    Get opportunities sent per platform
    
    Args:
        db: Database connection
        
    Returns:
        Dictionary of platform usage counts
    """
    try:
        pipeline = [
            {
                "$group": {
                    "_id": "$platform",
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"count": -1}}
        ]
        
        results = await db.opportunities.aggregate(pipeline).to_list(length=20)
        
        return {
            result['_id']: result['count']
            for result in results
        }
    
    except Exception as e:
        logger.error(f"Error getting platform usage: {str(e)}")
        return {}


async def get_signup_analytics(
    db: AsyncIOMotorDatabase,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get user signup analytics
    
    Args:
        db: Database connection
        days: Number of days to analyze
        
    Returns:
        Signup statistics
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Daily signups
        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": cutoff_date}
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at"
                        }
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        daily_signups = await db.users.aggregate(pipeline).to_list(length=days)
        
        # Total signups
        total_signups = await db.users.count_documents({
            "created_at": {"$gte": cutoff_date}
        })
        
        # Signups by tier
        tier_pipeline = [
            {"$match": {"created_at": {"$gte": cutoff_date}}},
            {
                "$group": {
                    "_id": "$tier",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        tier_signups = await db.users.aggregate(tier_pipeline).to_list(length=10)
        
        return {
            "total_signups": total_signups,
            "daily_breakdown": [
                {
                    "date": result['_id'],
                    "signups": result['count']
                }
                for result in daily_signups
            ],
            "by_tier": {
                result['_id']: result['count']
                for result in tier_signups
            },
            "period_days": days
        }
    
    except Exception as e:
        logger.error(f"Error getting signup analytics: {str(e)}")
        return {}


async def get_scan_analytics(
    db: AsyncIOMotorDatabase,
    days: int = 7
) -> Dict[str, Any]:
    """
    Get scan activity analytics
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Total scans
        total_scans = await db.user_scans.count_documents({
            "scanned_at": {"$gte": cutoff_date}
        })
        
        # Successful scans
        successful_scans = await db.user_scans.count_documents({
            "scanned_at": {"$gte": cutoff_date},
            "success": True
        })
        
        # Total opportunities found
        pipeline = [
            {"$match": {"scanned_at": {"$gte": cutoff_date}}},
            {
                "$group": {
                    "_id": None,
                    "total_found": {"$sum": "$opportunities_found"},
                    "total_sent": {"$sum": "$matches_sent"}
                }
            }
        ]
        
        scan_stats = await db.user_scans.aggregate(pipeline).to_list(length=1)
        
        total_found = scan_stats[0]['total_found'] if scan_stats else 0
        total_sent = scan_stats[0]['total_sent'] if scan_stats else 0
        
        return {
            "total_scans": total_scans,
            "successful_scans": successful_scans,
            "failed_scans": total_scans - successful_scans,
            "success_rate": round((successful_scans / total_scans * 100), 2) if total_scans > 0 else 0,
            "total_opportunities_found": total_found,
            "opportunities_sent_to_users": total_sent,
            "period_days": days
        }
    
    except Exception as e:
        logger.error(f"Error getting scan analytics: {str(e)}")
        return {}


async def get_engagement_metrics(
    db: AsyncIOMotorDatabase
) -> Dict[str, Any]:
    """
    Get user engagement metrics
    """
    try:
        from datetime import timedelta
        
        # Active users (logged in last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_users = await db.users.count_documents({
            "last_login": {"$gte": week_ago}
        })
        
        # Users with active niches
        users_with_niches = await db.niche_configs.distinct(
            "user_id",
            {"is_active": True}
        )
        
        # Users with opportunities
        users_with_opps = await db.user_opportunities.distinct(
            "user_id"
        )
        
        # Average opportunities per active user
        total_opps = await db.user_opportunities.count_documents({})
        avg_opps = total_opps / len(users_with_opps) if users_with_opps else 0
        
        return {
            "active_users_7d": active_users,
            "users_with_niches": len(users_with_niches),
            "users_with_opportunities": len(users_with_opps),
            "avg_opportunities_per_user": round(avg_opps, 2)
        }
    
    except Exception as e:
        logger.error(f"Error getting engagement metrics: {str(e)}")
        return {}