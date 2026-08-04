"""
Pair Trading Scanner - Phase 2: Real Login Test
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import time

print("=" * 60)
print("📊 PAIR TRADING SCANNER - LOGIN TEST")
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
if all([API_KEY, CLIENT_ID, PASSWORD, TOTP]):
    print("  ✅ All credentials are set.")
else:
    print("  ❌ Some credentials are missing.")
    sys.exit(1)

# ========== REAL LOGIN TEST ==========
print("\n🔄 Attempting Real Login to Angel One...")
print(f"   API Key: {API_KEY[:10]}...")
print(f"   Client ID: {CLIENT_ID}")

try:
    # Create SmartConnect object
    obj = SmartConnect(api_key=API_KEY)
    print("  ✅ SmartConnect object created")
    
    # Generate session
    print("  ⏳ Generating session...")
    response = obj.generateSession(
        clientCode=CLIENT_ID,
        password=PASSWORD,
        totp=TOTP
    )
    
    print(f"  📥 Response received: {type(response)}")
    
    if response and 'data' in response:
        print("\n" + "=" * 60)
        print("✅ LOGIN SUCCESSFUL!")
        print("=" * 60)
        
        data = response['data']
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
        print("✅ Ready for next step: Historical Data Fetch")
        print("=" * 60)
        
    else:
        print(f"\n❌ Login Failed: {response}")
        
except Exception as e:
    print(f"\n❌ Login Exception: {e}")
    print("   Possible reasons:")
    print("   1. Invalid API Key")
    print("   2. Wrong Client ID")
    print("   3. Incorrect Password")
    print("   4. TOTP expired")
    sys.exit(1)