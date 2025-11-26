"""Cache manager for Render optimization"""
from fastapi_cache2.decorators import cache
from functools import wraps
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

# Cache TTLs optimized for 50-100 users
CACHE_TTL = {
    "opportunities": timedelta(minutes=30),      # Job listings don't change frequently
    "user_profile": timedelta(minutes=5),        # User data: shorter TTL
    "niches": timedelta(hours=2),                # Niche data: rarely changes
    "admin_stats": timedelta(minutes=10),        # Stats: moderate frequency
    "search_results": timedelta(minutes=15),     # Search cache
}

def cached_endpoint(cache_key_prefix: str, ttl: timedelta = timedelta(minutes=5)):
    """Decorator to cache endpoint responses"""
    def decorator(func):
        @wraps(func)
        @cache(expire=int(ttl.total_seconds()))
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator
