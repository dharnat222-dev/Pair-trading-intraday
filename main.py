"""
📊 PAIR TRADING SCANNER - Angel One API
Fully fixed for GitHub Actions
"""

import subprocess
import sys
import os
import warnings
warnings.filterwarnings('ignore')

# ========== FORCE INSTALL SMARTAPI ==========
def install_smartapi():
    try:
        import SmartApi
        print("✅ SmartApi already installed")
        return True
    except ImportError:
        print("📦 Installing smartapi-python...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "smartapi-python==1.1.0",
                "--no-cache-dir",
                "--timeout", "60"
            ])
            import SmartApi
            print("✅ SmartApi installed successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to install SmartApi: {e}")
            return False

if not install_smartapi():
    print("❌ Cannot proceed without SmartApi")
    sys.exit(1)

# ========== IMPORTS ==========
from SmartApi import SmartConnect
import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint

# ========== CONFIG ==========
class Config:
    ANGEL_API_KEY = os.getenv("ANGEL_API_KEY", "YOUR_API_KEY")
    ANGEL_CLIENT_ID = os.getenv("ANGEL_CLIENT_ID", "YOUR_CLIENT_ID")
    ANGEL_PASSWORD = os.getenv("ANGEL_PASSWORD", "YOUR_PASSWORD")
    ANGEL_TOTP = os.getenv("ANGEL_TOTP", "YOUR_TOTP")
    TOP_PAIRS = 20
    COINT_THRESHOLD = 0.10

# ========== ANGEL BROKER ==========
class AngelBroker:
    def __init__(self):
        self.obj = None
        self.is_logged_in = False
    
    def login(self):
        try:
            print(f"🔄 Connecting to Angel One...")
            print(f"   Client: {Config.ANGEL_CLIENT_ID}")
            
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
            else:
                print(f"❌ Login Failed: {response}")
                return False
        except Exception as e:
            print(f"❌ Login Exception: {e}")
            return False
    
    def get_historical(self, symbol):
        try:
            import datetime
            from_date = (datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y-%m-%d")
            to_date = datetime.datetime.now().strftime("%Y-%m-%d")
            
            resp = self.obj.getCandleData(
                exchange="NSE",
                symbol=symbol,
                interval="ONE_MINUTE",
                fromdate=from_date,
                todate=to_date
            )
            
            if resp and 'data' in resp:
                cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                df = pd.DataFrame(resp['data'], columns=cols)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
            return None
        except Exception as e:
            print(f"⚠️ Error fetching {symbol}: {e}")
            return None

# ========== DATA FETCHER ==========
def get_data(symbols, broker):
    print(f"\n📊 Fetching {len(symbols)} stocks...")
    close_data = pd.DataFrame()
    
    for sym in symbols:
        df = broker.get_historical(sym)
        if df is not None and not df.empty:
            close_data[sym] = df.set_index('timestamp')['close']
            print(f"  ✅ {sym}: {len(df)} rows")
        else:
            print(f"  ❌ {sym}: No data")
    
    close_data = close_data.dropna(axis=1, how='all').dropna()
    print(f"\n✅ Retrieved data for {len(close_data.columns)} stocks")
    return close_data

# ========== PAIR SCANNER ==========
def scan_pairs(data, threshold=0.10, top_n=20):
    print(f"\n🔍 Scanning {len(data.columns)} stocks...")
    print(f"Total pairs: {len(data.columns) * (len(data.columns) - 1) // 2}")
    
    results = []
    for s1, s2 in combinations(data.columns, 2):
        try:
            clean = pd.DataFrame({s1: data[s1], s2: data[s2]}).dropna()
            if len(clean) < 10:
                continue
            
            score, pval, _ = coint(clean[s1], clean[s2])
            
            if pval < threshold:
                corr = clean[s1].corr(clean[s2])
                results.append({
                    'pair1': s1, 'pair2': s2,
                    'corr': round(corr, 4),
                    'pval': round(pval, 4),
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
    print(f"Python: {sys.version}")
    
    # Login
    broker = AngelBroker()
    if not broker.login():
        print("\n❌ Login Failed. Check secrets.")
        print("   ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP")
        return
    
    # Fetch data
    symbols = ["RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS", "HINDUNILVR", "ITC"]
    data = get_data(symbols, broker)
    
    if data.empty or len(data.columns) < 3:
        print("❌ Not enough data. Exiting.")
        return
    
    # Scan
    results = scan_pairs(data, threshold=Config.COINT_THRESHOLD, top_n=Config.TOP_PAIRS)
    
    # Display
    print("\n" + "=" * 60)
    print(f"🏆 TOP {len(results)} COINTEGRATED PAIRS")
    print("=" * 60)
    
    if not results:
        print("❌ No cointegrated pairs found.")
        return
    
    for i, r in enumerate(results, 1):
        signal = "🟢 BUY" if r['score'] > 60 else "🟡 WATCH"
        print(f"{i}. {signal} {r['pair1']:15} ↔ {r['pair2']:15}")
        print(f"   Corr: {r['corr']:.3f} | p-val: {r['pval']:.4f} | Score: {r['score']:.1f}")
    
    # Save
    pd.DataFrame(results).to_csv('pairs.csv', index=False)
    print(f"\n📁 Results saved to 'pairs.csv' ({len(results)} pairs)")

if __name__ == "__main__":
    main()