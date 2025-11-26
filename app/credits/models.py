"""
Credit System Models & Management
Handles daily credit allocation, usage tracking, and limits
"""
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class CreditUsageLog(BaseModel):
    """Log entry for credit usage"""
    user_id: str
    action: str  # "scan", "ai_analysis", "export", etc.
    credits_used: int
    credits_before: int
    credits_after: int
    details: Optional[Dict] = None
    timestamp: datetime


class UserCredits(BaseModel):
    """User's current credit balance"""
    user_id: str
    daily_credits_total: int
    daily_credits_used: int
    daily_credits_remaining: int
    last_refill_date: datetime
    next_refill_time: datetime
    tier: str
    usage_logs: List[CreditUsageLog] = []


class CreditCheckResponse(BaseModel):
    """Response for credit check"""
    has_enough_credits: bool
    current_balance: int
    required_credits: int
    deficit: Optional[int] = None  # If not enough, how many more needed
    next_refill_time: Optional[str] = None
    message: str
