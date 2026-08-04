"""
pair_engine_v6.py - Professional Pair Selection Engine
"""

import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint, adfuller
import warnings
warnings.filterwarnings("ignore")

class PairEngineV6:
    def __init__(self, data: pd.DataFrame):
        self.data = data
        self.results = []
        self.debug_log = []
        self._validate_data()
    
    def _validate_data(self):
        if self.data.empty:
            raise ValueError("DataFrame is empty!")
        if len(self.data.columns) < 2:
            raise ValueError("Need at least 2 stocks!")
        print(f"✅ Data: {len(self.data)} rows, {len(self.data.columns)} stocks")
    
    def _calculate_hurst(self, ts: pd.Series) -> float:
        ts = ts.values if isinstance(ts, pd.Series) else ts
        lags = range(2, min(20, len(ts)//2))
        if len(lags) < 2:
            return 0.5
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0] * 2.0
    
    def _calculate_half_life(self, spread: pd.Series) -> float:
        spread_lag = spread[:-1]
        spread_diff = spread[1:] - spread[:-1]
        try:
            theta = np.polyfit(spread_lag, spread_diff, 1)[0]
            if theta < 0:
                return -np.log(2) / theta
            return 999
        except:
            return 999
    
    def analyze_pair(self, s1: str, s2: str) -> dict:
        """Analyze a pair with full metrics for selection"""
        result = {
            'pair': (s1, s2),
            'valid': False,
            'metrics': {},
            'reject_reason': []
        }
        
        try:
            clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
            if len(clean) < 20:
                result['reject_reason'].append(f"Insufficient data: {len(clean)} rows")
                return result
            
            # 1. Correlation
            corr = clean[s1].corr(clean[s2])
            result['metrics']['correlation'] = round(corr, 4)
            if abs(corr) < 0.6:
                result['reject_reason'].append(f"Corr={corr:.3f} < 0.6")
                return result
            
            # 2. Beta
            beta = np.polyfit(clean[s1], clean[s2], 1)[0]
            result['metrics']['beta'] = round(beta, 3)
            if not (0.3 <= beta <= 3.0):
                result['reject_reason'].append(f"Beta={beta:.2f} outside [0.3, 3.0]")
                return result
            
            # 3. Spread
            spread = clean[s2] - beta * clean[s1]
            
            # 4. Cointegration
            coint_score, coint_pval, _ = coint(clean[s1], clean[s2])
            result['metrics']['coint_pval'] = round(coint_pval, 4)
            if coint_pval > 0.10:
                result['reject_reason'].append(f"Coint p={coint_pval:.4f} > 0.10")
                return result
            
            # 5. ADF
            adf_result = adfuller(spread, autolag='AIC')
            adf_pval = adf_result[1]
            result['metrics']['adf_pval'] = round(adf_pval, 4)
            if adf_pval > 0.10:
                result['reject_reason'].append(f"ADF p={adf_pval:.4f} > 0.10")
                return result
            
            # 6. Hurst
            h = self._calculate_hurst(spread)
            result['metrics']['hurst'] = round(h, 3)
            if h >= 0.5:
                result['reject_reason'].append(f"Hurst={h:.3f} >= 0.5")
                return result
            
            # 7. Half-life (information only)
            half_life = self._calculate_half_life(spread)
            result['metrics']['half_life'] = round(half_life, 1)
            
            # 8. Score
            score = 0
            score += min(abs(corr) * 25, 25)
            score += min((1 - min(coint_pval, 0.1) / 0.1) * 25, 25)
            score += min((1 - min(adf_pval, 0.1) / 0.1) * 20, 20)
            score += min((1 - min(h, 0.5) / 0.5) * 20, 20)
            score += min((1 - min(half_life, 100) / 100) * 10, 10)
            result['metrics']['score'] = round(min(score, 100), 1)
            
            result['valid'] = True
            
        except Exception as e:
            result['reject_reason'].append(f"Error: {str(e)}")
        
        return result
    
    def scan_pairs(self) -> list:
        """Scan all pairs with full filters"""
        symbols = list(self.data.columns)
        print(f"\n🔍 Scanning {len(symbols)} stocks for pair selection...")
        print(f"   Total pairs: {len(symbols) * (len(symbols) - 1) // 2}")
        
        results = []
        self.debug_log = []
        
        for s1, s2 in combinations(symbols, 2):
            result = self.analyze_pair(s1, s2)
            self.debug_log.append(result)
            if result['valid']:
                results.append(result)
        
        results.sort(key=lambda x: x['metrics']['score'], reverse=True)
        self.results = results
        return results
    
    def get_top_pairs(self, n: int = 50) -> list:
        return self.results[:n]
    
    def display_debug_report(self, n: int = 20):
        if not self.debug_log:
            print("No debug data available.")
            return
        
        print("\n" + "=" * 100)
        print(f"📋 PAIR SELECTION REPORT (First {n} pairs)")
        print("=" * 100)
        
        count = 0
        for r in self.debug_log:
            if count >= n:
                break
            s1, s2 = r['pair']
            count += 1
            
            status = "✅ PASS" if r['valid'] else "❌ FAIL"
            score = r['metrics'].get('score', 0)
            
            if status == "✅ PASS":
                print(f"\n{count}. {s1:12} ↔ {s2:12} [{status}] Score: {score:.1f}")
                corr = r['metrics'].get('correlation', 0)
                coint_p = r['metrics'].get('coint_pval', 1)
                h = r['metrics'].get('hurst', 1)
                print(f"      Corr: {corr:.3f} | Coint: {coint_p:.4f} | Hurst: {h:.3f}")
            else:
                reason = r['reject_reason'][0] if r['reject_reason'] else "Unknown"
                print(f"\n{count}. {s1:12} ↔ {s2:12} [{status}] ⛔ {reason}")
    
    def display_results(self, n: int = 20):
        if not self.results:
            print("\n❌ No pairs selected.")
            return
        
        print("\n" + "=" * 80)
        print(f"🏆 TOP {min(n, len(self.results))} PAIRS SELECTED")
        print("=" * 80)
        
        for i, r in enumerate(self.results[:n], 1):
            s1, s2 = r['pair']
            m = r['metrics']
            print(f"\n{i}. {s1:12} ↔ {s2:12} | Score: {m['score']:.1f}")
            print(f"   📈 Corr: {m['correlation']:.3f} | 📉 Coint: {m['coint_pval']:.4f}")
            print(f"   📊 Beta: {m['beta']:.3f} | 🌀 Hurst: {m['hurst']:.3f}")
            print(f"   ⏱️  Half-life: {m['half_life']:.1f} min")
        
        print("\n" + "=" * 80)
        print(f"✅ Total pairs selected: {len(self.results)}")