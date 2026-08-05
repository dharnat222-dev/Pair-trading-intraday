"""
batch_fetcher.py - Batch Data Fetcher using Yahoo Finance
Historical data only. Angel One kept for login/live trading.
"""

import pandas as pd
import datetime
import time
import sqlite3
import os
import json
import logging
import gc
from typing import List, Optional, Dict, Any
import yfinance as yf

logger = logging.getLogger(__name__)


class BatchFetcher:
    def __init__(self, smartconnect_obj=None, instrument_manager=None):
        """
        Initialize with optional SmartConnect object for Angel One compatibility
        Yahoo Finance does not require login, but we keep the same interface.
        
        Args:
            smartconnect_obj: Optional SmartConnect object (for Angel One compatibility)
            instrument_manager: Optional InstrumentManager (for symbol token mapping)
        """
        self.obj = smartconnect_obj
        self.instrument = instrument_manager
        self.max_retries = 3
        self.base_delay = 1
        self.max_delay = 30
        self.db_path = "data/nse_ohlcv.db"
        self.status_file = "data/fetch_status.json"
        self.fetched_count = 0
        self.failed_count = 0
        self.failed_symbols = []
        self.fetched_symbols = []
        self.max_workers = 5  # Parallel downloads for Yahoo Finance
        self._init_db()
        
        # Yahoo Finance session for batch downloads
        self.yf_session = None
        
        # NSE symbols mapping cache
        self._symbol_cache = {}

    def _init_db(self):
        """Initialize SQLite database for caching"""
        try:
            os.makedirs("data", exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''
                    CREATE TABLE IF NOT EXISTS daily_ohlcv (
                        symbol TEXT,
                        timestamp TEXT,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume INTEGER,
                        PRIMARY KEY (symbol, timestamp)
                    )
                ''')
                c.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON daily_ohlcv(symbol)')
                conn.commit()
            logger.info(f"✅ Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Database init error: {e}")

    def _load_status(self) -> Dict:
        """Load fetch status from file for resuming"""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Status file corrupt: {e}. Starting fresh.")
                try:
                    import shutil
                    shutil.copy(self.status_file, f"{self.status_file}.corrupted")
                except Exception:
                    pass
                return {'completed': [], 'failed': [], 'delisted': [], 'last_index': 0}
            except Exception as e:
                logger.warning(f"⚠️ Status file read error: {e}. Starting fresh.")
                return {'completed': [], 'failed': [], 'delisted': [], 'last_index': 0}
        return {'completed': [], 'failed': [], 'delisted': [], 'last_index': 0}

    def _save_status(self, status: Dict):
        """Save fetch status to file"""
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f)
        except Exception as e:
            logger.warning(f"⚠️ Could not save status: {e}")

    def _reset_status(self):
        """Reset status file after successful full scan"""
        try:
            if os.path.exists(self.status_file):
                os.remove(self.status_file)
                logger.info("✅ Status file reset for next scan")
        except Exception as e:
            logger.warning(f"⚠️ Could not reset status file: {e}")

    def reset_status(self):
        """Public method to reset fetch status"""
        self._reset_status()

    def _load_from_cache(self, symbol: str) -> Optional[pd.DataFrame]:
        """Load cached OHLC data for a symbol from SQLite"""
        try:
            query = "SELECT * FROM daily_ohlcv WHERE symbol = ? ORDER BY timestamp"
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn, params=(symbol,))
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e):
                time.sleep(0.5)
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        df = pd.read_sql_query(query, conn, params=(symbol,))
                    if not df.empty:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        return df
                except Exception:
                    pass
            logger.debug(f"Cache read error for {symbol}: {e}")
        except Exception as e:
            logger.debug(f"Cache read error for {symbol}: {e}")
        return None

    def _symbol_to_yahoo(self, symbol: str) -> str:
        """Convert NSE symbol to Yahoo Finance format"""
        # Remove -EQ suffix if present
        clean_symbol = symbol.replace('-EQ', '').strip()
        
        # Check cache
        if clean_symbol in self._symbol_cache:
            return self._symbol_cache[clean_symbol]
        
        # Special cases
        if clean_symbol == "M_M":
            clean_symbol = "M&M"
        
        # Add .NS suffix for NSE stocks
        yahoo_symbol = f"{clean_symbol}.NS"
        self._symbol_cache[clean_symbol] = yahoo_symbol
        
        return yahoo_symbol

    def _fetch_single_yahoo(self, symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
        """
        Fetch a single symbol from Yahoo Finance with retry
        """
        yahoo_symbol = self._symbol_to_yahoo(symbol)

        for attempt in range(self.max_retries):
            try:
                ticker = yf.Ticker(yahoo_symbol)
                df = ticker.history(period=period, interval=interval)
                df = df.tz_localize(None)  # Remove timezone for consistency

                if df.empty:
                    # Try without .NS suffix (some stocks like M_M)
                    if yahoo_symbol.endswith('.NS'):
                        alt_symbol = yahoo_symbol[:-3]
                        ticker = yf.Ticker(alt_symbol)
                        df = ticker.history(period=period, interval=interval)
                        df = df.tz_localize(None)
                
                if df.empty:
                    logger.debug(f"⚠️ No data for {symbol} ({yahoo_symbol})")
                    return None

                # Reset index to get date as column
                df = df.reset_index()
                df = df.rename(columns={
                    'Date': 'timestamp',
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                })

                # Keep only needed columns
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                df['timestamp'] = pd.to_datetime(df['timestamp'])

                return df

            except Exception as e:
                logger.debug(f"⚠️ {symbol} attempt {attempt+1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_delay * (attempt + 1))

        return None

    def _save_to_cache(self, symbol: str, df: pd.DataFrame):
        """Save data to SQLite cache"""
        try:
            df_copy = df.copy()
            df_copy['symbol'] = symbol

            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM daily_ohlcv WHERE symbol = ?", (symbol,))
                conn.commit()
                df_copy.to_sql('daily_ohlcv', conn, if_exists='append', index=False)
        except Exception as e:
            logger.debug(f"Cache write error for {symbol}: {e}")

    def _validate_ohlcv_data(self, df: pd.DataFrame) -> bool:
        """Validate OHLC data quality"""
        if df.empty:
            return False

        if len(df) < 10:
            return False

        if (df['close'] <= 0).any():
            logger.warning("⚠️ Negative or zero prices found")
            return False

        if (df['close'] > 100000).any():
            logger.warning("⚠️ Unrealistic high prices found")
            return False

        if df.isna().any().any():
            logger.warning("⚠️ NaN values found in data")
            return False

        if (df['high'] < df['low']).any():
            logger.warning("⚠️ High < Low found")
            return False

        if (df['volume'] < 0).any():
            logger.warning("⚠️ Negative volume found")
            return False

        return True

    def fetch_batch(self, symbols: List[str], days: int = 250, interval: str = "1d",
                    show_progress: bool = True, parallel: bool = False) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for a batch of symbols from Yahoo Finance

        Args:
            symbols: List of stock symbols (with -EQ suffix)
            days: Number of days to fetch (default: 250, ~1 year)
            interval: Yahoo Finance interval (default: "1d")
            show_progress: Print progress messages
            parallel: Use multithreading (default: False to avoid rate limits)

        Returns:
            Dictionary of {symbol: DataFrame}
        """
        # Yahoo Finance uses period, not days
        if days <= 30:
            period = "1mo"
        elif days <= 60:
            period = "2mo"
        elif days <= 90:
            period = "3mo"
        elif days <= 120:
            period = "4mo"
        elif days <= 180:
            period = "6mo"
        elif days <= 365:
            period = "1y"
        else:
            period = "2y"
        
        results = {}
        total = len(symbols)
        self.fetched_count = 0
        self.failed_count = 0
        self.failed_symbols = []
        self.fetched_symbols = []

        # Load previous status
        status = self._load_status()
        completed_symbols = set(status.get('completed', []))
        failed_previous = set(status.get('failed', []))
        delisted_symbols = set(status.get('delisted', []))

        # Filter out delisted symbols
        symbols_to_fetch = [s for s in symbols if s not in delisted_symbols]

        logger.info(f"📊 Yahoo Finance fetching for {len(symbols_to_fetch)} stocks...")
        logger.info(f"   Period: {period}, Interval: {interval}")
        logger.info(f"   Resume: {len(completed_symbols)} already in cache")
        logger.info(f"   Previously failed: {len(failed_previous)}")
        logger.info(f"   Delisted: {len(delisted_symbols)}")

        # Load completed from cache
        for symbol in list(completed_symbols):
            cached_df = self._load_from_cache(symbol)
            if cached_df is not None:
                results[symbol] = cached_df
                self.fetched_count += 1
                self.fetched_symbols.append(symbol)

        # Sequential fetching (avoid rate limits)
        for i, symbol in enumerate(symbols_to_fetch):
            if symbol in completed_symbols:
                continue

            if show_progress and i % 10 == 0:
                logger.info(f"  ⏳ Progress: {i+1}/{len(symbols_to_fetch)} (Fetched: {self.fetched_count}, Failed: {self.failed_count})")

            df = self._fetch_with_cache(symbol, period, interval)
            if df is not None:
                results[symbol] = df
                self.fetched_count += 1
                self.fetched_symbols.append(symbol)
                completed_symbols.add(symbol)
            else:
                self.failed_count += 1
                self.failed_symbols.append(symbol)
                failed_previous.add(symbol)

            # Update status every 50 symbols
            if i % 50 == 0:
                status['completed'] = list(completed_symbols)
                status['failed'] = list(failed_previous)
                status['last_index'] = i
                self._save_status(status)

            # Rate limit protection - small delay between requests
            time.sleep(0.2)

        # Final status update
        status['completed'] = list(completed_symbols)
        status['failed'] = list(failed_previous)
        status['delisted'] = list(delisted_symbols)
        self._save_status(status)

        logger.info(f"\n✅ Yahoo fetch complete: {self.fetched_count} stocks fetched, {self.failed_count} failed")
        if self.failed_symbols:
            logger.info(f"   Failed symbols: {self.failed_symbols[:10]}")
            if len(self.failed_symbols) > 10:
                logger.info(f"   ... and {len(self.failed_symbols) - 10} more")

        return results

    def _fetch_with_cache(self, symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
        """
        Fetch data with cache check
        """
        # Check cache first
        cached = self._get_from_cache(symbol)
        if cached is not None:
            if self._validate_ohlcv_data(cached):
                return cached

        # Fetch from Yahoo
        df = self._fetch_single_yahoo(symbol, period, interval)
        if df is not None and self._validate_ohlcv_data(df):
            self._save_to_cache(symbol, df)
            return df

        return None

    def _get_from_cache(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get data from SQLite cache"""
        try:
            query = "SELECT * FROM daily_ohlcv WHERE symbol = ? ORDER BY timestamp"
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn, params=(symbol,))
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
        except Exception as e:
            logger.debug(f"Cache read error for {symbol}: {e}")
        return None

    def get_cached_count(self) -> int:
        """Get number of cached symbols"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(DISTINCT symbol) FROM daily_ohlcv")
                count = c.fetchone()[0]
            return count
        except Exception:
            return 0

    def get_cache_info(self) -> Dict:
        """Get cache statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM daily_ohlcv")
                total_rows = c.fetchone()[0]
                c.execute("SELECT COUNT(DISTINCT symbol) FROM daily_ohlcv")
                total_symbols = c.fetchone()[0]
            return {
                'total_rows': total_rows,
                'total_symbols': total_symbols
            }
        except Exception:
            return {'total_rows': 0, 'total_symbols': 0}