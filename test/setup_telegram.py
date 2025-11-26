"""
Telegram Setup & Authentication
Interactive setup for Telegram API credentials
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key

# Load existing .env
ENV_FILE = Path(__file__).parent / ".env"
load_dotenv(ENV_FILE, override=True)

print("\n" + "="*70)
print("TELEGRAM API SETUP")
print("="*70)

print("\n[STEP 1] Get your Telegram API credentials")
print("-" * 70)
print("1. Go to: https://my.telegram.org/auth/login")
print("2. Login with your phone number (the one you'll use for scraping)")
print("3. Click 'API development tools'")
print("4. Fill in the form (App title, Short name, etc.)")
print("5. You'll get API_ID and API_HASH")
print()

api_id = input("Enter your TELEGRAM_API_ID: ").strip()
if not api_id:
    print("❌ API_ID is required!")
    sys.exit(1)

api_hash = input("Enter your TELEGRAM_API_HASH: ").strip()
if not api_hash:
    print("❌ API_HASH is required!")
    sys.exit(1)

phone = input("Enter your phone number (with country code, e.g., +234803123456): ").strip()
if not phone:
    print("❌ Phone number is required!")
    sys.exit(1)

# Validate phone format
if not phone.startswith('+'):
    phone = '+' + phone

print("\n[STEP 2] Saving credentials to .env")
print("-" * 70)

try:
    # Save to .env
    set_key(ENV_FILE, "TELEGRAM_API_ID", api_id)
    print(f"✅ Saved TELEGRAM_API_ID: {api_id}")

    set_key(ENV_FILE, "TELEGRAM_API_HASH", api_hash)
    print(f"✅ Saved TELEGRAM_API_HASH: {api_hash[:20]}...")

    set_key(ENV_FILE, "TELEGRAM_PHONE", phone)
    print(f"✅ Saved TELEGRAM_PHONE: {phone}")
    
    # CRITICAL: Reload .env to get new values
    print("\n[STEP 2b] Reloading environment variables...")
    load_dotenv(ENV_FILE, override=True)
    print("✅ Environment variables reloaded")

except Exception as e:
    print(f"❌ Error saving to .env: {e}")
    sys.exit(1)

print("\n[STEP 3] Testing Telegram Connection")
print("-" * 70)

# Test connection
try:
    from telethon.sync import TelegramClient
    
    # Convert to int
    api_id_int = int(api_id)
    
    print(f"\nCreating Telegram client...")
    client = TelegramClient('session_auth', api_id_int, api_hash)
    
    print(f"Connecting to Telegram...")
    client.connect()
    
    print(f"✅ Connected to Telegram successfully!")
    
    # Check if authorized
    if client.is_user_authorized():
        print(f"✅ Already authorized!")
        me = client.get_me()
        print(f"   Logged in as: {me.first_name} (@{me.username})")
    else:
        print(f"\n⚠️  Not authorized yet - need to verify phone")
        print(f"\nStarting authentication...")
        
        # Request code
        print(f"You will receive a code on Telegram. Enter it below.")
        client.send_code_request(phone)
        
        code = input("Enter the code you received: ").strip()
        
        try:
            client.sign_in(phone, code)
            print(f"✅ Successfully signed in!")
            
            me = client.get_me()
            print(f"   Logged in as: {me.first_name} (@{me.username})")
        
        except Exception as e:
            print(f"❌ Sign in failed: {str(e)}")
            print(f"   If you have 2FA, you may need to verify further")
    
    client.disconnect()
    print(f"\n✅ Telegram setup complete!")
    
except ImportError:
    print("❌ Telethon not installed")
    print("   Install with: pip install telethon")
    sys.exit(1)
except Exception as e:
    print(f"❌ Connection failed: {str(e)}")
    print(f"\nYour credentials were saved. Troubleshooting:")
    print(f"1. Check API_ID and API_HASH are correct")
    print(f"2. Verify phone number format: {phone}")
    print(f"3. Check internet connection")
    sys.exit(1)

print("\n" + "="*70 + "\n")
