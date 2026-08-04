"""
main.py - Scanner V5 (Intraday Optimized)
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp
import pandas as pd
from data_fetcher import AngelDataFetcher
from instrument import InstrumentManager
from pair_engine import PairEngineV5
from universe import StockUniverse

print("=" * 60)
print("📊 PAIR SCANNER V5 (INTRADAY OPTIMIZED)")
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

# ========== UNIVERSE ==========
print("\n🌐 Building trading universe...")
universe = StockUniverse(instrument_mgr)
all_stocks = universe.load_all_stocks()
liquid_stocks = universe.filter_liquid_stocks()

print(f"   Total NSE stocks: {len(all_stocks)}")
print(f"   Liquid stocks: {len(liquid_stocks)}")

# ========== FETCH DATA ==========
print("\n📊 Fetching historical data...")

test_symbols = liquid_stocks[:20]
print(f"   Fetching {len(test_symbols)} stocks...")

fetcher = AngelDataFetcher(obj, instrument_mgr)
close_data = fetcher.fetch_close_prices(test_symbols, interval="ONE_MINUTE", days=5)

if close_data.empty:
    print("❌ No data fetched. Exiting.")
    sys.exit(1)

print(f"\n✅ Data: {len(close_data)} rows, {len(close_data.columns)} stocks")

# ========== PAIR ENGINE V5 ==========
print("\n" + "=" * 60)
print("🔧 RUNNING PAIR ENGINE V5 (INTRADAY)")
print("=" * 60)

engine = PairEngineV5(close_data)

results = engine.scan_pairs(filters={
    'min_correlation': 0.6
})

engine.display_debug_report(n=20)
engine.display_results(n=10)

# ========== SAVE ==========
if results:
    df_results = pd.DataFrame([{
        'pair1': r['pair'][0],
        'pair2': r['pair'][1],
        'correlation': r['metrics']['correlation'],
        'rolling_corr': r['metrics']['rolling_corr'],
        'zscore': r['metrics']['zscore'],
        'atr': r['metrics']['atr'],
        'price_ratio': r['metrics']['price_ratio'],
        'score': r['metrics']['score'],
        'signal': r['metrics']['signal']
    } for r in results])
    
    df_results.to_csv('pairs_results_v5.csv', index=False)
    print(f"\n📁 Saved {len(results)} pairs to 'pairs_results_v5.csv'")

print("\n" + "=" * 60)
print("✅ Scanner Complete!")