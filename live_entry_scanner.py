"""
live_entry_scanner.py - Stage 2: Live Entry Scanner
Monitors selected pairs for entry signals using 5-min Z-Score
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

class LiveEntryScanner:
    def __init__(self, data_fetcher, instrument_manager):
        """
        Initialize with data fetcher and instrument manager
        
        Args:
            data_fetcher: AngelDataFetcher instance
            instrument_manager: InstrumentManager instance
        """
        self.fetcher = data_fetcher
        self.instrument = instrument_manager
        self.selected_pairs = []
        self.signals = []
        self.live_data = {}
    
    def set_pairs(self, pairs: list):
        """
        Set the selected pairs to monitor
        
        Args:
            pairs: List of pairs from PairEngineV7
        """
        self.selected_pairs = pairs
        print(f"📊 Monitoring {len(pairs)} selected pairs")
    
    def fetch_live_data(self, symbols: list, days: int = 3) -> pd.DataFrame:
        """
        Fetch 5-minute data for symbols
        """
        print(f"📊 Fetching 5-min data for {len(symbols)} symbols...")
        
        # Get unique symbols from pairs
        all_symbols = list(set(symbols))
        
        # Fetch 5-minute data (last 3 days)
        close_data = self.fetcher.fetch_close_prices(
            all_symbols,
            interval="FIVE_MINUTE",
            days=days
        )
        
        return close_data
    
    def calculate_spread_zscore(self, data: pd.DataFrame, pair: dict) -> dict:
        """
        Calculate spread and Z-Score for a pair
        
        Args:
            data: OHLC data for both stocks
            pair: Pair dict with beta and other metrics
        
        Returns:
            dict with spread, zscore, signal
        """
        s1, s2 = pair['pair']
        beta = pair['metrics']['beta']
        
        # Get aligned data
        clean = pd.DataFrame({s1: data[s1], s2: data[s2]}).dropna()
        
        if len(clean) < 20:
            return {
                'pair': (s1, s2),
                'error': 'Insufficient data',
                'signal': 'NO_DATA'
            }
        
        # Calculate spread
        spread = clean[s2] - beta * clean[s1]
        
        # Rolling Z-Score (20 periods)
        mean = spread.rolling(20).mean()
        std = spread.rolling(20).std()
        zscore = (spread - mean) / std
        
        # Latest values
        current_z = zscore.iloc[-1] if not zscore.empty else 0
        current_spread = spread.iloc[-1] if not spread.empty else 0
        current_mean = mean.iloc[-1] if not mean.empty else 0
        current_std = std.iloc[-1] if not std.empty else 0
        
        # Generate signal
        signal = self._generate_signal(current_z)
        
        # Entry levels
        entry_z = 2.0
        target_z = 0.0
        stop_loss_z = 3.0
        
        # Price levels
        if current_z > 2.0:
            # BUY s1, SELL s2
            entry_price_leg1 = clean[s1].iloc[-1]
            entry_price_leg2 = clean[s2].iloc[-1]
            target_price_leg1 = clean[s1].iloc[-1] + (clean[s1].std() * 0.5)  # Approx
            target_price_leg2 = clean[s2].iloc[-1] - (clean[s2].std() * 0.5)
            stop_price_leg1 = clean[s1].iloc[-1] - (clean[s1].std() * 0.5)
            stop_price_leg2 = clean[s2].iloc[-1] + (clean[s2].std() * 0.5)
        elif current_z < -2.0:
            # SELL s1, BUY s2
            entry_price_leg1 = clean[s1].iloc[-1]
            entry_price_leg2 = clean[s2].iloc[-1]
            target_price_leg1 = clean[s1].iloc[-1] - (clean[s1].std() * 0.5)
            target_price_leg2 = clean[s2].iloc[-1] + (clean[s2].std() * 0.5)
            stop_price_leg1 = clean[s1].iloc[-1] + (clean[s1].std() * 0.5)
            stop_price_leg2 = clean[s2].iloc[-1] - (clean[s2].std() * 0.5)
        else:
            return {
                'pair': (s1, s2),
                'zscore': current_z,
                'signal': signal,
                'entry': None
            }
        
        return {
            'pair': (s1, s2),
            'zscore': current_z,
            'spread': current_spread,
            'mean': current_mean,
            'std': current_std,
            'signal': signal,
            'entry': {
                'leg1': s1,
                'leg2': s2,
                'entry_price_leg1': round(entry_price_leg1, 2),
                'entry_price_leg2': round(entry_price_leg2, 2),
                'target_price_leg1': round(target_price_leg1, 2),
                'target_price_leg2': round(target_price_leg2, 2),
                'stop_price_leg1': round(stop_price_leg1, 2),
                'stop_price_leg2': round(stop_price_leg2, 2),
                'action': 'BUY' if current_z > 2.0 else 'SELL'
            }
        }
    
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
    
    def scan_all_pairs(self, days: int = 3) -> list:
        """
        Scan all selected pairs for entry signals
        """
        if not self.selected_pairs:
            print("❌ No selected pairs. Call set_pairs() first.")
            return []
        
        # Get all symbols
        all_symbols = []
        for pair in self.selected_pairs:
            all_symbols.extend(pair['pair'])
        all_symbols = list(set(all_symbols))
        
        # Fetch live data
        live_data = self.fetch_live_data(all_symbols, days=days)
        
        if live_data.empty:
            print("❌ No live data fetched")
            return []
        
        print(f"\n🔍 Scanning {len(self.selected_pairs)} pairs for entry signals...")
        
        results = []
        for pair in self.selected_pairs:
            result = self.calculate_spread_zscore(live_data, pair)
            results.append(result)
        
        # Filter only signals
        signals = [r for r in results if r.get('signal') in ['🟢 BUY_LEG1_SELL_LEG2', '🔴 SELL_LEG1_BUY_LEG2']]
        
        self.signals = signals
        return signals
    
    def display_signals(self, signals: list = None):
        """Display entry signals"""
        if signals is None:
            signals = self.signals
        
        if not signals:
            print("\n⚪ No entry signals at this time.")
            return
        
        print("\n" + "=" * 80)
        print(f"🚦 ENTRY SIGNALS ({len(signals)})")
        print("=" * 80)
        
        for i, signal in enumerate(signals, 1):
            s1, s2 = signal['pair']
            z = signal['zscore']
            action = signal['signal']
            
            print(f"\n{i}. {action}")
            print(f"   Pair: {s1} ↔ {s2}")
            print(f"   Z-Score: {z:.3f}")
            
            if signal.get('entry'):
                e = signal['entry']
                print(f"   📊 Entry:")
                print(f"      {e['leg1']}: {e['action']} @ {e['entry_price_leg1']}")
                print(f"      {e['leg2']}: {'SELL' if e['action'] == 'BUY' else 'BUY'} @ {e['entry_price_leg2']}")
                print(f"   🎯 Target:")
                print(f"      {e['leg1']}: {e['target_price_leg1']}")
                print(f"      {e['leg2']}: {e['target_price_leg2']}")
                print(f"   🛑 Stop Loss:")
                print(f"      {e['leg1']}: {e['stop_price_leg1']}")
                print(f"      {e['leg2']}: {e['stop_price_leg2']}")
    
    def run_continuous_scan(self, interval_minutes: int = 5, max_runs: int = 10):
        """
        Run continuous scanning every N minutes
        
        Args:
            interval_minutes: Minutes between scans
            max_runs: Maximum number of scans (None for infinite)
        """
        if not self.selected_pairs:
            print("❌ No selected pairs. Call set_pairs() first.")
            return
        
        print(f"\n🔄 Starting continuous scan every {interval_minutes} minutes...")
        print("   Press Ctrl+C to stop\n")
        
        run_count = 0
        try:
            while max_runs is None or run_count < max_runs:
                run_count += 1
                print(f"\n{'='*60}")
                print(f"📊 Scan #{run_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print('='*60)
                
                signals = self.scan_all_pairs(days=3)
                self.display_signals(signals)
                
                if max_runs is not None and run_count >= max_runs:
                    break
                
                # Wait for next scan
                print(f"\n⏳ Waiting {interval_minutes} minutes for next scan...")
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print("\n🛑 Scan stopped by user")