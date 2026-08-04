import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint
import yfinance as yf
import time

class PairTradingScanner:
    def __init__(self, symbols=None):
        if symbols is None:
            self.symbols = [
                "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
                "INFY.NS", "TCS.NS", "HINDUNILVR.NS", "ITC.NS",
                "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS", "WIPRO.NS"
            ]
        else:
            self.symbols = symbols
        self.results = []
    
    def scan(self, period="15d", interval="15m"):
        print(f"🔍 Scanning {len(self.symbols)} stocks...")
        data = yf.download(self.symbols, period=period, interval=interval, progress=False)
        
        close_data = pd.DataFrame()
        if isinstance(data.columns, pd.MultiIndex):
            for sym in self.symbols:
                try:
                    close_data[sym] = data[sym]['Close']
                except:
                    pass
        else:
            for sym in self.symbols:
                try:
                    close_data[sym] = data['Close'][sym]
                except:
                    pass
        
        close_data = close_data.dropna(axis=1, how='all').dropna()
        valid_symbols = list(close_data.columns)
        
        results = []
        for s1, s2 in combinations(valid_symbols, 2):
            try:
                clean = pd.DataFrame({s1: close_data[s1], s2: close_data[s2]}).dropna()
                if len(clean) < 15:
                    continue
                
                score, pval, _ = coint(clean[s1], clean[s2])
                if pval < 0.10:
                    corr = clean[s1].corr(clean[s2])
                    spread = clean[s2] - clean[s1]
                    
                    def hurst(ts):
                        ts = ts.values if isinstance(ts, pd.Series) else ts
                        lags = range(2, min(20, len(ts)//2))
                        if len(lags) < 2:
                            return 0.5
                        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
                        poly = np.polyfit(np.log(lags), np.log(tau), 1)
                        return poly[0] * 2.0
                    
                    h = hurst(spread)
                    
                    score_val = (
                        (abs(corr) * 30) + 
                        ((1 - min(pval, 0.1) / 0.1) * 30) + 
                        ((1 - min(h, 0.5) / 0.5) * 20)
                    )
                    
                    results.append({
                        'pair1': s1.replace('.NS',''),
                        'pair2': s2.replace('.NS',''),
                        'corr': round(corr, 4),
                        'pval': round(pval, 4),
                        'hurst': round(h, 3),
                        'score': round(min(score_val, 100), 1)
                    })
            except:
                pass
        
        self.results = sorted(results, key=lambda x: x['score'], reverse=True)
        return self.results

if __name__ == "__main__":
    scanner = PairTradingScanner()
    results = scanner.scan()
    print(f"✅ Found {len(results)} cointegrated pairs")
    for r in results[:10]:
        print(f"  {r['pair1']} ↔ {r['pair2']} | Score: {r['score']}")