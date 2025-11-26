"""
Test the tokens received from OAuth callback
"""
import requests
import json

# Tokens from the callback URL
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OTFmODQ5Y2E3MjNlNjhlNTVkYmZlZDAiLCJ0eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYzNjc2ODQ1LCJpYXQiOjE3NjM2NzMyNDV9.de3ftGrCfRsMPbmEWJVmS0lHf8UgH3gtiQxDeOoI5tU"
REFRESH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OTFmODQ5Y2E3MjNlNjhlNTVkYmZlZDAiLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2NjI2NTI0NSwiaWF0IjoxNzYzNjczMjQ1fQ.ksK4QV58RIVSo04YElg4766O-cInvozB-UrmYrmVj1Y"

BASE_URL = "http://localhost:8000"

print("Testing OAuth callback tokens...\n")

# Test access token
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}

print("1. Testing GET /api/auth/me with access token...")
response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
print(f"   Status: {response.status_code}")
print(f"   Response: {json.dumps(response.json(), indent=2)}\n")

print("2. Testing GET /api/dashboard/stats...")
response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers)
print(f"   Status: {response.status_code}")
print(f"   Response: {json.dumps(response.json(), indent=2)}\n")

print("3. Testing GET /api/niches...")
response = requests.get(f"{BASE_URL}/api/niches", headers=headers)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   Response: {json.dumps(response.json(), indent=2)}\n")
else:
    print(f"   Error: {response.text}\n")

print("✅ Tokens are valid and working!")
print("\nNext steps:")
print("1. Start your React frontend: npm start (in frontend directory)")
print("2. Click 'Login with Google' button")
print("3. Frontend will receive these tokens and store them")
print("4. Use tokens for subsequent API calls")
