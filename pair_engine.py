"""
pair_engine.py - Pair Engine V4 with Debug Prints
"""

import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint, adfuller
import warnings
warnings.filterwarnings("ignore")

class PairEngineV4:
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
    
    def analyze_pair(self, s1: str, s2: str) -> dict:
        """Analyze a pair with all metrics"""
        result = {
            'pair': (s1, s2),
            'valid': False,
            'metrics': {},
            'filters': {},
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
            result['filters']['corr_pass'] = abs(corr) >= 0.5
            if not result['filters']['corr_pass']:
                result['reject_reason'].append(f"Corr={corr:.3f} < 0.5")
            
            # 2. Beta
            beta = np.polyfit(clean[s1], clean[s2], 1)[0]
            result['metrics']['beta'] = round(beta, 3)
            result['filters']['beta_pass'] = 0.3 <= beta <= 3.0
            if not result['filters']['beta_pass']:
                result['reject_reason'].append(f"Beta={beta:.2f} outside [0.3, 3.0]")
            
            # 3. Cointegration
            spread = clean[s2] - beta * clean[s1]
            coint_score, coint_pval, _ = coint(clean[s1], clean[s2])
            result['metrics']['coint_pval'] = round(coint_pval, 4)
            result['filters']['coint_pass'] = coint_pval <= 0.10
            if not result['filters']['coint_pass']:
                result['reject_reason'].append(f"Coint p={coint_pval:.4f} > 0.10")
            
            # 4. ADF
            adf_result = adfuller(spread, autolag='AIC')
            adf_pval = adf_result[1]
            result['metrics']['adf_pval'] = round(adf_pval, 4)
            result['filters']['adf_pass'] = adf_pval <= 0.10
            if not result['filters']['adf_pass']:
                result['reject_reason'].append(f"ADF p={adf_pval:.4f} > 0.10")
            
            # 5. Hurst
            h = self._calculate_hurst(spread)
            result['metrics']['hurst'] = round(h, 3)
            result['filters']['hurst_pass'] = h < 0.6
            if not result['filters']['hurst_pass']:
                result['reject_reason'].append(f"Hurst={h:.3f} >= 0.6")
            
            # 6. Half-life
            half_life = self._calculate_half_life(spread)
            result['metrics']['half_life'] = round(half_life, 1)
            result['filters']['half_life_pass'] = half_life < 100
            if not result['filters']['half_life_pass']:
                result['reject_reason'].append(f"Half-life={half_life:.1f} >= 100")
            
            # 7. Z-Score
            zscore = (spread - spread.rolling(20).mean()) / spread.rolling(20).std()
            result['metrics']['zscore'] = round(zscore.iloc[-1], 3) if not zscore.empty else 0
            
            # 8. Score
            score = 0
            score += min(abs(corr) * 25, 25)
            score += min((1 - min(coint_pval, 0.1) / 0.1) * 25, 25)
            score += min((1 - min(adf_pval, 0.1) / 0.1) * 20, 20)
            score += min((1 - min(h, 0.6) / 0.6) * 20, 20)
            score += min((1 - min(half_life, 100) / 100) * 10, 10)
            result['metrics']['score'] = round(min(score, 100), 1)
            
            # 9. Signal
            result['metrics']['signal'] = self._generate_signal(zscore.iloc[-1] if not zscore.empty else 0)
            
            # Final validation (all filters pass)
            result['valid'] = all([
                result['filters']['corr_pass'],
                result['filters']['beta_pass'],
                result['filters']['coint_pass'],
                result['filters']['adf_pass'],
                result['filters']['hurst_pass'],
                result['filters']['half_life_pass']
            ])
            
        except Exception as e:
            result['reject_reason'].append(f"Error: {str(e)}")
        
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
    
    def scan_pairs(self, filters: dict = None) -> list:
        """Scan all pairs with filters"""
        filters = filters or {}
        same_sector = filters.get('same_sector', False)  # Default False
        min_corr = filters.get('min_correlation', 0.5)
        max_pval = filters.get('max_pval', 0.10)
        
        symbols = list(self.data.columns)
        print(f"\n🔍 Scanning {len(symbols)} stocks...")
        print(f"   Filters: Same Sector={same_sector}, Min Corr={min_corr}, Max Pval={max_pval}")
        
        results = []
        self.debug_log = []
        total_pairs = len(symbols) * (len(symbols) - 1) // 2
        checked = 0
        
        for s1, s2 in combinations(symbols, 2):
            checked += 1
            
            # Sector filter (optional)
            if same_sector:
                sector1 = self._get_sector(s1)
                sector2 = self._get_sector(s2)
                if sector1 != sector2 or sector1 == "Unknown":
                    continue
            
            # Analyze
            result = self.analyze_pair(s1, s2)
            self.debug_log.append(result)
            
            if result['valid']:
                results.append(result)
            
            # Progress update
            if checked % 50 == 0:
                print(f"   Checked {checked}/{total_pairs} pairs...")
        
        results.sort(key=lambda x: x['metrics']['score'], reverse=True)
        self.results = results
        return results
    
    def display_debug_report(self, n: int = 30):
        """Display detailed debug report"""
        if not self.debug_log:
            print("No debug data available.")
            return
        
        print("\n" + "=" * 100)
        print(f"📋 DEBUG REPORT (First {min(n, len(self.debug_log))} pairs)")
        print("=" * 100)
        
        count = 0
        for r in self.debug_log:
            if count >= n:
                break
            s1, s2 = r['pair']
            
            # Skip if no metrics (error)
            if not r['metrics']:
                continue
            
            count += 1
            status = "✅ PASS" if r['valid'] else "❌ FAIL"
            score = r['metrics'].get('score', 0)
            
            print(f"\n{count}. {s1:12} ↔ {s2:12} [{status}] Score: {score:.1f}")
            
            if r['reject_reason']:
                for reason in r['reject_reason'][:3]:  # Show max 3 reasons
                    print(f"      ⛔ {reason}")
            else:
                # Show metrics if passed
                corr = r['metrics'].get('correlation', 0)
                coint_p = r['metrics'].get('coint_pval', 1)
                beta = r['metrics'].get('beta', 0)
                z = r['metrics'].get('zscore', 0)
                print(f"      📈 Corr: {corr:.3f} | 📉 Coint: {coint_p:.4f} | Beta: {beta:.2f} | Z: {z:.2f}")
    
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
            m = r['metrics']
            print(f"\n{i}. {s1:12} ↔ {s2:12} | Score: {m['score']:.1f} | {m['signal']}")
            print(f"   📈 Corr: {m['correlation']:.3f} | 📉 Coint: {m['coint_pval']:.4f}")
            print(f"   📊 Beta: {m['beta']:.3f} | 🌀 Hurst: {m['hurst']:.3f}")
            print(f"   ⏱️  Half-life: {m['half_life']:.1f} min | 🎯 Z: {m['zscore']:.3f}")
        
        print("\n" + "=" * 80)
        print(f"✅ Total pairs found: {len(self.results)}")