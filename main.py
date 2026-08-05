"""
main.py - Professional Pair Trading Scanner (Yahoo Finance Data)
Angel One kept only for login and sector mapping.
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import pyotp
import pandas as pd
import logging
from datetime import datetime

# ========== SETUP LOGGING ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scanner.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import all modules
from instrument import InstrumentManager
from universe import StockUniverse
from batch_fetcher import BatchFetcher
from pair_engine_v7 import PairEngineV7
from sector_map import SECTOR_MAP, load_sectors_from_scrip_master

logger.info("=" * 60)
logger.info("📊 PAIR TRADING SCANNER - YAHOO FINANCE")
logger.info("=" * 60)
logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ========== ANGEL ONE LOGIN (OPTIONAL - ONLY FOR SECTOR MAP) ==========
ANGEL_API_KEY = os.getenv("ANGEL_API_KEY")
ANGEL_CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
ANGEL_PASSWORD = os.getenv("ANGEL_PASSWORD")
ANGEL_TOTP_SECRET = os.getenv("ANGEL_TOTP")

obj = None
instrument_mgr = None
sector_map = SECTOR_MAP.copy()

# Try to login to Angel One for sector mapping (optional)
if all([ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET]):
    try:
        import pyotp
        from SmartApi import SmartConnect

        logger.info("🔄 Logging in to Angel One for sector mapping...")
        totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
        obj = SmartConnect(api_key=ANGEL_API_KEY)
        response = obj.generateSession(
            clientCode=ANGEL_CLIENT_ID,
            password=ANGEL_PASSWORD,
            totp=totp
        )

        if response and response.get('status') == True:
            logger.info("✅ Angel One Login Successful!")
            instrument_mgr = InstrumentManager(obj)
            if instrument_mgr.load_master_contract():
                sector_map = load_sectors_from_scrip_master(instrument_mgr)
                logger.info(f"✅ Sector map loaded: {len(sector_map)} symbols")
        else:
            logger.warning("⚠️ Angel One login failed. Using fallback sector map.")
    except Exception as e:
        logger.warning(f"⚠️ Angel One login error: {e}. Using fallback sector map.")
else:
    logger.info("ℹ️ Angel One credentials not provided. Using fallback sector map.")

# ========== UNIVERSE ==========
logger.info("🌐 Building trading universe...")
if instrument_mgr is not None:
    universe = StockUniverse(instrument_mgr)
    all_stocks = universe.load_all_stocks()
    liquid_stocks = universe.filter_liquid_stocks()
else:
    # Fallback universe without Angel One
    universe = StockUniverse(None)
    all_stocks = []
    liquid_stocks = []

logger.info(f"   Total NSE -EQ stocks: {len(all_stocks)}")
logger.info(f"   Liquid stocks: {len(liquid_stocks)}")

# ========== SCAN MODE ==========
SCAN_MODE = os.getenv("SCAN_MODE", "FAST").upper()
VALID_MODES = ["FAST", "MEDIUM", "FULL"]
if SCAN_MODE not in VALID_MODES:
    logger.warning(f"⚠️ Invalid SCAN_MODE='{SCAN_MODE}'. Using 'FAST'.")
    SCAN_MODE = "FAST"

if SCAN_MODE == "FULL":
    symbols_to_scan = all_stocks if all_stocks else liquid_stocks
    logger.info(f"🔴 FULL SCAN: {len(symbols_to_scan)} stocks (may take 1-2 hours)")
elif SCAN_MODE == "MEDIUM":
    symbols_to_scan = all_stocks[:500] if len(all_stocks) > 500 else all_stocks
    symbols_to_scan = symbols_to_scan if symbols_to_scan else liquid_stocks[:500]
    logger.info(f"🟡 MEDIUM SCAN: {len(symbols_to_scan)} stocks (may take 15-30 minutes)")
else:  # FAST
    symbols_to_scan = liquid_stocks if liquid_stocks else all_stocks[:100]
    logger.info(f"🟢 FAST SCAN: {len(symbols_to_scan)} liquid stocks (takes 2-3 minutes)")

logger.info(f"   Scanning {len(symbols_to_scan)} stocks")

if not symbols_to_scan:
    logger.error("❌ No stocks to scan. Please check universe configuration.")
    sys.exit(1)

# ========== FETCH DATA (YAHOO FINANCE) ==========
logger.info("=" * 60)
logger.info("📊 STAGE 1: DATA FETCH (Yahoo Finance)")
logger.info("=" * 60)

fetcher = BatchFetcher(obj, instrument_mgr)

cache_info = fetcher.get_cache_info()
logger.info(f"   Cache: {cache_info['total_symbols']} symbols, {cache_info['total_rows']} rows")

logger.info(f"📊 Fetching data for {len(symbols_to_scan)} stocks from Yahoo Finance...")

try:
    data_dict = fetcher.fetch_batch(
        symbols_to_scan,
        days=250,  # ~1 year of daily data
        interval="1d",
        parallel=False  # Sequential to avoid rate limits
    )
except Exception as e:
    logger.error(f"❌ Data fetch error: {e}")
    sys.exit(1)

logger.info(f"✅ Data fetched for {len(data_dict)} stocks")
logger.info(f"   Failed: {fetcher.failed_count} stocks")

if not data_dict:
    logger.error("❌ No data fetched. Exiting.")
    sys.exit(1)

# ========== BUILD DATAFRAME ==========
logger.info("📊 Building close price DataFrame...")
close_data = pd.DataFrame()
for symbol, df in data_dict.items():
    close_data[symbol] = df.set_index('timestamp')['close']

logger.info(f"   Before dropna: {len(close_data)} rows, {len(close_data.columns)} stocks")

close_data = close_data.dropna()

logger.info(f"   After dropna: {len(close_data)} rows, {len(close_data.columns)} stocks")

if len(close_data.columns) < 5:
    logger.error(f"❌ Only {len(close_data.columns)} stocks available. Minimum 5 required.")
    sys.exit(1)

# ========== PAIR SELECTION ==========
logger.info("=" * 60)
logger.info("📊 STAGE 2: PAIR SELECTION")
logger.info("=" * 60)

try:
    engine = PairEngineV7(
        data=close_data,
        sector_map=sector_map,
        interval="ONE_DAY"
    )
    results = engine.scan_pairs()
except Exception as e:
    logger.error(f"❌ PairEngine error: {e}")
    sys.exit(1)

# Display statistics
engine.display_stats()

# Display results
engine.display_debug_report(n=20)
engine.display_results(n=20)

# ========== SAVE RESULTS WITH TIMESTAMP ==========
try:
    os.makedirs("output", exist_ok=True)
except Exception as e:
    logger.error(f"❌ Failed to create output directory: {e}")
    sys.exit(1)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

top_pairs = engine.get_top_pairs(n=30)
if top_pairs:
    try:
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

        df_pairs.to_csv(f'output/selected_pairs_{timestamp}.csv', index=False)
        logger.info(f"📁 Saved {len(top_pairs)} selected pairs to 'output/selected_pairs_{timestamp}.csv'")
    except Exception as e:
        logger.error(f"❌ Failed to save selected pairs: {e}")
else:
    logger.warning("❌ No pairs selected. Check debug report.")

# Save rejection statistics
rejected_pairs = engine.get_rejected_pairs(n=100)
if rejected_pairs:
    try:
        df_rejected = pd.DataFrame([{
            'pair1': r['pair'][0],
            'pair2': r['pair'][1],
            'reason': r['reject_reason'][0] if r['reject_reason'] else 'Unknown'
        } for r in rejected_pairs])

        df_rejected.to_csv(f'output/rejected_pairs_{timestamp}.csv', index=False)
        logger.info(f"📁 Saved {len(rejected_pairs)} rejected pairs to 'output/rejected_pairs_{timestamp}.csv'")
    except Exception as e:
        logger.error(f"❌ Failed to save rejected pairs: {e}")

# Save debug report
if engine.debug_log:
    try:
        df_debug = pd.DataFrame([{
            'pair1': r['pair'][0],
            'pair2': r['pair'][1],
            'valid': r['valid'],
            'correlation': r['metrics'].get('correlation', 0),
            'rolling_corr': r['metrics'].get('rolling_corr', 0),
            'coint_pval': r['metrics'].get('coint_pval', 1),
            'beta': r['metrics'].get('beta', 0),
            'hurst': r['metrics'].get('hurst', 0.5),
            'half_life': r['metrics'].get('half_life', 999),
            'score': r['metrics'].get('score', 0),
            'reject_reason': r['reject_reason'][0] if r['reject_reason'] else 'None'
        } for r in engine.debug_log])

        df_debug.to_csv(f'output/debug_report_{timestamp}.csv', index=False)
        logger.info(f"📁 Saved debug report to 'output/debug_report_{timestamp}.csv'")
    except Exception as e:
        logger.error(f"❌ Failed to save debug report: {e}")

# ========== RESET STATUS AFTER SUCCESSFUL SCAN ==========
try:
    fetcher.reset_status()
    logger.info("✅ Status file reset for next scan")
except Exception as e:
    logger.warning(f"⚠️ Could not reset status file: {e}")

# ========== SUMMARY ==========
logger.info("=" * 60)
logger.info("📊 SCAN SUMMARY")
logger.info("=" * 60)
logger.info(f"  Data source: Yahoo Finance")
logger.info(f"  Total stocks in universe: {len(all_stocks)}")
logger.info(f"  Stocks scanned: {len(symbols_to_scan)}")
logger.info(f"  Data fetched: {len(data_dict)} stocks")
logger.info(f"  Pairs selected: {len(top_pairs)}")
logger.info(f"  Scan mode: {SCAN_MODE}")
logger.info(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info("=" * 60)
logger.info("✅ Scanner Complete!")