"""
Quick test for niche creation endpoint
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Generate a valid JWT token for test user
from app.auth.jwt_handler import create_access_token

test_user_id = "507f1f77bcf86cd799439011"
token = create_access_token(test_user_id)

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

payload = {
    "name": "Python Test Niche",
    "keywords": ["react", "web3", "developer"],
    "platforms": ["Twitter/X", "Reddit"],
    "description": "Test niche from Python",
    "min_confidence": 70
}

print("Testing POST /api/niches...")
print(f"Token: {token[:50]}...")
print(f"Payload: {json.dumps(payload, indent=2)}\n")

try:
    response = requests.post(
        f"{BASE_URL}/api/niches",
        json=payload,
        headers=headers,
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 201:
        print("\n✅ SUCCESS! Niche created!")
    else:
        print(f"\n❌ FAILED: {response.status_code}")
        
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
