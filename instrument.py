"""
instrument.py - Scrip Master Download from Angel One
"""

import json
import requests
import os
import gzip
from typing import Optional, Dict

class InstrumentManager:
    def __init__(self, smartconnect_obj):
        self.obj = smartconnect_obj
        self.token_map: Dict[str, str] = {}
        self.symbol_map: Dict[str, str] = {}
        self._loaded = False
    
    def download_scrip_master(self) -> bool:
        """
        Download Scrip Master JSON from Angel One
        """
        try:
            print("📥 Downloading Scrip Master...")
            
            # Scrip Master URL (Angel One Open API)
            url = "https://margincalculator.angelbroking.com/OpenAPI_ScripMaster.json"
            
            response = requests.get(url, timeout=30)
            
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            print(f"  Content-Length: {len(response.text)}")
            
            if response.status_code != 200:
                print(f"❌ Download failed: {response.status_code}")
                return False
            
            # Parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                print(f"❌ JSON Parse Error: {e}")
                return False
            
            if not data:
                print("❌ No data received")
                return False
            
            print(f"✅ Downloaded {len(data)} instruments")
            
            # Build token maps
            self.token_map = {}
            self.symbol_map = {}
            
            for item in data:
                symbol = item.get('symbol', '').upper()
                token = item.get('token', '')
                exchange = item.get('exch_seg', '')
                
                if symbol and token and exchange in ['NSE', 'NSEFO']:
                    # Store with multiple formats
                    self.token_map[symbol] = token
                    self.token_map[f"{symbol}.NS"] = token
                    self.symbol_map[token] = symbol
            
            self._loaded = True
            print(f"✅ Loaded {len(self.token_map)} symbols")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Exception: {e}")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
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
        except:
            pass
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
    
    def load_master_contract(self) -> bool:
        """Main method to load instruments"""
        # First try cache
        if self.load_cache():
            return True
        
        # Then download from web
        if self.download_scrip_master():
            self.save_cache()
            return True
        
        return False
    
    def get_token(self, symbol: str) -> Optional[str]:
        """Get token for a symbol"""
        if not self._loaded:
            print("⚠️ Instruments not loaded")
            return None
        
        symbol_upper = symbol.upper()
        token = self.token_map.get(symbol_upper)
        
        if token:
            return token
        
        # Try without .NS suffix
        if symbol_upper.endswith('.NS'):
            token = self.token_map.get(symbol_upper[:-3])
            if token:
                return token
        
        print(f"⚠️ Token not found: {symbol}")
        return None
    
    def get_symbol(self, token: str) -> Optional[str]:
        """Get symbol for a token"""
        return self.symbol_map.get(token)
    
    def is_loaded(self) -> bool:
        return self._loaded