"""
Enhanced Pydantic Models for MongoDB Collections
Complete data validation with better type safety
"""
from pydantic import BaseModel, EmailStr, Field, validator, root_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson.objectid import ObjectId
from enum import Enum


class PyObjectId(ObjectId):
    """Custom type for MongoDB ObjectId with validation"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId format")
        return ObjectId(v)
    
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class TierEnum(str, Enum):
    """Subscription tier enum"""
    FREE = "free"
    PRO = "pro"
    PREMIUM = "premium"


class PlatformEnum(str, Enum):
    """Available platforms enum"""
    TWITTER = "Twitter/X"
    REDDIT = "Reddit"
    WEB3_CAREER = "Web3.career"
    PUMP_FUN = "Pump.fun"
    DEX_SCREENER = "DexScreener"
    COINMARKETCAP = "CoinMarketCap"
    COINGECKO = "CoinGecko"
    TELEGRAM = "Telegram"


class UserSettings(BaseModel):
    """User notification and preference settings"""
    notifications_enabled: bool = True
    email_notifications: bool = True
    whatsapp_notifications: bool = False
    notification_hours: Dict[str, int] = Field(
        default={"start": 8, "end": 22},
        description="Hours when user wants notifications (UTC)"
    )
    timezone: str = "UTC"
    language: str = "en"


class UserModel(BaseModel):
    """Enhanced user document model with full validation"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    google_id: Optional[str] = Field(None, min_length=1)  # Optional - not set for traditional auth
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    profile_picture: Optional[str] = None
    tier: TierEnum = TierEnum.FREE
    is_active: bool = True
    is_email_verified: bool = True  # From Google OAuth
    settings: UserSettings = Field(default_factory=UserSettings)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: datetime = Field(default_factory=datetime.utcnow)
    last_scan_at: Optional[datetime] = None
    
    # Encrypted Twilio credentials (optional - user configures)
    encrypted_twilio_credentials: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}
        use_enum_values = True
        schema_extra = {
            "example": {
                "google_id": "123456789",
                "email": "user@example.com",
                "name": "John Doe",
                "tier": "free",
                "is_active": True
            }
        }
    
    @validator('profile_picture')
    def validate_profile_picture(cls, v):
        """Validate profile picture URL"""
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("Profile picture must be a valid URL")
        return v


class NicheConfigModel(BaseModel):
    """Enhanced user's custom job niche configuration"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    keywords: List[str] = Field(..., min_items=1, max_items=20)
    excluded_keywords: List[str] = Field(default=[], max_items=20)
    platforms: List[PlatformEnum] = Field(..., min_items=1)
    min_confidence: int = Field(default=60, ge=0, le=100)
    is_active: bool = True
    priority: int = Field(default=1, ge=1, le=10, description="Priority for matching (1=highest)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Statistics
    total_matches: int = Field(default=0, ge=0)
    last_match_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}
        use_enum_values = True
        schema_extra = {
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "name": "Frontend React Jobs",
                "description": "Remote React developer positions",
                "keywords": ["react", "frontend", "javascript", "remote"],
                "excluded_keywords": ["senior", "lead"],
                "platforms": ["Twitter/X", "Reddit"],
                "min_confidence": 70
            }
        }
    
    @validator('keywords', 'excluded_keywords')
    def validate_keywords(cls, v):
        """Normalize keywords to lowercase"""
        return [kw.lower().strip() for kw in v if kw.strip()]
    
    @root_validator
    def validate_keywords_not_overlap(cls, values):
        """Ensure keywords and excluded_keywords don't overlap"""
        keywords = set(values.get('keywords', []))
        excluded = set(values.get('excluded_keywords', []))
        
        overlap = keywords & excluded
        if overlap:
            raise ValueError(f"Keywords cannot be in both include and exclude: {overlap}")
        
        return values


class OpportunityModel(BaseModel):
    """Enhanced job opportunity from scrapers"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    external_id: str = Field(..., description="Unique ID from source platform")
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", max_length=5000)
    platform: PlatformEnum
    url: str = Field(..., description="Link to opportunity")
    
    # Contact information
    contact: Optional[str] = None
    telegram: Optional[str] = None
    twitter: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    
    # Platform-specific metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Status tracking
    is_active: bool = True
    times_matched: int = Field(default=0, ge=0)
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}
        use_enum_values = True
    
    @validator('url', 'website')
    def validate_url(cls, v):
        """Validate URLs"""
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("Must be a valid URL starting with http:// or https://")
        return v


class AIAnalysis(BaseModel):
    """AI matching analysis result"""
    is_match: bool
    confidence: int = Field(..., ge=0, le=100)
    reasoning: str
    relevant_keywords: List[str] = Field(default_factory=list)
    urgency: str = Field(default="medium")  # high, medium, low
    match_score: Optional[float] = None
    
    @validator('urgency')
    def validate_urgency(cls, v):
        """Validate urgency level"""
        if v not in ['high', 'medium', 'low']:
            return 'medium'
        return v


class UserOpportunityModel(BaseModel):
    """Enhanced user-opportunity relationship (what's been sent)"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    opportunity_id: str
    niche_id: str
    
    # AI analysis result
    confidence: int = Field(..., ge=0, le=100)
    ai_analysis: AIAnalysis
    
    # User interaction
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    viewed: bool = False
    viewed_at: Optional[datetime] = None
    saved: bool = False
    saved_at: Optional[datetime] = None
    applied: bool = False
    applied_at: Optional[datetime] = None
    
    # Notification tracking
    notification_sent_via: List[str] = Field(default_factory=list)  # ['whatsapp', 'email']
    notification_failed: bool = False
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class SubscriptionModel(BaseModel):
    """Enhanced subscription tracking"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    tier: TierEnum
    status: str = Field(default="active")  # active, cancelled, expired, past_due
    
    # Payment details
    payment_method: Optional[str] = None
    paystack_subscription_id: Optional[str] = None
    paystack_customer_code: Optional[str] = None
    
    # Billing period
    current_period_start: datetime
    current_period_end: datetime
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    cancelled_at: Optional[datetime] = None
    
    # Auto-renewal
    auto_renew: bool = True
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}
        use_enum_values = True
    
    @validator('status')
    def validate_status(cls, v):
        """Validate subscription status"""
        allowed = ['active', 'cancelled', 'expired', 'past_due', 'trial']
        if v not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(allowed)}")
        return v


class UsageTrackingModel(BaseModel):
    """Enhanced monthly usage tracking"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    month: str = Field(..., regex=r"^\d{4}-\d{2}$")  # YYYY-MM format
    
    # Usage metrics
    opportunities_sent: int = Field(default=0, ge=0)
    scans_completed: int = Field(default=0, ge=0)
    ai_analyses_used: int = Field(default=0, ge=0)
    notifications_sent: int = Field(default=0, ge=0)
    
    # Detailed breakdown
    notifications_by_channel: Dict[str, int] = Field(
        default_factory=lambda: {"whatsapp": 0, "email": 0}
    )
    opportunities_by_platform: Dict[str, int] = Field(default_factory=dict)
    
    # Timestamps
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


class UserScanModel(BaseModel):
    """Enhanced scan history tracking"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    scanned_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Scan results
    opportunities_found: int = Field(default=0, ge=0)
    matches_sent: int = Field(default=0, ge=0)
    
    # Performance metrics
    duration_seconds: float = Field(default=0.0, ge=0)
    platforms_scanned: List[str] = Field(default_factory=list)
    
    # Errors
    errors: List[str] = Field(default_factory=list)
    success: bool = True
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, datetime: lambda v: v.isoformat()}


# Request/Response Models for API

class CreateNicheRequest(BaseModel):
    """Request model for creating a niche"""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    keywords: List[str] = Field(..., min_items=1, max_items=20)
    excluded_keywords: List[str] = Field(default=[], max_items=20)
    platforms: List[str] = Field(..., min_items=1)
    min_confidence: int = Field(default=60, ge=0, le=100)
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Frontend React Jobs",
                "description": "Remote React developer positions",
                "keywords": ["react", "frontend", "typescript"],
                "excluded_keywords": ["senior"],
                "platforms": ["Twitter/X", "Reddit"],
                "min_confidence": 70
            }
        }


class UpdateNicheRequest(BaseModel):
    """Request model for updating a niche"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    keywords: Optional[List[str]] = Field(None, min_items=1, max_items=20)
    excluded_keywords: Optional[List[str]] = Field(None, max_items=20)
    platforms: Optional[List[str]] = Field(None, min_items=1)
    min_confidence: Optional[int] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class OpportunityResponse(BaseModel):
    """Response model for opportunity"""
    id: str
    title: str
    description: str
    platform: str
    url: str
    contact: Optional[str]
    match_data: Dict[str, Any]
    created_at: datetime
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}