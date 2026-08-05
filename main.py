"""
main.py - Professional Pair Scanner (Full NSE Scan)
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp
import pandas as pd
from batch_fetcher import BatchFetcher
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
all_stocks = universe.load_all_stocks()  # 2440 -EQ stocks
liquid_stocks = universe.filter_liquid_stocks()  # 43 F&O stocks

print(f"   Total NSE -EQ stocks: {len(all_stocks)}")
print(f"   Liquid stocks: {len(liquid_stocks)}")

# ========== OPTION: SCAN ALL OR LIMITED ==========
# Option 1: Scan all 2440 stocks (SLOW - 30 lakh pairs)
# Option 2: Scan 500 stocks (FAST - 1.25 lakh pairs)
# Option 3: Scan only liquid stocks (VERY FAST - 903 pairs)

SCAN_MODE = "FAST"  # "FULL", "MEDIUM", "FAST"

if SCAN_MODE == "FULL":
    symbols_to_scan = all_stocks
    print("\n🔴 FULL SCAN: 2440 stocks (may take 1-2 hours)")
elif SCAN_MODE == "MEDIUM":
    symbols_to_scan = all_stocks[:500]
    print("\n🟡 MEDIUM SCAN: 500 stocks (may take 15-30 minutes)")
else:  # FAST
    symbols_to_scan = liquid_stocks
    print("\n🟢 FAST SCAN: 43 liquid stocks (takes 2-3 minutes)")

print(f"   Scanning {len(symbols_to_scan)} stocks")

# ========== FETCH DATA ==========
print("\n" + "=" * 60)
print("📊 STAGE 1: DATA FETCH (Batch Processing)")
print("=" * 60)

fetcher = BatchFetcher(obj, instrument_mgr)

print(f"\n📊 Fetching data for {len(symbols_to_scan)} stocks...")
print("   ⚠️ This may take several minutes...")

data_dict = fetcher.fetch_batch(symbols_to_scan, days=250)

print(f"\n✅ Data fetched for {len(data_dict)} stocks")

if not data_dict:
    print("❌ No data fetched")
    sys.exit(1)

# Build close price DataFrame
close_data = pd.DataFrame()
for symbol, df in data_dict.items():
    close_data[symbol] = df.set_index('timestamp')['close']

close_data = close_data.dropna()

print(f"\n✅ Data: {len(close_data)} rows, {len(close_data.columns)} stocks")

# ========== PAIR SELECTION ==========
print("\n" + "=" * 60)
print("📊 STAGE 2: PAIR SELECTION")
print("=" * 60)

engine = PairEngineV7(close_data, sector_map)
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