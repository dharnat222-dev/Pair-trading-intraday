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
        if not self.instrument_mgr.is_loaded():
            print("❌ Instruments not loaded")
            return []
        
        print(f"\n🔍 Total symbols in token_map: {len(self.instrument_mgr.token_map)}")
        
        all_symbols = list(self.instrument_mgr.token_map.keys())
        print(f"🔍 First 20 symbols: {all_symbols[:20]}")
        
        self.all_stocks = []
        seen = set()
        
        for symbol in all_symbols:
            # Skip indices
            if any(x in symbol for x in ['NIFTY', 'SENSEX', 'BANK', 'MIDCAP']):
                continue
            
            # Skip derivatives
            if any(symbol.endswith(suffix) for suffix in ['-BE', '-SM', '-FO', '-BZ']):
                continue
            
            # Skip ST stocks
            if '-ST' in symbol or symbol.endswith('-ST'):
                continue
            
            # Skip special chars
            if ' ' in symbol or '&' in symbol:
                continue
            
            if len(symbol) < 2:
                continue
            
            # Clean symbol
            clean_symbol = symbol.replace('-EQ', '').strip()
            
            if clean_symbol in seen:
                continue
            
            if clean_symbol.replace('.', '').replace('-', '').isalnum():
                seen.add(clean_symbol)
                self.all_stocks.append(clean_symbol)
        
        print(f"✅ Loaded {len(self.all_stocks)} NSE equity stocks")
        print(f"🔍 Sample stocks: {self.all_stocks[:10]}")
        
        return self.all_stocks
    
    def filter_liquid_stocks(self) -> List[str]:
        """
        Filter liquid stocks - Use F&O list + high volume stocks
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
            "CIPLA", "ICICIPRULI", "HDFC", "ADANIENT", "VEDL", 
            "JSWSTEEL", "HDFC", "BAJAJFINSV", "TATACONSUM"
        ]
        
        # Filter: only keep those in all_stocks
        self.liquid_stocks = [s for s in fo_stocks if s in self.all_stocks]
        
        # If no liquid stocks, use all stocks as fallback
        if not self.liquid_stocks:
            print("⚠️ No F&O stocks found. Using all stocks as fallback.")
            self.liquid_stocks = self.all_stocks[:500]
        
        print(f"✅ Filtered {len(self.liquid_stocks)} liquid stocks")
        print(f"🔍 Liquid samples: {self.liquid_stocks[:10]}")
        
        return self.liquid_stocks