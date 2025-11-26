"""
Admin Authorization Middleware
Verify user is admin before allowing access
"""
from fastapi import HTTPException, Depends
from bson.objectid import ObjectId
from datetime import datetime
import logging

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id

logger = logging.getLogger(__name__)


async def require_admin(
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_database)
) -> str:
    """
    Verify user is admin
    Returns user_id if admin, raises HTTPException otherwise
    """
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check is_admin flag
        if not user.get("is_admin", False):
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        return user_id
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Authorization error")


async def log_admin_action(
    admin_id: str,
    action: str,
    details: dict = None,
    db = None
) -> bool:
    """
    Log an admin action for audit trail
    
    Args:
        admin_id: Admin user ID
        action: Action type (e.g., 'update_user_tier', 'suspend_user')
        details: Additional details about the action
        db: Database connection
        
    Returns:
        True if logged successfully
    """
    try:
        if not db:
            from app.database.connection import get_database
            db = await get_database()
        
        action_record = {
            "admin_id": admin_id,
            "action": action,
            "details": details or {},
            "timestamp": datetime.utcnow()
        }
        
        result = await db.admin_actions.insert_one(action_record)
        
        logger.info(f"Admin action logged: {action} by {admin_id}")
        return True
    
    except Exception as e:
        logger.error(f"Error logging admin action: {str(e)}")
        return False