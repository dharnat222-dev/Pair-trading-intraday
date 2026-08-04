"""
Test DataFetcher with Angel One Login
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp
import pandas as pd

print("=" * 60)
print("📊 DATA FETCHER TEST")
print("=" * 60)

# ========== SMARTAPI IMPORT ==========
try:
    from SmartApi import SmartConnect
    print("✅ SmartApi imported!")
except ImportError as e:
    print(f"❌ {e}")
    sys.exit(1)

# ========== CREDENTIALS ==========
API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PASSWORD = os.getenv("ANGEL_PASSWORD")
TOTP_SECRET = os.getenv("ANGEL_TOTP")

print("\n🔍 Checking secrets:")
print(f"  API_KEY: {API_KEY is not None}")
print(f"  CLIENT_ID: {CLIENT_ID is not None}")
print(f"  PASSWORD: {PASSWORD is not None}")
print(f"  TOTP_SECRET: {TOTP_SECRET is not None}")

if not all([API_KEY, CLIENT_ID, PASSWORD, TOTP_SECRET]):
    print("❌ Missing credentials")
    sys.exit(1)

# ========== GENERATE TOTP ==========
totp = pyotp.TOTP(TOTP_SECRET).now()
print(f"\n🔄 TOTP: {totp}")

# ========== LOGIN ==========
print("\n🔄 Logging in...")
obj = SmartConnect(api_key=API_KEY)
response = obj.generateSession(
    clientCode=CLIENT_ID,
    password=PASSWORD,
    totp=totp
)

if not response or response.get('status') != True:
    print(f"❌ Login Failed: {response}")
    sys.exit(1)

print("✅ Login Successful!")

# ========== FETCH DATA ==========
print("\n📊 Fetching historical data...")

# We'll add DataFetcher here later
print("✅ DataFetcher will be imported in next step")

print("\n" + "=" * 60)
print("✅ Test Passed!")