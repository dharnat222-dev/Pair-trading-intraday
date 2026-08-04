"""
instrument.py - Master Contract Manager for Angel One
Handles symbol to token mapping
"""

import json
import os
import pandas as pd
from typing import Optional, Dict

class InstrumentManager:
    """
    Manage Angel One instrument master contract
    Provides symbol -> token mapping
    """
    
    def __init__(self, smartconnect_obj):
        """
        Args:
            smartconnect_obj: Logged-in SmartConnect instance
        """
        self.obj = smartconnect_obj
        self.token_map: Dict[str, str] = {}
        self.symbol_map: Dict[str, str] = {}
        self._loaded = False
        
    def load_master_contract(self, exchange: str = "NSE") -> bool:
        """
        Download and cache master contract from Angel One
        
        Returns:
            True if loaded successfully
        """
        try:
            print(f"📥 Downloading master contract for {exchange}...")
            
            # Get master contract from API
            master = self.obj.masterContract(exchange)
            
            if not master:
                print("❌ No master contract data received")
                return False
            
            # Build token maps
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
        """
        Get token for a symbol
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE')
            
        Returns:
            Token string or None if not found
        """
        if not self._loaded:
            print("⚠️ Master contract not loaded. Call load_master_contract() first.")
            return None
        
        # Try direct lookup
        symbol_upper = symbol.upper()
        token = self.token_map.get(symbol_upper)
        
        if token:
            return token
        
        # Try with .NS suffix (for NSE)
        if symbol_upper.endswith('.NS'):
            token = self.token_map.get(symbol_upper[:-3])
            if token:
                return token
        
        print(f"⚠️ Token not found for symbol: {symbol}")
        return None
    
    def get_symbol(self, token: str) -> Optional[str]:
        """Get symbol for a token"""
        if not self._loaded:
            return None
        return self.symbol_map.get(token)
    
    def get_multiple_tokens(self, symbols: list) -> Dict[str, Optional[str]]:
        """Get tokens for multiple symbols"""
        return {sym: self.get_token(sym) for sym in symbols}
    
    def save_cache(self, filepath: str = "token_cache.json"):
        """Save token map to file"""
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
        """Load token map from file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.token_map = data.get('token_map', {})
                self.symbol_map = data.get('symbol_map', {})
                self._loaded = True
                print(f"✅ Token cache loaded from {filepath} ({len(self.token_map)} symbols)")
                return True
        except:
            return False
    
    def is_loaded(self) -> bool:
        return self._loaded


# ========== TEST ==========
if __name__ == "__main__":
    print("Testing InstrumentManager...")