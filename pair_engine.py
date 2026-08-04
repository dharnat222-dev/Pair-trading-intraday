"""
pair_engine.py - Pair Selection Engine
Calculates Correlation, Cointegration, Z-Score, Beta, Spread
Version 1
"""

import pandas as pd
import numpy as np
from itertools import combinations
from statsmodels.tsa.stattools import coint
import warnings
warnings.filterwarnings("ignore")

class PairEngine:
    def __init__(self, data: pd.DataFrame):
        """
        Initialize with OHLC data
        
        Args:
            data: DataFrame with close prices (columns = symbols, index = timestamp)
        """
        self.data = data
        self.results = []
        self._validate_data()
    
    def _validate_data(self):
        """Ensure data is valid"""
        if self.data.empty:
            raise ValueError("DataFrame is empty!")
        if len(self.data.columns) < 2:
            raise ValueError("Need at least 2 stocks for pair trading!")
        print(f"✅ Data loaded: {len(self.data)} rows, {len(self.data.columns)} stocks")
    
    def calculate_correlation(self, s1: str, s2: str) -> float:
        """Calculate Pearson correlation between two stocks"""
        clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
        return clean[s1].corr(clean[s2])
    
    def calculate_beta(self, s1: str, s2: str) -> float:
        """Calculate beta (hedge ratio) between two stocks"""
        clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
        if len(clean) < 2:
            return 1.0
        # Beta = covariance(s1, s2) / variance(s1)
        covariance = np.cov(clean[s1], clean[s2])[0][1]
        variance = np.var(clean[s1])
        return covariance / variance if variance > 0 else 1.0
    
    def calculate_spread(self, s1: str, s2: str, beta: float) -> pd.Series:
        """Calculate spread between two stocks using beta hedge"""
        clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
        spread = clean[s2] - beta * clean[s1]
        return spread
    
    def calculate_zscore(self, spread: pd.Series, window: int = 20) -> pd.Series:
        """Calculate rolling Z-Score of spread"""
        mean = spread.rolling(window).mean()
        std = spread.rolling(window).std()
        return (spread - mean) / std
    
    def cointegration_test(self, s1: str, s2: str) -> tuple:
        """Perform Cointegration test (ADF)"""
        clean = pd.DataFrame({s1: self.data[s1], s2: self.data[s2]}).dropna()
        if len(clean) < 10:
            return None, 1.0
        score, pval, _ = coint(clean[s1], clean[s2])
        return score, pval
    
    def scan_pairs(self, corr_threshold: float = 0.7, pval_threshold: float = 0.05) -> list:
        """
        Scan all pairs for correlation and cointegration
        
        Args:
            corr_threshold: Minimum correlation (0.7 default)
            pval_threshold: Maximum p-value for cointegration (0.05 default)
        
        Returns:
            List of pairs with metrics
        """
        symbols = list(self.data.columns)
        print(f"\n🔍 Scanning {len(symbols)} stocks...")
        total_pairs = len(symbols) * (len(symbols) - 1) // 2
        print(f"   Total pairs to check: {total_pairs}")
        
        results = []
        for s1, s2 in combinations(symbols, 2):
            try:
                # 1. Correlation
                corr = self.calculate_correlation(s1, s2)
                if abs(corr) < corr_threshold:
                    continue
                
                # 2. Cointegration
                score, pval = self.cointegration_test(s1, s2)
                if pval >= pval_threshold:
                    continue
                
                # 3. Beta
                beta = self.calculate_beta(s1, s2)
                
                # 4. Spread & Z-Score
                spread = self.calculate_spread(s1, s2, beta)
                zscore = self.calculate_zscore(spread)
                last_z = zscore.iloc[-1] if not zscore.empty else 0
                
                # 5. Score (higher is better)
                quality_score = (
                    (abs(corr) * 40) +  # 40% weight to correlation
                    ((1 - min(pval, 0.1) / 0.1) * 30) +  # 30% weight to cointegration
                    ((1 - min(abs(last_z), 3) / 3) * 30)  # 30% weight to current Z
                )
                
                results.append({
                    'pair': (s1, s2),
                    'correlation': round(corr, 4),
                    'coint_pval': round(pval, 4),
                    'beta': round(beta, 3),
                    'zscore': round(last_z, 3),
                    'score': round(min(quality_score, 100), 1),
                    'signal': self._generate_signal(last_z)
                })
                
            except Exception as e:
                print(f"⚠️ Error analyzing {s1}-{s2}: {e}")
                continue
        
        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)
        self.results = results
        return results
    
    def _generate_signal(self, zscore: float) -> str:
        """Generate trading signal based on Z-Score"""
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
    
    def get_top_pairs(self, n: int = 10) -> list:
        """Get top N pairs"""
        return self.results[:n]
    
    def display_results(self, n: int = 10):
        """Display formatted results"""
        if not self.results:
            print("No results to display.")
            return
        
        print("\n" + "=" * 70)
        print(f"🏆 TOP {n} PAIRS")
        print("=" * 70)
        
        for i, r in enumerate(self.results[:n], 1):
            s1, s2 = r['pair']
            print(f"\n{i}. {s1:12} ↔ {s2:12} | Score: {r['score']:.1f}")
            print(f"   📈 Correlation: {r['correlation']:.3f}")
            print(f"   📉 Cointegration p-val: {r['coint_pval']:.4f}")
            print(f"   📊 Beta: {r['beta']:.3f}")
            print(f"   🎯 Current Z-Score: {r['zscore']:.3f}")
            print(f"   🚦 Signal: {r['signal']}")
        
        print("\n" + "=" * 70)