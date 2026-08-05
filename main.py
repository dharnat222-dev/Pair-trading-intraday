"""
main.py - Pair Scanner (Full NSE Scan)
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
from sector_map import SECTOR_MAP, load_sectors_from_scrip_master

print("=" * 60)
print("📊 PAIR TRADING SCANNER (FULL NSE SCAN)")
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
    print("❌ Failed to load instruments")
    sys.exit(1)

# ========== AUTO-GENERATE SECTORS ==========
print("\n📥 Generating sector map...")
sector_map = load_sectors_from_scrip_master(instrument_mgr)
print(f"   Total sectors: {len(sector_map)} symbols")

# ========== UNIVERSE ==========
print("\n🌐 Building trading universe...")
universe = StockUniverse(instrument_mgr)
all_stocks = universe.load_all_stocks()
liquid_stocks = universe.filter_liquid_stocks()

print(f"   Total NSE stocks: {len(all_stocks)}")
print(f"   Liquid stocks: {len(liquid_stocks)}")

if not liquid_stocks:
    print("❌ No liquid stocks found")
    sys.exit(1)

# ========== STAGE-1: PAIR SELECTION ==========
print("\n" + "=" * 60)
print("📊 STAGE 1: PAIR SELECTION")
print("=" * 60)

fetcher = AngelDataFetcher(obj, instrument_mgr)

# 🔧 FIX: Use ALL liquid stocks, not just 30
print(f"\n📊 Fetching data for {len(liquid_stocks)} liquid stocks...")
print("   ⚠️ This will take 5-10 minutes for 100+ stocks...")

close_data_daily = fetcher.fetch_close_prices(
    liquid_stocks,  # 🔧 ALL liquid stocks
    interval="ONE_DAY",
    days=250
)

if close_data_daily.empty:
    print("❌ No daily data fetched")
    sys.exit(1)

print(f"\n✅ Daily data: {len(close_data_daily)} rows, {len(close_data_daily.columns)} stocks")

# Run Pair Engine
engine = PairEngineV7(close_data_daily, sector_map)
results = engine.scan_pairs()

engine.display_debug_report(n=20)
engine.display_results(n=20)

# Save top pairs
top_pairs = engine.get_top_pairs(n=20)
if top_pairs:
    df_pairs = pd.DataFrame([{
        'pair1': r['pair'][0],
        'pair2': r['pair'][1],
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