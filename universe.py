"""
universe.py - Filter only NSE Equity stocks
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
        Load ONLY NSE Equity stocks (-EQ)
        """
        if not self.instrument_mgr.is_loaded():
            print("❌ Instruments not loaded")
            return []
        
        print(f"\n🔍 Total symbols in token_map: {len(self.instrument_mgr.token_map)}")
        
        all_symbols = list(self.instrument_mgr.token_map.keys())
        
        self.all_stocks = []
        seen = set()
        
        for symbol in all_symbols:
            # Only keep -EQ stocks
            if not symbol.endswith('-EQ'):
                continue
            
            # Skip if already seen
            if symbol in seen:
                continue
            
            seen.add(symbol)
            self.all_stocks.append(symbol)
        
        print(f"✅ Loaded {len(self.all_stocks)} NSE equity (-EQ) stocks")
        print(f"🔍 Sample stocks: {self.all_stocks[:10]}")
        
        return self.all_stocks
    
    def filter_liquid_stocks(self) -> List[str]:
        """
        Filter liquid stocks from -EQ list
        """
        # F&O Stocks (most liquid)
        fo_stocks = [
            "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS",
            "HINDUNILVR", "ITC", "KOTAKBANK", "LT", "AXISBANK", "WIPRO",
            "MARUTI", "SUNPHARMA", "TITAN", "BAJFINANCE", "BHARTIARTL",
            "ASIANPAINT", "HCLTECH", "NTPC", "ONGC", "POWERGRID",
            "ULTRACEMCO", "NESTLEIND", "M_M", "TATASTEEL", "TECHM",
            "INDUSINDBK", "ADANIPORTS", "GRASIM", "DIVISLAB", "HDFCLIFE",
            "DRREDDY", "EICHERMOT", "SBILIFE", "BPCL", "COALINDIA",
            "BRITANNIA", "HINDALCO", "APOLLOHOSP", "UPL", "TATAMOTORS",
            "CIPLA", "ICICIPRULI", "HDFC", "ADANIENT"
        ]
        
        # Convert to -EQ format
        fo_stocks_eq = [f"{s}-EQ" for s in fo_stocks]
        
        # Filter: only keep those in all_stocks
        self.liquid_stocks = [s for s in fo_stocks_eq if s in self.all_stocks]
        
        # If no liquid stocks, use first 100 -EQ stocks
        if not self.liquid_stocks:
            print("⚠️ No F&O stocks found. Using first 100 -EQ stocks.")
            self.liquid_stocks = self.all_stocks[:100]
        
        print(f"✅ Filtered {len(self.liquid_stocks)} liquid stocks")
        print(f"🔍 Liquid samples: {self.liquid_stocks[:10]}")
        
        return self.liquid_stocks