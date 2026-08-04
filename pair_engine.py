"""
pair_engine.py - Advanced Pair Selection Engine V2
Filters: Correlation, Cointegration, Beta, Half-life, Hurst, ADF
"""

import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint, adfuller
import warnings
warnings.filterwarnings("ignore")

class PairEngineV2:
    def __init__(self, data: pd.DataFrame, sector_map: dict = None):
        """
        Initialize with OHLC data and optional sector mapping
        """
        self.data = data
        self.sector_map = sector_map or {}
        self.results = []
        self._validate_data()
    
    def _validate_data(self):
        if self.data.empty:
            raise ValueError("DataFrame is empty!")
        if len(self.data.columns) < 2:
            raise ValueError("Need at least 2 stocks!")
        print(f"✅ Data: {len(self.data)} rows, {len(self.data.columns)} stocks")
    
    def _get_sector(self, symbol: str) -> str:
        """Get sector for a symbol"""
        clean_symbol = symbol.replace('.NS', '').strip()
        return self.sector_map.get(clean_symbol, "Unknown")
    
    def _same_sector_filter(self, s1: str, s2: str) -> bool:
        """Check if two stocks are in the same sector"""
        sector1 = self._get_sector(s1)
        sector2 = self._get_sector(s2)
        return sector1 == sector2 and sector1 != "Unknown"
    
    def _calculate_hurst(self, ts: pd.Series) -> float:
        """Calculate Hurst Exponent"""
        ts = ts.values if isinstance(ts, pd.Series) else ts
        lags = range(2, min(20, len(ts)//2))
        if len(lags) < 2:
            return 0.5
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0] * 2.0
    
    def _calculate_half_life(self, spread: pd.Series) -> float:
        """Calculate half-life of mean reversion"""
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
        result = {'pair': (s1, s2), 'valid': True, 'errors': []}
        
        try:
            clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
            if len(clean) < 30:
                result['valid'] = False
                result['errors'].append("Insufficient data")
                return result
            
            # 1. Correlation
            corr = clean[s1].corr(clean[s2])
            result['correlation'] = round(corr, 4)
            
            # 2. Beta
            beta = np.polyfit(clean[s1], clean[s2], 1)[0]
            result['beta'] = round(beta, 3)
            
            # 3. Spread
            spread = clean[s2] - beta * clean[s1]
            result['spread_mean'] = round(spread.mean(), 2)
            result['spread_std'] = round(spread.std(), 2)
            
            # 4. Cointegration
            coint_score, coint_pval, _ = coint(clean[s1], clean[s2])
            result['coint_pval'] = round(coint_pval, 4)
            
            # 5. ADF
            adf_result = adfuller(spread, autolag='AIC')
            result['adf_pval'] = round(adf_result[1], 4)
            
            # 6. Hurst
            h = self._calculate_hurst(spread)
            result['hurst'] = round(h, 3)
            
            # 7. Half-life
            half_life = self._calculate_half_life(spread)
            result['half_life'] = round(half_life, 1)
            
            # 8. Z-Score (last 20 periods)
            zscore = (spread - spread.rolling(20).mean()) / spread.rolling(20).std()
            result['zscore'] = round(zscore.iloc[-1], 3) if not zscore.empty else 0
            
            # 9. Quality Score
            score = 0
            score += min(abs(corr) * 30, 30)
            score += min((1 - min(coint_pval, 0.1) / 0.1) * 25, 25)
            score += min((1 - min(adf_result[1], 0.1) / 0.1) * 20, 20)
            score += min((1 - min(h, 0.5) / 0.5) * 15, 15)
            score += min((1 - min(half_life, 50) / 50) * 10, 10)
            result['score'] = round(min(score, 100), 1)
            
            # 10. Signal
            result['signal'] = self._generate_signal(zscore.iloc[-1] if not zscore.empty else 0)
            
        except Exception as e:
            result['valid'] = False
            result['errors'].append(str(e))
        
        return result
    
    def _generate_signal(self, zscore: float) -> str:
        """Generate signal based on Z-Score"""
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
        same_sector = filters.get('same_sector', True)
        min_corr = filters.get('min_correlation', 0.7)
        max_coint_pval = filters.get('max_coint_pval', 0.05)
        max_adf_pval = filters.get('max_adf_pval', 0.05)
        max_hurst = filters.get('max_hurst', 0.5)
        max_half_life = filters.get('max_half_life', 50)
        min_beta = filters.get('min_beta', 0.5)
        max_beta = filters.get('max_beta', 2.0)
        
        symbols = list(self.data.columns)
        print(f"\n🔍 Scanning {len(symbols)} stocks...")
        print(f"   Filters: Same Sector={same_sector}, Min Corr={min_corr}")
        
        results = []
        for s1, s2 in combinations(symbols, 2):
            if same_sector and not self._same_sector_filter(s1, s2):
                continue
            
            result = self.analyze_pair(s1, s2)
            if not result['valid']:
                continue
            
            if result.get('correlation', 0) < min_corr:
                continue
            if result.get('coint_pval', 1) > max_coint_pval:
                continue
            if result.get('adf_pval', 1) > max_adf_pval:
                continue
            if result.get('hurst', 1) > max_hurst:
                continue
            if result.get('half_life', 999) > max_half_life:
                continue
            if result.get('beta', 0) < min_beta or result.get('beta', 10) > max_beta:
                continue
            
            results.append(result)
        
        results.sort(key=lambda x: x['score'], reverse=True)
        self.results = results
        return results
    
    def display_results(self, n: int = 10):
        """Display formatted results"""
        if not self.results:
            print("No results to display.")
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