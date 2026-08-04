"""
data_fetcher.py - Historical OHLC Data Fetcher with Correct Date Format
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
        """
        Fetch historical OHLC data for a symbol using token
        """
        # Get token for symbol
        token = self.instrument.get_token(symbol)
        if not token:
            print(f"❌ Token not found for {symbol}")
            return None
        
        # 🔧 FIX 1: Include Time in Date Format
        today = datetime.datetime.now()
        
        # Get market open time (9:15 AM)
        from_date = (today - datetime.timedelta(days=days)).strftime("%Y-%m-%d 09:15")
        to_date = today.strftime("%Y-%m-%d 15:30")
        
        # 🔧 FIX 2: If today is weekend, adjust to last trading day
        if today.weekday() >= 5:  # Saturday = 5, Sunday = 6
            # Go back to Friday
            friday = today - datetime.timedelta(days=(today.weekday() - 4))
            to_date = friday.strftime("%Y-%m-%d 15:30")
            from_date = (friday - datetime.timedelta(days=days)).strftime("%Y-%m-%d 09:15")
        
        print(f"\n📤 Request Debug for {symbol}:")
        print(f"  Token: {token}")
        print(f"  Interval: {interval}")
        print(f"  From: {from_date}")
        print(f"  To: {to_date}")
        
        for attempt in range(self.max_retries):
            try:
                # 🔧 FIX 3: Try both formats
                # Format A: Dictionary with date-time
                params = {
                    "exchange": "NSE",
                    "symboltoken": token,
                    "interval": interval,
                    "fromdate": from_date,
                    "todate": to_date
                }
                print(f"  Params: {params}")
                
                # 🔧 FIX 4: Try getCandleData with params
                try:
                    resp = self.obj.getCandleData(params)
                except TypeError:
                    # If TypeError, try without exchange
                    params.pop("exchange", None)
                    resp = self.obj.getCandleData(params)
                
                print(f"  Response type: {type(resp)}")
                print(f"  Response: {str(resp)[:300] if resp else 'None'}")
                
                if resp and resp.get('status') == True and resp.get('data'):
                    cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    df = pd.DataFrame(resp['data'], columns=cols)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    print(f"✅ {symbol}: {len(df)} rows fetched")
                    return df
                else:
                    print(f"⚠️ {symbol}: Response status: {resp.get('status') if resp else 'None'}")
                    print(f"  Message: {resp.get('message') if resp else 'No response'}")
                    
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
                print(f"  ✅ {symbol}: {len(df)} rows")
            else:
                print(f"  ❌ {symbol}: No data")
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