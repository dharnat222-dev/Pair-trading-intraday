# main.py - Angel One API Version
import os
import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint
import warnings
warnings.filterwarnings('ignore')

# ========== ANGEL ONE SETUP ==========
try:
    from SmartApi import SmartConnect
    SMART_API_AVAILABLE = True
except:
    SMART_API_AVAILABLE = False
    print("❌ SmartApi not installed. Run: pip install smartapi-python")

class Config:
    ANGEL_API_KEY = os.getenv("ANGEL_API_KEY", "YOUR_API_KEY")
    ANGEL_CLIENT_ID = os.getenv("ANGEL_CLIENT_ID", "YOUR_CLIENT_ID")
    ANGEL_PASSWORD = os.getenv("ANGEL_PASSWORD", "YOUR_PASSWORD")
    ANGEL_TOTP = os.getenv("ANGEL_TOTP", "YOUR_TOTP")
    TOP_PAIRS = 20
    COINT_THRESHOLD = 0.10

# ========== ANGEL ONE CONNECTION ==========
class AngelBroker:
    def __init__(self):
        self.obj = None
        self.is_logged_in = False
    
    def login(self):
        if not SMART_API_AVAILABLE:
            return False
        try:
            self.obj = SmartConnect(api_key=Config.ANGEL_API_KEY)
            response = self.obj.generateSession(
                clientCode=Config.ANGEL_CLIENT_ID,
                password=Config.ANGEL_PASSWORD,
                totp=Config.ANGEL_TOTP
            )
            if response and 'data' in response:
                self.is_logged_in = True
                print("✅ Angel One Login Successful")
                return True
        except Exception as e:
            print(f"❌ Login Failed: {e}")
        return False
    
    def get_historical(self, symbol):
        try:
            import datetime
            from_date = (datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y-%m-%d")
            to_date = datetime.datetime.now().strftime("%Y-%m-%d")
            resp = self.obj.getCandleData("NSE", symbol, "ONE_MINUTE", from_date, to_date)
            if resp and 'data' in resp:
                cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                df = pd.DataFrame(resp['data'], columns=cols)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
        except:
            pass
        return None

# ========== DATA FETCHER ==========
def get_angel_data(symbols, broker):
    print(f"📊 Fetching {len(symbols)} stocks from Angel One...")
    close_data = pd.DataFrame()
    for sym in symbols:
        df = broker.get_historical(sym)
        if df is not None and not df.empty:
            close_data[sym] = df.set_index('timestamp')['close']
            print(f"  ✅ {sym}: {len(df)} rows")
        else:
            print(f"  ❌ {sym}: No data")
    close_data = close_data.dropna(axis=1, how='all').dropna()
    print(f"✅ Retrieved data for {len(close_data.columns)} stocks")
    return close_data

# ========== PAIR SCANNER ==========
class PairScanner:
    def __init__(self, symbols=None):
        self.symbols = symbols or ["RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS"]
        self.results = []
    
    def scan(self, data, top_n=20):
        results = []
        for s1, s2 in combinations(data.columns, 2):
            try:
                clean = pd.DataFrame({s1: data[s1], s2: data[s2]}).dropna()
                if len(clean) < 10:
                    continue
                score, pval, _ = coint(clean[s1], clean[s2])
                if pval < Config.COINT_THRESHOLD:
                    corr = clean[s1].corr(clean[s2])
                    results.append({
                        'pair1': s1, 'pair2': s2,
                        'corr': round(corr, 4), 'pval': round(pval, 4),
                        'score': round((abs(corr) * 70) + ((1 - pval) * 30), 1)
                    })
            except:
                pass
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_n]

# ========== MAIN ==========
def main():
    print("=" * 60)
    print("📊 PAIR TRADING SCANNER (Angel One)")
    print("=" * 60)
    
    broker = AngelBroker()
    if not broker.login():
        print("❌ Angel One Login Failed. Check credentials.")
        return
    
    symbols = ["RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS"]
    data = get_angel_data(symbols, broker)
    
    if data.empty or len(data) < 3:
        print("❌ Not enough data. Please check.")
        return
    
    scanner = PairScanner()
    results = scanner.scan(data)
    
    print(f"\n🏆 TOP {len(results)} COINTEGRATED PAIRS")
    for i, r in enumerate(results, 1):
        signal = "🟢" if r['score'] > 60 else "🟡"
        print(f"{i}. {signal} {r['pair1']:15} ↔ {r['pair2']:15} | Corr: {r['corr']:.3f} | Score: {r['score']:.1f}")
    
    if results:
        pd.DataFrame(results).to_csv('pairs.csv', index=False)
        print("\n📁 Results saved to 'pairs.csv'")

if __name__ == "__main__":
    main()