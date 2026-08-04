"""
main.py - Full Intraday Pair Trading Scanner (Root Version)
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp
import pandas as pd
import numpy as np

# ========== ALL IMPORTS ==========
from data_fetcher import AngelDataFetcher
from instrument import InstrumentManager
from pair_engine import PairEngineV2  # Rename pair_engine_v2.py to pair_engine.py
from universe import StockUniverse
from sector_map import get_sector

# ========== SMARTAPI ==========
try:
    from SmartApi import SmartConnect
    print("✅ SmartApi imported!")
except ImportError as e:
    print(f"❌ {e}")
    sys.exit(1)

print("=" * 60)
print("📊 INTRADAY PAIR TRADING SCANNER")
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

# ========== UNIVERSE ==========
print("\n🌐 Building trading universe...")
universe = StockUniverse(instrument_mgr)
all_stocks = universe.load_all_stocks()
liquid_stocks = universe.filter_liquid_stocks(min_price=50, min_volume=100000)

print(f"   Total NSE stocks: {len(all_stocks)}")
print(f"   Liquid stocks: {len(liquid_stocks)}")

# ========== FETCH DATA ==========
print("\n📊 Fetching historical data...")

# Start with top liquid stocks for testing
test_symbols = liquid_stocks[:20]
print(f"   Fetching {len(test_symbols)} stocks...")

fetcher = AngelDataFetcher(obj, instrument_mgr)
close_data = fetcher.fetch_close_prices(test_symbols, interval="ONE_MINUTE", days=3)

if close_data.empty:
    print("❌ No data fetched. Exiting.")
    sys.exit(1)

print(f"\n✅ Data: {len(close_data)} rows, {len(close_data.columns)} stocks")

# ========== PAIR ENGINE ==========
print("\n" + "=" * 60)
print("🔧 RUNNING PAIR ENGINE")
print("=" * 60)

from pair_engine import PairEngineV2

engine = PairEngineV2(close_data)
results = engine.scan_pairs(filters={
    'same_sector': True,
    'min_correlation': 0.7,
    'max_coint_pval': 0.05,
    'max_adf_pval': 0.05,
    'max_hurst': 0.5,
    'max_half_life': 50,
    'min_beta': 0.5,
    'max_beta': 2.0
})

engine.display_results(n=15)

# ========== SAVE RESULTS ==========
if results:
    df_results = pd.DataFrame(results)
    df_results.to_csv('pairs_results_full.csv', index=False)
    print(f"\n📁 Saved {len(results)} pairs to 'pairs_results_full.csv'")
    
    # Show top signal pairs
    signal_pairs = [r for r in results if 'BUY' in r['signal'] or 'SELL' in r['signal']]
    if signal_pairs:
        print(f"\n🚦 SIGNAL PAIRS ({len(signal_pairs)}):")
        for r in signal_pairs[:5]:
            s1, s2 = r['pair']
            print(f"   {r['signal']}: {s1} ↔ {s2} | Z-Score: {r['zscore']:.3f} | Score: {r['score']:.1f}")

print("\n" + "=" * 60)
print("✅ Scanner Complete!")