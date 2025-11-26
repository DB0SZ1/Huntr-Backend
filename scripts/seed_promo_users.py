"""
Seed promo users from CSV into database
Uses existing MongoDB Atlas cluster from config
Usage: python scripts/seed_promo_users.py --file data/promo_users.csv
"""
import asyncio
import csv
import argparse
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys

# Add parent directory to path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import settings from config (uses .env file)
from config import settings

async def seed_promo_users(csv_file: str, db_uri: str = None):
    """
    Seed promo users from CSV file using existing MongoDB cluster
    
    Args:
        csv_file: Path to CSV file
        db_uri: MongoDB connection URI (defaults to settings.MONGODB_URL)
    """
    # Use settings from .env if not provided
    if db_uri is None:
        db_uri = settings.MONGODB_URL
    
    if not db_uri:
        print("[ERROR] MONGODB_URL not set in .env file")
        print("Please configure your MongoDB connection in .env:")
        print("  MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/job_hunter")
        return False
    
    # Check if file exists
    if not os.path.exists(csv_file):
        print(f"[ERROR] CSV file not found: {csv_file}")
        print(f"Expected at: {os.path.abspath(csv_file)}")
        return False
    
    # Create client using existing cluster settings
    client = AsyncIOMotorClient(
        db_uri,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=15000,
        socketTimeoutMS=20000,
        retryWrites=True,
        retryReads=True
    )
    
    # Use same database name from config
    db = client[settings.DATABASE_NAME]
    
    try:
        print(f"[INFO] Reading CSV file: {csv_file}")
        print(f"[INFO] Database: {settings.DATABASE_NAME}")
        print(f"[INFO] Using existing MongoDB cluster")
        
        # Test connection
        print("[INFO] Testing MongoDB connection...")
        try:
            await asyncio.wait_for(
                db.command('ping'),
                timeout=10.0
            )
            print("[OK] ✅ MongoDB connection successful")
        except asyncio.TimeoutError:
            print("[ERROR] Connection timeout - MongoDB not responding")
            print("\n[HELP] Make sure:")
            print("  1. Your IP is whitelisted in MongoDB Atlas")
            print("  2. Your password is URL-encoded in MONGODB_URL")
            print("  3. Network connectivity is working")
            return False
        except Exception as e:
            print(f"[ERROR] Cannot connect to MongoDB: {str(e)}")
            print("\n[HELP] Check your MONGODB_URL in .env file")
            return False
        
        successful = 0
        failed = 0
        duplicates = 0
        errors = []
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Extract fields
                    twitter_handle = row.get('x_handle', '').strip().lstrip('@').lower()
                    email = row.get('email', '').strip().lower()
                    phone = row.get('whatsapp', '').strip()
                    
                    if not twitter_handle or not email or not phone:
                        error_msg = f"Missing required fields"
                        print(f"[SKIP] Row {row_num}: {error_msg}")
                        errors.append({"row": row_num, "error": error_msg})
                        failed += 1
                        continue
                    
                    # Handle URLs like https://x.com/mose61544
                    if 'x.com/' in twitter_handle or 'twitter.com/' in twitter_handle:
                        twitter_handle = twitter_handle.split('/')[-1].split('?')[0]
                    
                    # Normalize phone (remove spaces, dashes, but keep + and digits)
                    phone_normalized = ''.join(c for c in phone if c.isdigit() or c == '+')
                    
                    # Validate phone length
                    if len(phone_normalized) < 7:
                        error_msg = f"Invalid phone: {phone}"
                        print(f"[SKIP] Row {row_num}: {error_msg}")
                        errors.append({"row": row_num, "error": error_msg})
                        failed += 1
                        continue
                    
                    # Check for duplicates
                    existing = await db.promo_users.find_one({
                        "twitter_handle": twitter_handle,
                        "phone_number": phone_normalized
                    })
                    
                    if existing:
                        print(f"[DUP] Row {row_num}: {twitter_handle} already exists")
                        duplicates += 1
                        continue
                    
                    # Insert promo user
                    await db.promo_users.insert_one({
                        "twitter_handle": twitter_handle,
                        "email": email,
                        "phone_number": phone_normalized,
                        "status": "available",
                        "trial_tier": "pro",
                        "trial_duration_days": 14,
                        "created_at": datetime.utcnow(),
                        "redeemed_at": None,
                        "redeemed_by_user_id": None,
                        "redeemed_by_email": None,
                        "expires_at": datetime.utcnow() + timedelta(days=90),
                        "notes": "CSV seed import"
                    })
                    
                    print(f"[OK] Row {row_num}: @{twitter_handle} ({email})")
                    successful += 1
                
                except Exception as e:
                    error_msg = str(e)
                    print(f"[ERROR] Row {row_num}: {error_msg}")
                    errors.append({"row": row_num, "error": error_msg})
                    failed += 1
        
        # Create index for faster lookups
        print("\n[INFO] Creating database index...")
        try:
            await db.promo_users.create_index([
                ("twitter_handle", 1),
                ("phone_number", 1)
            ])
            print("[OK] Index created successfully")
        except Exception as e:
            print(f"[WARN] Index creation (may already exist): {e}")
        
        # Print summary
        print("\n" + "="*60)
        print("IMPORT SUMMARY")
        print("="*60)
        print(f"✅ Successful:  {successful}")
        print(f"❌ Failed:      {failed}")
        print(f"⚠️  Duplicates:  {duplicates}")
        print(f"📊 Total:       {successful + failed + duplicates}")
        print("="*60)
        
        if errors:
            print(f"\n[ERRORS] (first 10):")
            for error in errors[:10]:
                print(f"  Row {error.get('row')}: {error.get('error')}")
        
        if successful > 0:
            print(f"\n[SUCCESS] ✅ {successful} promo users imported to {settings.DATABASE_NAME}")
        
        return successful > 0
    
    except Exception as e:
        print(f"[CRITICAL ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        client.close()
        print("[INFO] Database connection closed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed promo users from CSV into MongoDB Atlas cluster",
        epilog="Uses MONGODB_URL from .env file"
    )
    parser.add_argument(
        '--file',
        default='data/promo_users.csv',
        help='CSV file path (default: data/promo_users.csv)'
    )
    parser.add_argument(
        '--db',
        default=None,
        help='MongoDB URI (defaults to MONGODB_URL in .env)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("PROMO USERS CSV IMPORT - MongoDB Atlas")
    print("="*60)
    print(f"Using config from: {os.path.abspath('.env')}")
    print()
    
    success = asyncio.run(seed_promo_users(args.file, args.db))
    
    sys.exit(0 if success else 1)
