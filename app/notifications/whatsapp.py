"""
WhatsApp Notification Service
Sends job alerts via Twilio WhatsApp API using user's credentials
"""
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from cryptography.fernet import Fernet
import logging
import json
from typing import Dict, List

from config import settings

logger = logging.getLogger(__name__)


def decrypt_twilio_credentials(encrypted_data: str, encryption_key: str) -> Dict:
    """
    Decrypt user's Twilio credentials
    
    Args:
        encrypted_data: Encrypted JSON string containing Twilio credentials
        encryption_key: Fernet encryption key
        
    Returns:
        Dictionary with decrypted credentials
        
    Raises:
        Exception: If decryption fails
    """
    try:
        fernet = Fernet(encryption_key.encode())
        decrypted = fernet.decrypt(encrypted_data.encode())
        credentials = json.loads(decrypted.decode())
        
        # Validate required fields
        required_fields = ['account_sid', 'auth_token', 'from_number', 'to_number']
        for field in required_fields:
            if field not in credentials:
                raise ValueError(f"Missing required field: {field}")
        
        return credentials
    
    except Exception as e:
        logger.error(f"Credential decryption error: {str(e)}")
        raise ValueError(f"Failed to decrypt Twilio credentials: {str(e)}")


async def send_whatsapp_notification(
    user_config: Dict,
    opportunity: Dict,
    analysis: Dict
) -> bool:
    """
    Send WhatsApp notification via user's Twilio account
    
    Args:
        user_config: User configuration with encrypted Twilio credentials
        opportunity: Job opportunity dictionary
        analysis: AI analysis result dictionary
        
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Check if user has WhatsApp configured
        if not user_config.get('encrypted_twilio_credentials'):
            logger.warning("User has no Twilio credentials configured")
            return False
        
        # Decrypt credentials
        creds = decrypt_twilio_credentials(
            user_config['encrypted_twilio_credentials'],
            settings.ENCRYPTION_KEY
        )
        
        # Initialize Twilio client with user's credentials
        client = Client(creds['account_sid'], creds['auth_token'])
        
        # Format message
        message_body = format_whatsapp_message(opportunity, analysis)
        
        # Send WhatsApp message
        message = client.messages.create(
            from_=f"whatsapp:{creds['from_number']}",
            to=f"whatsapp:{creds['to_number']}",
            body=message_body
        )
        
        logger.info(f"WhatsApp message sent: {message.sid} to {creds['to_number']}")
        return True
    
    except TwilioRestException as e:
        logger.error(f"Twilio API error: {e.code} - {e.msg}")
        return False
    
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        return False
    
    except Exception as e:
        logger.error(f"WhatsApp notification error: {str(e)}", exc_info=True)
        return False


def format_whatsapp_message(opportunity: Dict, analysis: Dict) -> str:
    """
    Format opportunity into WhatsApp message with emojis and structure
    
    Args:
        opportunity: Job opportunity dictionary
        analysis: AI analysis result dictionary
        
    Returns:
        Formatted WhatsApp message string (max 1600 chars)
    """
    urgency_emoji = {
        "high": "🔥",
        "medium": "⚡",
        "low": "📌"
    }
    
    urgency = analysis.get('urgency', 'medium')
    confidence = analysis.get('confidence', 0)
    
    # Build message
    message = f"{urgency_emoji.get(urgency, '📌')} *NEW JOB MATCH*\n"
    message += "━━━━━━━━━━━━━━━━━━\n\n"
    
    # Title
    title = opportunity.get('title', 'Untitled Opportunity')
    message += f"*{title}*\n\n"
    
    # Platform
    platform = opportunity.get('platform', 'Unknown')
    message += f"🌐 *Platform:* {platform}\n"
    
    # Confidence
    confidence_bar = "█" * (confidence // 10) + "▒" * (10 - confidence // 10)
    message += f"🎯 *Match:* {confidence}% {confidence_bar}\n\n"
    
    # AI Reasoning
    reasoning = analysis.get('reasoning', 'Matched your niche requirements')
    message += f"💡 *Why it matches:*\n{reasoning}\n\n"
    
    # Relevant keywords
    keywords = analysis.get('relevant_keywords', [])
    if keywords:
        keywords_text = ", ".join(keywords[:5])  # Limit to 5 keywords
        message += f"🔑 *Keywords:* {keywords_text}\n\n"
    
    # Description (truncated)
    description = opportunity.get('description', '')
    if description:
        max_desc_length = 200
        if len(description) > max_desc_length:
            description = description[:max_desc_length] + "..."
        message += f"📝 *Description:*\n{description}\n\n"
    
    # Contact information
    contact_added = False
    
    if opportunity.get('contact'):
        message += f"📞 *Contact:* {opportunity['contact']}\n"
        contact_added = True
    
    if opportunity.get('telegram'):
        message += f"✈️ *Telegram:* {opportunity['telegram']}\n"
        contact_added = True
    
    if opportunity.get('twitter'):
        message += f"🐦 *Twitter:* {opportunity['twitter']}\n"
        contact_added = True
    
    if opportunity.get('email'):
        message += f"📧 *Email:* {opportunity['email']}\n"
        contact_added = True
    
    if contact_added:
        message += "\n"
    
    # Apply link
    url = opportunity.get('url', '')
    if url:
        message += f"🔗 *Apply Now:*\n{url}\n\n"
    
    # Footer
    message += "━━━━━━━━━━━━━━━━━━\n"
    message += "💼 Job Hunter | AI-Powered Job Matching"
    
    # Ensure message doesn't exceed WhatsApp limit
    max_length = 1600
    if len(message) > max_length:
        message = message[:max_length - 3] + "..."
    
    return message


async def send_batch_whatsapp_notifications(
    user_config: Dict,
    opportunities: List[Dict],
    analyses: List[Dict],
    max_messages: int = 5
) -> Dict[str, int]:
    """
    Send multiple WhatsApp notifications in batch
    
    Args:
        user_config: User configuration with Twilio credentials
        opportunities: List of job opportunities
        analyses: List of corresponding AI analyses
        max_messages: Maximum number of messages to send in batch
        
    Returns:
        Dictionary with success and failure counts
    """
    import asyncio
    
    success_count = 0
    failure_count = 0
    
    # Limit number of messages
    opportunities = opportunities[:max_messages]
    analyses = analyses[:max_messages]
    
    for opp, analysis in zip(opportunities, analyses):
        success = await send_whatsapp_notification(user_config, opp, analysis)
        
        if success:
            success_count += 1
        else:
            failure_count += 1
        
        # Rate limiting - wait 2 seconds between messages
        if opp != opportunities[-1]:  # Don't wait after last message
            await asyncio.sleep(2)
    
    logger.info(
        f"Batch WhatsApp send complete: {success_count} sent, {failure_count} failed"
    )
    
    return {
        "success": success_count,
        "failed": failure_count,
        "total": len(opportunities)
    }


def encrypt_twilio_credentials(credentials: Dict, encryption_key: str) -> str:
    """
    Encrypt Twilio credentials for storage
    
    Args:
        credentials: Dictionary with Twilio credentials
        encryption_key: Fernet encryption key
        
    Returns:
        Encrypted credentials string
    """
    try:
        # Validate credentials
        required_fields = ['account_sid', 'auth_token', 'from_number', 'to_number']
        for field in required_fields:
            if field not in credentials:
                raise ValueError(f"Missing required field: {field}")
        
        # Encrypt
        fernet = Fernet(encryption_key.encode())
        json_str = json.dumps(credentials)
        encrypted = fernet.encrypt(json_str.encode())
        
        return encrypted.decode()
    
    except Exception as e:
        logger.error(f"Credential encryption error: {str(e)}")
        raise ValueError(f"Failed to encrypt Twilio credentials: {str(e)}")


async def verify_twilio_credentials(credentials: Dict) -> bool:
    """
    Verify Twilio credentials are valid by making a test API call
    
    Args:
        credentials: Dictionary with Twilio credentials
        
    Returns:
        True if credentials are valid, False otherwise
    """
    try:
        client = Client(credentials['account_sid'], credentials['auth_token'])
        
        # Test by fetching account info
        account = client.api.accounts(credentials['account_sid']).fetch()
        
        if account.status == 'active':
            logger.info("Twilio credentials verified successfully")
            return True
        else:
            logger.warning(f"Twilio account status: {account.status}")
            return False
    
    except TwilioRestException as e:
        logger.error(f"Twilio verification failed: {e.code} - {e.msg}")
        return False
    
    except Exception as e:
        logger.error(f"Credential verification error: {str(e)}")
        return False


def format_whatsapp_digest(
    opportunities: List[Dict],
    analyses: List[Dict],
    max_opportunities: int = 10
) -> str:
    """
    Format multiple opportunities into a single digest message
    
    Args:
        opportunities: List of job opportunities
        analyses: List of corresponding AI analyses
        max_opportunities: Maximum opportunities to include
        
    Returns:
        Formatted digest message
    """
    opportunities = opportunities[:max_opportunities]
    analyses = analyses[:max_opportunities]
    
    message = "📬 *JOB DIGEST - NEW MATCHES*\n"
    message += "━━━━━━━━━━━━━━━━━━\n\n"
    message += f"You have *{len(opportunities)} new job matches*!\n\n"
    
    for i, (opp, analysis) in enumerate(zip(opportunities, analyses), 1):
        title = opp.get('title', 'Untitled')
        platform = opp.get('platform', 'Unknown')
        confidence = analysis.get('confidence', 0)
        
        message += f"{i}. *{title}*\n"
        message += f"   📍 {platform} | 🎯 {confidence}%\n"
        
        if i < len(opportunities):
            message += "\n"
    
    message += "\n━━━━━━━━━━━━━━━━━━\n"
    message += "💼 View all opportunities in the app"
    
    # Ensure message doesn't exceed limit
    if len(message) > 1600:
        message = message[:1597] + "..."
    
    return message