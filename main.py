import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint
import yfinance as yf
import time
import warnings
warnings.filterwarnings('ignore')

class Config:
    ANGEL_API_KEY = "YOUR_API_KEY"
    ANGEL_CLIENT_ID = "YOUR_CLIENT_ID"
    ANGEL_PASSWORD = "YOUR_PASSWORD"
    ANGEL_TOTP = "YOUR_TOTP"
    
    TOP_PAIRS = 20
    PERIOD = "5d"  # 15d થી 5d કર્યું (વધુ ઝડપી)
    TIMEFRAME = "5m"  # 15m થી 5m કર્યું (વધુ ડેટા)
    COINT_THRESHOLD = 0.10

class DataSource:
    @staticmethod
    def get_yahoo_data(symbols, period="5d", interval="5m"):
        """Fetch data from Yahoo Finance with better error handling"""
        print(f"📊 Fetching {len(symbols)} stocks from Yahoo Finance...")
        
        try:
            # Download with timeout
            data = yf.download(
                symbols, 
                period=period, 
                interval=interval, 
                progress=False,
                timeout=30
            )
            
            if data.empty:
                print("❌ No data received from Yahoo Finance")
                return pd.DataFrame()
            
            # Extract close prices
            close_data = pd.DataFrame()
            if isinstance(data.columns, pd.MultiIndex):
                for sym in symbols:
                    try:
                        if sym in data.columns.levels[0]:
                            close_data[sym] = data[sym]['Close']
                    except:
                        pass
            else:
                for sym in symbols:
                    try:
                        if sym in data.columns:
                            close_data[sym] = data['Close'][sym]
                    except:
                        pass
            
            # Clean data
            close_data = close_data.dropna(axis=1, how='all').dropna()
            
            print(f"✅ Retrieved data for {len(close_data.columns)} stocks")
            print(f"✅ Data rows: {len(close_data)}")
            
            return close_data
            
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            return pd.DataFrame()

class PairScanner:
    def __init__(self, symbols=None):
        if symbols is None:
            # NSE stocks with correct Yahoo Finance symbols
            self.symbols = [
                "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
                "INFY.NS", "TCS.NS", "HINDUNILVR.NS", "ITC.NS",
                "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS", "WIPRO.NS",
                "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS"
            ]
        else:
            self.symbols = symbols
        self.results = []
    
    @staticmethod
    def hurst(ts):
        ts = ts.values if isinstance(ts, pd.Series) else ts
        lags = range(2, min(20, len(ts)//2))
        if len(lags) < 2:
            return 0.5
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0] * 2.0
    
    def scan(self, data, top_n=None):
        if top_n is None:
            top_n = Config.TOP_PAIRS
        
        valid_symbols = list(data.columns)
        print(f"\n🔍 Scanning {len(valid_symbols)} stocks...")
        print(f"Total pairs: {len(valid_symbols) * (len(valid_symbols) - 1) // 2}")
        
        results = []
        for s1, s2 in combinations(valid_symbols, 2):
            try:
                clean = pd.DataFrame({s1: data[s1], s2: data[s2]}).dropna()
                if len(clean) < 15:
                    continue
                
                score, pval, _ = coint(clean[s1], clean[s2])
                
                if pval < Config.COINT_THRESHOLD:
                    corr = clean[s1].corr(clean[s2])
                    spread = clean[s2] - clean[s1]
                    h = self.hurst(spread)
                    
                    score_val = (
                        (abs(corr) * 30) + 
                        ((1 - min(pval, 0.1) / 0.1) * 30) + 
                        ((1 - min(h, 0.5) / 0.5) * 20)
                    )
                    
                    spread_lag = spread[:-1]
                    spread_diff = spread[1:] - spread[:-1]
                    try:
                        theta = np.polyfit(spread_lag, spread_diff, 1)[0]
                        half_life = -np.log(2) / theta if theta < 0 else 999
                    except:
                        half_life = 999
                    
                    results.append({
                        'pair1': s1.replace('.NS',''),
                        'pair2': s2.replace('.NS',''),
                        'corr': round(corr, 4),
                        'pval': round(pval, 4),
                        'hurst': round(h, 3),
                        'half_life': round(half_life, 1),
                        'score': round(min(score_val, 100), 1)
                    })
            except:
                pass
        
        self.results = sorted(results, key=lambda x: x['score'], reverse=True)
        return self.results[:top_n]

def main():
    print("=" * 60)
    print("📊 PAIR TRADING SCANNER")
    print("=" * 60)
    
    scanner = PairScanner()
    
    # Try multiple approaches to get data
    print("\n📈 Attempting to fetch market data...")
    
    # Approach 1: Default settings
    data = DataSource.get_yahoo_data(scanner.symbols, period="5d", interval="5m")
    
    # Approach 2: If no data, try daily data
    if data.empty:
        print("\n🔄 Trying daily data...")
        data = DataSource.get_yahoo_data(scanner.symbols, period="10d", interval="1d")
    
    # Approach 3: If still no data, use smaller symbol list
    if data.empty:
        print("\n🔄 Trying with smaller symbol list...")
        small_symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"]
        data = DataSource.get_yahoo_data(small_symbols, period="5d", interval="5m")
    
    if data.empty or len(data) < 3:
        print("\n❌ Could not fetch data. Please check:")
        print("  1. Internet connection")
        print("  2. Yahoo Finance availability")
        print("  3. Stock symbols (should end with .NS)")
        
        # Create dummy data for testing
        print("\n💡 Creating sample data for testing...")
        np.random.seed(42)
        dates = pd.date_range(start='2026-08-01', periods=100, freq='5min')
        data = pd.DataFrame({
            'RELIANCE.NS': 2500 + np.cumsum(np.random.randn(100)) * 10,
            'TCS.NS': 4000 + np.cumsum(np.random.randn(100)) * 15,
            'INFY.NS': 1800 + np.cumsum(np.random.randn(100)) * 8,
            'HDFCBANK.NS': 1700 + np.cumsum(np.random.randn(100)) * 12
        }, index=dates)
        print("✅ Sample data created for testing")
    
    if len(data) >= 3:
        results = scanner.scan(data)
        
        print(f"\n🏆 TOP {len(results)} COINTEGRATED PAIRS")
        print("=" * 60)
        
        if len(results) == 0:
            print("❌ No cointegrated pairs found.")
            print("   Try adjusting Config.COINT_THRESHOLD (currently 0.10)")
        else:
            for i, r in enumerate(results, 1):
                signal = "🟢 BUY" if r['score'] > 60 else "🟡 WATCH"
                print(f"\n{i}. {signal} {r['pair1']:15} ↔ {r['pair2']:15}")
                print(f"   📈 Corr: {r['corr']:.3f} | 📉 p-val: {r['pval']:.4f}")
                print(f"   📊 Hurst: {r['hurst']:.3f} | ⏱️ Half-life: {r['half_life']:.1f} min")
                print(f"   🎯 Score: {r['score']:.1f}/100")
            
            pd.DataFrame(results).to_csv('pairs.csv', index=False)
            print(f"\n📁 Results saved to 'pairs.csv'")
    else:
        print("❌ Not enough data to scan. Minimum 3 stocks required.")

if __name__ == "__main__":
    main()