"""
Real-Time Monitoring Routes
System health and performance monitoring
"""
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import Optional
import logging
import psutil

from app.database.connection import get_database
from app.admin.middleware import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@router.get("/health")
async def get_system_health(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get comprehensive system health metrics
    """
    try:
        # Database health
        db_health = await db.command("ping")
        
        # Collection counts
        collections = {
            "users": await db.users.count_documents({}),
            "opportunities": await db.opportunities.count_documents({}),
            "niches": await db.niche_configs.count_documents({}),
            "subscriptions": await db.subscriptions.count_documents({})
        }
        
        # System resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "status": "connected" if db_health else "disconnected",
                "collections": collections
            },
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": round(memory.used / (1024 ** 3), 2),
                "memory_total_gb": round(memory.total / (1024 ** 3), 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024 ** 3), 2),
                "disk_total_gb": round(disk.total / (1024 ** 3), 2)
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/api-metrics")
async def get_api_metrics(
    hours: int = Query(24, ge=1, le=168),
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get API usage metrics
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Total requests
        total_requests = await db.api_metrics.count_documents({
            "timestamp": {"$gte": cutoff_time}
        })
        
        # Requests by endpoint
        endpoint_pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff_time}}},
            {
                "$group": {
                    "_id": "$endpoint",
                    "count": {"$sum": 1},
                    "avg_response_time": {"$avg": "$response_time"}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        
        endpoint_stats = await db.api_metrics.aggregate(endpoint_pipeline).to_list(length=20)
        
        # Error rate
        error_count = await db.api_metrics.count_documents({
            "timestamp": {"$gte": cutoff_time},
            "status_code": {"$gte": 400}
        })
        
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        
        # Average response time
        avg_pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff_time}}},
            {
                "$group": {
                    "_id": None,
                    "avg_response_time": {"$avg": "$response_time"}
                }
            }
        ]
        
        avg_result = await db.api_metrics.aggregate(avg_pipeline).to_list(length=1)
        avg_response_time = avg_result[0]['avg_response_time'] if avg_result else 0
        
        return {
            "total_requests": total_requests,
            "error_rate": round(error_rate, 2),
            "avg_response_time_ms": round(avg_response_time, 2),
            "top_endpoints": [
                {
                    "endpoint": stat['_id'],
                    "requests": stat['count'],
                    "avg_response_time_ms": round(stat['avg_response_time'], 2)
                }
                for stat in endpoint_stats
            ]
        }
    
    except Exception as e:
        logger.error(f"Error getting API metrics: {str(e)}")
        return {"error": str(e)}


@router.get("/scraper-status")
async def get_scraper_status(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get scraper health and performance
    """
    try:
        # Last 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Scan statistics
        total_scans = await db.user_scan.count_documents({
            "scanned_at": {"$gte": cutoff_time}
        })
        
        successful_scans = await db.user_scan.count_documents({
            "scanned_at": {"$gte": cutoff_time},
            "success": True
        })
        
        failed_scans = total_scans - successful_scans
        success_rate = (successful_scans / total_scans * 100) if total_scans > 0 else 0
        
        # Platform statistics
        platform_pipeline = [
            {"$match": {"scanned_at": {"$gte": cutoff_time}}},
            {"$unwind": "$platforms_scanned"},
            {
                "$group": {
                    "_id": "$platforms_scanned",
                    "scans": {"$sum": 1}
                }
            },
            {"$sort": {"scans": -1}}
        ]
        
        platform_stats = await db.user_scan.aggregate(platform_pipeline).to_list(length=20)
        
        # Recent errors
        recent_errors = await db.user_scan.find({
            "scanned_at": {"$gte": cutoff_time},
            "success": False
        }).sort("scanned_at", -1).limit(10).to_list(length=10)
        
        return {
            "total_scans": total_scans,
            "successful_scans": successful_scans,
            "failed_scans": failed_scans,
            "success_rate": round(success_rate, 2),
            "platforms": [
                {
                    "platform": stat['_id'],
                    "scans": stat['scans']
                }
                for stat in platform_stats
            ],
            "recent_errors": [
                {
                    "user_id": error['user_id'],
                    "timestamp": error['scanned_at'].isoformat(),
                    "errors": error.get('errors', [])
                }
                for error in recent_errors
            ]
        }
    
    except Exception as e:
        logger.error(f"Error getting scraper status: {str(e)}")
        return {"error": str(e)}


@router.get("/active-sessions")
async def get_active_sessions(
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get count of active user sessions
    """
    try:
        # Users active in last 15 minutes
        cutoff_time = datetime.utcnow() - timedelta(minutes=15)
        
        active_users = await db.users.count_documents({
            "last_active_at": {"$gte": cutoff_time}
        })
        
        # Active by tier
        tier_pipeline = [
            {"$match": {"last_active_at": {"$gte": cutoff_time}}},
            {
                "$group": {
                    "_id": "$tier",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        tier_breakdown = await db.users.aggregate(tier_pipeline).to_list(length=10)
        
        return {
            "active_sessions": active_users,
            "by_tier": {
                stat['_id']: stat['count']
                for stat in tier_breakdown
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting active sessions: {str(e)}")
        return {"error": str(e)}


@router.get("/errors")
async def get_recent_errors(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=200),
    admin_id: str = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get recent system errors
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Get errors from system_alerts collection
        errors = await db.system_alerts.find({
            "timestamp": {"$gte": cutoff_time},
            "level": {"$in": ["error", "critical"]}
        }).sort("timestamp", -1).limit(limit).to_list(length=limit)
        
        # Get API errors
        api_errors = await db.api_metrics.find({
            "timestamp": {"$gte": cutoff_time},
            "status_code": {"$gte": 500}
        }).sort("timestamp", -1).limit(20).to_list(length=20)
        
        return {
            "system_errors": [
                {
                    "level": error.get('level'),
                    "message": error.get('message'),
                    "source": error.get('source'),
                    "timestamp": error['timestamp'].isoformat()
                }
                for error in errors
            ],
            "api_errors": [
                {
                    "endpoint": error.get('endpoint'),
                    "method": error.get('method'),
                    "status_code": error.get('status_code'),
                    "error": error.get('error'),
                    "timestamp": error['timestamp'].isoformat()
                }
                for error in api_errors
            ]
        }
    
    except Exception as e:
        logger.error(f"Error getting errors: {str(e)}")
        return {"error": str(e)}