"""
main.py - Test DataFetcher
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp
import pandas as pd
from data_fetcher import AngelDataFetcher

print("=" * 60)
print("📊 DATA FETCHER TEST")
print("=" * 60)

# ========== SMARTAPI ==========
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

# ========== TOTP & LOGIN ==========
totp = pyotp.TOTP(TOTP_SECRET).now()
print(f"\n🔄 TOTP: {totp}")

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

fetcher = AngelDataFetcher(obj)

symbols = ["RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS"]

print(f"\n  Fetching {len(symbols)} symbols:")
for sym in symbols:
    print(f"    - {sym}")

close_data = fetcher.fetch_close_prices(symbols, interval="ONE_MINUTE", days=3)

print(f"\n✅ Data fetched: {len(close_data)} rows, {len(close_data.columns)} columns")
print(f"   Columns: {list(close_data.columns)}")

if not close_data.empty:
    print("\n📊 Sample data (first 5 rows):")
    print(close_data.head())
    
    close_data.to_csv('close_prices.csv')
    print("\n📁 Saved to 'close_prices.csv'")
else:
    print("❌ No data fetched!")

print("\n" + "=" * 60)
print("✅ Test Passed!")