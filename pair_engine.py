"""
pair_engine.py - Pair Engine V5 (Intraday Optimized)
No Half-life/ADF hard filters. Uses Rolling Correlation, Z-Score, ATR.
"""

import pandas as pd
import numpy as np
from itertools import combinations
import warnings
warnings.filterwarnings("ignore")

class PairEngineV5:
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
    
    def _calculate_rolling_corr(self, s1: str, s2: str, window: int = 20) -> pd.Series:
        """Calculate rolling correlation between two stocks"""
        clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
        return clean[s1].rolling(window).corr(clean[s2])
    
    def _calculate_spread(self, s1: str, s2: str) -> pd.Series:
        """Calculate spread (price difference)"""
        clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
        return clean[s2] - clean[s1]
    
    def _calculate_zscore(self, spread: pd.Series, window: int = 20) -> pd.Series:
        """Calculate rolling Z-Score"""
        mean = spread.rolling(window).mean()
        std = spread.rolling(window).std()
        return (spread - mean) / std
    
    def _calculate_atr(self, s1: str, s2: str, window: int = 14) -> float:
        """Calculate Average True Range for volatility"""
        clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
        
        # Daily range for both stocks
        high1 = clean[s1].max()
        low1 = clean[s1].min()
        high2 = clean[s2].max()
        low2 = clean[s2].min()
        
        # Average spread volatility
        spread = clean[s2] - clean[s1]
        atr = spread.std()
        return atr
    
    def analyze_pair(self, s1: str, s2: str) -> dict:
        """Analyze a pair with intraday metrics"""
        result = {
            'pair': (s1, s2),
            'valid': False,
            'metrics': {},
            'filters': {},
            'reject_reason': []
        }
        
        try:
            # Clean data
            clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
            if len(clean) < 30:
                result['reject_reason'].append(f"Insufficient data: {len(clean)} rows")
                return result
            
            # 1. Static Correlation
            corr = clean[s1].corr(clean[s2])
            result['metrics']['correlation'] = round(corr, 4)
            result['filters']['corr_pass'] = abs(corr) >= 0.6
            if not result['filters']['corr_pass']:
                result['reject_reason'].append(f"Corr={corr:.3f} < 0.6")
            
            # 2. Rolling Correlation (last 20 periods)
            try:
                rolling_corr = self._calculate_rolling_corr(s1, s2, window=20)
                avg_rolling_corr = rolling_corr.mean() if not rolling_corr.empty else 0
                result['metrics']['rolling_corr'] = round(avg_rolling_corr, 4)
                result['filters']['rolling_corr_pass'] = abs(avg_rolling_corr) >= 0.5
                if not result['filters']['rolling_corr_pass']:
                    result['reject_reason'].append(f"Rolling Corr={avg_rolling_corr:.3f} < 0.5")
            except:
                result['filters']['rolling_corr_pass'] = True
                result['metrics']['rolling_corr'] = corr
            
            # 3. Spread & Z-Score
            spread = self._calculate_spread(s1, s2)
            zscore = self._calculate_zscore(spread, window=20)
            current_z = zscore.iloc[-1] if not zscore.empty else 0
            result['metrics']['zscore'] = round(current_z, 3)
            result['filters']['zscore_pass'] = abs(current_z) >= 1.5
            if not result['filters']['zscore_pass']:
                result['reject_reason'].append(f"Z-Score={current_z:.2f} < 1.5")
            
            # 4. Spread Volatility (ATR)
            atr = self._calculate_atr(s1, s2, window=14)
            result['metrics']['atr'] = round(atr, 2)
            
            # 5. Price Ratio (for normalization)
            price_ratio = clean[s2].iloc[-1] / clean[s1].iloc[-1]
            result['metrics']['price_ratio'] = round(price_ratio, 3)
            
            # 6. Signal
            result['metrics']['signal'] = self._generate_signal(current_z)
            
            # 7. Score (0-100)
            score = 0
            score += min(abs(corr) * 30, 30)  # Max 30
            score += min(abs(result['metrics']['rolling_corr']) * 25, 25)  # Max 25
            score += min(abs(current_z) * 15, 15)  # Max 15
            score += min((1 - min(atr / 10, 1)) * 15, 15)  # Max 15
            score += min((1 - abs(current_z - 2) / 4) * 15, 15)  # Max 15
            result['metrics']['score'] = round(min(score, 100), 1)
            
            # Final validation (pass if correlation and zscore are good)
            result['valid'] = all([
                result['filters']['corr_pass'],
                result['filters']['rolling_corr_pass'],
                abs(current_z) >= 1.5  # Z-Score threshold
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
        """Scan all pairs with intraday filters"""
        filters = filters or {}
        min_corr = filters.get('min_correlation', 0.6)
        
        symbols = list(self.data.columns)
        print(f"\n🔍 Scanning {len(symbols)} stocks...")
        print(f"   Filters: Min Corr={min_corr}")
        
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
            
            if not r['metrics']:
                continue
            
            count += 1
            status = "✅ PASS" if r['valid'] else "❌ FAIL"
            score = r['metrics'].get('score', 0)
            
            print(f"\n{count}. {s1:12} ↔ {s2:12} [{status}] Score: {score:.1f}")
            
            if r['reject_reason']:
                for reason in r['reject_reason'][:3]:
                    print(f"      ⛔ {reason}")
            else:
                corr = r['metrics'].get('correlation', 0)
                z = r['metrics'].get('zscore', 0)
                atr = r['metrics'].get('atr', 0)
                print(f"      📈 Corr: {corr:.3f} | 🎯 Z: {z:.2f} | 📊 ATR: {atr:.2f}")
    
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
            print(f"   📈 Corr: {m['correlation']:.3f} | 🌀 Rolling Corr: {m['rolling_corr']:.3f}")
            print(f"   🎯 Z-Score: {m['zscore']:.3f} | 📊 ATR: {m['atr']:.2f}")
            print(f"   📊 Price Ratio: {m['price_ratio']:.3f}")
        
        print("\n" + "=" * 80)
        print(f"✅ Total pairs found: {len(self.results)}")