"""
data_fetcher.py - Historical Data Fetcher from Angel One
Phase 1: Fetch OHLC data without database caching
"""

import pandas as pd
import datetime
import time
import logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

class DataFetcher:
    """
    Fetch historical OHLC data from Angel One API
    Supports multiple stocks, error handling, retry logic
    """
    
    def __init__(self, broker):
        """
        Initialize with Angel Broker instance
        
        Args:
            broker: AngelBroker instance (already logged in)
        """
        self.broker = broker
        self.default_interval = "ONE_MINUTE"
        self.default_days = 5
        self.max_retries = 3
        self.retry_delay = 2  # seconds
    
    def get_historical_data(
        self, 
        symbol: str, 
        interval: str = "ONE_MINUTE",
        days: int = 5
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical OHLC data for a single symbol
        
        Args:
            symbol: Stock symbol (e.g., "RELIANCE")
            interval: "ONE_MINUTE", "FIVE_MINUTE", "ONE_DAY"
            days: Number of days to fetch (default: 5)
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
            Returns None if fetch fails
        """
        if not self.broker.is_logged_in:
            logger.error("❌ Not logged in to Angel One")
            return None
        
        from_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"📊 Fetching {symbol} ({interval})...")
                
                response = self.broker.obj.getCandleData(
                    exchange="NSE",
                    symbol=symbol,
                    interval=interval,
                    fromdate=from_date,
                    todate=to_date
                )
                
                if response and response.get('status') == True and response.get('data'):
                    cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    df = pd.DataFrame(response['data'], columns=cols)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                    logger.info(f"✅ {symbol}: {len(df)} candles fetched")
                    return df
                else:
                    logger.warning(f"⚠️ {symbol}: No data (attempt {attempt+1}/{self.max_retries})")
                    
            except Exception as e:
                logger.warning(f"⚠️ {symbol}: Error (attempt {attempt+1}): {e}")
                time.sleep(self.retry_delay)
        
        logger.error(f"❌ {symbol}: Failed after {self.max_retries} attempts")
        return None
    
    def fetch_multiple(
        self, 
        symbols: List[str], 
        interval: str = "ONE_MINUTE",
        days: int = 5,
        show_progress: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple symbols
        
        Args:
            symbols: List of stock symbols
            interval: Candle interval
            days: Number of days
            show_progress: Print progress messages
        
        Returns:
            Dictionary {symbol: DataFrame}
        """
        results = {}
        total = len(symbols)
        
        for i, symbol in enumerate(symbols):
            if show_progress:
                print(f"  [{i+1}/{total}] Fetching {symbol}...")
            
            df = self.get_historical_data(symbol, interval, days)
            if df is not None and not df.empty:
                results[symbol] = df
            
            # Small delay between requests to avoid rate limiting
            time.sleep(0.5)
        
        return results
    
    def get_combined_close_data(
        self, 
        symbols: List[str], 
        interval: str = "ONE_MINUTE",
        days: int = 5
    ) -> pd.DataFrame:
        """
        Fetch and combine close prices for all symbols
        
        Returns:
            DataFrame with columns = symbols, index = timestamp
            Rows aligned by timestamp
        """
        data_dict = self.fetch_multiple(symbols, interval, days)
        
        if not data_dict:
            logger.warning("❌ No data fetched for any symbol")
            return pd.DataFrame()
        
        # Extract close prices from each DataFrame
        close_data = pd.DataFrame()
        for symbol, df in data_dict.items():
            if 'close' in df.columns:
                close_data[symbol] = df.set_index('timestamp')['close']
        
        # Drop rows with any NaN values
        close_data = close_data.dropna()
        
        logger.info(f"✅ Combined data: {len(close_data.columns)} stocks, {len(close_data)} rows")
        return close_data
    
    def validate_data(self, df: pd.DataFrame, min_rows: int = 10) -> bool:
        """
        Validate that data is usable for pair trading
        
        Args:
            df: DataFrame to validate
            min_rows: Minimum rows required
        
        Returns:
            True if data is valid
        """
        if df is None or df.empty:
            logger.warning("❌ Data is empty")
            return False
        
        if len(df) < min_rows:
            logger.warning(f"❌ Only {len(df)} rows (< {min_rows})")
            return False
        
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                logger.warning(f"❌ Missing column: {col}")
                return False
        
        return True


# ========== TEST ==========
if __name__ == "__main__":
    # This will run when file is executed directly
    print("Testing DataFetcher...")