import os
from dotenv import load_dotenv

load_dotenv()

secret = os.getenv('PAYSTACK_SECRET_KEY')
public = os.getenv('PAYSTACK_PUBLIC_KEY')

print("\n=== PAYSTACK KEY VERIFICATION ===\n")

print(f"Secret Key: {secret[:20]}...")
print(f"  ✅ Valid format" if secret.startswith('sk_test_') else f"  ❌ Invalid format")

print(f"\nPublic Key: {public[:20]}...")
print(f"  ✅ Valid format" if public.startswith('pk_test_') else f"  ❌ Invalid format")

if secret.startswith('sk_test_') and public.startswith('pk_test_'):
    print("\n✅ Keys look good! Ready to test.")
else:
    print("\n❌ Keys are still placeholder values!")
    print("\nFix: Replace with real test keys from:")
    print("https://dashboard.paystack.com/settings/developers")
