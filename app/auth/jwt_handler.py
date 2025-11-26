"""
JWT Token Creation and Verification
Real JWT implementation with access/refresh tokens
"""
from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi import HTTPException, Header, Depends
from typing import Optional
import logging

from config import settings

logger = logging.getLogger(__name__)


def create_access_token(user_id: str) -> str:
    """
    Create JWT access token
    
    Args:
        user_id: User's MongoDB ObjectId as string
        
    Returns:
        JWT access token string
    """
    try:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        
        payload = {
            "sub": user_id,
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return token
    
    except Exception as e:
        logger.error(f"Error creating access token: {str(e)}")
        raise


def create_refresh_token(user_id: str) -> str:
    """
    Create JWT refresh token (longer expiry)
    
    Args:
        user_id: User's MongoDB ObjectId as string
        
    Returns:
        JWT refresh token string
    """
    try:
        expire = datetime.utcnow() + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return token
    
    except Exception as e:
        logger.error(f"Error creating refresh token: {str(e)}")
        raise


def verify_token(token: str, token_type: str = "access") -> dict:
    """
    Verify JWT token and return payload
    
    Args:
        token: JWT token string
        token_type: "access" or "refresh"
        
    Returns:
        Token payload dict
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify token type
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=401,
                detail=f"Invalid token type. Expected {token_type}"
            )
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(
                status_code=401,
                detail="Token has expired"
            )
        
        return payload
    
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Token verification failed"
        )


async def get_current_user_id(
    authorization: Optional[str] = Header(None)
) -> str:
    """
    FastAPI dependency to extract user ID from JWT token
    
    Args:
        authorization: Authorization header value
        
    Returns:
        User ID string
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )
    
    # Extract token from "Bearer <token>"
    try:
        scheme, token = authorization.split()
        
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme"
            )
        
        # Verify token
        payload = verify_token(token, token_type="access")
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload"
            )
        
        return user_id
    
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User ID extraction error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )


def decode_token_without_verification(token: str) -> dict:
    """
    Decode JWT token without verification (for debugging only)
    
    Args:
        token: JWT token string
        
    Returns:
        Token payload dict
    """
    try:
        # --- FIX ---
        # Added 'key=None' as the second positional argument.
        # It's required by the 'jwt.decode' signature even when
        # signature verification is disabled in 'options'.
        return jwt.decode(
            token,
            key=None,
            options={"verify_signature": False}
        )
        # -----------
    except Exception as e:
        logger.error(f"Token decode error: {str(e)}")
        return {}