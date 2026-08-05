"""
pair_engine_v7.py - Professional Pair Selection Engine
Sector Filter: Reject only if both sectors are known and different
"""

import pandas as pd
import numpy as np
import heapq
from itertools import combinations
from statsmodels.tsa.stattools import coint, adfuller
import warnings
import logging
from typing import List, Dict, Optional

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


class PairEngineV7:
    def __init__(
        self,
        data: pd.DataFrame,
        sector_map: dict = None,
        interval: str = "ONE_DAY",
        max_rejected: int = 1000,
        max_results: int = 50000
    ):
        """
        Initialize with OHLC data and optional sector mapping

        Args:
            data: DataFrame with close prices (columns = symbols, index = timestamp)
            sector_map: Dict mapping symbol -> sector
            interval: "ONE_DAY", "ONE_HOUR", "FIVE_MINUTE", "ONE_MINUTE"
            max_rejected: Maximum rejected pairs to keep in memory
            max_results: Maximum valid pairs to keep in memory
        """
        self.data = data
        self.sector_map = sector_map or {}
        self.interval = interval
        self.max_rejected = max_rejected
        self.max_results = max_results
        self.results = []
        self.rejected = []
        self.debug_log = []
        self.stats = {
            'total_pairs': 0,
            'sector_rejected': 0,
            'passed_corr': 0,
            'passed_rolling_corr': 0,
            'passed_beta': 0,
            'passed_coint': 0,
            'passed_adf': 0,
            'passed_hurst': 0,
            'passed_half_life': 0,
            'final_selected': 0
        }
        self._validate_data()

    def _validate_data(self):
        """Validate input data"""
        if self.data.empty:
            raise ValueError("DataFrame is empty!")
        if len(self.data.columns) < 2:
            raise ValueError("Need at least 2 stocks!")
        logger.info(f"✅ Data: {len(self.data)} rows, {len(self.data.columns)} stocks")

        if self.data.isna().any().any():
            logger.warning("⚠️ NaN values found in data")

        if (self.data == np.inf).any().any() or (self.data == -np.inf).any().any():
            logger.warning("⚠️ Infinite values found in data")

    def _get_sector(self, symbol: str) -> str:
        """Get sector for a symbol"""
        clean_symbol = symbol.replace('.NS', '').replace('-EQ', '').strip()
        return self.sector_map.get(clean_symbol, "Unknown")

    def _get_unit(self) -> str:
        """
        Get time unit based on interval
        """
        unit_map = {
            "ONE_DAY": "days",
            "ONE_HOUR": "hours",
            "FIVE_MINUTE": "minutes",
            "ONE_MINUTE": "minutes",
            "TWO_MINUTE": "minutes",
            "THREE_MINUTE": "minutes",
            "FIFTEEN_MINUTE": "minutes",
            "THIRTY_MINUTE": "minutes",
        }
        return unit_map.get(self.interval, "candles")

    def _calculate_hurst(self, ts: pd.Series) -> float:
        """
        Calculate Hurst Exponent with robust error handling
        """
        ts = ts.values if isinstance(ts, pd.Series) else ts

        if len(ts) < 20:
            return 0.5

        try:
            lags = range(2, min(20, len(ts) // 2))
            if len(lags) < 2:
                return 0.5

            tau = []
            for lag in lags:
                diff = np.subtract(ts[lag:], ts[:-lag])
                std_val = np.std(diff)
                if std_val == 0:
                    std_val = 1e-10  # Epsilon to avoid log(0)
                tau.append(std_val)

            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return poly[0] * 2.0

        except Exception as e:
            logger.debug(f"Hurst calculation error: {e}")
            return 0.5

    def _calculate_beta(self, s1: str, s2: str, clean: pd.DataFrame) -> float:
        """
        Calculate Beta using price-level hedge ratio
        """
        try:
            x = clean[s1].values.astype(float)
            y = clean[s2].values.astype(float)

            mask = np.isfinite(x) & np.isfinite(y)
            x = x[mask]
            y = y[mask]

            if len(x) < 10:
                return 1.0

            beta = np.polyfit(x, y, 1)[0]

            if abs(beta) < 0.01:
                return 1.0

            return beta

        except Exception as e:
            logger.debug(f"Beta calculation error: {e}")
            return 1.0

    def _calculate_half_life(self, spread: pd.Series) -> float:
        """
        Calculate Half-life of Mean Reversion with robust error handling
        """
        if len(spread) < 10:
            return 50

        try:
            spread_lag = spread.shift(1).dropna().values
            spread_diff = spread.diff().dropna().values

            min_len = min(len(spread_lag), len(spread_diff))
            if min_len < 5:
                return 50

            spread_lag = spread_lag[:min_len]
            spread_diff = spread_diff[:min_len]

            theta = np.polyfit(spread_lag, spread_diff, 1)[0]

            if theta < 0:
                # Avoid division by zero
                if abs(theta) < 1e-10:
                    return 50
                half_life = -np.log(2) / theta
                if half_life > 500:
                    return 100
                if half_life < 1:
                    return 1
                return half_life
            else:
                return 50

        except Exception as e:
            logger.debug(f"Half-life calculation error: {e}")
            return 50

    def analyze_pair(self, s1: str, s2: str) -> dict:
        """Analyze a pair with full metrics and validation"""
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

            if clean.isna().any().any():
                result['reject_reason'].append("NaN values in data")
                return result

            if (clean[s1] <= 0).any() or (clean[s2] <= 0).any():
                result['reject_reason'].append("Zero or negative prices")
                return result

            # Sector Filter
            sector1 = self._get_sector(s1)
            sector2 = self._get_sector(s2)
            result['debug']['sector'] = f"{sector1} ↔ {sector2}"

            if sector1 != "Unknown" and sector2 != "Unknown" and sector1 != sector2:
                result['reject_reason'].append(f"Sector mismatch: {sector1} vs {sector2}")
                self.stats['sector_rejected'] += 1
                return result

            result['debug']['sector_pass'] = "✅"

            # 1. Correlation
            corr = clean[s1].corr(clean[s2])
            result['metrics']['correlation'] = round(corr, 4)
            result['debug']['corr'] = f"{corr:.3f}"

            if abs(corr) < 0.55:
                result['reject_reason'].append(f"Corr={corr:.3f} < 0.55")
                return result
            result['debug']['corr_pass'] = "✅"
            self.stats['passed_corr'] += 1

            # 2. Rolling Correlation (adaptive window)
            window = min(60, max(20, len(clean) // 3))
            if window >= 20:
                rolling_corr = clean[s1].rolling(window).corr(clean[s2])
                avg_rolling_corr = rolling_corr.mean() if not rolling_corr.empty else 0
            else:
                avg_rolling_corr = corr

            result['metrics']['rolling_corr'] = round(avg_rolling_corr, 4)
            result['debug']['rolling_corr'] = f"{avg_rolling_corr:.3f}"

            if abs(avg_rolling_corr) < 0.40:
                result['reject_reason'].append(f"Rolling Corr={avg_rolling_corr:.3f} < 0.40")
                return result
            result['debug']['rolling_corr_pass'] = "✅"
            self.stats['passed_rolling_corr'] += 1

            # 3. Beta
            beta = self._calculate_beta(s1, s2, clean)
            result['metrics']['beta'] = round(beta, 3)
            result['debug']['beta'] = f"{beta:.2f}"

            if not (0.4 <= beta <= 2.0):
                result['reject_reason'].append(f"Beta={beta:.2f} outside [0.4, 2.0]")
                return result
            result['debug']['beta_pass'] = "✅"
            self.stats['passed_beta'] += 1

            # 4. Spread
            spread = clean[s2] - beta * clean[s1]

            # 5. Cointegration
            if len(clean) < 10:
                result['reject_reason'].append("Insufficient data for cointegration")
                return result

            try:
                coint_score, coint_pval, _ = coint(clean[s1], clean[s2])
                result['metrics']['coint_pval'] = round(coint_pval, 4)
                result['debug']['coint'] = f"{coint_pval:.4f}"

                if coint_pval > 0.10:
                    result['reject_reason'].append(f"Coint p={coint_pval:.4f} > 0.10")
                    return result
                result['debug']['coint_pass'] = "✅"
                self.stats['passed_coint'] += 1

            except Exception as e:
                logger.warning(f"Cointegration error for {s1}-{s2}: {e}")
                result['reject_reason'].append(f"Cointegration error: {e}")
                return result

            # 6. ADF
            try:
                adf_result = adfuller(spread, autolag='AIC')
                adf_pval = adf_result[1]
                result['metrics']['adf_pval'] = round(adf_pval, 4)
                result['debug']['adf'] = f"{adf_pval:.4f}"

                if adf_pval > 0.10:
                    result['reject_reason'].append(f"ADF p={adf_pval:.4f} > 0.10")
                    return result
                result['debug']['adf_pass'] = "✅"
                self.stats['passed_adf'] += 1

            except Exception as e:
                logger.warning(f"ADF error for {s1}-{s2}: {e}")
                result['reject_reason'].append(f"ADF error: {e}")
                return result

            # 7. Hurst
            h = self._calculate_hurst(spread)
            result['metrics']['hurst'] = round(h, 3)
            result['debug']['hurst'] = f"{h:.3f}"

            if h >= 0.50:
                result['reject_reason'].append(f"Hurst={h:.3f} >= 0.50")
                return result
            result['debug']['hurst_pass'] = "✅"
            self.stats['passed_hurst'] += 1

            # 8. Half-life
            half_life = self._calculate_half_life(spread)
            result['metrics']['half_life'] = round(half_life, 1)
            result['debug']['half_life'] = f"{half_life:.1f}"

            if half_life >= 150:
                result['reject_reason'].append(f"Half-life={half_life:.1f} >= 150")
                return result
            result['debug']['half_life_pass'] = "✅"
            self.stats['passed_half_life'] += 1

            # 9. Score
            score = 0
            score += min(abs(corr) * 18, 18)
            score += min(abs(avg_rolling_corr) * 18, 18)
            score += min((1 - min(coint_pval, 0.10) / 0.10) * 18, 18)
            score += min((1 - min(adf_pval, 0.10) / 0.10) * 16, 16)
            score += min((1 - min(h, 0.50) / 0.50) * 15, 15)
            score += min((1 - min(half_life, 150) / 150) * 15, 15)
            result['metrics']['score'] = round(min(score, 100), 1)

            result['valid'] = True
            self.stats['final_selected'] += 1

        except Exception as e:
            logger.error(f"Unexpected error for {s1}-{s2}: {e}")
            result['reject_reason'].append(f"Unexpected error: {str(e)[:50]}")

        return result

    def scan_pairs(self, debug: bool = False) -> list:
        """
        Scan all pairs with filters

        Args:
            debug: If True, store full debug logs (memory heavy)
        """
        symbols = list(self.data.columns)
        total_pairs = len(symbols) * (len(symbols) - 1) // 2

        self.stats = {
            'total_pairs': total_pairs,
            'sector_rejected': 0,
            'passed_corr': 0,
            'passed_rolling_corr': 0,
            'passed_beta': 0,
            'passed_coint': 0,
            'passed_adf': 0,
            'passed_hurst': 0,
            'passed_half_life': 0,
            'final_selected': 0
        }

        if debug and total_pairs > 100000:
            logger.warning(
                f"⚠️ Debug mode ON with {total_pairs:,} pairs. "
                "This may consume significant memory."
            )

        logger.info(f"🔍 Scanning {len(symbols)} stocks for pair selection...")
        logger.info(f"   Total pairs: {total_pairs:,}")
        logger.info(f"   Filters: Corr≥0.55, Beta 0.4-2.0, Hurst<0.50")
        logger.info(f"   Sector Filter: Reject only if both known and different")

        heap = []
        counter = 0
        self.rejected = []
        self.debug_log = []
        checked = 0
        limit_warning_shown = False

        store_debug = debug or total_pairs < 50000

        for s1, s2 in combinations(symbols, 2):
            checked += 1

            if checked % 10000 == 0:
                logger.info(f"  ⏳ Scanning: {checked:,}/{total_pairs:,} pairs...")

            result = self.analyze_pair(s1, s2)

            if store_debug:
                self.debug_log.append(result)

            if result['valid']:
                counter += 1
                score = result['metrics']['score']

                if len(heap) < self.max_results:
                    heapq.heappush(heap, (score, counter, result))
                else:
                    if score > heap[0][0]:
                        heapq.heapreplace(heap, (score, counter, result))
                    elif not limit_warning_shown and len(heap) >= self.max_results:
                        limit_warning_shown = True
                        logger.warning(
                            f"⚠️ Results limit ({self.max_results}) reached. "
                            "Keeping only top scoring pairs."
                        )
            else:
                if len(self.rejected) < self.max_rejected:
                    self.rejected.append(result)

        results = [item[2] for item in heap]
        results.sort(key=lambda x: x['metrics']['score'], reverse=True)

        if not store_debug:
            self.debug_log = self.rejected[:100]

        logger.info(f"  ✅ Scan complete: {len(results):,} pairs selected")

        self.results = results
        return results

    def get_top_pairs(self, n: int = 30) -> list:
        """Get top N pairs from results"""
        return self.results[:n] if self.results else []

    def get_rejected_pairs(self, n: int = 100) -> list:
        """Get rejected pairs"""
        return self.rejected[:n] if self.rejected else []

    def get_stats(self) -> dict:
        """Get selection statistics"""
        return self.stats

    def display_debug_report(self, n: int = 30):
        """Display debug report"""
        if not self.debug_log:
            logger.info("No debug data available.")
            return

        unit = self._get_unit()

        logger.info("\n" + "=" * 110)
        logger.info("📋 DEBUG REPORT")
        logger.info("=" * 110)

        count = 0
        for r in self.debug_log:
            if count >= n:
                break
            s1, s2 = r['pair']
            count += 1

            status = "✅ PASS" if r['valid'] else "❌ FAIL"
            score = r['metrics'].get('score', 0)

            logger.info(f"\n{count}. {s1:12} ↔ {s2:12} [{status}] Score: {score:.1f}")

            corr = r['debug'].get('corr', '0.00')
            rc = r['debug'].get('rolling_corr', '0.00')
            beta = r['debug'].get('beta', '0.00')
            coint_val = r['debug'].get('coint', '1.00')
            adf = r['debug'].get('adf', '1.00')
            hurst = r['debug'].get('hurst', '0.50')
            hl = r['debug'].get('half_life', '999')
            sector = r['debug'].get('sector', 'Unknown')

            logger.info(f"   📈 Corr: {corr} | 🔄 RC: {rc} | 📊 Beta: {beta}")
            logger.info(f"   📉 Coint: {coint_val} | 📈 ADF: {adf} | 🌀 Hurst: {hurst} | ⏱️ HL: {hl} {unit}")
            logger.info(f"   🏢 Sector: {sector}")

            if r['reject_reason']:
                logger.info(f"   ⛔ REJECT: {r['reject_reason'][0]}")

    def display_results(self, n: int = 20):
        """Display selected pairs"""
        if not self.results:
            logger.info("❌ No pairs selected. Check debug report.")
            return

        unit = self._get_unit()

        logger.info("\n" + "=" * 80)
        logger.info(f"🏆 TOP {min(n, len(self.results))} PAIRS SELECTED")
        logger.info("=" * 80)

        for i, r in enumerate(self.results[:n], 1):
            s1, s2 = r['pair']
            m = r['metrics']
            sector1 = self._get_sector(s1)
            sector2 = self._get_sector(s2)
            logger.info(f"\n{i}. {s1:12} ↔ {s2:12} | Score: {m['score']:.1f}")
            logger.info(f"   📈 Corr: {m['correlation']:.3f} | 🔄 RollCorr: {m['rolling_corr']:.3f}")
            logger.info(f"   📉 Coint: {m['coint_pval']:.4f} | 📊 Beta: {m['beta']:.3f}")
            logger.info(f"   🌀 Hurst: {m['hurst']:.3f} | ⏱️ Half-life: {m['half_life']:.1f} {unit}")
            logger.info(f"   🏢 Sectors: {sector1} ↔ {sector2}")

        logger.info("\n" + "=" * 80)
        logger.info(f"✅ Total pairs selected: {len(self.results)}")

    def display_stats(self):
        """Display selection statistics"""
        stats = self.get_stats()
        logger.info("=" * 60)
        logger.info("📊 SELECTION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"  Total pairs scanned: {stats['total_pairs']:,}")
        logger.info(f"  Sector rejected: {stats['sector_rejected']:,}")
        logger.info(f"  Passed Correlation: {stats['passed_corr']:,}")
        logger.info(f"  Passed Rolling Correlation: {stats['passed_rolling_corr']:,}")
        logger.info(f"  Passed Beta: {stats['passed_beta']:,}")
        logger.info(f"  Passed Cointegration: {stats['passed_coint']:,}")
        logger.info(f"  Passed ADF: {stats['passed_adf']:,}")
        logger.info(f"  Passed Hurst: {stats['passed_hurst']:,}")
        logger.info(f"  Passed Half-life: {stats['passed_half_life']:,}")
        logger.info(f"  ✅ Final Selected: {stats['final_selected']:,}")
        logger.info("=" * 60)