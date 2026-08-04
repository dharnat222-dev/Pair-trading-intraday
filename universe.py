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
        """Load all NSE equity stocks from instrument manager"""
        if not self.instrument_mgr.is_loaded():
            print("❌ Instruments not loaded")
            return []
        
        # Get all tokens from NSE segment
        all_tokens = self.instrument_mgr.token_map
        
        # Filter only NSE equity (not derivatives)
        self.all_stocks = []
        for symbol, token in all_tokens.items():
            # Skip if it has special suffixes
            if any(symbol.endswith(suffix) for suffix in ['-BE', '-SM', '-FO']):
                continue
            # Skip if it contains spaces or special chars
            if ' ' in symbol or '&' in symbol:
                continue
            # Keep only clean symbols
            if symbol.isalpha():
                self.all_stocks.append(symbol)
        
        print(f"✅ Loaded {len(self.all_stocks)} NSE equity stocks")
        return self.all_stocks
    
    def filter_liquid_stocks(self, 
                             min_price: float = 50.0,
                             min_volume: int = 100000,
                             min_turnover: float = 1000000) -> List[str]:
        """
        Filter stocks based on liquidity criteria
        """
        # Placeholder: In production, fetch from Angel One LTP/volume
        # For now, use known liquid stocks
        known_liquid = [
            "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS",
            "HINDUNILVR", "ITC", "KOTAKBANK", "LT", "AXISBANK", "WIPRO",
            "MARUTI", "SUNPHARMA", "TITAN", "BAJFINANCE", "BHARTIARTL",
            "ASIANPAINT", "HCLTECH", "NTPC", "ONGC", "POWERGRID",
            "ULTRACEMCO", "NESTLEIND", "M_M", "TATASTEEL", "TECHM",
            "INDUSINDBK", "ADANIPORTS", "GRASIM", "DIVISLAB", "HDFCLIFE",
            "DRREDDY", "EICHERMOT", "SBILIFE", "BPCL", "COALINDIA",
            "BRITANNIA", "HINDALCO", "APOLLOHOSP", "UPL", "TATAMOTORS",
            "CIPLA", "HDFCBANK", "ICICIPRULI"
        ]
        
        self.liquid_stocks = [s for s in known_liquid if s in self.all_stocks]
        print(f"✅ Filtered {len(self.liquid_stocks)} liquid stocks")
        return self.liquid_stocks