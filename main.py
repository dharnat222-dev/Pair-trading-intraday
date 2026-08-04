"""
Pair Trading Scanner - Login with TOTP Secret
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp

print("=" * 60)
print("📊 PAIR TRADING SCANNER - LOGIN (TOTP SECRET)")
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
TOTP_SECRET = os.getenv("ANGEL_TOTP")  # JBSWY3DPEHPK3PXP

print("\n🔍 Checking GitHub Secrets:")
print(f"  ANGEL_API_KEY: {API_KEY is not None}")
print(f"  ANGEL_CLIENT_ID: {CLIENT_ID is not None}")
print(f"  ANGEL_PASSWORD: {PASSWORD is not None}")
print(f"  ANGEL_TOTP (Secret): {TOTP_SECRET is not None}")

if not all([API_KEY, CLIENT_ID, PASSWORD, TOTP_SECRET]):
    print("\n❌ Missing credentials. Check GitHub Secrets.")
    sys.exit(1)

# ========== GENERATE TOTP ==========
try:
    print("\n🔄 Generating TOTP from Secret...")
    totp = pyotp.TOTP(TOTP_SECRET).now()
    print(f"  ✅ Generated TOTP: {totp}")
except Exception as e:
    print(f"❌ TOTP Generation Failed: {e}")
    sys.exit(1)

# ========== LOGIN ==========
print("\n🔄 Logging in to Angel One...")
try:
    obj = SmartConnect(api_key=API_KEY)
    response = obj.generateSession(
        clientCode=CLIENT_ID,
        password=PASSWORD,
        totp=totp   # 6-digit OTP
    )
    
    if response and response.get('status') == True:
        print("\n✅ LOGIN SUCCESSFUL!")
        data = response.get('data', {})
        print(f"  Auth Token: {data.get('jwtToken', 'N/A')[:30]}...")
        print(f"  Refresh Token: {data.get('refreshToken', 'N/A')[:30]}...")
        
        # Get feed token
        try:
            feed_token = obj.getfeedToken()
            print(f"  Feed Token: {feed_token[:30] if feed_token else 'N/A'}...")
        except:
            pass
        
        print("\n✅ Ready for Data Fetching!")
        
    else:
        print(f"\n❌ Login Failed: {response}")
        print("\n  Possible reasons:")
        print("  1. ❌ TOTP Secret is wrong or expired")
        print("  2. ❌ Invalid Client ID")
        print("  3. ❌ Wrong Password")
        sys.exit(1)
        
except Exception as e:
    print(f"\n❌ Login Exception: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ Login Test Passed!")