"""
Pair Trading Scanner - SmartAPI Login (NO TOTP)
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import json

print("=" * 60)
print("📊 PAIR TRADING SCANNER - LOGIN (NO TOTP)")
print("=" * 60)

# ========== SMARTAPI IMPORT ==========
try:
    from SmartApi import SmartConnect
    print("✅ SmartApi imported!")
except ImportError as e:
    print(f"❌ {e}")
    sys.exit(1)

# ========== LOAD CREDENTIALS ==========
API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PASSWORD = os.getenv("ANGEL_PASSWORD")
# TOTP not needed

print(f"  API Key: {API_KEY[:8]}...")
print(f"  Client ID: {CLIENT_ID}")

if not all([API_KEY, CLIENT_ID, PASSWORD]):
    print("❌ Missing credentials")
    sys.exit(1)

# ========== LOGIN ==========
print("\n🔄 Logging in...")
try:
    obj = SmartConnect(api_key=API_KEY)
    response = obj.generateSession(
        clientCode=CLIENT_ID,
        password=PASSWORD,
        totp=None  # No TOTP
    )
    
    if response and response.get('status') == True:
        print("✅ Login Successful!")
        data = response.get('data', {})
        print(f"  Auth Token: {data.get('jwtToken', 'N/A')[:30]}...")
        print(f"  Refresh Token: {data.get('refreshToken', 'N/A')[:30]}...")
    else:
        print(f"❌ Login Failed: {response}")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Login Exception: {e}")
    sys.exit(1)

print("\n✅ Ready for Data Fetching!")