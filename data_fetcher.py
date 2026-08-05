"""
data_fetcher.py - Historical OHLC Data Fetcher
"""

import pandas as pd
import datetime
import time
from typing import List, Optional, Dict, Any

class AngelDataFetcher:
    def __init__(self, smartconnect_obj: Any, instrument_manager: Any):
        self.obj = smartconnect_obj
        self.instrument = instrument_manager
        self.max_retries = 3
        self.retry_delay = 1
    
    def fetch(self, symbol: str, interval: str = "ONE_MINUTE", days: int = 5) -> Optional[pd.DataFrame]:
        """Fetch historical OHLC data for a symbol"""
        token = self.instrument.get_token(symbol)
        if not token:
            print(f"❌ Token not found for {symbol}")
            return None
        
        from_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d 09:15")
        to_date = datetime.datetime.now().strftime("%Y-%m-%d 15:30")
        
        # Weekend adjustment
        today = datetime.datetime.now()
        if today.weekday() >= 5:
            friday = today - datetime.timedelta(days=(today.weekday() - 4))
            to_date = friday.strftime("%Y-%m-%d 15:30")
            from_date = (friday - datetime.timedelta(days=days)).strftime("%Y-%m-%d 09:15")
        
        for attempt in range(self.max_retries):
            try:
                params = {
                    "exchange": "NSE",
                    "symboltoken": token,
                    "interval": interval,
                    "fromdate": from_date,
                    "todate": to_date
                }
                
                resp = self.obj.getCandleData(params)
                
                if resp and resp.get('status') == True and resp.get('data'):
                    cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    df = pd.DataFrame(resp['data'], columns=cols)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                    # 🔍 DEBUG: Show data shape
                    print(f"  ✅ {symbol}: {len(df)} rows")
                    return df
                    
                time.sleep(self.retry_delay)
                
            except Exception as e:
                print(f"⚠️ {symbol} attempt {attempt+1}: {e}")
                time.sleep(self.retry_delay)
        
        print(f"❌ {symbol}: Failed after {self.max_retries} attempts")
        return None
    
    def fetch_multiple(self, symbols: List[str], interval: str = "ONE_MINUTE", days: int = 5) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols"""
        results = {}
        for symbol in symbols:
            print(f"\n📊 Fetching {symbol}...")
            df = self.fetch(symbol, interval, days)
            if df is not None:
                results[symbol] = df
            else:
                print(f"  ❌ {symbol}: No data")
        return results
    
    def fetch_close_prices(self, symbols: List[str], interval: str = "ONE_MINUTE", days: int = 5) -> pd.DataFrame:
        """
        Fetch and combine close prices for multiple symbols
        """
        data_dict = self.fetch_multiple(symbols, interval, days)
        
        if not data_dict:
            print("❌ No data fetched for any symbol")
            return pd.DataFrame()
        
        # 🔍 DEBUG: Show fetched data
        print(f"\n🔍 Fetched {len(data_dict)} symbols")
        for sym, df in data_dict.items():
            print(f"  {sym}: {len(df)} rows, {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        # Combine close prices
        close_data = pd.DataFrame()
        for symbol, df in data_dict.items():
            # Set timestamp as index and extract close
            df_indexed = df.set_index('timestamp')
            close_data[symbol] = df_indexed['close']
        
        # 🔍 DEBUG: Before dropna
        print(f"\n🔍 Before dropna: {len(close_data)} rows, {len(close_data.columns)} columns")
        
        # Drop rows with any NaN values
        close_data = close_data.dropna()
        
        # 🔍 DEBUG: After dropna
        print(f"🔍 After dropna: {len(close_data)} rows, {len(close_data.columns)} columns")
        
        # 🔍 DEBUG: Show date range
        if not close_data.empty:
            print(f"🔍 Date range: {close_data.index.min()} to {close_data.index.max()}")
            print(f"🔍 Sample data:\n{close_data.head()}")
        
        # 🔍 CRITICAL: If only 5 rows, check what's happening
        if len(close_data) < 20:
            print(f"\n⚠️ WARNING: Only {len(close_data)} rows after dropna!")
            print("   Checking for NaN counts per symbol:")
            for col in close_data.columns:
                nan_count = close_data[col].isna().sum()
                if nan_count > 0:
                    print(f"     {col}: {nan_count} NaN values")
            
            # Try filling NaN with forward fill
            print("   Attempting forward fill...")
            close_data = close_data.ffill().dropna()
            print(f"   After ffill: {len(close_data)} rows")
        
        return close_data