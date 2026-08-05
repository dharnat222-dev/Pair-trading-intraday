"""
batch_fetcher.py - Batch Data Fetcher with Rate Limit, Resume, and Validation
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

logger = logging.getLogger(__name__)


class BatchFetcher:
    def __init__(self, smartconnect_obj, instrument_manager):
        """
        Initialize with SmartConnect object and instrument manager
        """
        self.obj = smartconnect_obj
        self.instrument = instrument_manager
        self.max_retries = 5
        self.base_delay = 1
        self.max_delay = 60
        self.db_path = "data/nse_ohlcv.db"
        self.status_file = "data/fetch_status.json"
        self.fetched_count = 0
        self.failed_count = 0
        self.failed_symbols = []
        self.fetched_symbols = []
        self._init_db()

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
        """
        Load fetch status from file for resuming
        """
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
                return {'completed': [], 'failed': [], 'last_index': 0}
            except Exception as e:
                logger.warning(f"⚠️ Status file read error: {e}. Starting fresh.")
                return {'completed': [], 'failed': [], 'last_index': 0}
        return {'completed': [], 'failed': [], 'last_index': 0}

    def _save_status(self, status: Dict):
        """
        Save fetch status to file
        """
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f)
        except Exception as e:
            logger.warning(f"⚠️ Could not save status: {e}")

    def _reset_status(self):
        """
        Reset status file after successful full scan
        """
        try:
            if os.path.exists(self.status_file):
                os.remove(self.status_file)
                logger.info("✅ Status file reset for next scan")
        except Exception as e:
            logger.warning(f"⚠️ Could not reset status file: {e}")

    def reset_status(self):
        """
        Public method to reset fetch status
        """
        self._reset_status()

    def _load_from_cache(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Load cached OHLC data for a symbol from SQLite
        """
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

    def fetch_batch(self, symbols: List[str], days: int = 250, show_progress: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for a batch of symbols with rate limit handling and resume support
        """
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
        start_index = status.get('last_index', 0)

        # Load previously completed symbols from cache
        for symbol in list(completed_symbols):
            cached_df = self._load_from_cache(symbol)
            if cached_df is not None:
                results[symbol] = cached_df
                self.fetched_count += 1
                self.fetched_symbols.append(symbol)
                logger.debug(f"✅ Loaded {symbol} from cache ({len(cached_df)} rows)")
            else:
                completed_symbols.remove(symbol)
                logger.warning(f"⚠️ Cache missing for {symbol}, will retry")

        logger.info(f"📊 Fetching data for {total} stocks...")
        logger.info(f"   Resume: {len(completed_symbols)} already loaded from cache")
        logger.info(f"   Previously failed: {len(failed_previous)}")
        logger.info(f"   Using cache: {self.db_path}")

        for i, symbol in enumerate(symbols):
            if symbol in completed_symbols and symbol in results:
                continue

            if show_progress and i % 10 == 0:
                logger.info(f"  ⏳ Progress: {i+1}/{total} (Fetched: {self.fetched_count}, Failed: {self.failed_count})")

            df = self.fetch_with_cache(symbol, days)
            if df is not None:
                results[symbol] = df
                self.fetched_count += 1
                self.fetched_symbols.append(symbol)
                completed_symbols.add(symbol)
                if symbol in failed_previous:
                    failed_previous.remove(symbol)
            else:
                self.failed_count += 1
                self.failed_symbols.append(symbol)
                failed_previous.add(symbol)

            if i % 50 == 0:
                status['completed'] = list(completed_symbols)
                status['failed'] = list(failed_previous)
                status['last_index'] = i
                self._save_status(status)

            time.sleep(self._calculate_delay(i))

        status['completed'] = list(completed_symbols)
        status['failed'] = list(failed_previous)
        status['last_index'] = total
        self._save_status(status)

        logger.info(f"\n✅ Fetch complete: {self.fetched_count} stocks fetched, {self.failed_count} failed")
        if self.failed_symbols:
            logger.info(f"   Failed symbols: {self.failed_symbols[:10]}")
            if len(self.failed_symbols) > 10:
                logger.info(f"   ... and {len(self.failed_symbols) - 10} more")

        return results

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay with exponential backoff and jitter
        """
        if attempt < 10:
            return 0.3
        elif attempt < 50:
            return 0.5
        elif attempt < 100:
            return 0.8
        elif attempt < 200:
            return 1.0
        else:
            return 1.5

    def fetch_with_cache(self, symbol: str, days: int = 250) -> Optional[pd.DataFrame]:
        """
        Fetch data with cache check, exponential backoff, and data validation
        """
        cached = self._get_from_cache(symbol)
        if cached is not None:
            if self._validate_ohlcv_data(cached):
                return cached
            else:
                logger.warning(f"⚠️ Cached data for {symbol} is invalid, refetching...")

        for attempt in range(self.max_retries):
            try:
                df = self._fetch_from_api(symbol, days)
                if df is not None and self._validate_ohlcv_data(df):
                    self._save_to_cache(symbol, df)
                    return df

                wait_time = min(self.base_delay * (2 ** attempt), self.max_delay)
                if attempt < self.max_retries - 1:
                    time.sleep(wait_time)

            except Exception as e:
                logger.debug(f"⚠️ {symbol} attempt {attempt+1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_delay * (attempt + 1))

        return None

    def _validate_ohlcv_data(self, df: pd.DataFrame) -> bool:
        """
        Validate OHLC data quality before using it
        """
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

    def _fetch_from_api(self, symbol: str, days: int = 250) -> Optional[pd.DataFrame]:
        """
        Fetch from Angel One API with rate limit detection
        """
        token = self.instrument.get_token_fast(symbol)
        if not token:
            return None

        from_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d 09:15")
        to_date = datetime.datetime.now().strftime("%Y-%m-%d 15:30")

        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": "ONE_DAY",
            "fromdate": from_date,
            "todate": to_date
        }

        try:
            resp = self.obj.getCandleData(params)

            if resp and isinstance(resp, dict):
                msg = resp.get('message', '')
                if msg == 'Access denied because of exceeding access rate':
                    logger.warning(f"⚠️ Rate limit hit for {symbol}")
                    return None
                if resp.get('status') is False and 'rate' in str(msg).lower():
                    logger.warning(f"⚠️ Rate limit hit for {symbol}")
                    return None

            if resp and resp.get('status') is True and resp.get('data'):
                cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                df = pd.DataFrame(resp['data'], columns=cols)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df

            return None

        except Exception as e:
            error_msg = str(e).lower()
            if 'rate' in error_msg or 'access' in error_msg:
                logger.warning(f"⚠️ Rate limit hit for {symbol}")
            else:
                logger.debug(f"API error for {symbol}: {e}")
            return None

    def _get_from_cache(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get data from SQLite cache
        """
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

    def _save_to_cache(self, symbol: str, df: pd.DataFrame):
        """
        Save data to SQLite cache
        """
        try:
            # Create a copy to avoid modifying the original DataFrame
            df_copy = df.copy()
            df_copy['symbol'] = symbol
            
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM daily_ohlcv WHERE symbol = ?", (symbol,))
                conn.commit()
                df_copy.to_sql('daily_ohlcv', conn, if_exists='append', index=False)
        except Exception as e:
            logger.debug(f"Cache write error for {symbol}: {e}")

    def get_cached_count(self) -> int:
        """
        Get number of cached symbols
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(DISTINCT symbol) FROM daily_ohlcv")
                count = c.fetchone()[0]
            return count
        except Exception:
            return 0

    def get_cache_info(self) -> Dict:
        """
        Get cache statistics
        """
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