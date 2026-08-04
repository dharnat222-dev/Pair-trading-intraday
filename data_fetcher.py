"""
data_fetcher.py - Historical OHLC Data Fetcher
"""

import pandas as pd
import datetime
import time
from typing import List, Optional, Dict, Any

class AngelDataFetcher:
    def __init__(self, smartconnect_obj: Any):
        self.obj = smartconnect_obj
        self.max_retries = 3
        self.retry_delay = 1
    
    def fetch(self, symbol: str, interval: str = "ONE_MINUTE", days: int = 5) -> Optional[pd.DataFrame]:
        from_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        for attempt in range(self.max_retries):
            try:
                # 🔧 FIX: Positional arguments: exchange, symbol, interval, fromdate, todate
                resp = self.obj.getCandleData(
                    "NSE",      # exchange
                    symbol,     # symbol
                    interval,   # interval
                    from_date,  # fromdate
                    to_date     # todate
                )
                
                if resp and resp.get('status') == True and resp.get('data'):
                    cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    df = pd.DataFrame(resp['data'], columns=cols)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    return df
                    
                time.sleep(self.retry_delay)
                
            except Exception as e:
                print(f"⚠️ {symbol} attempt {attempt+1}: {e}")
                time.sleep(self.retry_delay)
        
        return None
    
    def fetch_multiple(self, symbols: List[str], interval: str = "ONE_MINUTE", days: int = 5) -> Dict[str, pd.DataFrame]:
        results = {}
        for symbol in symbols:
            print(f"  Fetching {symbol}...")
            df = self.fetch(symbol, interval, days)
            if df is not None:
                results[symbol] = df
                print(f"    ✅ {symbol}: {len(df)} rows")
            else:
                print(f"    ❌ {symbol}: No data")
        return results
    
    def fetch_close_prices(self, symbols: List[str], interval: str = "ONE_MINUTE", days: int = 5) -> pd.DataFrame:
        data_dict = self.fetch_multiple(symbols, interval, days)
        
        if not data_dict:
            return pd.DataFrame()
        
        close_data = pd.DataFrame()
        for symbol, df in data_dict.items():
            close_data[symbol] = df.set_index('timestamp')['close']
        
        return close_data.dropna()