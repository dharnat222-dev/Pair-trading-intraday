"""
main.py - Pair Scanner with Instrument Check
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp
import pandas as pd
from data_fetcher import AngelDataFetcher
from instrument import InstrumentManager
from pair_engine_v7 import PairEngineV7
from universe import StockUniverse
from sector_map import SECTOR_MAP

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
if not instrument_mgr.load_master_contract():
    print("\n❌ Failed to load instruments. Exiting...")
    sys.exit(1)

# ========== UNIVERSE ==========
print("\n🌐 Building trading universe...")
universe = StockUniverse(instrument_mgr)
all_stocks = universe.load_all_stocks()
liquid_stocks = universe.filter_liquid_stocks()

print(f"   Total NSE stocks: {len(all_stocks)}")
print(f"   Liquid stocks: {len(liquid_stocks)}")

if not liquid_stocks:
    print("\n❌ No liquid stocks found. Exiting...")
    sys.exit(1)

# ========== STAGE-1: PAIR SELECTION ==========
print("\n" + "=" * 60)
print("📊 STAGE 1: PAIR SELECTION (Daily Data)")
print("=" * 60)

fetcher = AngelDataFetcher(obj, instrument_mgr)

print(f"\n📊 Fetching daily data for {len(liquid_stocks)} stocks...")
close_data_daily = fetcher.fetch_close_prices(
    liquid_stocks, 
    interval="ONE_DAY", 
    days=250
)

if close_data_daily.empty:
    print("❌ No daily data fetched. Exiting.")
    sys.exit(1)

if len(close_data_daily.columns) < 5:
    print(f"❌ Only {len(close_data_daily.columns)} stocks available. Minimum 5 required.")
    sys.exit(1)

print(f"\n✅ Daily data: {len(close_data_daily)} rows, {len(close_data_daily.columns)} stocks")

# Run Pair Engine
engine = PairEngineV7(close_data_daily, SECTOR_MAP)
results = engine.scan_pairs()

engine.display_debug_report(n=20)
engine.display_results(n=20)

# Save top pairs
top_pairs = engine.get_top_pairs(n=20)
if top_pairs:
    df_pairs = pd.DataFrame([{
        'pair1': r['pair'][0],
        'pair2': r['pair'][1],
        'sector': engine._get_sector(r['pair'][0]),
        'correlation': r['metrics']['correlation'],
        'rolling_corr': r['metrics']['rolling_corr'],
        'coint_pval': r['metrics']['coint_pval'],
        'beta': r['metrics']['beta'],
        'hurst': r['metrics']['hurst'],
        'half_life': r['metrics']['half_life'],
        'score': r['metrics']['score']
    } for r in top_pairs])
    
    df_pairs.to_csv('selected_pairs_v7.csv', index=False)
    print(f"\n📁 Saved {len(top_pairs)} selected pairs to 'selected_pairs_v7.csv'")
else:
    print("\n❌ No pairs selected. Check debug report.")

print("\n" + "=" * 60)
print("✅ Scanner Complete!")