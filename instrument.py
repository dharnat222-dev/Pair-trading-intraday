"""
instrument.py - Master Contract Manager for Angel One
"""

import json
import os
import pandas as pd
from typing import Optional, Dict

class InstrumentManager:
    def __init__(self, smartconnect_obj):
        self.obj = smartconnect_obj
        self.token_map: Dict[str, str] = {}
        self.symbol_map: Dict[str, str] = {}
        self._loaded = False
        
    def load_master_contract(self, exchange: str = "NSE") -> bool:
        try:
            print(f"📥 Downloading master contract for {exchange}...")
            
            # 🔧 FIX: Use getMasterContract instead of masterContract
            if hasattr(self.obj, 'getMasterContract'):
                master = self.obj.getMasterContract(exchange)
            else:
                # Fallback: try direct attribute
                master = self.obj.masterContract(exchange)
            
            if not master:
                print("❌ No master contract data received")
                return False
            
            self.token_map = {}
            self.symbol_map = {}
            
            for item in master:
                symbol = item.get('symbol', '').upper()
                token = item.get('token', '')
                if symbol and token:
                    self.token_map[symbol] = token
                    self.symbol_map[token] = symbol
            
            self._loaded = True
            print(f"✅ Loaded {len(self.token_map)} symbols")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load master contract: {e}")
            return False
    
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