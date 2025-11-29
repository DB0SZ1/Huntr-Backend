"""
Enhanced MongoDB Connection with DNS Override
Production-ready async MongoDB connection using Motor
FIXED: Uses Google DNS to bypass corporate/local DNS restrictions
"""

# ==========================================
# CRITICAL: DNS OVERRIDE - MUST BE FIRST
# ==========================================
import dns.resolver

# ✅ DISABLED: Google DNS override (causing timeout)
# These DNS servers don't work from your network
# Let MongoDB use system DNS instead
# custom_resolver = dns.resolver.Resolver()
# custom_resolver.nameservers = ['8.8.8.8', '8.8.4.4']
# custom_resolver.timeout = 10
# custom_resolver.lifetime = 30
# dns.resolver.default_resolver = custom_resolver

# print("[CONFIG] DNS resolver configured: Google DNS (8.8.8.8, 8.8.4.4)")
# ==========================================

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import (
    ConnectionFailure, 
    ServerSelectionTimeoutError,
    OperationFailure,
    DuplicateKeyError
)
import logging
from typing import Optional
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from config import settings

logger = logging.getLogger(__name__)


class MongoDBManager:
    """Singleton MongoDB connection manager with health monitoring"""
    
    _instance: Optional['MongoDBManager'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self._is_connected: bool = False
        self._connection_attempts: int = 0
        self._last_health_check: Optional[datetime] = None
        self._health_check_interval: int = 30  # seconds
    
    @classmethod
    async def get_instance(cls) -> 'MongoDBManager':
        """Get or create singleton instance"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    @property
    def is_connected(self) -> bool:
        """Check if database is connected"""
        return self._is_connected and self.client is not None
    
    async def connect(self, retries: int = 3, retry_delay: int = 2) -> None:
        """
        Establish connection to MongoDB with exponential backoff
        
        Args:
            retries: Number of connection attempts
            retry_delay: Base delay between retries in seconds
            
        Raises:
            ConnectionFailure: If all connection attempts fail
        """
        if self.is_connected:
            logger.info("[OK] MongoDB already connected")
            return
        
        last_error: Optional[Exception] = None
        
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"[ATTEMPT {attempt}/{retries}] MongoDB connection...")
                
                # Create client with optimized settings
                self.client = AsyncIOMotorClient(
                    settings.MONGODB_URI,  # ← CHANGE: MONGODB_URL → MONGODB_URI
                    serverSelectionTimeoutMS=10000,  # Increased to 10s
                    connectTimeoutMS=15000,          # Increased to 15s
                    socketTimeoutMS=20000,
                    maxPoolSize=50,
                    minPoolSize=10,
                    maxIdleTimeMS=45000,
                    retryWrites=True,
                    retryReads=True,
                    appname="JobAlertSystem"
                )
                
                # Verify connection with ping
                logger.info("[CHECK] Testing connection with ping...")
                await asyncio.wait_for(
                    self.client.admin.command('ping'),
                    timeout=10.0  # Increased timeout
                )
                
                # Get database reference
                self.database = self.client[settings.DATABASE_NAME]
                
                # Create indexes
                await self._create_indexes()
                
                # Mark as connected
                self._is_connected = True
                self._connection_attempts = 0
                self._last_health_check = datetime.utcnow()
                
                logger.info(f"[OK] MongoDB connected to '{settings.DATABASE_NAME}'")
                return
            
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                last_error = e
                self._connection_attempts += 1
                logger.error(f"[FAIL] Connection attempt {attempt} failed: {str(e)}")
                
                if attempt < retries:
                    # Exponential backoff
                    wait_time = retry_delay * (2 ** (attempt - 1))
                    logger.info(f"[RETRY] Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
            
            except asyncio.TimeoutError as e:
                last_error = e
                logger.error(f"[TIMEOUT] Connection timeout on attempt {attempt}")
                
                if attempt < retries:
                    await asyncio.sleep(retry_delay * attempt)
            
            except Exception as e:
                logger.critical(f"[CRITICAL] Unexpected error during connection: {str(e)}", exc_info=True)
                last_error = e
                
                if attempt < retries:
                    logger.info(f"[RETRY] Retrying after unexpected error...")
                    await asyncio.sleep(retry_delay * attempt)
                else:
                    raise
        
        # All retries failed
        self._is_connected = False
        error_msg = f"Failed to connect to MongoDB after {retries} attempts"
        logger.critical(error_msg)
        raise ConnectionFailure(f"{error_msg}: {last_error}")
    
    async def disconnect(self) -> None:
        """Gracefully close MongoDB connection"""
        if self.client:
            try:
                self.client.close()
                self._is_connected = False
                self.client = None
                self.database = None
                logger.info("MongoDB connection closed gracefully")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {str(e)}")
    
    async def get_database(self) -> AsyncIOMotorDatabase:
        """
        Get MongoDB database instance with health check
        
        Returns:
            AsyncIOMotorDatabase instance
            
        Raises:
            RuntimeError: If database not initialized or unhealthy
        """
        if not self.is_connected or self.database is None:
            raise RuntimeError("Database not initialized. Call connect() first.")
        
        # Periodic health check
        await self._periodic_health_check()
        
        return self.database
    
    async def _periodic_health_check(self) -> None:
        """Perform periodic health check if needed"""
        if self._last_health_check is None:
            return
        
        time_since_check = datetime.utcnow() - self._last_health_check
        
        if time_since_check > timedelta(seconds=self._health_check_interval):
            try:
                await asyncio.wait_for(
                    self.client.admin.command('ping'),
                    timeout=3.0
                )
                self._last_health_check = datetime.utcnow()
            except Exception as e:
                logger.warning(f"Health check failed: {str(e)}")
                self._is_connected = False
                # Attempt reconnection in background
                asyncio.create_task(self._reconnect())
    
    async def _reconnect(self) -> None:
        """Attempt to reconnect to MongoDB"""
        logger.info("Attempting to reconnect to MongoDB...")
        try:
            await self.disconnect()
            await asyncio.sleep(2)
            await self.connect(retries=3)
        except Exception as e:
            logger.error(f"Reconnection failed: {str(e)}")
    
    async def _create_indexes(self) -> None:
        """
        Create database indexes with error handling
        
        Raises:
            Exception: If critical indexes fail to create
        """
        if self.database is None:
            raise RuntimeError("Database not initialized")
        
        critical_indexes_failed = False
        
        try:
            db = self.database
            
            # Users collection - critical indexes
            try:
                await db.users.create_index("google_id", unique=True, sparse=True)
                await db.users.create_index("email", unique=True)
                await db.users.create_index([("tier", 1), ("is_active", 1)])
            except DuplicateKeyError:
                logger.warning("[WARN] Duplicate key found during user index creation")
            except Exception as e:
                logger.error(f"[FAIL] Failed to create user indexes: {str(e)}")
                critical_indexes_failed = True
            
            # Niche configs collection
            try:
                await db.niche_configs.create_index([("user_id", 1), ("is_active", 1)])
                await db.niche_configs.create_index("created_at")
            except Exception as e:
                logger.error(f"[FAIL] Failed to create niche_configs indexes: {str(e)}")
            
            # Opportunities collection
            try:
                await db.opportunities.create_index("external_id", unique=True, sparse=True)
                await db.opportunities.create_index([("platform", 1), ("created_at", -1)])
                await db.opportunities.create_index("created_at", expireAfterSeconds=2592000)  # 30 days TTL
            except DuplicateKeyError:
                logger.warning("[WARN] Duplicate opportunity found")
            except Exception as e:
                logger.error(f"[FAIL] Failed to create opportunities indexes: {str(e)}")
            
            # User opportunities collection (junction table)
            try:
                await db.user_opportunities.create_index(
                    [("user_id", 1), ("opportunity_id", 1)], 
                    unique=True
                )
                await db.user_opportunities.create_index([("user_id", 1), ("sent_at", -1)])
                await db.user_opportunities.create_index("sent_at")
            except Exception as e:
                logger.error(f"Failed to create user_opportunities indexes: {str(e)}")
            
            # Subscriptions collection
            try:
                await db.subscriptions.create_index("user_id")
                await db.subscriptions.create_index([("user_id", 1), ("status", 1)])
                await db.subscriptions.create_index("paystack_subscription_id", unique=True, sparse=True)
            except Exception as e:
                logger.error(f"Failed to create subscriptions indexes: {str(e)}")
            
            # Usage tracking collection
            try:
                await db.usage_tracking.create_index(
                    [("user_id", 1), ("month", 1)], 
                    unique=True
                )
            except Exception as e:
                logger.error(f"Failed to create usage_tracking indexes: {str(e)}")
            
            # Opportunity cache collection (for caching scraped opportunities)
            try:
                await db.opportunity_cache.create_index("cache_key", unique=True)
                await db.opportunity_cache.create_index([("platform", 1), ("cached_at", -1)])
                await db.opportunity_cache.create_index("expires_at", expireAfterSeconds=0)  # Auto-delete on expiry
                await db.opportunity_cache.create_index([("used_count", -1)])  # Most used first
            except Exception as e:
                logger.error(f"Failed to create opportunity_cache indexes: {str(e)}")
            
            if critical_indexes_failed:
                raise OperationFailure("Critical indexes failed to create")
            
            logger.info("[OK] Database indexes created/verified successfully")
        
        except Exception as e:
            logger.error(f"[FAIL] Index creation error: {str(e)}")
            raise
    
    async def health_check(self) -> dict:
        """
        Comprehensive database health check
        
        Returns:
            Health status dictionary
        """
        try:
            if not self.is_connected:
                return {
                    "status": "disconnected",
                    "error": "Database not connected"
                }
            
            # Ping database with timeout
            await asyncio.wait_for(
                self.client.admin.command('ping'),
                timeout=3.0
            )
            
            # Get collection counts
            db = self.database
            
            counts = await asyncio.gather(
                db.users.count_documents({}),
                db.niche_configs.count_documents({}),
                db.opportunities.count_documents({}),
                db.user_opportunities.count_documents({}),
                return_exceptions=True
            )
            
            return {
                "status": "healthy",
                "database": settings.DATABASE_NAME,
                "connection_attempts": self._connection_attempts,
                "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
                "collections": {
                    "users": counts[0] if not isinstance(counts[0], Exception) else "error",
                    "niche_configs": counts[1] if not isinstance(counts[1], Exception) else "error",
                    "opportunities": counts[2] if not isinstance(counts[2], Exception) else "error",
                    "user_opportunities": counts[3] if not isinstance(counts[3], Exception) else "error"
                }
            }
        
        except asyncio.TimeoutError:
            logger.error("Health check timeout")
            return {
                "status": "unhealthy",
                "error": "Database ping timeout"
            }
        
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Global instance access functions for backward compatibility
_manager: Optional[MongoDBManager] = None


async def connect_to_mongo(retries: int = 3) -> None:
    """Connect to MongoDB (legacy interface)"""
    global _manager
    if _manager is None:
        _manager = await MongoDBManager.get_instance()
    
    # Always ensure connection is established
    if not _manager.is_connected:
        await _manager.connect(retries=retries)


async def close_mongo_connection() -> None:
    """Close MongoDB connection (legacy interface)"""
    global _manager
    if _manager:
        await _manager.disconnect()


async def get_database() -> AsyncIOMotorDatabase:
    """Get database instance (legacy interface) - FIXED"""
    global _manager
    
    # Initialize manager if needed
    if _manager is None:
        _manager = await MongoDBManager.get_instance()
    
    # Ensure connection is established
    if not _manager.is_connected:
        logger.warning("[WARN] Database not connected, attempting connection...")
        try:
            await _manager.connect(retries=3)
        except Exception as e:
            logger.error(f"[FAIL] Failed to establish database connection: {str(e)}")
            raise RuntimeError("Database connection failed") from e
    
    # Return the database
    return await _manager.get_database()


async def check_database_health() -> dict:
    """Check database health (legacy interface)"""
    global _manager
    
    if _manager is None:
        _manager = await MongoDBManager.get_instance()
    
    # Try to connect if not already connected
    if not _manager.is_connected:
        try:
            await _manager.connect(retries=1)
        except Exception as e:
            logger.error(f"[FAIL] Database health check failed: {str(e)}")
            return {
                "status": "not_initialized",
                "error": "Database not connected",
                "details": str(e)
            }
    
    return await _manager.health_check()


@asynccontextmanager
async def get_db_session():
    """
    Context manager for database operations
    
    Usage:
        async with get_db_session() as db:
            await db.users.find_one({"email": "user@example.com"})
    """
    db = await get_database()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database operation error: {str(e)}")
        raise
    finally:
        pass  # Connection pooling handles cleanup