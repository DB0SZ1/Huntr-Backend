import aiosmtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

# Import settings - adjust the import path based on your project structure
try:
    from config import settings
except ImportError:
    # Fallback if settings module doesn't exist yet
    class Settings:
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        SMTP_USERNAME = ""
        SMTP_PASSWORD = ""
    settings = Settings()

logger = logging.getLogger(__name__)


async def send_email_notification(
    to_email: str,
    opportunities: List[Dict[str, Any]],
    analyses: List[Dict[str, Any]],
    user_name: Optional[str] = None,
    subject_prefix: str = "🎯"
) -> Dict[str, Any]:
    """
    Send email digest of matched opportunities with retry logic
    
    Args:
        to_email: Recipient email address
        opportunities: List of opportunity dictionaries
        analyses: Corresponding AI analyses
        user_name: Optional user name for personalization
        subject_prefix: Email subject prefix
        
    Returns:
        Dict with success status and details
    """
    if len(opportunities) != len(analyses):
        logger.error(f"Mismatch: {len(opportunities)} opportunities vs {len(analyses)} analyses")
        return {"success": False, "error": "Data mismatch"}
    
    if not opportunities:
        logger.warning("No opportunities to send")
        return {"success": False, "error": "No opportunities"}
    
    # Validate SMTP settings
    if not all([settings.SMTP_SERVER, settings.SMTP_USERNAME, settings.SMTP_PASSWORD]):
        logger.error("SMTP settings not configured")
        return {"success": False, "error": "SMTP not configured"}
    
    try:
        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = f"{subject_prefix} {len(opportunities)} New Job Match{'es' if len(opportunities) != 1 else ''}!"
        message['From'] = settings.SMTP_USERNAME
        message['To'] = to_email
        message['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
        
        # Generate content
        html_body = generate_email_html(opportunities, analyses, user_name)
        text_body = generate_email_text(opportunities, analyses, user_name)
        
        # Attach both versions
        text_part = MIMEText(text_body, 'plain')
        html_part = MIMEText(html_body, 'html')
        message.attach(text_part)
        message.attach(html_part)
        
        # Send with retry logic
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"[EMAIL] Attempt {attempt}/{max_retries} - Sending to {to_email}")
                
                await aiosmtplib.send(
                    message,
                    hostname=settings.SMTP_SERVER,
                    port=settings.SMTP_PORT,
                    username=settings.SMTP_USERNAME,
                    password=settings.SMTP_PASSWORD,
                    start_tls=True,
                    timeout=30
                )
                
                logger.info(f"✅ [EMAIL] Sent successfully to {to_email} - {len(opportunities)} opportunities")
                
                return {
                    "success": True,
                    "email": to_email,
                    "opportunities_count": len(opportunities),
                    "message": f"Email sent with {len(opportunities)} job opportunities"
                }
            
            except aiosmtplib.SMTPException as e:
                logger.warning(f"[EMAIL] SMTP error on attempt {attempt}: {str(e)}")
                
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"[EMAIL] Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
            
            except asyncio.TimeoutError:
                logger.warning(f"[EMAIL] Timeout on attempt {attempt}")
                
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
    
    except Exception as e:
        logger.error(f"❌ [EMAIL] Failed to send to {to_email}: {str(e)}", exc_info=True)
        return {
            "success": False,
            "email": to_email,
            "error": str(e)
        }


async def send_batch_job_alerts(
    user_email: str,
    user_name: str,
    opportunities: List[Dict[str, Any]],
    analyses: List[Dict[str, Any]],
    db = None
) -> bool:
    """
    Send batch job alert emails with tracking
    
    Args:
        user_email: User's email address
        user_name: User's name
        opportunities: List of matched opportunities
        analyses: Corresponding analyses
        db: Database connection for tracking
        
    Returns:
        True if email sent successfully
    """
    try:
        logger.info(f"[BATCH EMAIL] Preparing batch alert for {user_email} ({len(opportunities)} opportunities)")
        
        result = await send_email_notification(
            to_email=user_email,
            opportunities=opportunities,
            analyses=analyses,
            user_name=user_name
        )
        
        if result['success'] and db:
            # Track email send
            await db.email_notifications.insert_one({
                "user_email": user_email,
                "user_name": user_name,
                "opportunities_count": len(opportunities),
                "sent_at": datetime.utcnow(),
                "status": "sent"
            })
        
        return result['success']
    
    except Exception as e:
        logger.error(f"[BATCH EMAIL] Error: {str(e)}")
        return False


async def send_daily_job_digest(
    user_id: str,
    user_email: str,
    user_name: str,
    db
) -> Dict[str, Any]:
    """
    Send daily digest of all new job opportunities
    
    Args:
        user_id: User's ID
        user_email: User's email
        user_name: User's name
        db: Database connection
        
    Returns:
        Result dict with status and count
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Get opportunities from past 24 hours
        opportunities = await db.user_opportunities.find({
            "user_id": user_id,
            "created_at": {"$gte": cutoff_time},
            "is_saved": False
        }).sort("created_at", -1).limit(20).to_list(length=20)
        
        if not opportunities:
            logger.info(f"[DAILY DIGEST] No new opportunities for {user_email}")
            return {
                "success": False,
                "reason": "No new opportunities",
                "count": 0
            }
        
        # Get analyses for each
        analyses = []
        for opp in opportunities:
            analysis = opp.get("match_data", {})
            if not analysis:
                analysis = {
                    "confidence": opp.get("confidence", 0),
                    "reasoning": "Matched your niche",
                    "urgency": opp.get("urgency", "medium")
                }
            analyses.append(analysis)
        
        logger.info(f"[DAILY DIGEST] Sending {len(opportunities)} opportunities to {user_email}")
        
        # Send email
        success = await send_batch_job_alerts(
            user_email=user_email,
            user_name=user_name,
            opportunities=opportunities,
            analyses=analyses,
            db=db
        )
        
        if success:
            # Mark as digest sent
            await db.users.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "last_digest_sent": datetime.utcnow()
                    }
                }
            )
        
        return {
            "success": success,
            "count": len(opportunities)
        }
    
    except Exception as e:
        logger.error(f"[DAILY DIGEST] Error for {user_email}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "count": 0
        }


async def send_weekly_top_gigs_email(
    user_id: str,
    user_email: str,
    user_name: str,
    top_gigs: List[Dict[str, Any]],
    db
) -> bool:
    """
    Send weekly top 20 curated gigs email
    
    Args:
        user_id: User's ID
        user_email: User's email
        user_name: User's name
        top_gigs: Top 20 curated gigs
        db: Database connection
        
    Returns:
        True if sent successfully
    """
    try:
        if not top_gigs:
            logger.warning(f"[WEEKLY EMAIL] No top gigs for {user_email}")
            return False
        
        # Extract opportunities and analyses
        opportunities = [g['opportunity'] for g in top_gigs]
        analyses = [{
            "confidence": g['scores']['niche_match'],
            "reasoning": f"Matches {g['niche_name']} niche",
            "urgency": "high" if g['scores']['niche_match'] >= 80 else "medium"
        } for g in top_gigs]
        
        logger.info(f"[WEEKLY EMAIL] Sending top {len(opportunities)} gigs to {user_email}")
        
        result = await send_email_notification(
            to_email=user_email,
            opportunities=opportunities,
            analyses=analyses,
            user_name=user_name,
            subject_prefix="🏆 WEEKLY TOP GIGS"
        )
        
        if result['success'] and db:
            await db.weekly_email_log.insert_one({
                "user_id": user_id,
                "user_email": user_email,
                "gigs_count": len(top_gigs),
                "sent_at": datetime.utcnow(),
                "status": "sent"
            })
        
        return result['success']
    
    except Exception as e:
        logger.error(f"[WEEKLY EMAIL] Error for {user_email}: {str(e)}")
        return False


async def send_urgent_job_alert(
    user_id: str,
    user_email: str,
    user_name: str,
    opportunity: Dict[str, Any],
    analysis: Dict[str, Any],
    db
) -> bool:
    """
    Send urgent job alert for high-priority opportunities
    
    Args:
        user_id: User's ID
        user_email: User's email
        user_name: User's name
        opportunity: Single opportunity
        analysis: Analysis result
        db: Database connection
        
    Returns:
        True if sent successfully
    """
    try:
        urgency = analysis.get('urgency', 'medium')
        if urgency != 'high':
            logger.warning(f"[URGENT ALERT] Opportunity doesn't meet urgency threshold")
            return False
        
        logger.info(f"[URGENT ALERT] Sending urgent opportunity to {user_email}: {opportunity.get('title')}")
        
        result = await send_email_notification(
            to_email=user_email,
            opportunities=[opportunity],
            analyses=[analysis],
            user_name=user_name,
            subject_prefix="🚨 URGENT"
        )
        
        if result['success'] and db:
            await db.urgent_alerts_log.insert_one({
                "user_id": user_id,
                "user_email": user_email,
                "opportunity_title": opportunity.get('title'),
                "sent_at": datetime.utcnow(),
                "status": "sent"
            })
        
        return result['success']
    
    except Exception as e:
        logger.error(f"[URGENT ALERT] Error for {user_email}: {str(e)}")
        return False


def generate_email_html(
    opportunities: List[Dict[str, Any]],
    analyses: List[Dict[str, Any]],
    user_name: Optional[str] = None
) -> str:
    """
    Generate HTML email template
    
    Args:
        opportunities: List of opportunity dicts
        analyses: List of analysis dicts
        user_name: Optional user name
        
    Returns:
        HTML string for email body
    """
    greeting = f"Hi {user_name}" if user_name else "Hello"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background-color: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #3498db;
            }}
            .header h1 {{
                color: #2c3e50;
                margin: 0;
                font-size: 24px;
            }}
            .summary {{
                background-color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 25px;
            }}
            .opportunity {{
                border: 1px solid #ddd;
                border-left: 4px solid #3498db;
                padding: 20px;
                margin: 20px 0;
                border-radius: 5px;
                background-color: #fafafa;
                transition: box-shadow 0.3s ease;
            }}
            .opportunity:hover {{
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }}
            .title {{
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }}
            .meta {{
                color: #7f8c8d;
                font-size: 14px;
                margin-bottom: 10px;
            }}
            .confidence {{
                display: inline-block;
                background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
                color: white;
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: bold;
                margin: 10px 0;
            }}
            .confidence.high {{
                background: linear-gradient(135deg, #27ae60 0%, #229954 100%);
            }}
            .confidence.medium {{
                background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
            }}
            .reasoning {{
                color: #555;
                font-size: 14px;
                margin: 10px 0;
                padding: 10px;
                background-color: white;
                border-radius: 4px;
            }}
            .button {{
                display: inline-block;
                background-color: #3498db;
                color: white !important;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }}
            .button:hover {{
                background-color: #2980b9;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                color: #7f8c8d;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 Your New Job Matches</h1>
            </div>
            
            <div class="summary">
                <p><strong>{greeting}!</strong></p>
                <p>We found <strong>{len(opportunities)}</strong> new job {'opportunity' if len(opportunities) == 1 else 'opportunities'} matching your criteria.</p>
            </div>
    """
    
    # Add opportunities (limit to 10)
    display_count = min(len(opportunities), 10)
    
    for i, (opp, analysis) in enumerate(zip(opportunities[:display_count], analyses[:display_count]), 1):
        confidence = analysis.get('confidence', 0)
        confidence_class = 'high' if confidence >= 80 else 'medium' if confidence >= 60 else ''
        
        # Extract and sanitize fields
        title = opp.get('title', 'Untitled Position')
        platform = opp.get('platform', 'N/A')
        company = opp.get('company', 'Company Not Specified')
        location = opp.get('location', 'Remote')
        reasoning = analysis.get('reasoning', 'No analysis available')
        url = opp.get('url', '#')
        
        html += f"""
        <div class="opportunity">
            <div class="title">{i}. {title}</div>
            <div class="meta">
                <strong>Platform:</strong> {platform}<br>
                <strong>Location:</strong> {location}
            </div>
            <span class="confidence {confidence_class}">{confidence}% Match</span>
            <div class="reasoning">💡 {reasoning}</div>
            <a href="{url}" class="button">View Opportunity →</a>
        </div>
        """
    
    if len(opportunities) > 10:
        html += f"""
        <div style="text-align: center; margin: 20px 0; color: #7f8c8d;">
            <p>+ {len(opportunities) - 10} more opportunities in your dashboard</p>
        </div>
        """
    
    html += """
            <div class="footer">
                <p>This email was sent by Job Hunter - AI-Powered Job Matching</p>
                <p>© 2025 Job Hunter. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def generate_email_text(
    opportunities: List[Dict[str, Any]],
    analyses: List[Dict[str, Any]],
    user_name: Optional[str] = None
) -> str:
    """
    Generate plain text email version
    
    Args:
        opportunities: List of opportunity dicts
        analyses: List of analysis dicts
        user_name: Optional user name
        
    Returns:
        Plain text string for email body
    """
    greeting = f"Hi {user_name}" if user_name else "Hello"
    
    text = f"""
{greeting}!

🎯 Your New Job Matches
{'=' * 50}

We found {len(opportunities)} new job {'opportunity' if len(opportunities) == 1 else 'opportunities'} matching your criteria.

"""
    
    display_count = min(len(opportunities), 10)
    
    for i, (opp, analysis) in enumerate(zip(opportunities[:display_count], analyses[:display_count]), 1):
        title = opp.get('title', 'Untitled Position')
        platform = opp.get('platform', 'N/A')
        location = opp.get('location', 'Remote')
        confidence = analysis.get('confidence', 0)
        reasoning = analysis.get('reasoning', 'No analysis available')
        url = opp.get('url', '#')
        
        text += f"""
{i}. {title}
{'-' * 50}
Platform: {platform}
Location: {location}
Match Score: {confidence}%

Why this matches:
{reasoning}

View opportunity: {url}

"""
    
    if len(opportunities) > 10:
        text += f"\n+ {len(opportunities) - 10} more opportunities in your dashboard\n"
    
    text += """
---
This email was sent by Job Hunter - AI-Powered Job Matching
You're receiving this because you signed up for job notifications.

© 2025 Job Hunter. All rights reserved.
"""
    
    return text


async def send_verification_email(email: str, name: str, verification_token: str):
    """Send email verification link"""
    verification_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={verification_token}"
    
    subject = "Verify Your Email - Job Hunter"
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto;">
                <h2>Welcome to Job Hunter, {name}!</h2>
                <p>Please verify your email address to activate your account.</p>
                <p>
                    <a href="{verification_url}" 
                       style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">
                        Verify Email
                    </a>
                </p>
                <p>Or copy this link: {verification_url}</p>
                <p style="color: #666; font-size: 12px;">This link expires in 24 hours.</p>
            </div>
        </body>
    </html>
    """
    
    await send_email(email, subject, html_content)


async def send_password_reset_email(email: str, name: str, reset_token: str):
    """Send password reset link"""
    reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={reset_token}"
    
    subject = "Reset Your Password - Job Hunter"
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto;">
                <h2>Password Reset Request</h2>
                <p>Hi {name},</p>
                <p>Click the link below to reset your password.</p>
                <p>
                    <a href="{reset_url}" 
                       style="background-color: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">
                        Reset Password
                    </a>
                </p>
                <p>Or copy this link: {reset_url}</p>
                <p style="color: #666; font-size: 12px;">This link expires in 1 hour.</p>
                <p style="color: #666; font-size: 12px;">If you didn't request this, ignore this email.</p>
            </div>
        </body>
    </html>
    """
    
    await send_email(email, subject, html_content)