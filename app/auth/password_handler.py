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
    def _truncate_to_72_bytes(password: str) -> str:
        """
        Truncate password to exactly 72 bytes for bcrypt
        Handles multi-byte UTF-8 characters correctly
        """
        password_bytes = password.encode('utf-8')
        if len(password_bytes) <= 72:
            return password
        
        # Truncate to 72 bytes, then decode back to string
        # Handle potential UTF-8 character boundaries
        truncated = password_bytes[:72]
        
        # Try to decode; if it fails, keep removing bytes until valid
        while len(truncated) > 0:
            try:
                return truncated.decode('utf-8')
            except UnicodeDecodeError:
                truncated = truncated[:-1]
        
        # Fallback (should never reach here)
        return password[:50]
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password with bcrypt (handles 72-byte limit)"""
        try:
            # Truncate to 72 bytes
            truncated_password = PasswordHandler._truncate_to_72_bytes(password)
            return pwd_context.hash(truncated_password)
        except Exception as e:
            logger.error(f"Password hashing error: {str(e)}")
            raise
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against hash (handles 72-byte bcrypt limit)"""
        try:
            # Truncate to 72 bytes to match hash_password behavior
            truncated_password = PasswordHandler._truncate_to_72_bytes(plain_password)
            return pwd_context.verify(truncated_password, hashed_password)
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