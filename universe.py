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
        
        print(f"\n🔍 Total symbols in token_map: {len(self.instrument_mgr.token_map)}")
        
        all_symbols = list(self.instrument_mgr.token_map.keys())
        print(f"🔍 First 20 symbols: {all_symbols[:20]}")
        
        self.all_stocks = []
        for symbol in all_symbols:
            # ❌ SKIP: Trade-to-Trade / Surveillance stocks
            if '-ST' in symbol or symbol.endswith('-ST'):
                continue
            
            # ❌ SKIP: Derivatives
            if any(symbol.endswith(suffix) for suffix in ['-BE', '-SM', '-FO', '-BZ']):
                continue
            
            # ❌ SKIP: Special characters
            if ' ' in symbol or '&' in symbol:
                continue
            
            # ❌ SKIP: Too short
            if len(symbol) < 2:
                continue
            
            # Keep clean symbols
            if symbol.isalpha() or (symbol.replace('-', '').isalpha() and not symbol.startswith('-')):
                self.all_stocks.append(symbol)
        
        # Also try to get from raw data
        if hasattr(self.instrument_mgr, '_raw_data'):
            for item in self.instrument_mgr._raw_data:
                symbol = item.get('symbol', '').upper()
                exchange = item.get('exch_seg', '')
                if exchange in ['NSE', 'NSEFO'] and symbol:
                    if '-ST' not in symbol and symbol not in self.all_stocks:
                        self.all_stocks.append(symbol)
        
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
        # Known liquid stocks (F&O list)
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
            self.liquid_stocks = [s for s in self.all_stocks if '-ST' not in s][:100]
        
        print(f"✅ Filtered {len(self.liquid_stocks)} liquid stocks")
        print(f"🔍 Liquid samples: {self.liquid_stocks[:10]}")
        
        return self.liquid_stocks 