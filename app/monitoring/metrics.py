"""
API Metrics Middleware
Tracks all API calls for monitoring and analytics
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from datetime import datetime
import time
import logging

logger = logging.getLogger(__name__)


class APIMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API usage metrics
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Intercept requests and track metrics
        """
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate response time
        response_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Extract user ID if authenticated
        user_id = None
        try:
            from app.auth.jwt_handler import verify_token
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                payload = verify_token(token, token_type="access")
                user_id = payload.get("sub")
        except:
            pass
        
        # Store metrics in background
        try:
            from app.database.connection import get_database
            db = await get_database()
            
            await db.api_metrics.insert_one({
                "endpoint": request.url.path,
                "method": request.method,
                "response_time": response_time,
                "status_code": response.status_code,
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                "user_agent": request.headers.get("User-Agent"),
                "ip_address": request.client.host if request.client else None
            })
            
            # Update user's last_active_at if authenticated
            if user_id:
                from bson.objectid import ObjectId
                await db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {
                        "$set": {"last_active_at": datetime.utcnow()},
                        "$inc": {"total_api_calls": 1}
                    }
                )
        
        except Exception as e:
            # Don't fail requests if metrics storage fails
            logger.error(f"Failed to store API metrics: {str(e)}")
        
        return response