"""
pair_engine.py - Pair Engine V3 with Debug Report
"""

import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint, adfuller
import warnings
warnings.filterwarnings("ignore")

class PairEngineV3:
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
    
    def analyze_pair(self, s1: str, s2: str, debug: bool = False) -> dict:
        """Analyze a pair with detailed debug info"""
        result = {
            'pair': (s1, s2),
            'valid': True,
            'checks': {},
            'errors': []
        }
        
        try:
            # Data check
            clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
            if len(clean) < 30:
                result['valid'] = False
                result['checks']['data'] = f"❌ Insufficient data: {len(clean)} rows (need 30+)"
                return result
            
            # 1. Sector Check
            sector1 = self._get_sector(s1)
            sector2 = self._get_sector(s2)
            same_sector = sector1 == sector2 and sector1 != "Unknown"
            result['checks']['sector'] = f"{'✅' if same_sector else '❌'} {sector1} ↔ {sector2}"
            
            # 2. Correlation
            corr = clean[s1].corr(clean[s2])
            result['checks']['correlation'] = f"{'✅' if abs(corr) >= 0.6 else '❌'} {corr:.3f} (need ≥ 0.6)"
            result['correlation'] = round(corr, 4)
            
            # 3. Beta
            beta = np.polyfit(clean[s1], clean[s2], 1)[0]
            result['checks']['beta'] = f"{'✅' if 0.3 <= beta <= 3.0 else '❌'} {beta:.3f} (need 0.3-3.0)"
            result['beta'] = round(beta, 3)
            
            # 4. Spread
            spread = clean[s2] - beta * clean[s1]
            
            # 5. Cointegration
            coint_score, coint_pval, _ = coint(clean[s1], clean[s2])
            result['checks']['coint'] = f"{'✅' if coint_pval <= 0.10 else '❌'} p={coint_pval:.4f} (need ≤ 0.10)"
            result['coint_pval'] = round(coint_pval, 4)
            
            # 6. ADF
            adf_result = adfuller(spread, autolag='AIC')
            adf_pval = adf_result[1]
            result['checks']['adf'] = f"{'✅' if adf_pval <= 0.10 else '❌'} p={adf_pval:.4f} (need ≤ 0.10)"
            result['adf_pval'] = round(adf_pval, 4)
            
            # 7. Hurst
            h = self._calculate_hurst(spread)
            result['checks']['hurst'] = f"{'✅' if h < 0.5 else '❌'} {h:.3f} (need < 0.5)"
            result['hurst'] = round(h, 3)
            
            # 8. Half-life
            half_life = self._calculate_half_life(spread)
            result['checks']['half_life'] = f"{'✅' if half_life < 100 else '❌'} {half_life:.1f} min (need < 100)"
            result['half_life'] = round(half_life, 1)
            
            # 9. Z-Score
            zscore = (spread - spread.rolling(20).mean()) / spread.rolling(20).std()
            result['zscore'] = round(zscore.iloc[-1], 3) if not zscore.empty else 0
            
            # 10. Quality Score
            score = 0
            score += min(abs(corr) * 25, 25)
            score += min((1 - min(coint_pval, 0.1) / 0.1) * 25, 25)
            score += min((1 - min(adf_pval, 0.1) / 0.1) * 20, 20)
            score += min((1 - min(h, 0.5) / 0.5) * 20, 20)
            score += min((1 - min(half_life, 100) / 100) * 10, 10)
            result['score'] = round(min(score, 100), 1)
            
            # 11. Signal
            result['signal'] = self._generate_signal(zscore.iloc[-1] if not zscore.empty else 0)
            
            # Final validation (for filters)
            passed = all([
                abs(corr) >= 0.6,
                coint_pval <= 0.10,
                adf_pval <= 0.10,
                h < 0.5,
                half_life < 100,
                0.3 <= beta <= 3.0
            ])
            result['valid'] = passed
            
        except Exception as e:
            result['valid'] = False
            result['errors'].append(str(e))
        
        return result
    
    def _generate_signal(self, zscore: float) -> str:
        if zscore > 2.0:
            return "🟢 BUY_LEG1_SELL_LEG2"
        elif zscore < -2.0:
            return "🔴 SELL_LEG1_BUY_LEG2"
        elif zscore > 1.5:
            return "🟡 WATCH_BUY"
        elif zscore < -1.5:
            return "🟡 WATCH_SELL"
        else:
            return "⚪ NO_SIGNAL"
    
    def scan_pairs(self, filters: dict = None, debug: bool = True) -> list:
        """Scan all pairs with filters and debug report"""
        filters = filters or {}
        same_sector = filters.get('same_sector', True)
        
        symbols = list(self.data.columns)
        print(f"\n🔍 Scanning {len(symbols)} stocks...")
        
        results = []
        self.debug_log = []
        
        for s1, s2 in combinations(symbols, 2):
            # Sector filter
            if same_sector:
                sector1 = self._get_sector(s1)
                sector2 = self._get_sector(s2)
                if sector1 != sector2 or sector1 == "Unknown":
                    continue
            
            # Analyze pair
            result = self.analyze_pair(s1, s2, debug=debug)
            self.debug_log.append(result)
            
            if result['valid']:
                results.append(result)
        
        results.sort(key=lambda x: x['score'], reverse=True)
        self.results = results
        return results
    
    def display_debug_report(self, n: int = 20):
        """Display detailed debug report"""
        if not self.debug_log:
            print("No debug data available.")
            return
        
        print("\n" + "=" * 80)
        print("📋 DEBUG REPORT (First 20 pairs)")
        print("=" * 80)
        
        count = 0
        for r in self.debug_log:
            if count >= n:
                break
            s1, s2 = r['pair']
            
            # Skip if both sectors are Unknown (no sector data)
            if self._get_sector(s1) == "Unknown" and self._get_sector(s2) == "Unknown":
                continue
            
            count += 1
            status = "✅ PASS" if r['valid'] else "❌ FAIL"
            print(f"\n{count}. {s1:12} ↔ {s2:12} [{status}] Score: {r.get('score', 0):.1f}")
            
            for check_name, check_value in r.get('checks', {}).items():
                print(f"      {check_name}: {check_value}")
    
    def display_results(self, n: int = 10):
        """Display formatted results"""
        if not self.results:
            print("\n❌ No pairs found. Check debug report for reasons.")
            return
        
        print("\n" + "=" * 80)
        print(f"🏆 TOP {min(n, len(self.results))} PAIRS")
        print("=" * 80)
        
        for i, r in enumerate(self.results[:n], 1):
            s1, s2 = r['pair']
            print(f"\n{i}. {s1:12} ↔ {s2:12} | Score: {r['score']:.1f} | {r['signal']}")
            print(f"   📈 Corr: {r['correlation']:.3f} | 📉 Coint: {r['coint_pval']:.4f}")
            print(f"   📊 Beta: {r['beta']:.3f} | 🌀 Hurst: {r['hurst']:.3f}")
            print(f"   ⏱️  Half-life: {r['half_life']:.1f} min | 🎯 Z: {r['zscore']:.3f}")
        
        print("\n" + "=" * 80)
        print(f"✅ Total pairs found: {len(self.results)}")