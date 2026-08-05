"""
batch_fetcher.py - Batch Data Fetcher with Cache and Rate Limit Handling
"""

import pandas as pd
import datetime
import time
import sqlite3
import os
from typing import List, Optional, Dict

class BatchFetcher:
    def __init__(self, smartconnect_obj, instrument_manager):
        self.obj = smartconnect_obj
        self.instrument = instrument_manager
        self.max_retries = 5
        self.retry_delay = 2
        self.db_path = "data/nse_ohlvc.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for caching"""
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
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
        conn.commit()
        conn.close()
    
    def fetch_batch(self, symbols: List[str], days: int = 250) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for a batch of symbols with rate limit handling
        """
        results = {}
        total = len(symbols)
        
        for i, symbol in enumerate(symbols):
            print(f"  [{i+1}/{total}] Fetching {symbol}...", end=" ")
            
            df = self.fetch_with_cache(symbol, days)
            if df is not None:
                results[symbol] = df
                print(f"✅ {len(df)} rows")
            else:
                print("❌ Failed")
            
            # Rate limit protection
            time.sleep(0.5)  # 500ms delay between requests
        
        return results
    
    def fetch_with_cache(self, symbol: str, days: int = 250) -> Optional[pd.DataFrame]:
        """
        Fetch data with cache check
        """
        # Check cache first
        cached = self._get_from_cache(symbol)
        if cached is not None:
            return cached
        
        # Fetch from API
        for attempt in range(self.max_retries):
            try:
                df = self._fetch_from_api(symbol, days)
                if df is not None:
                    self._save_to_cache(symbol, df)
                    return df
                
                # Rate limit - wait longer
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"(retry {attempt+1}/{self.max_retries} in {wait_time}s)", end=" ")
                    time.sleep(wait_time)
                    
            except Exception as e:
                print(f"Error: {e}", end=" ")
                time.sleep(self.retry_delay)
        
        return None
    
    def _fetch_from_api(self, symbol: str, days: int = 250) -> Optional[pd.DataFrame]:
        """Fetch from Angel One API"""
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
        
        resp = self.obj.getCandleData(params)
        
        if resp and resp.get('status') == True and resp.get('data'):
            cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            df = pd.DataFrame(resp['data'], columns=cols)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        
        return None
    
    def _get_from_cache(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get data from SQLite cache"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = f"SELECT * FROM daily_ohlcv WHERE symbol='{symbol}' ORDER BY timestamp"
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
        except:
            pass
        return None
    
    def _save_to_cache(self, symbol: str, df: pd.DataFrame):
        """Save data to SQLite cache"""
        try:
            df['symbol'] = symbol
            conn = sqlite3.connect(self.db_path)
            df.to_sql('daily_ohlcv', conn, if_exists='append', index=False)
            conn.close()
        except:
            pass