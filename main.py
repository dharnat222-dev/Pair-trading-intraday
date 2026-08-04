"""
main.py - Scanner V4 with Looser Filters
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp
import pandas as pd
from data_fetcher import AngelDataFetcher
from instrument import InstrumentManager
from pair_engine import PairEngineV4
from universe import StockUniverse

print("=" * 60)
print("📊 PAIR SCANNER V4 (LOOSER FILTERS + DEBUG)")
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
close_data = fetcher.fetch_close_prices(test_symbols, interval="ONE_MINUTE", days=3)

if close_data.empty:
    print("❌ No data fetched. Exiting.")
    sys.exit(1)

print(f"\n✅ Data: {len(close_data)} rows, {len(close_data.columns)} stocks")

# ========== PAIR ENGINE V4 ==========
print("\n" + "=" * 60)
print("🔧 RUNNING PAIR ENGINE V4 (LOOSER FILTERS)")
print("=" * 60)

engine = PairEngineV4(close_data)

# Looser filters
results = engine.scan_pairs(filters={
    'same_sector': False,      # Disable sector filter
    'min_correlation': 0.5,    # Looser correlation
    'max_pval': 0.10           # Same coint p-value
})

# Show debug report
engine.display_debug_report(n=20)

# Show results
engine.display_results(n=10)

# ========== SAVE ==========
if results:
    df_results = pd.DataFrame([{
        'pair1': r['pair'][0],
        'pair2': r['pair'][1],
        'correlation': r['metrics']['correlation'],
        'coint_pval': r['metrics']['coint_pval'],
        'beta': r['metrics']['beta'],
        'hurst': r['metrics']['hurst'],
        'half_life': r['metrics']['half_life'],
        'zscore': r['metrics']['zscore'],
        'score': r['metrics']['score'],
        'signal': r['metrics']['signal']
    } for r in results])
    
    df_results.to_csv('pairs_results_v4.csv', index=False)
    print(f"\n📁 Saved {len(results)} pairs to 'pairs_results_v4.csv'")

print("\n" + "=" * 60)
print("✅ Scanner Complete!")