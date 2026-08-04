"""
main.py - Test with Scrip Master
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
print("📊 SCRIP MASTER + DATA FETCHER TEST")
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

if not all([API_KEY, CLIENT_ID, PASSWORD, TOTP_SECRET]):
    print("❌ Missing credentials")
    sys.exit(1)

# ========== LOGIN ==========
totp = pyotp.TOTP(TOTP_SECRET).now()
print(f"\n🔄 TOTP: {totp}")

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

# ========== INSTRUMENTS ==========
print("\n📥 Loading instruments...")
instrument_mgr = InstrumentManager(obj)
if not instrument_mgr.load_master_contract():
    print("❌ Failed to load instruments")
    sys.exit(1)

# ========== FETCH DATA ==========
print("\n📊 Fetching historical data...")

fetcher = AngelDataFetcher(obj, instrument_mgr)

symbols = ["RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS"]
close_data = fetcher.fetch_close_prices(symbols, interval="ONE_MINUTE", days=3)

if not close_data.empty:
    print(f"\n✅ Data: {len(close_data)} rows, {len(close_data.columns)} stocks")
    print(close_data.head())
    close_data.to_csv('close_prices.csv')
    print("📁 Saved to close_prices.csv")
else:
    print("❌ No data")

print("\n" + "=" * 60)
print("✅ Test Complete!")