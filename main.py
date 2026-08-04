"""
main.py - Test DataFetcher with Instrument Manager
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp
import pandas as pd
from data_fetcher import AngelDataFetcher
from instrument import InstrumentManager

print("=" * 60)
print("📊 INSTRUMENT + DATA FETCHER TEST")
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

print("\n🔍 Checking secrets...")
if not all([API_KEY, CLIENT_ID, PASSWORD, TOTP_SECRET]):
    print("❌ Missing credentials")
    sys.exit(1)

# ========== LOGIN ==========
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

# ========== LOAD INSTRUMENTS ==========
print("\n📥 Loading instrument master...")
instrument_mgr = InstrumentManager(obj)

# Try cache first
if not instrument_mgr.load_cache():
    print("  No cache found. Downloading master contract...")
    instrument_mgr.load_master_contract()
    instrument_mgr.save_cache()
else:
    print("  ✅ Using cached instruments")

if not instrument_mgr.is_loaded():
    print("❌ Failed to load instruments")
    sys.exit(1)

# Test token lookup
test_symbol = "RELIANCE"
token = instrument_mgr.get_token(test_symbol)
print(f"\n🔍 Test token lookup: {test_symbol} → {token}")

# ========== FETCH DATA ==========
print("\n📊 Fetching historical data...")

fetcher = AngelDataFetcher(obj, instrument_mgr)

symbols = ["RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS"]
close_data = fetcher.fetch_close_prices(symbols, interval="ONE_MINUTE", days=3)

print(f"\n✅ Data fetched: {len(close_data)} rows, {len(close_data.columns)} columns")

if not close_data.empty:
    print("\n📊 Sample data:")
    print(close_data.head())
    close_data.to_csv('close_prices.csv')
    print("\n📁 Saved to 'close_prices.csv'")
else:
    print("❌ No data fetched!")

print("\n" + "=" * 60)
print("✅ Test Passed!")