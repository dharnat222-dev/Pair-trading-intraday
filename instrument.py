"""
instrument.py - Instrument Manager with Raw Data Storage
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
        self._raw_data = []  # Store raw instrument data
    
    def load_master_contract(self) -> bool:
        """
        Load instruments with cache-first strategy
        """
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
        """
        Download Scrip Master JSON from given URL
        """
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
            
            # Store raw data for filtering
            self._raw_data = data
            
            # Build token maps
            self.token_map = {}
            self.symbol_map = {}
            
            for item in data:
                symbol = item.get('symbol', '').upper()
                token = item.get('token', '')
                exchange = item.get('exch_seg', '')
                
                if symbol and token and exchange in ['NSE', 'NSEFO']:
                    self.token_map[symbol] = token
                    self.token_map[f"{symbol}.NS"] = token
                    self.symbol_map[token] = symbol
            
            self._loaded = True
            print(f"✅ Loaded {len(self.token_map)} symbols")
            return True
            
        except Exception as e:
            print(f"❌ Download error: {e}")
            return False
    
    def load_cache(self, filepath: str = "token_cache.json") -> bool:
        """Load token map from cache"""
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
        """Save token map to cache"""
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
        if not self._loaded:
            print("⚠️ Instruments not loaded")
            return None
        
        symbol_upper = symbol.upper()
        token = self.token_map.get(symbol_upper)
        
        if token:
            return token
        
        if symbol_upper.endswith('.NS'):
            token = self.token_map.get(symbol_upper[:-3])
            if token:
                return token
        
        print(f"⚠️ Token not found: {symbol}")
        return None
    
    def get_symbol(self, token: str) -> Optional[str]:
        return self.symbol_map.get(token)
    
    def is_loaded(self) -> bool:
        return self._loaded