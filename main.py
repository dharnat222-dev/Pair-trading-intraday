"""
📊 Pair Trading Scanner
Supports: Angel One API + Yahoo Finance
"""

import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint
import yfinance as yf
import time
import warnings
warnings.filterwarnings('ignore')

# ========== CONFIGURATION ==========
class Config:
    # Angel One Credentials
    ANGEL_API_KEY = "YOUR_API_KEY"
    ANGEL_CLIENT_ID = "YOUR_CLIENT_ID"
    ANGEL_PASSWORD = "YOUR_PASSWORD"
    ANGEL_TOTP = "YOUR_TOTP"
    
    # Scanner Settings
    TOP_PAIRS = 20
    PERIOD = "15d"
    TIMEFRAME = "15m"
    COINT_THRESHOLD = 0.10

# ========== DATA SOURCE ==========
class DataSource:
    @staticmethod
    def get_yahoo_data(symbols, period="15d", interval="15m"):
        """Fetch data from Yahoo Finance"""
        print("📊 Fetching from Yahoo Finance...")
        data = yf.download(symbols, period=period, interval=interval, progress=False)
        
        # Extract close prices
        close_data = pd.DataFrame()
        if isinstance(data.columns, pd.MultiIndex):
            for sym in symbols:
                try:
                    close_data[sym] = data[sym]['Close']
                except:
                    pass
        else:
            for sym in symbols:
                try:
                    close_data[sym] = data['Close'][sym]
                except:
                    pass
        
        close_data = close_data.dropna(axis=1, how='all').dropna()
        return close_data
    
    @staticmethod
    def get_angel_data(symbols, broker):
        """Fetch data from Angel One API"""
        print("📊 Fetching from Angel One...")
        close_data = pd.DataFrame()
        for sym in symbols:
            try:
                df = broker.get_historical(sym, interval="ONE_MINUTE")
                if not df.empty:
                    close_data[sym] = df.set_index('timestamp')['close']
            except:
                pass
        return close_data

# ========== PAIR SCANNER ==========
class PairScanner:
    def __init__(self, symbols=None):
        if symbols is None:
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
        """Calculate Hurst Exponent"""
        ts = ts.values if isinstance(ts, pd.Series) else ts
        lags = range(2, min(20, len(ts)//2))
        if len(lags) < 2:
            return 0.5
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0] * 2.0
    
    def scan(self, data, top_n=None):
        """Scan for cointegrated pairs"""
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
                    
                    # Confidence Score
                    score_val = (
                        (abs(corr) * 30) + 
                        ((1 - min(pval, 0.1) / 0.1) * 30) + 
                        ((1 - min(h, 0.5) / 0.5) * 20)
                    )
                    
                    # Half-life
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

# ========== MAIN ==========
def main():
    print("=" * 60)
    print("📊 PAIR TRADING SCANNER")
    print("=" * 60)
    
    scanner = PairScanner()
    
    # Option 1: Yahoo Finance (Free, No Login)
    print("\n✅ Using Yahoo Finance (free data source)")
    data = DataSource.get_yahoo_data(scanner.symbols, period=Config.PERIOD, interval=Config.TIMEFRAME)
    
    if len(data) < 5:
        print("❌ Not enough data. Try reducing symbols or changing period.")
        return
    
    # Scan
    results = scanner.scan(data)
    
    # Display Results
    print(f"\n🏆 TOP {len(results)} COINTEGRATED PAIRS")
    print("=" * 60)
    
    if len(results) == 0:
        print("❌ No pairs found. Try adjusting thresholds.")
    else:
        for i, r in enumerate(results, 1):
            signal = "🟢 BUY" if r['score'] > 60 else "🟡 WATCH"
            print(f"\n{i}. {signal} {r['pair1']:15} ↔ {r['pair2']:15}")
            print(f"   📈 Corr: {r['corr']:.3f} | 📉 p-val: {r['pval']:.4f}")
            print(f"   📊 Hurst: {r['hurst']:.3f} | ⏱️ Half-life: {r['half_life']:.1f} min")
            print(f"   🎯 Score: {r['score']:.1f}/100")
    
    # Save results
    if len(results) > 0:
        df = pd.DataFrame(results)
        df.to_csv('pairs.csv', index=False)
        print("\n📁 Results saved to 'pairs.csv'")

if __name__ == "__main__":
    main()