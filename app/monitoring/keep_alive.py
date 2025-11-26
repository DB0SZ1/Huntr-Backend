"""Keep-alive service to prevent Render free tier from spinning down"""
import httpx
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

class KeepAliveService:
    """Ping the API periodically to prevent sleep"""
    
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.scheduler: AsyncIOScheduler = None
    
    async def start(self):
        """Start keep-alive pings"""
        self.scheduler = AsyncIOScheduler()
        # Ping every 14 minutes (Render spins down after 15 min inactivity)
        self.scheduler.add_job(self._ping, 'interval', minutes=14, id='keep_alive_ping')
        self.scheduler.start()
        logger.info("✓ Keep-alive service started (pings every 14 min)")
    
    async def stop(self):
        """Stop keep-alive pings"""
        if self.scheduler:
            self.scheduler.shutdown()
    
    async def _ping(self):
        """Ping health endpoint"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_url}/health", timeout=5)
                if response.status_code == 200:
                    logger.debug(f"[PING] Keep-alive successful at {datetime.now()}")
                else:
                    logger.warning(f"[PING] Unexpected status: {response.status_code}")
        except Exception as e:
            logger.error(f"[PING] Failed: {str(e)}")
