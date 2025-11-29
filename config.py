"""
Application Configuration & Tier Limits
OPTIMIZED: Render-compatible environment variable handling
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env only in development (not on Render)
if os.getenv("RENDER") != "true":  # Render sets this automatically
    BASE_DIR = Path(__file__).resolve().parent
    ENV_FILE = BASE_DIR / ".env"
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
        print(f"✅ Loaded .env from: {ENV_FILE}")
    else:
        print(f"⚠️  .env file not found at: {ENV_FILE}")
else:
    print("✅ Running on Render - using environment variables")


class Settings(BaseSettings):
    """Application settings with explicit defaults"""
    
    # Environment
    DEBUG: bool = Field(default=False, validation_alias="DEBUG")
    API_URL: str = Field(default="https://huntr-backend.onrender.com", validation_alias="API_URL")
    FRONTEND_URL: str = Field(default="https://huntr-bot.netlify.app", validation_alias="FRONTEND_URL")
    
    # MongoDB
    MONGODB_URI: str = Field(default="mongodb://localhost:27017", env="MONGODB_URI")
    # Make sure this matches what Render expects
    DATABASE_NAME: str = Field(default="jobhunter", validation_alias="DATABASE_NAME")
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = Field(default="", validation_alias="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = Field(default="", validation_alias="GOOGLE_CLIENT_SECRET")
    
    # JWT
    JWT_SECRET_KEY: str = Field(default="your-secret-key-change-this", validation_alias="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Encryption (for user's Twilio credentials)
    ENCRYPTION_KEY: str = Field(default="", validation_alias="ENCRYPTION_KEY")
    
    # Paystack
    PAYSTACK_SECRET_KEY: str = Field(default="", validation_alias="PAYSTACK_SECRET_KEY")
    PAYSTACK_PUBLIC_KEY: str = Field(default="", validation_alias="PAYSTACK_PUBLIC_KEY")
    PAYSTACK_WEBHOOK_SECRET: str = Field(default="", validation_alias="PAYSTACK_WEBHOOK_SECRET")
    
    # Gmail SMTP
    SMTP_USERNAME: str = Field(default="", validation_alias="SMTP_USERNAME")
    SMTP_PASSWORD: str = Field(default="", validation_alias="SMTP_PASSWORD")
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    
    # OpenRouter AI
    OPENROUTER_API_KEY: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    
    # Twitter API
    TWITTER_BEARER_TOKEN: str = Field(default="", validation_alias="TWITTER_BEARER_TOKEN")
    
    # CoinMarketCap
    CMC_API_KEY: str = Field(default="", validation_alias="CMC_API_KEY")
    
    # Telegram
    TELEGRAM_API_ID: int = Field(default=0, validation_alias="TELEGRAM_API_ID")
    TELEGRAM_API_HASH: str = Field(default="", validation_alias="TELEGRAM_API_HASH")
    TELEGRAM_PHONE: str = Field(default="", validation_alias="TELEGRAM_PHONE")
    
    # CORS - dynamically set based on environment
    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        if self.DEBUG:
            return ["*"]
        origins = [self.FRONTEND_URL]
        if self.API_URL:
            origins.append(self.API_URL)
        # Add Netlify frontend
        if "https://huntr-bot.netlify.app" not in origins:
            origins.append("https://huntr-bot.netlify.app")
        print(f"[CORS] Allowed origins: {origins}")  # Debug log
        return origins
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        populate_by_name = True
        extra = "ignore"
    
    def __init__(self, **data):
        super().__init__(**data)
        # Debug: Log telegram settings
        if self.TELEGRAM_API_ID:
            print(f"[CONFIG] Telegram API ID loaded: {self.TELEGRAM_API_ID}")
        if self.TELEGRAM_API_HASH:
            print(f"[CONFIG] Telegram API Hash loaded: {self.TELEGRAM_API_HASH[:20]}...")
        if self.TELEGRAM_PHONE:
            print(f"[CONFIG] Telegram Phone loaded: {self.TELEGRAM_PHONE}")


# TIER LIMITS (unchanged)
TIER_LIMITS = {
    "free": {
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
        "platforms": ["Twitter/X",  "Telegram"],
        "price_ngn": 0,
    },
    "pro": {
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
            "10 curated gigs per scan",
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
    },
    "premium": {
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
            "5 curated gigs per scan",
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
        "platforms": ["Twitter/X", "Web3.career", "Pump.fun", "DexScreener", "CoinMarketCap", "CoinGecko", "Telegram"],
        "price_ngn": 7500,
    }
}

# Scam detection keywords (unchanged)
SCAM_INDICATORS = {
    "comment_based": [
        "comment done", "comment interested", "comment hi", "reply done",
        "reply interested", "dm if interested", "dm to apply", "slide into dms",
        "comment your telegram", "comment your whatsapp", "comment your discord",
        "react if interested", "like if interested", "share if interested"
    ],
    "suspicious": [
        "guaranteed", "easy money", "passive income", "earn while you sleep",
        "work from home 100%", "no experience needed", "limited spots",
        "act now", "dont miss out", "only today", "high commission",
        "pyramid", "multi-level", "recruitment bonus"
    ],
    "urgency": [
        "urgent", "asap", "immediate", "right now", "this week only",
        "last chance", "hurry", "quickly", "fast", "no time"
    ]
}

# Salary detection patterns (unchanged)
SALARY_PATTERNS = {
    "hourly": [
        r"\$\d+/hr", r"₦\d+/hour", r"\d+k/hour", r"\$\d+-\$\d+/hour"
    ],
    "monthly": [
        r"\$\d+/month", r"₦\d+/month", r"\d+k/month", r"\$\d+-\$\d+/month"
    ],
    "project": [
        r"\$\d+-\$\d+", r"₦\d+-₦\d+", r"\$\d+ project", r"₦\d+ project"
    ]
}

CREDIT_COSTS = {
    "scan": 5,
    "ai_analysis": 2,
    "export": 1,
}

PLATFORM_CONFIGS = {
    'Twitter/X': {
        'enabled': True,
        'requires_api_key': True,
        'free_tier': True
    },
    'Web3.career': {
        'enabled': True,
        'requires_api_key': False,
        'free_tier': True
    },
    'Pump.fun': {
        'enabled': True,
        'requires_api_key': False,
        'free_tier': False
    },
    'DexScreener': {
        'enabled': True,
        'requires_api_key': False,
        'free_tier': False
    },
    'CoinMarketCap': {
        'enabled': True,
        'requires_api_key': True,
        'free_tier': False
    },
    'CoinGecko': {
        'enabled': True,
        'requires_api_key': False,
        'free_tier': False
    },
    'Telegram': {
        'enabled': True,
        'requires_api_key': True,
        'free_tier': True
    }
}

AI_MATCHING_CONFIG = {
    'min_confidence_threshold': 60,
    'timeout_seconds': 30,
    'max_retries': 2,
    'fallback_to_keywords': True
}

NOTIFICATION_CONFIG = {
    'whatsapp': {
        'enabled': True,
        'max_message_length': 1600,
        'rate_limit_seconds': 2
    },
    'email': {
        'enabled': True,
        'max_batch_size': 10,
        'from_name': 'Job Hunter'
    }
}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()


def validate_settings():
    """Validate critical settings are configured"""
    errors = []
    
    if not settings.MONGODB_URI or settings.MONGODB_URI == "mongodb+srv://user:pass@cluster.mongodb.net/jobhunter":
        errors.append("MONGODB_URI is not properly configured")
    if not settings.JWT_SECRET_KEY or settings.JWT_SECRET_KEY == "your-secret-key-change-this":
        errors.append("JWT_SECRET_KEY is not set or using default")
    if not settings.GOOGLE_CLIENT_ID:
        errors.append("GOOGLE_CLIENT_ID is not set")
    if not settings.OPENROUTER_API_KEY:
        errors.append("OPENROUTER_API_KEY is not set")
    
    if errors:
        print("\n⚠️  CONFIGURATION ERRORS:")
        for error in errors:
            print(f"   ❌ {error}")
        print("\n")
    else:
        print("✅ All critical settings configured\n")
    
    return len(errors) == 0


def validate_paystack_keys():
    """Validate Paystack configuration"""
    secret = settings.PAYSTACK_SECRET_KEY
    public = settings.PAYSTACK_PUBLIC_KEY
    
    print("\n" + "="*60)
    print("PAYSTACK CONFIGURATION CHECK")
    print("="*60)
    
    if not secret:
        print("❌ PAYSTACK_SECRET_KEY not set")
    elif secret.startswith('sk_test_'):
        print(f"✅ Paystack Secret Key: TEST KEY")
    elif secret.startswith('sk_live_'):
        print(f"⚠️  Paystack Secret Key: LIVE KEY")
    else:
        print(f"❌ Paystack Secret Key: INVALID FORMAT")
    
    if not public:
        print("❌ PAYSTACK_PUBLIC_KEY not set")
    elif public.startswith('pk_test_'):
        print(f"✅ Paystack Public Key: TEST KEY")
    elif public.startswith('pk_live_'):
        print(f"⚠️  Paystack Public Key: LIVE KEY")
    else:
        print(f"❌ Paystack Public Key: INVALID FORMAT")
    
    print("="*60 + "\n")


# Auto-validate on import (only in non-test environments)
if __name__ != "__main__" and os.getenv("PYTEST_CURRENT_TEST") is None:
    validate_settings()
    if settings.PAYSTACK_SECRET_KEY:  # Only validate if keys are set
        validate_paystack_keys()