"""
Credit Management System
Handles credit deduction, balance checking, and daily refills
"""
import logging
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from config import TIER_LIMITS

logger = logging.getLogger(__name__)


class CreditManager:
    """Manages user credits and daily refills"""
    
    @staticmethod
    async def get_balance(user_id: str, db) -> int:
        """Get current credit balance"""
        try:
            credit_record = await db.user_credits.find_one({"user_id": user_id})
            
            if not credit_record:
                return 0
            
            return credit_record.get("current_credits", 0)
        
        except Exception as e:
            logger.error(f"Error getting credit balance: {str(e)}")
            return 0
    
    @staticmethod
    async def get_full_balance(user_id: str, db) -> dict:
        """Get full credit information including refill time"""
        try:
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            tier = user.get("tier", "free") if user else "free"
            daily_credits = TIER_LIMITS.get(tier, {}).get("daily_credits", 10)
            
            credit_record = await db.user_credits.find_one({"user_id": user_id})
            
            if not credit_record:
                # Create new record
                credit_record = {
                    "current_credits": daily_credits,
                    "daily_credits": daily_credits,
                    "last_refill": datetime.utcnow()
                }
                await db.user_credits.insert_one({
                    **credit_record,
                    "user_id": user_id,
                    "total_credits_used": 0,
                    "total_credits_purchased": 0
                })
            
            # Check if refill needed
            last_refill = credit_record.get("last_refill", datetime.utcnow())
            now = datetime.utcnow()
            
            if (now - last_refill).days >= 1:
                await db.user_credits.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "current_credits": daily_credits,
                            "last_refill": now
                        }
                    }
                )
                credit_record["current_credits"] = daily_credits
                credit_record["last_refill"] = now
            
            next_refill = credit_record.get("last_refill") + timedelta(days=1)
            hours_until = max(0, round((next_refill - now).total_seconds() / 3600))
            
            return {
                "current_credits": credit_record.get("current_credits", daily_credits),
                "daily_credits": daily_credits,
                "next_refill": next_refill.isoformat(),
                "hours_until_refill": hours_until,
                "total_used": credit_record.get("total_credits_used", 0),
                "total_purchased": credit_record.get("total_credits_purchased", 0)
            }
        
        except Exception as e:
            logger.error(f"Error getting full credit balance: {str(e)}")
            return {
                "current_credits": 0,
                "daily_credits": 10,
                "total_used": 0,
                "total_purchased": 0,
                "error": "Failed to get credit info"
            }
    
    @staticmethod
    async def has_sufficient_credits(user_id: str, amount: int, db) -> bool:
        """Check if user has sufficient credits"""
        try:
            balance = await CreditManager.get_balance(user_id, db)
            return balance >= amount
        except:
            return False
    
    @staticmethod
    async def deduct_credits(user_id: str, amount: int, reason: str, db) -> bool:
        """
        Deduct credits from user
        
        Args:
            user_id: User ID
            amount: Credits to deduct
            reason: Reason for deduction (scan, analysis, etc.)
            db: Database connection
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check balance first
            has_credits = await CreditManager.has_sufficient_credits(user_id, amount, db)
            
            if not has_credits:
                logger.warning(f"Insufficient credits for user {user_id}")
                return False
            
            # Deduct credits
            result = await db.user_credits.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        "current_credits": -amount,
                        "total_credits_used": amount
                    }
                }
            )
            
            # Log credit usage
            await db.credit_usage.insert_one({
                "user_id": user_id,
                "amount": amount,
                "reason": reason,
                "timestamp": datetime.utcnow(),
                "balance_after": await CreditManager.get_balance(user_id, db)
            })
            
            logger.info(f"Deducted {amount} credits from user {user_id} for {reason}")
            return result.modified_count > 0
        
        except Exception as e:
            logger.error(f"Error deducting credits: {str(e)}")
            return False
