"""
instrument.py - Instrument Manager with Token Lookup
"""

import json
import requests
import os
from typing import Optional, Dict

class InstrumentManager:
    def __init__(self, smartconnect_obj):
        self.obj = smartconnect_obj
        self.token_map: Dict[str, str] = {}
        self.symbol_map: Dict[str, str] = {}
        self._loaded = False
        self.cache_file = "token_cache.json"
        self._raw_data = []
    
    def load_master_contract(self) -> bool:
        if self.load_cache():
            print("✅ Using cached instruments")
            return True
        
        urls = [
            "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json",
            "https://margincalculator.angelbroking.com/OpenAPI_ScripMaster.json"
        ]
        
        for url in urls:
            print(f"📥 Attempting download from: {url}")
            if self.download_scrip_master(url):
                self.save_cache()
                return True
        
        print("\n❌ CRITICAL: Scrip Master Download Failed")
        return False
    
    def download_scrip_master(self, url: str) -> bool:
        try:
            response = requests.get(url, timeout=15)
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code != 200:
                return False
            
            if 'application/json' not in response.headers.get('Content-Type', ''):
                return False
            
            data = response.json()
            if not data:
                return False
            
            self._raw_data = data
            
            self.token_map = {}
            self.symbol_map = {}
            
            for item in data:
                symbol = item.get('symbol', '').upper()
                token = item.get('token', '')
                exchange = item.get('exch_seg', '')
                
                if symbol and token and exchange in ['NSE', 'NSEFO']:
                    # Store with and without -EQ
                    self.token_map[symbol] = token
                    # Also store clean version (without -EQ)
                    clean_symbol = symbol.replace('-EQ', '').strip()
                    self.token_map[clean_symbol] = token
                    # Store with .NS suffix
                    self.token_map[f"{clean_symbol}.NS"] = token
                    
                    self.symbol_map[token] = clean_symbol
            
            self._loaded = True
            print(f"✅ Loaded {len(self.token_map)} symbols")
            return True
            
        except Exception as e:
            print(f"❌ Download error: {e}")
            return False
    
    def load_cache(self, filepath: str = "token_cache.json") -> bool:
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    self.token_map = data.get('token_map', {})
                    self.symbol_map = data.get('symbol_map', {})
                    self._loaded = True
                    print(f"✅ Cache loaded: {len(self.token_map)} symbols")
                    return True
        except Exception as e:
            print(f"⚠️ Cache load error: {e}")
        return False
    
    def save_cache(self, filepath: str = "token_cache.json") -> bool:
        try:
            with open(filepath, 'w') as f:
                json.dump({
                    'token_map': self.token_map,
                    'symbol_map': self.symbol_map
                }, f)
            print(f"✅ Cache saved: {len(self.token_map)} symbols")
            return True
        except Exception as e:
            print(f"⚠️ Could not save cache: {e}")
            return False
    
    def get_token(self, symbol: str) -> Optional[str]:
        """
        Get token for a symbol - Supports multiple formats
        """
        if not self._loaded:
            print("⚠️ Instruments not loaded")
            return None
        
        symbol_upper = symbol.upper()
        
        # Try all possible formats
        lookup_formats = [
            symbol_upper,                    # "RELIANCE"
            f"{symbol_upper}-EQ",            # "RELIANCE-EQ"
            f"{symbol_upper}.NS",            # "RELIANCE.NS"
            symbol_upper.replace('_', '-'),  # "M_M" → "M-M"
            f"{symbol_upper}-BE",            # "RELIANCE-BE"
        ]
        
        for fmt in lookup_formats:
            token = self.token_map.get(fmt)
            if token:
                return token
        
        # Try partial match
        matching_keys = [k for k in self.token_map.keys() if symbol_upper in k or k.startswith(symbol_upper)]
        if matching_keys:
            print(f"⚠️ Token not found for '{symbol}'. Did you mean: {matching_keys[:3]}")
        else:
            print(f"⚠️ Token not found: {symbol}")
        
        return None
    
    def get_token_fast(self, symbol: str) -> Optional[str]:
        """
        Fast token lookup - auto adds -EQ suffix
        """
        if not self._loaded:
            return None
        
        # Try direct lookup
        token = self.token_map.get(symbol)
        if token:
            return token
        
        # Try with -EQ suffix
        token = self.token_map.get(f"{symbol}-EQ")
        if token:
            return token
        
        # Try with .NS suffix
        token = self.token_map.get(f"{symbol}.NS")
        if token:
            return token
        
        return None
    
    def get_symbol(self, token: str) -> Optional[str]:
        return self.symbol_map.get(token)
    
    def is_loaded(self) -> bool:
        return self._loaded