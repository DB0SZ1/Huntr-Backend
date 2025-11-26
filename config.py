"""
Application Configuration & Tier Limits
FIXED: Explicit .env loading for Windows compatibility
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache
import os
from pathlib import Path
from dotenv import load_dotenv

# CRITICAL FIX: Explicitly load .env file
# Get the project root directory
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

# Force load .env file
if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=True)
    print(f"✅ Loaded .env from: {ENV_FILE}")
else:
    print(f"⚠️  .env file not found at: {ENV_FILE}")


class Settings(BaseSettings):
    """Application settings with explicit defaults"""
    
    # Environment
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    API_URL: str = os.getenv("API_URL", "http://localhost:8000")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5501")  # Match your Live Server port
    
    # MongoDB
    MONGODB_URI: str = os.getenv(
        "MONGODB_URI",
        "mongodb+srv://user:pass@cluster.mongodb.net/jobhunter"
    )
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "jobhunter")
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Encryption (for user's Twilio credentials)
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    # Paystack
    PAYSTACK_SECRET_KEY: str = os.getenv("PAYSTACK_SECRET_KEY", "")
    PAYSTACK_PUBLIC_KEY: str = os.getenv("PAYSTACK_PUBLIC_KEY", "")
    PAYSTACK_WEBHOOK_SECRET: str = os.getenv("PAYSTACK_WEBHOOK_SECRET", "")
    
    # Gmail SMTP
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    
    # OpenRouter AI
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    
    # Twitter API
    TWITTER_BEARER_TOKEN: str = os.getenv("TWITTER_BEARER_TOKEN", "")
    
    # CoinMarketCap
    CMC_API_KEY: str = os.getenv("CMC_API_KEY", "")
    
    # Telegram
    TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_PHONE: str = os.getenv("TELEGRAM_PHONE", "")
    
    # CORS
    ALLOWED_ORIGINS: list = [
        os.getenv("FRONTEND_URL", "https://your-frontend.vercel.app"),
        "https://your-app.railway.app"
    ]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Allow population by field name
        populate_by_name = True
        extra = "ignore"  # Ignore extra fields
    
    def __init__(self, **data):
        super().__init__(**data)
        # Debug: Log telegram settings
        if self.TELEGRAM_API_ID:
            print(f"[CONFIG] Telegram API ID loaded: {self.TELEGRAM_API_ID}")
        if self.TELEGRAM_API_HASH:
            print(f"[CONFIG] Telegram API Hash loaded: {self.TELEGRAM_API_HASH[:20]}...")
        if self.TELEGRAM_PHONE:
            print(f"[CONFIG] Telegram Phone loaded: {self.TELEGRAM_PHONE}")


# UPDATED TIER LIMITS with new features
TIER_LIMITS = {
    "free": {
        "max_niches": 1,
        "scans_per_day": 2,  # ← NEW: 2 scans per day
        "curated_gigs_per_scan": 3,  # ← NEW: 3 curated gigs per scan
        "scan_interval_minutes": 0,
        "auto_scan_enabled": False,
        "monthly_opportunities_limit": 50,
        "daily_credits": 10,
        "credit_refill_hour": 0,
        "features": [
            "Create 1 niche",
            "2 scans per day",
            "3 curated gigs per scan",
            "Scam detection",
            "Salary detection",
            "Manual scanning only",
            "Up to 50 opportunities/month",
            "Email notifications"
        ],
        "platforms": ["Twitter/X", "Reddit"],
        "price_ngn": 0,
    },
    "pro": {
        "max_niches": 5,
        "scans_per_day": 5,  # ← NEW: 5 scans per day
        "curated_gigs_per_scan": 4,  # ← NEW: 4 curated gigs per scan
        "scan_interval_minutes": 90,
        "auto_scan_enabled": True,
        "monthly_opportunities_limit": 500,
        "daily_credits": 50,
        "credit_refill_hour": 0,
        "features": [
            "Create up to 5 niches",
            "5 scans per day",
            "4 curated gigs per scan",
            "Advanced scam detection",
            "Salary detection & analysis",
            "Automatic scans every 90 minutes",
            "Up to 500 opportunities/month",
            "CV Analyzer Lite (PDF <5MB)",
            "Email + WhatsApp notifications",
            "Priority support"
        ],
        "platforms": ["Twitter/X", "Reddit", "Web3.career", "Telegram"],
        "price_ngn": 2500,
    },
    "premium": {
        "max_niches": 20,
        "scans_per_day": 10,  # ← NEW: 10 scans per day
        "curated_gigs_per_scan": 5,  # ← NEW: 5 curated gigs per scan
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
        "platforms": ["Twitter/X", "Reddit", "Web3.career", "Pump.fun", "DexScreener", "CoinMarketCap", "CoinGecko", "Telegram"],
        "price_ngn": 7500,
    }
}

# Scam detection keywords
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

# Salary detection patterns
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


# Credit costs
CREDIT_COSTS = {
    "scan": 5,  # Each scan costs 5 credits
    "ai_analysis": 2,  # AI analysis costs 2 credits
    "export": 1,  # Export costs 1 credit
}


# Platform configurations
PLATFORM_CONFIGS = {
    'Twitter/X': {
        'enabled': True,
        'requires_api_key': True,
        'free_tier': True
    },
    'Reddit': {
        'enabled': True,
        'requires_api_key': False,
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
        'free_tier': False
    }
}


# AI matching configuration
AI_MATCHING_CONFIG = {
    'min_confidence_threshold': 60,
    'timeout_seconds': 30,
    'max_retries': 2,
    'fallback_to_keywords': True
}


# Notification settings
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


# Create global settings instance
settings = get_settings()

# Validation check
def validate_settings():
    """Validate critical settings are configured"""
    errors = []
    
    if not settings.MONGODB_URI:
        errors.append("MONGODB_URI is not set")
    if not settings.JWT_SECRET_KEY:
        errors.append("JWT_SECRET_KEY is not set")
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

# Add key validation
def validate_paystack_keys():
    """Validate Paystack configuration"""
    secret = settings.PAYSTACK_SECRET_KEY
    public = settings.PAYSTACK_PUBLIC_KEY
    
    print("\n" + "="*60)
    print("PAYSTACK CONFIGURATION CHECK")
    print("="*60)
    
    # Check secret key
    if not secret:
        print("❌ PAYSTACK_SECRET_KEY not set in .env")
    elif secret.startswith('sk_test_'):
        print(f"✅ Paystack Secret Key: TEST KEY (correct)")
    elif secret.startswith('sk_live_'):
        print(f"⚠️  Paystack Secret Key: LIVE KEY (for production only!)")
    else:
        print(f"❌ Paystack Secret Key: INVALID FORMAT")
        print(f"   Expected: sk_test_xxx or sk_live_xxx")
        print(f"   Got: {secret[:30]}...")
    
    # Check public key
    if not public:
        print("❌ PAYSTACK_PUBLIC_KEY not set in .env")
    elif public.startswith('pk_test_'):
        print(f"✅ Paystack Public Key: TEST KEY (correct)")
    elif public.startswith('pk_live_'):
        print(f"⚠️  Paystack Public Key: LIVE KEY (for production only!)")
    else:
        print(f"❌ Paystack Public Key: INVALID FORMAT")
    
    print("="*60 + "\n")

# Auto-validate on import
if __name__ != "__main__":
    validate_settings()
    validate_paystack_keys()  # ← Add this