"""
instrument.py - Instrument Manager with Symbol Normalization
"""

import json
import requests
import os
import re
from typing import Optional, Dict

class InstrumentManager:
    def __init__(self, smartconnect_obj):
        self.obj = smartconnect_obj
        self.token_map: Dict[str, str] = {}
        self.symbol_map: Dict[str, str] = {}
        self._loaded = False
        self.cache_file = "token_cache.json"
    
    def load_master_contract(self) -> bool:
        """Load instruments with cache-first strategy"""
        if self.load_cache():
            print("✅ Using cached instruments")
            return True
        
        # Primary URL
        url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        
        print(f"📥 Downloading Scrip Master...")
        
        try:
            response = requests.get(url, timeout=20)
            
            if response.status_code != 200:
                print(f"❌ Download failed: {response.status_code}")
                self._load_emergency_tokens()
                return True
            
            data = response.json()
            if not data:
                print("❌ No data received")
                self._load_emergency_tokens()
                return True
            
            print(f"✅ Downloaded {len(data)} instruments")
            
            # Build token maps with normalization
            self.token_map = {}
            self.symbol_map = {}
            
            for item in data:
                symbol = item.get('symbol', '').strip()
                token = item.get('token', '')
                exchange = item.get('exch_seg', '')
                
                if not symbol or not token:
                    continue
                
                if exchange not in ['NSE', 'NSEFO']:
                    continue
                
                # 🔧 NORMALIZE: Remove common suffixes
                normalized_symbol = self._normalize_symbol(symbol)
                
                # Store both original and normalized
                self.token_map[symbol] = token
                self.token_map[normalized_symbol] = token
                self.symbol_map[token] = normalized_symbol
            
            self._loaded = True
            print(f"✅ Loaded {len(self.token_map)} tokens")
            
            # 🔍 DEBUG: Check specific symbols
            test_symbols = ["RELIANCE", "HDFCBANK", "ICICIBANK"]
            print("\n🔍 Test symbol lookup:")
            for sym in test_symbols:
                token = self.token_map.get(sym)
                print(f"  {sym} → {token}")
            
            # Find actual keys
            print("\n🔍 Actual keys containing RELIANCE:")
            matches = [k for k in self.token_map.keys() if "RELIANCE" in k]
            print(f"  {matches[:10]}")
            
            self.save_cache()
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            self._load_emergency_tokens()
            return True
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol by removing common suffixes
        
        Examples:
            RELIANCE-EQ → RELIANCE
            HDFCBANK-BE → HDFCBANK
            INFY-NS → INFY
        """
        # Remove common suffixes
        suffixes = ["-EQ", "-BE", "-NS", "-NSE", "-FO", "-BZ", "-SM"]
        normalized = symbol
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
                break
        
        # Remove any trailing hyphens or underscores
        normalized = re.sub(r'[-_]+$', '', normalized)
        
        return normalized.strip()
    
    def _load_emergency_tokens(self):
        """Emergency hardcoded tokens"""
        emergency_tokens = {
            "RELIANCE": "2885", "HDFCBANK": "341", "ICICIBANK": "1333",
            "SBIN": "112", "INFY": "408", "TCS": "512",
            "HINDUNILVR": "1257", "ITC": "1660", "KOTAKBANK": "492",
            "LT": "1395", "AXISBANK": "162", "WIPRO": "1706",
            "MARUTI": "1690", "SUNPHARMA": "1842", "TITAN": "1858"
        }
        
        self.token_map = {}
        self.symbol_map = {}
        
        for symbol, token in emergency_tokens.items():
            self.token_map[symbol] = token
            self.token_map[f"{symbol}.NS"] = token
            self.symbol_map[token] = symbol
        
        self._loaded = True
        print(f"✅ Emergency tokens loaded: {len(self.token_map)} symbols")
    
    def load_cache(self, filepath: str = "token_cache.json") -> bool:
        """Load token map from cache"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    self.token_map = data.get('token_map', {})
                    self.symbol_map = data.get('symbol_map', {})
                    self._loaded = True
                    print(f"✅ Cache loaded: {len(self.token_map)} tokens")
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
            print(f"✅ Cache saved: {len(self.token_map)} tokens")
            return True
        except Exception as e:
            print(f"⚠️ Could not save cache: {e}")
            return False
    
    def get_token(self, symbol: str) -> Optional[str]:
        """Get token for a symbol with multiple lookup attempts"""
        if not self._loaded:
            print("⚠️ Instruments not loaded")
            return None
        
        symbol_upper = symbol.upper()
        
        # Try multiple formats
        lookup_formats = [
            symbol_upper,
            f"{symbol_upper}.NS",
            f"{symbol_upper}-EQ",
            f"{symbol_upper}-BE",
            symbol_upper.replace("_", "-"),
        ]
        
        for fmt in lookup_formats:
            token = self.token_map.get(fmt)
            if token:
                return token
        
        # Try partial match (if symbol is a substring of a key)
        for key, token in self.token_map.items():
            if symbol_upper in key:
                return token
        
        print(f"⚠️ Token not found: {symbol}")
        return None
    
    def get_symbol(self, token: str) -> Optional[str]:
        return self.symbol_map.get(token)
    
    def is_loaded(self) -> bool:
        return self._loaded