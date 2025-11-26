import os
import requests
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_whatsapp_message(message):
    """Send message via Twilio's WhatsApp API with proper error handling"""
    
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_WHATSAPP_FROM')
    to_number = os.getenv('WHATSAPP_TO')
    
    # Validate all credentials exist
    if not all([account_sid, auth_token, from_number, to_number]):
        print("❌ WhatsApp credentials incomplete")
        return False
    
    # Additional type safety check
    if not isinstance(account_sid, str) or not isinstance(auth_token, str):
        print("❌ Invalid credential types")
        return False
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    
    try:
        response = requests.post(
            url,
            auth=(account_sid, auth_token),
            data={
                'From': from_number,
                'To': to_number,
                'Body': message
            },
            timeout=10
        )
        
        if response.status_code == 201:
            return True
        else:
            print(f"❌ WhatsApp send failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ WhatsApp request timeout")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ WhatsApp connection error")
        return False
    except Exception as e:
        print(f"❌ WhatsApp error: {str(e)}")
        return False

def send_email_notification(opportunities):
    """Send email digest as fallback when WhatsApp fails"""
    
    api_key = os.getenv('SENDGRID_API_KEY')
    from_email = os.getenv('EMAIL_FROM', 'bot@jobhunter.app')
    to_email = os.getenv('EMAIL_TO')
    
    if not api_key or not to_email:
        print("⚠️  Email not configured - skipping email fallback")
        return False
    
    try:
        # Build HTML email
        email_body = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; }
                .opportunity { 
                    border: 1px solid #ddd; 
                    padding: 15px; 
                    margin: 15px 0; 
                    border-radius: 5px;
                    background: #f9f9f9;
                }
                .title { color: #2c3e50; font-size: 18px; font-weight: bold; }
                .meta { color: #7f8c8d; font-size: 14px; margin: 5px 0; }
                .confidence { 
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 3px;
                    font-size: 12px;
                    font-weight: bold;
                }
                .high { background: #e74c3c; color: white; }
                .medium { background: #f39c12; color: white; }
                .low { background: #3498db; color: white; }
                .contact { 
                    background: #ecf0f1; 
                    padding: 10px; 
                    margin: 10px 0;
                    border-left: 3px solid #3498db;
                }
                .btn {
                    display: inline-block;
                    padding: 10px 20px;
                    background: #3498db;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 10px 0;
                }
            </style>
        </head>
        <body>
            <h2>🚀 New Web3 Opportunities Detected</h2>
            <p>Your job hunter bot found <strong>{}</strong> new opportunities matching your criteria.</p>
        """.format(len(opportunities))
        
        for i, opp in enumerate(opportunities[:15], 1):  # Max 15 in email
            urgency = opp.get('urgency', 'medium')
            confidence = opp.get('confidence', 0)
            
            email_body += f"""
            <div class="opportunity">
                <div class="title">
                    {i}. {opp.get('title', 'No title')[:100]}
                </div>
                <div class="meta">
                    <strong>Platform:</strong> {opp.get('platform', 'Unknown')} | 
                    <strong>Category:</strong> {opp.get('role_category', 'General')}
                </div>
                <div class="meta">
                    <span class="confidence {urgency}">{confidence}% confidence - {urgency.upper()} priority</span>
                </div>
                <p>{opp.get('description', '')[:250]}...</p>
                <div class="contact">
                    <strong>📞 Contact:</strong> {opp.get('contact', 'See listing')}
                </div>
                <a href="{opp.get('url', '#')}" class="btn">View Opportunity →</a>
            </div>
            """
        
        email_body += """
            <hr>
            <p style="color: #7f8c8d; font-size: 12px;">
                This email was sent because WhatsApp notification failed. 
                Configure WhatsApp in your bot settings for instant notifications.
            </p>
        </body>
        </html>
        """
        
        # Prepare and send email
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=f'🎯 {len(opportunities)} New Web3 Job Opportunities',
            html_content=email_body
        )
        
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            print(f"✅ Email sent successfully to {to_email}")
            return True
        else:
            print(f"⚠️  Email send returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Email send error: {str(e)}")
        return False

def send_notification(message, opportunity_data=None):
    """
    Smart notification sender that tries WhatsApp first, falls back to email
    
    Args:
        message: Text message for WhatsApp
        opportunity_data: List of opportunity dicts for email fallback
    """
    from modules.utils import load_config
    
    config = load_config()
    notification_prefs = config.get('notification', {})
    
    # Try WhatsApp first if enabled
    if notification_prefs.get('whatsapp_enabled', True):
        if send_whatsapp_message(message):
            return True
        else:
            print("⚠️  WhatsApp failed, trying email fallback...")
    
    # Try email fallback if enabled
    if notification_prefs.get('email_enabled', False) and opportunity_data:
        return send_email_notification(opportunity_data)
    
    print("❌ All notification methods failed")
    return False

def send_batch_notifications(opportunities, format_func):
    """
    Send multiple opportunities with rate limiting
    
    Args:
        opportunities: List of opportunity dicts with analysis
        format_func: Function to format opportunity into WhatsApp message
    
    Returns:
        Number of successfully sent notifications
    """
    import time
    from modules.utils import load_config
    
    config = load_config()
    max_per_scan = config.get('notification', {}).get('max_per_scan', 20)
    
    sent_count = 0
    failed_opportunities = []
    
    for i, opp_data in enumerate(opportunities[:max_per_scan], 1):
        opp, analysis = opp_data['opportunity'], opp_data['analysis']
        
        # Format message
        message = format_func(opp, analysis)
        
        # Try to send
        if send_whatsapp_message(message):
            sent_count += 1
            print(f"   ✅ [{i}/{min(len(opportunities), max_per_scan)}] Sent")
        else:
            failed_opportunities.append({**opp, **analysis})
            print(f"   ❌ [{i}/{min(len(opportunities), max_per_scan)}] Failed")
        
        # Rate limiting between messages
        if i < len(opportunities):
            time.sleep(2)
    
    # If many failed, try email batch fallback
    if len(failed_opportunities) >= 3:
        print(f"\n📧 Attempting email fallback for {len(failed_opportunities)} failed notifications...")
        if send_email_notification(failed_opportunities):
            print(f"✅ Email digest sent with {len(failed_opportunities)} opportunities")
    
    return sent_count