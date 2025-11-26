"""
Password hashing and verification utilities
Uses bcrypt for secure password storage
"""
from passlib.context import CryptContext
from passlib.exc import InvalidTokenError
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from config import settings
import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)

# Token serializer for email verification and password reset
serializer = URLSafeTimedSerializer(settings.JWT_SECRET_KEY)


class PasswordHandler:
    """Handle password operations"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against hash"""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False
    
    @staticmethod
    def generate_verification_token(email: str, expires_in: int = 86400) -> str:
        """Generate email verification token (valid for 24 hours by default)"""
        return serializer.dumps(email, salt=settings.JWT_SECRET_KEY)
    
    @staticmethod
    def verify_email_token(token: str, max_age: int = 86400) -> str | None:
        """Verify email token and return email if valid"""
        try:
            email = serializer.loads(token, salt=settings.JWT_SECRET_KEY, max_age=max_age)
            return email
        except (SignatureExpired, BadSignature, Exception) as e:
            logger.warning(f"Invalid email token: {str(e)}")
            return None
    
    @staticmethod
    def generate_password_reset_token(email: str) -> str:
        """Generate password reset token"""
        return serializer.dumps(email, salt="password-reset")
    
    @staticmethod
    def verify_password_reset_token(token: str, max_age: int = 3600) -> str | None:
        """Verify password reset token (valid for 1 hour)"""
        try:
            email = serializer.loads(token, salt="password-reset", max_age=max_age)
            return email
        except (SignatureExpired, BadSignature, Exception) as e:
            logger.warning(f"Invalid password reset token: {str(e)}")
            return None
