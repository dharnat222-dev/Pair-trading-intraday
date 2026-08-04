"""
universe.py - Filter liquid stocks from NSE universe
"""

import pandas as pd
import numpy as np
from typing import List, Dict

class StockUniverse:
    def __init__(self, instrument_manager):
        self.instrument_mgr = instrument_manager
        self.all_stocks = []
        self.liquid_stocks = []
    
    def load_all_stocks(self) -> List[str]:
        """
        Load all NSE equity stocks from instrument manager
        """
        if not self.instrument_mgr.is_loaded():
            print("❌ Instruments not loaded")
            return []
        
        # 🔍 DEBUG: Print all available keys in token_map
        print(f"\n🔍 Total symbols in token_map: {len(self.instrument_mgr.token_map)}")
        
        # Get all symbols from token_map
        all_symbols = list(self.instrument_mgr.token_map.keys())
        
        # 🔍 DEBUG: Print first 20 symbols to understand format
        print(f"🔍 First 20 symbols: {all_symbols[:20]}")
        
        # Filter only NSE equity stocks
        self.all_stocks = []
        for symbol in all_symbols:
            # Skip if it has special suffixes (derivatives)
            if any(symbol.endswith(suffix) for suffix in ['-BE', '-SM', '-FO', '-BZ']):
                continue
            # Skip if it contains spaces or special chars
            if ' ' in symbol or '&' in symbol:
                continue
            # Skip if symbol is too short or contains numbers (may be not equity)
            if len(symbol) < 2:
                continue
            # Keep only clean symbols (alphabetical with possible hyphens)
            if symbol.isalpha() or (symbol.replace('-', '').isalpha() and not symbol.startswith('-')):
                self.all_stocks.append(symbol)
        
        # Also try to get from instrument manager's raw data if available
        if hasattr(self.instrument_mgr, '_raw_data'):
            for item in self.instrument_mgr._raw_data:
                symbol = item.get('symbol', '').upper()
                exchange = item.get('exch_seg', '')
                if exchange in ['NSE', 'NSEFO'] and symbol:
                    if symbol not in self.all_stocks:
                        self.all_stocks.append(symbol)
        
        # 🔍 DEBUG: Print count
        print(f"✅ Loaded {len(self.all_stocks)} NSE equity stocks")
        print(f"🔍 Sample stocks: {self.all_stocks[:10]}")
        
        return self.all_stocks
    
    def filter_liquid_stocks(self, 
                             min_price: float = 50.0,
                             min_volume: int = 100000,
                             min_turnover: float = 1000000) -> List[str]:
        """
        Filter stocks based on liquidity criteria
        """
        # Since we don't have real-time price/volume here,
        # use a list of known liquid stocks as fallback
        known_liquid = [
            "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS",
            "HINDUNILVR", "ITC", "KOTAKBANK", "LT", "AXISBANK", "WIPRO",
            "MARUTI", "SUNPHARMA", "TITAN", "BAJFINANCE", "BHARTIARTL",
            "ASIANPAINT", "HCLTECH", "NTPC", "ONGC", "POWERGRID",
            "ULTRACEMCO", "NESTLEIND", "M_M", "TATASTEEL", "TECHM",
            "INDUSINDBK", "ADANIPORTS", "GRASIM", "DIVISLAB", "HDFCLIFE",
            "DRREDDY", "EICHERMOT", "SBILIFE", "BPCL", "COALINDIA",
            "BRITANNIA", "HINDALCO", "APOLLOHOSP", "UPL", "TATAMOTORS",
            "CIPLA", "ICICIPRULI"
        ]
        
        # Filter: only keep those that exist in our all_stocks list
        self.liquid_stocks = [s for s in known_liquid if s in self.all_stocks]
        
        # If no liquid stocks found, use all stocks as fallback
        if not self.liquid_stocks:
            print("⚠️ No liquid stocks found. Using all stocks as fallback.")
            self.liquid_stocks = self.all_stocks[:100]
        
        print(f"✅ Filtered {len(self.liquid_stocks)} liquid stocks")
        print(f"🔍 Liquid samples: {self.liquid_stocks[:10]}")
        
        return self.liquid_stocks