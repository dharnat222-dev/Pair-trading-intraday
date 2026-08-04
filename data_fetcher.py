"""
src/data_fetcher.py
Historical OHLC Data Fetcher from Angel One
"""

import pandas as pd
import datetime
import time
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

class AngelDataFetcher:
    """Fetch historical OHLC data from Angel One API"""
    
    def __init__(self, smartconnect_obj: Any):
        """
        Initialize with SmartConnect object
        
        Args:
            smartconnect_obj: Logged-in SmartConnect instance
        """
        self.obj = smartconnect_obj
        self.default_interval = "ONE_MINUTE"
        self.default_days = 5
        self.max_retries = 3
        self.retry_delay = 1
        self.exchange = "NSE"
    
    def fetch(self, symbol: str, interval: str = "ONE_MINUTE", days: int = 5) -> Optional[pd.DataFrame]:
        """
        Fetch historical OHLC data for a single symbol
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        from_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        for attempt in range(self.max_retries):
            try:
                resp = self.obj.getCandleData(
                    exchange=self.exchange,
                    symbol=symbol,
                    interval=interval,
                    fromdate=from_date,
                    todate=to_date
                )
                
                if resp and resp.get('status') == True and resp.get('data'):
                    cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    df = pd.DataFrame(resp['data'], columns=cols)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    return df
                    
                time.sleep(self.retry_delay)
                
            except Exception as e:
                logger.warning(f"⚠️ {symbol} attempt {attempt+1}: {e}")
                time.sleep(self.retry_delay)
        
        return None
    
    def fetch_multiple(self, symbols: List[str], interval: str = "ONE_MINUTE", days: int = 5) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols"""
        results = {}
        for symbol in symbols:
            df = self.fetch(symbol, interval, days)
            if df is not None:
                results[symbol] = df
        return results
    
    def fetch_close_prices(self, symbols: List[str], interval: str = "ONE_MINUTE", days: int = 5) -> pd.DataFrame:
        """Fetch and combine close prices for multiple symbols"""
        data_dict = self.fetch_multiple(symbols, interval, days)
        
        if not data_dict:
            return pd.DataFrame()
        
        close_data = pd.DataFrame()
        for symbol, df in data_dict.items():
            close_data[symbol] = df.set_index('timestamp')['close']
        
        return close_data.dropna()