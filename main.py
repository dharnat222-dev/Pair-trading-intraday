"""
main.py - Pair Trading Scanner with Pair Engine
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp
import pandas as pd
from data_fetcher import AngelDataFetcher
from instrument import InstrumentManager
from pair_engine import PairEngine

print("=" * 60)
print("📊 PAIR TRADING SCANNER")
print("=" * 60)

# ========== CREDENTIALS ==========
API_KEY = os.getenv("ANGEL_API_KEY")
CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
PASSWORD = os.getenv("ANGEL_PASSWORD")
TOTP_SECRET = os.getenv("ANGEL_TOTP")

if not all([API_KEY, CLIENT_ID, PASSWORD, TOTP_SECRET]):
    print("❌ Missing credentials")
    sys.exit(1)

# ========== LOGIN ==========
try:
    from SmartApi import SmartConnect
    print("✅ SmartApi imported!")
except ImportError as e:
    print(f"❌ {e}")
    sys.exit(1)

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
instrument_mgr.load_master_contract()

# ========== FETCH DATA ==========
print("\n📊 Fetching historical data...")

symbols = ["RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS", "HINDUNILVR", "ITC"]

fetcher = AngelDataFetcher(obj, instrument_mgr)
close_data = fetcher.fetch_close_prices(symbols, interval="ONE_MINUTE", days=3)

if close_data.empty:
    print("❌ No data fetched. Exiting.")
    sys.exit(1)

print(f"\n✅ Data: {len(close_data)} rows, {len(close_data.columns)} stocks")
close_data.to_csv('close_prices.csv', index=True)
print("📁 Saved to close_prices.csv")

# ========== PAIR ENGINE ==========
print("\n" + "=" * 60)
print("🔧 RUNNING PAIR ENGINE")
print("=" * 60)

engine = PairEngine(close_data)
results = engine.scan_pairs(corr_threshold=0.6, pval_threshold=0.10)
engine.display_results(n=10)

if results:
    df_results = pd.DataFrame(results)
    df_results.to_csv('pairs_results.csv', index=False)
    print(f"\n📁 Saved {len(results)} pairs to 'pairs_results.csv'")

print("\n" + "=" * 60)
print("✅ Scanner Complete!")