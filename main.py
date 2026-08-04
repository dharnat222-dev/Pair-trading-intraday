"""
Pair Trading Scanner - Phase 2: Real Login Test (with Debug)
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import time
import json

print("=" * 60)
print("📊 PAIR TRADING SCANNER - LOGIN TEST (DEBUG)")
print("=" * 60)
print(f"Python: {sys.version}")

# ========== SMARTAPI IMPORT ==========
print("\n🔍 Importing SmartAPI...")
try:
    from SmartApi import SmartConnect
    print("✅ SmartApi imported successfully!")
except ImportError as e:
    print(f"❌ SmartApi import failed: {e}")
    sys.exit(1)

# ========== LOAD CREDENTIALS ==========
API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PASSWORD = os.getenv("ANGEL_PASSWORD")
TOTP = os.getenv("ANGEL_TOTP")

print("\n🔍 Checking Credentials...")
print(f"  API Key: {API_KEY[:10] if API_KEY else 'None'}...")
print(f"  Client ID: {CLIENT_ID if CLIENT_ID else 'None'}")
print(f"  Password: {'*' * 8 if PASSWORD else 'None'}")
print(f"  TOTP: {'*' * 8 if TOTP else 'None'}")

if not all([API_KEY, CLIENT_ID, PASSWORD, TOTP]):
    print("  ❌ Some credentials are missing.")
    sys.exit(1)
else:
    print("  ✅ All credentials are set.")

# ========== REAL LOGIN TEST ==========
print("\n🔄 Attempting Real Login to Angel One...")

try:
    # Create SmartConnect object
    obj = SmartConnect(api_key=API_KEY)
    print("  ✅ SmartConnect object created")
    
    # Generate session
    print("  ⏳ Generating session...")
    print(f"  Client Code: {CLIENT_ID}")
    print(f"  TOTP (first 4): {TOTP[:4] if TOTP else 'None'}...")
    
    response = obj.generateSession(
        clientCode=CLIENT_ID,
        password=PASSWORD,
        totp=TOTP
    )
    
    print(f"  📥 Response received")
    print(f"  📥 Response type: {type(response)}")
    print(f"  📥 Response content: {json.dumps(response, indent=2)[:500]}...")
    
    # Check response
    if response and isinstance(response, dict):
        if response.get('status') == True and 'data' in response:
            print("\n" + "=" * 60)
            print("✅ LOGIN SUCCESSFUL!")
            print("=" * 60)
            
            data = response.get('data', {})
            auth_token = data.get('jwtToken', 'N/A')
            refresh_token = data.get('refreshToken', 'N/A')
            
            print(f"  Auth Token: {auth_token[:30]}..." if auth_token != 'N/A' else "  Auth Token: N/A")
            print(f"  Refresh Token: {refresh_token[:30]}..." if refresh_token != 'N/A' else "  Refresh Token: N/A")
            
            # Get feed token
            try:
                feed_token = obj.getfeedToken()
                print(f"  Feed Token: {feed_token[:30]}..." if feed_token else "  Feed Token: N/A")
            except:
                print("  ⚠️ Could not get feed token")
            
            print("\n" + "=" * 60)
            print("✅ Login Test Passed!")
            print("=" * 60)
            
        else:
            error_msg = response.get('message', 'Unknown error')
            error_code = response.get('errorcode', 'Unknown')
            print(f"\n❌ Login Failed (API Error):")
            print(f"  Error: {error_msg}")
            print(f"  Code: {error_code}")
            print(f"  Full Response: {json.dumps(response, indent=2)}")
            sys.exit(1)
    else:
        print(f"\n❌ Login Failed: Invalid response format")
        print(f"  Response: {response}")
        sys.exit(1)
        
except Exception as e:
    print(f"\n❌ Login Exception: {e}")
    print("\n  Possible reasons:")
    print("  1. ❌ Invalid TOTP (2FA code) - Check your TOTP secret")
    print("  2. ❌ Wrong Client ID - Should be 8-digit number")
    print("  3. ❌ Incorrect Password - Check Angel One password")
    print("  4. ❌ Invalid API Key - Check if API is active")
    print("  5. ❌ TOTP expired - TOTP changes every 30 seconds")
    sys.exit(1)