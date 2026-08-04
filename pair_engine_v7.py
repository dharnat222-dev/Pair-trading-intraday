"""
pair_engine_v7.py - Professional Pair Selection Engine V7.1
Same Sector Filter ON, Looser Thresholds, Full Debug
"""

import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint, adfuller
import warnings
warnings.filterwarnings("ignore")

class PairEngineV7:
    def __init__(self, data: pd.DataFrame, sector_map: dict = None):
        self.data = data
        self.sector_map = sector_map or {}
        self.results = []
        self.debug_log = []
        self._validate_data()
    
    def _validate_data(self):
        if self.data.empty:
            raise ValueError("DataFrame is empty!")
        if len(self.data.columns) < 2:
            raise ValueError("Need at least 2 stocks!")
        print(f"✅ Data: {len(self.data)} rows, {len(self.data.columns)} stocks")
    
    def _get_sector(self, symbol: str) -> str:
        clean_symbol = symbol.replace('.NS', '').replace('-EQ', '').strip()
        return self.sector_map.get(clean_symbol, "Unknown")
    
    def _calculate_hurst(self, ts: pd.Series) -> float:
        ts = ts.values if isinstance(ts, pd.Series) else ts
        if len(ts) < 20:
            return 0.5
        lags = range(2, min(20, len(ts)//2))
        if len(lags) < 2:
            return 0.5
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
        try:
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return poly[0] * 2.0
        except:
            return 0.5
    
    def _calculate_half_life(self, spread: pd.Series) -> float:
        if len(spread) < 10:
            return 999
        
        spread_lag = spread[:-1].values
        spread_diff = spread.diff().dropna().values
        
        if len(spread_lag) < 5 or len(spread_diff) < 5:
            return 999
        
        try:
            from sklearn.linear_model import LinearRegression
            X = spread_lag.reshape(-1, 1)
            y = spread_diff
            model = LinearRegression()
            model.fit(X, y)
            theta = model.coef_[0]
            
            if theta < 0:
                half_life = -np.log(2) / theta
                if half_life > 500:
                    return 999
                return max(1, half_life)
            else:
                return 999
        except:
            return 999
    
    def analyze_pair(self, s1: str, s2: str) -> dict:
        """Analyze a pair with full metrics and debug info"""
        result = {
            'pair': (s1, s2),
            'valid': False,
            'metrics': {},
            'reject_reason': [],
            'debug': {}
        }
        
        try:
            clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
            if len(clean) < 60:
                result['reject_reason'].append(f"Insufficient data: {len(clean)} rows")
                return result
            
            # 1. Sector Filter (MANDATORY)
            sector1 = self._get_sector(s1)
            sector2 = self._get_sector(s2)
            result['debug']['sector'] = f"{sector1} ↔ {sector2}"
            
            if sector1 != sector2 or sector1 == "Unknown":
                result['reject_reason'].append(f"Sector mismatch: {sector1} vs {sector2}")
                return result
            result['debug']['sector_pass'] = "✅"
            
            # 2. Correlation
            corr = clean[s1].corr(clean[s2])
            result['metrics']['correlation'] = round(corr, 4)
            result['debug']['corr'] = f"{corr:.3f}"
            
            if abs(corr) < 0.55:  # Looser: 0.55
                result['reject_reason'].append(f"Corr={corr:.3f} < 0.55")
                return result
            result['debug']['corr_pass'] = "✅"
            
            # 3. Rolling Correlation (30-day)
            rolling_corr = clean[s1].rolling(30).corr(clean[s2])
            avg_rolling_corr = rolling_corr.mean() if not rolling_corr.empty else 0
            result['metrics']['rolling_corr'] = round(avg_rolling_corr, 4)
            result['debug']['rolling_corr'] = f"{avg_rolling_corr:.3f}"
            
            if abs(avg_rolling_corr) < 0.45:
                result['reject_reason'].append(f"Rolling Corr={avg_rolling_corr:.3f} < 0.45")
                return result
            result['debug']['rolling_corr_pass'] = "✅"
            
            # 4. Beta (Looser: 0.5-1.5)
            beta = np.polyfit(clean[s1], clean[s2], 1)[0]
            result['metrics']['beta'] = round(beta, 3)
            result['debug']['beta'] = f"{beta:.2f}"
            
            if not (0.5 <= beta <= 1.5):
                result['reject_reason'].append(f"Beta={beta:.2f} outside [0.5, 1.5]")
                return result
            result['debug']['beta_pass'] = "✅"
            
            # 5. Spread
            spread = clean[s2] - beta * clean[s1]
            
            # 6. Cointegration (Looser: 0.10)
            coint_score, coint_pval, _ = coint(clean[s1], clean[s2])
            result['metrics']['coint_pval'] = round(coint_pval, 4)
            result['debug']['coint'] = f"{coint_pval:.4f}"
            
            if coint_pval > 0.10:
                result['reject_reason'].append(f"Coint p={coint_pval:.4f} > 0.10")
                return result
            result['debug']['coint_pass'] = "✅"
            
            # 7. ADF (Looser: 0.10)
            adf_result = adfuller(spread, autolag='AIC')
            adf_pval = adf_result[1]
            result['metrics']['adf_pval'] = round(adf_pval, 4)
            result['debug']['adf'] = f"{adf_pval:.4f}"
            
            if adf_pval > 0.10:
                result['reject_reason'].append(f"ADF p={adf_pval:.4f} > 0.10")
                return result
            result['debug']['adf_pass'] = "✅"
            
            # 8. Hurst (Looser: 0.50)
            h = self._calculate_hurst(spread)
            result['metrics']['hurst'] = round(h, 3)
            result['debug']['hurst'] = f"{h:.3f}"
            
            if h >= 0.50:
                result['reject_reason'].append(f"Hurst={h:.3f} >= 0.50")
                return result
            result['debug']['hurst_pass'] = "✅"
            
            # 9. Half-life (Looser: 150)
            half_life = self._calculate_half_life(spread)
            result['metrics']['half_life'] = round(half_life, 1)
            result['debug']['half_life'] = f"{half_life:.1f}"
            
            if half_life >= 150:
                result['reject_reason'].append(f"Half-life={half_life:.1f} >= 150")
                return result
            result['debug']['half_life_pass'] = "✅"
            
            # 10. Score
            score = 0
            score += min(abs(corr) * 18, 18)
            score += min(abs(avg_rolling_corr) * 18, 18)
            score += min((1 - min(coint_pval, 0.10) / 0.10) * 18, 18)
            score += min((1 - min(adf_pval, 0.10) / 0.10) * 16, 16)
            score += min((1 - min(h, 0.50) / 0.50) * 15, 15)
            score += min((1 - min(half_life, 150) / 150) * 15, 15)
            result['metrics']['score'] = round(min(score, 100), 1)
            
            result['valid'] = True
            
        except Exception as e:
            result['reject_reason'].append(f"Error: {str(e)}")
        
        return result
    
    def scan_pairs(self) -> list:
        symbols = list(self.data.columns)
        print(f"\n🔍 Scanning {len(symbols)} stocks for pair selection...")
        print(f"   Filters: Same Sector, Corr≥0.55, Beta 0.5-1.5, Hurst<0.50")
        
        results = []
        self.debug_log = []
        total_pairs = len(symbols) * (len(symbols) - 1) // 2
        checked = 0
        
        for s1, s2 in combinations(symbols, 2):
            checked += 1
            result = self.analyze_pair(s1, s2)
            self.debug_log.append(result)
            if result['valid']:
                results.append(result)
            
            if checked % 100 == 0:
                print(f"   Checked {checked}/{total_pairs} pairs...")
        
        results.sort(key=lambda x: x['metrics']['score'], reverse=True)
        self.results = results
        return results
    
    def get_top_pairs(self, n: int = 30) -> list:
        return self.results[:n]
    
    def display_debug_report(self, n: int = 30):
        """Full Debug with all metrics"""
        if not self.debug_log:
            print("No debug data available.")
            return
        
        print("\n" + "=" * 110)
        print(f"📋 FULL DEBUG REPORT (Same Sector Pairs Only)")
        print("=" * 110)
        
        count = 0
        for r in self.debug_log:
            if count >= n:
                break
            s1, s2 = r['pair']
            
            # Only show pairs that passed sector filter
            if r['debug'].get('sector_pass') != "✅":
                continue
            
            count += 1
            status = "✅ PASS" if r['valid'] else "❌ FAIL"
            score = r['metrics'].get('score', 0)
            
            print(f"\n{count}. {s1:12} ↔ {s2:12} [{status}] Score: {score:.1f}")
            print(f"   Sector: {r['debug'].get('sector', 'Unknown')}")
            
            # All metrics in one line
            corr = r['debug'].get('corr', '0.00')
            rc = r['debug'].get('rolling_corr', '0.00')
            beta = r['debug'].get('beta', '0.00')
            coint = r['debug'].get('coint', '1.00')
            adf = r['debug'].get('adf', '1.00')
            hurst = r['debug'].get('hurst', '0.50')
            hl = r['debug'].get('half_life', '999')
            
            print(f"   📈 Corr: {corr} | 🔄 RC: {rc} | 📊 Beta: {beta}")
            print(f"   📉 Coint: {coint} | 📈 ADF: {adf} | 🌀 Hurst: {hurst} | ⏱️ HL: {hl}")
            
            if r['reject_reason']:
                print(f"   ⛔ REJECT: {r['reject_reason'][0]}")
    
    def display_results(self, n: int = 20):
        if not self.results:
            print("\n❌ No pairs selected. Check debug report.")
            return
        
        print("\n" + "=" * 80)
        print(f"🏆 TOP {min(n, len(self.results))} PAIRS SELECTED")
        print("=" * 80)
        
        for i, r in enumerate(self.results[:n], 1):
            s1, s2 = r['pair']
            m = r['metrics']
            sector1 = self._get_sector(s1)
            print(f"\n{i}. {s1:12} ↔ {s2:12} | Score: {m['score']:.1f} | Sector: {sector1}")
            print(f"   📈 Corr: {m['correlation']:.3f} | 🔄 RollCorr: {m['rolling_corr']:.3f}")
            print(f"   📉 Coint: {m['coint_pval']:.4f} | 📊 Beta: {m['beta']:.3f}")
            print(f"   🌀 Hurst: {m['hurst']:.3f} | ⏱️ Half-life: {m['half_life']:.1f} min")
        
        print("\n" + "=" * 80)
        print(f"✅ Total pairs selected: {len(self.results)}")