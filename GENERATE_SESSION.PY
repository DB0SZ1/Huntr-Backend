"""
Telegram Session Generator for Production Deployment

Run this script LOCALLY on your computer to generate the session file.
Then upload the generated 'job_bot_session.session' file to Render.

Steps:
1. Install Telethon: pip install telethon
2. Set environment variables or enter them when prompted
3. Run: python generate_session.py
4. Enter your phone number and verification code
5. Upload the generated .session file to Render (via Git or Render Dashboard)
"""

import os
from telethon.sync import TelegramClient

def generate_session():
    print("=" * 60)
    print("🔐 TELEGRAM SESSION GENERATOR")
    print("=" * 60)
    print("\nThis will generate a session file for production deployment.")
    print("You'll need to enter your phone number and verification code.\n")
    
    # Get credentials
    api_id = os.getenv('TELEGRAM_API_ID') or input("Enter your Telegram API ID: ").strip()
    api_hash = os.getenv('TELEGRAM_API_HASH') or input("Enter your Telegram API Hash: ").strip()
    phone = os.getenv('TELEGRAM_PHONE') or input("Enter your phone number (with country code, e.g., +1234567890): ").strip()
    
    if not api_id or not api_hash or not phone:
        print("❌ Missing required credentials!")
        return
    
    try:
        api_id = int(api_id)
    except ValueError:
        print("❌ API ID must be a number!")
        return
    
    print(f"\n📱 Connecting to Telegram as {phone}...")
    
    # Create client with session file
    session_name = 'job_bot_session'
    
    with TelegramClient(session_name, api_id, api_hash) as client:
        # This will prompt for phone and code if needed
        client.start(phone=phone)
        
        print("\n✅ Session created successfully!")
        print(f"✅ File generated: {session_name}.session")
        print("\n📤 NEXT STEPS:")
        print("1. Upload this .session file to your Render project")
        print("   Option A: Add to Git repo (if private)")
        print("   Option B: Upload via Render Dashboard > Files")
        print("2. Set these environment variables in Render:")
        print(f"   - TELEGRAM_API_ID={api_id}")
        print(f"   - TELEGRAM_API_HASH={api_hash}")
        print(f"   - TELEGRAM_PHONE={phone}")
        print("\n3. Deploy your app - Telegram scraping will work without login prompts!")
        print("\n⚠️  SECURITY NOTE: Keep the .session file secure!")
        print("   It contains your login credentials.")
        print("=" * 60)

if __name__ == "__main__":
    try:
        generate_session()
    except KeyboardInterrupt:
        print("\n\n❌ Session generation cancelled.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure you have Telethon installed:")
        print("  pip install telethon")