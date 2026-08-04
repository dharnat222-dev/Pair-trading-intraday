"""
instrument.py - Master Contract Manager with Debug
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
        self.exchange = "NSE"
    
    def load_master_contract(self) -> bool:
        """
        Download master contract using REST API
        """
        try:
            print("📥 Downloading master contract...")
            
            # 🔧 Get access token from SmartConnect object
            access_token = ""
            private_key = ""
            
            if hasattr(self.obj, 'access_token'):
                access_token = self.obj.access_token
            if hasattr(self.obj, 'privateKey'):
                private_key = self.obj.privateKey
            
            print(f"  Access Token: {access_token[:20] if access_token else 'None'}...")
            print(f"  Private Key: {private_key[:10] if private_key else 'None'}...")
            
            # SmartAPI v2 Master Contract URL
            url = "https://apiconnect.angelone.in/rest/secure/angelbroking/contract/v1/getMasterContract"
            
            headers = {
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "00:00:00:00:00:00",
                "X-PrivateKey": private_key,
                "X-AccessToken": access_token,
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            payload = {
                "segment": self.exchange,
                "status": "ACTIVE"
            }
            
            print(f"\n🔍 Debug Info:")
            print(f"  URL: {url}")
            print(f"  Headers: X-PrivateKey: {private_key[:10] if private_key else 'None'}...")
            print(f"  Payload: {payload}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            print(f"\n📥 Response Debug:")
            print(f"  Status Code: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            print(f"  Content-Length: {len(response.text)}")
            print(f"  First 500 chars: {response.text[:500]}")
            
            if response.status_code != 200:
                print(f"❌ HTTP Error: {response.status_code}")
                return False
            
            # Try to parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                print(f"❌ JSON Parse Error: {e}")
                print(f"  Response Text: {response.text[:200]}")
                return False
            
            if data.get('status') == True and data.get('data'):
                self._build_maps(data['data'])
                self._loaded = True
                print(f"✅ Loaded {len(self.token_map)} symbols")
                return True
            else:
                print(f"❌ API Error: {data}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Exception: {e}")
            return False
        except Exception as e:
            print(f"❌ Failed to load master contract: {e}")
            return False
    
    def _build_maps(self, master_data):
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


# ========== TEST ==========
if __name__ == "__main__":
    print("Testing InstrumentManager...")