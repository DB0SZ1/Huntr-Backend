"""
Test if Paystack keys are loaded correctly
"""
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

print("\n=== PAYSTACK KEYS CHECK ===\n")

secret_key = os.getenv('PAYSTACK_SECRET_KEY')
public_key = os.getenv('PAYSTACK_PUBLIC_KEY')

print(f"Secret Key loaded: {'✅ Yes' if secret_key else '❌ No'}")
print(f"Public Key loaded: {'✅ Yes' if public_key else '❌ No'}")

if secret_key:
    print(f"\nSecret Key format check:")
    print(f"  Starts with 'sk_test_': {'✅ Yes' if secret_key.startswith('sk_test_') else '❌ No'}")
    print(f"  Length: {len(secret_key)} characters")
    print(f"  Preview: {secret_key[:20]}...")
else:
    print("❌ PAYSTACK_SECRET_KEY not found in .env")

if public_key:
    print(f"\nPublic Key format check:")
    print(f"  Starts with 'pk_test_': {'✅ Yes' if public_key.startswith('pk_test_') else '❌ No'}")
    print(f"  Length: {len(public_key)} characters")
    print(f"  Preview: {public_key[:20]}...")
else:
    print("❌ PAYSTACK_PUBLIC_KEY not found in .env")

print("\n=== KEY VALIDATION ===\n")

if secret_key and secret_key.startswith('sk_test_'):
    print("✅ Secret key looks correct (test key)")
elif secret_key and secret_key.startswith('sk_live_'):
    print("❌ Using LIVE key in development! Change to test key!")
else:
    print("❌ Secret key is invalid or missing")

if public_key and public_key.startswith('pk_test_'):
    print("✅ Public key looks correct (test key)")
elif public_key and public_key.startswith('pk_live_'):
    print("❌ Using LIVE key in development! Change to test key!")
else:
    print("❌ Public key is invalid or missing")

print()
