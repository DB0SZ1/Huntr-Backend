"""
Promotional trial management models
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TrialStatus(str, Enum):
    """Trial status enum"""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class PromoUserStatus(str, Enum):
    """Promo user redemption status"""
    AVAILABLE = "available"
    REDEEMED = "redeemed"
    EXPIRED = "expired"


class PromoUserModel(BaseModel):
    """Promotional user record from CSV (one-time use per user)"""
    twitter_handle: str
    email: str
    phone_number: str
    status: PromoUserStatus = PromoUserStatus.AVAILABLE
    trial_tier: str = "pro"
    trial_duration_days: int = 14
    created_at: datetime = Field(default_factory=datetime.utcnow)
    redeemed_at: Optional[datetime] = None
    redeemed_by_user_id: Optional[str] = None
    redeemed_by_email: Optional[str] = None
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
    
    class Config:
        use_enum_values = True


class PromoTrialModel(BaseModel):
    """Promotional trial record (linked to promo user)"""
    user_id: str
    email: str
    twitter_handle: str
    phone_number: str
    trial_tier: str = "pro"
    trial_status: str = "active"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    extended: bool = False
    extended_until: Optional[datetime] = None
    auto_downgraded: bool = False
    downgrade_date: Optional[datetime] = None
    original_tier: str = "free"
    notes: Optional[str] = None
    
    class Config:
        use_enum_values = True


class PromoImportRequest(BaseModel):
    """Request for importing promo users from CSV"""
    trial_duration_days: int = Field(default=14, ge=1, le=90)
    trial_tier: str = Field(default="pro")
    
    class Config:
        schema_extra = {
            "example": {
                "trial_duration_days": 14,
                "trial_tier": "pro"
            }
        }


class PromoTrialExtendRequest(BaseModel):
    """Request to extend a trial"""
    additional_days: int = Field(default=7, ge=1, le=30)
    reason: Optional[str] = None


class BatchPromoResult(BaseModel):
    """Result of batch promo import"""
    total_processed: int
    successful: int
    failed: int
    duplicates: int
    errors: List[dict] = Field(default_factory=list)
    message: str


class RedeemPromoRequest(BaseModel):
    """Request to redeem promo (provide X handle and phone number)"""
    twitter_handle: str = Field(..., min_length=1, description="X/Twitter handle")
    phone_number: str = Field(..., min_length=7, description="Phone number")
    
    @validator('twitter_handle')
    def validate_twitter_handle(cls, v):
        """Normalize Twitter handle"""
        v = v.lstrip('@').lower().strip()
        # Handle full URLs like https://x.com/handle
        if 'x.com/' in v or 'twitter.com/' in v:
            v = v.split('/')[-1].split('?')[0]
        return v
    
    @validator('phone_number')
    def validate_phone(cls, v):
        """Normalize phone number"""
        normalized = ''.join(c for c in v if c.isdigit() or c == '+')
        if len(normalized) < 7:
            raise ValueError("Phone number must be at least 7 digits")
        return normalized
    
    class Config:
        schema_extra = {
            "example": {
                "twitter_handle": "@noorhd_3",
                "phone_number": "+2347036692250"
            }
        }


class PromoValidationResponse(BaseModel):
    """Response for promo validation"""
    valid: bool
    message: str
    tier: Optional[str] = None
    duration_days: Optional[int] = None
    already_used: bool = False
    error: Optional[str] = None
