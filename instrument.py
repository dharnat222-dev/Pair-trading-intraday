"""
instrument.py - Master Contract Manager for Angel One
"""

import json
import requests
import pandas as pd
from typing import Optional, Dict

class InstrumentManager:
    def __init__(self, smartconnect_obj):
        self.obj = smartconnect_obj
        self.token_map: Dict[str, str] = {}
        self.symbol_map: Dict[str, str] = {}
        self._loaded = False
    
    def load_master_contract(self) -> bool:
        """
        Download master contract using REST API
        """
        try:
            print("📥 Downloading master contract...")
            
            # SmartAPI v2 uses REST endpoint for master contract
            url = "https://apiconnect.angelone.in/rest/secure/angelbroking/contract/v1/getMasterContract"
            
            # Headers for API call
            headers = {
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "00:00:00:00:00:00",
                "X-PrivateKey": self.obj.privateKey if hasattr(self.obj, 'privateKey') else "",
                "X-AccessToken": self.obj.access_token if hasattr(self.obj, 'access_token') else "",
                "Accept": "application/json"
            }
            
            params = {
                "segment": "NSE",
                "status": "ACTIVE"
            }
            
            response = requests.post(url, headers=headers, json=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == True and data.get('data'):
                    self._build_maps(data['data'])
                    self._loaded = True
                    print(f"✅ Loaded {len(self.token_map)} symbols")
                    return True
                else:
                    print(f"❌ API Error: {data}")
                    return False
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to load master contract: {e}")
            return False
    
    def _build_maps(self, master_data):
        """Build token maps from master data"""
        self.token_map = {}
        self.symbol_map = {}
        
        for item in master_data:
            symbol = item.get('symbolname', '').upper()
            token = item.get('symboltoken', '')
            if symbol and token:
                self.token_map[symbol] = token
                self.symbol_map[token] = symbol
    
    def get_token(self, symbol: str) -> Optional[str]:
        if not self._loaded:
            print("⚠️ Master contract not loaded.")
            return None
        
        symbol_upper = symbol.upper()
        token = self.token_map.get(symbol_upper)
        
        if token:
            return token
        
        if symbol_upper.endswith('.NS'):
            token = self.token_map.get(symbol_upper[:-3])
            if token:
                return token
        
        print(f"⚠️ Token not found for symbol: {symbol}")
        return None
    
    def get_symbol(self, token: str) -> Optional[str]:
        return self.symbol_map.get(token)
    
    def save_cache(self, filepath: str = "token_cache.json"):
        try:
            with open(filepath, 'w') as f:
                json.dump({
                    'token_map': self.token_map,
                    'symbol_map': self.symbol_map
                }, f)
            print(f"✅ Token cache saved to {filepath}")
        except Exception as e:
            print(f"⚠️ Could not save cache: {e}")
    
    def load_cache(self, filepath: str = "token_cache.json") -> bool:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.token_map = data.get('token_map', {})
                self.symbol_map = data.get('symbol_map', {})
                self._loaded = True
                print(f"✅ Token cache loaded ({len(self.token_map)} symbols)")
                return True
        except:
            return False
    
    def is_loaded(self) -> bool:
        return self._loaded