"""
FastAPI Application Entry Point
Multi-Tenant Job Hunter Backend - RENDER OPTIMIZED
Added: Admin Dashboard, Monitoring, Reports, Scan, Dashboard modules
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import sys
import os

from config import settings
from app.database.connection import connect_to_mongo, close_mongo_connection
from app.scheduler.tasks import start_scheduler, shutdown_scheduler
from app.monitoring.keep_alive import KeepAliveService

# Import all routers
from app.auth.oauth import router as auth_router
from app.auth.oauth_enhanced import router as auth_enhanced_router
from app.auth.traditional import router as traditional_auth_router
from app.auth.follow import router as follow_router
from app.niches.routes import router as niches_router
from app.opportunities.routes import router as opportunities_router
from app.payments.paystack import router as payments_router
from app.credits.routes import router as credits_router  # Import credit router

# NEW: Admin, Monitoring, Reports modules
from app.admin.routes import router as admin_router
from app.monitoring.routes import router as monitoring_router
from app.reports.routes import router as reports_router

# NEW: Scan and Dashboard modules
from app.scan.routes import router as scan_router
from app.dashboard.routes import router as dashboard_router

# NEW: API Metrics Middleware
from app.monitoring.metrics import APIMetricsMiddleware

# NEW: Promo management module
from app.promo.routes import router as promo_router
from routes.pricing import router as pricing_router

# Configure logging with Windows UTF-8 support
def setup_logging():
    """Configure logging with proper encoding for Windows"""
    # Force UTF-8 encoding for all handlers
    if sys.platform == "win32":
        import io
        # Reconfigure stdout to use UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # File handler with UTF-8 encoding
            logging.FileHandler('app.log', encoding='utf-8'),
            # Console handler with UTF-8 encoding
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Get logger
    logger = logging.getLogger(__name__)
    
    # Force UTF-8 for all handlers
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.setEncoding('utf-8')
    
    return logger


logger = setup_logging()


keep_alive_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("=" * 60)
    logger.info("Starting Multi-Tenant Job Hunter Backend (v2.1 - Render Optimized)...")
    logger.info("=" * 60)
    
    connection_success = False
    
    try:
        # Connect to MongoDB - CRITICAL STEP
        logger.info("[INFO] Connecting to MongoDB...")
        await connect_to_mongo()
        logger.info("[OK] MongoDB connected successfully")
        connection_success = True
        
        # Verify connection with health check
        health = await check_database_health()
        if health.get("status") != "healthy":
            raise RuntimeError(f"Database health check failed: {health.get('error', 'Unknown error')}")
        
        logger.info("[OK] Database health check passed")
        
        # Initialize admin user if needed
        await initialize_admin_user()
        
        # Initialize database fields
        await initialize_database_fields()
        
    except Exception as e:
        logger.critical(f"[FAIL] MongoDB connection failed: {str(e)}")
        if not connection_success:
            logger.critical("[CRITICAL] Application cannot start without database connection")
            # Don't raise - let the app start but it will fail on requests
            logger.warning("[WARNING] App starting in degraded mode - database unavailable")
    
    try:
        # Start background scheduler
        start_scheduler()
        logger.info("[OK] Background scheduler started")
    except Exception as e:
        logger.error(f"[WARN] Scheduler start failed: {str(e)}")
    
    # NEW: Start keep-alive service for Render free tier
    try:
        global keep_alive_service
        keep_alive_service = KeepAliveService(settings.API_URL)
        await keep_alive_service.start()
        logger.info("[OK] Keep-alive service started (Render optimization)")
    except Exception as e:
        logger.error(f"[WARN] Keep-alive service failed: {str(e)}")
    
    logger.info("=" * 60)
    logger.info("Application startup complete!")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("Shutting down application...")
    logger.info("=" * 60)
    shutdown_scheduler()
    
    # NEW: Stop keep-alive service
    if keep_alive_service:
        await keep_alive_service.stop()
    
    await close_mongo_connection()
    logger.info("[OK] Cleanup complete")


# Initialize FastAPI app
app = FastAPI(
    title="Job Hunter API",
    description="Multi-tenant job hunting platform with AI matching and admin dashboard",
    version="2.1.0",
    lifespan=lifespan
)

# API Metrics Middleware (MUST come first to track all requests)
app.add_middleware(APIMetricsMiddleware)

# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET_KEY,
    max_age=3600,
    same_site="lax",
    https_only=not settings.DEBUG
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5500",
        "http://localhost:5501",
        "https://huntr-bot.netlify.app",  # ← Add your frontend
    ] if settings.DEBUG else settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    # Log to system_alerts collection for monitoring
    try:
        from app.database.connection import get_database
        from datetime import datetime
        db = await get_database()
        await db.system_alerts.insert_one({
            "level": "error",
            "message": str(exc),
            "source": request.url.path,
            "timestamp": datetime.utcnow()
        })
    except:
        pass
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.DEBUG else "An error occurred"
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from app.database.connection import check_database_health
    
    db_health = await check_database_health()
    
    return {
        "status": "healthy" if db_health.get("status") == "healthy" else "unhealthy",
        "service": "job-hunter-api",
        "version": "2.1.0",
        "database": db_health
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Job Hunter API v2.1",
        "status": "operational",
        "features": [
            "Multi-tenant job hunting",
            "AI-powered matching",
            "Admin dashboard",
            "Real-time monitoring",
            "Automated scanning"
        ],
        "docs": f"{settings.API_URL}/docs",
        "health": f"{settings.API_URL}/health"
    }


# Include routers
# Authentication
app.include_router(auth_router)
app.include_router(auth_enhanced_router)
app.include_router(traditional_auth_router)
app.include_router(follow_router)

# User features
app.include_router(niches_router)
app.include_router(opportunities_router)
app.include_router(scan_router)
app.include_router(dashboard_router)

# Payments
app.include_router(payments_router)

# Credits management
app.include_router(credits_router)

# Admin features
app.include_router(admin_router)
app.include_router(monitoring_router)
app.include_router(reports_router)

# Promotional management ← VERIFY THIS IS INCLUDED
app.include_router(promo_router)

# Register public routes (no auth required)
app.include_router(pricing_router)

# Add new routers
from app.scan.curated_routes import router as curated_router
from app.documents.routes import router as documents_router

# Include new routers
app.include_router(curated_router)
app.include_router(documents_router)

from app.admin import routes as admin_routes

app.include_router(admin_routes.router)


async def initialize_admin_user():
    """
    Create initial admin user if none exists
    Only runs once on first startup
    """
    try:
        from app.database.connection import get_database
        from datetime import datetime
        
        db = await get_database()
        
        # Check if any admin exists
        admin_exists = await db.users.find_one({"is_admin": True})
        
        if not admin_exists:
            # Create default admin (you should change these credentials!)
            admin_user = {
                "google_id": "admin-default",
                "email": "admin@jobhunter.com",
                "name": "System Admin",
                "profile_picture": None,
                "tier": "premium",
                "is_active": True,
                "is_admin": True,  # Admin flag
                "created_at": datetime.utcnow(),
                "last_login": datetime.utcnow(),
                "settings": {
                    "notifications_enabled": True,
                    "email_notifications": True,
                    "whatsapp_notifications": False
                }
            }
            
            result = await db.users.insert_one(admin_user)
            logger.warning(f"Default admin user created: admin@jobhunter.com")
            logger.warning("IMPORTANT: Change admin credentials immediately!")
        else:
            logger.info("Admin user already exists")
    
    except Exception as e:
        logger.error(f"Error initializing admin user: {str(e)}")


async def initialize_database_fields():
    """
    Add new fields to existing collections
    """
    try:
        from app.database.connection import get_database
        from datetime import datetime
        
        db = await get_database()
        
        # Add is_admin, last_active_at, total_api_calls to existing users
        await db.users.update_many(
            {"is_admin": {"$exists": False}},
            {"$set": {"is_admin": False}}
        )
        
        await db.users.update_many(
            {"last_active_at": {"$exists": False}},
            {"$set": {"last_active_at": datetime.utcnow()}}
        )
        
        await db.users.update_many(
            {"total_api_calls": {"$exists": False}},
            {"$set": {"total_api_calls": 0}}
        )
        
        logger.info("Database fields initialized")
    
    except Exception as e:
        logger.error(f"Error initializing database fields: {str(e)}")


async def check_database_health():
    """Check database health"""
    from app.database.connection import check_database_health
    return await check_database_health()


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    
    logger.info("="*60)
    logger.info("Starting Uvicorn Server...")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    logger.info(f"API URL: {settings.API_URL}")
    logger.info("="*60)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,  # ← Use PORT env var from Render
        reload=settings.DEBUG,
        log_level="info"
    )