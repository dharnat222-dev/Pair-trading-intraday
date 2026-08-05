"""
instrument.py - Instrument Manager with Token Lookup and Auto-Refresh
"""

import json
import requests
import os
import time
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class InstrumentManager:
    def __init__(self, smartconnect_obj):
        """
        Initialize with SmartConnect object
        """
        self.obj = smartconnect_obj
        self.token_map: Dict[str, str] = {}
        self.symbol_map: Dict[str, str] = {}
        self._loaded = False
        self.cache_file = "token_cache.json"
        self._raw_data = []
        self.cache_timestamp = 0
        self.cache_max_age = 86400  # 24 hours in seconds
    
    def load_master_contract(self, force_refresh: bool = False) -> bool:
        """
        Load instruments with cache-first strategy and auto-refresh after 24 hours
        
        Args:
            force_refresh: Force download even if cache exists
        """
        if not force_refresh and self._is_cache_valid():
            if self.load_cache():
                logger.info("✅ Using cached instruments (valid)")
                return True
        
        logger.info("📥 Downloading fresh Scrip Master...")
        if self._download_scrip_master():
            self.save_cache()
            self.cache_timestamp = time.time()
            return True
        
        if self.load_cache():
            logger.warning("⚠️ Using cached instruments (download failed)")
            return True
        
        logger.error("❌ CRITICAL: Scrip Master Download Failed")
        logger.error("   Please check:")
        logger.error("   1. Internet connection")
        logger.error("   2. Angel One API access")
        logger.error("   3. URL: https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json")
        return False
    
    def _is_cache_valid(self) -> bool:
        """
        Check if cache file exists and is within 24 hours
        """
        if not os.path.exists(self.cache_file):
            return False
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                timestamp = data.get('_timestamp')
                if timestamp is None:
                    logger.warning("⚠️ Cache missing _timestamp, treating as invalid")
                    return False
                age = time.time() - timestamp
                if age < self.cache_max_age:
                    return True
                logger.info(f"⏰ Cache is {age/3600:.1f} hours old (max: 24 hours)")
                return False
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Cache file corrupted: {e}")
            return False
        except Exception as e:
            logger.debug(f"Cache validation error: {e}")
            return False
    
    def _download_scrip_master(self) -> bool:
        """
        Download Scrip Master JSON from URL
        """
        urls = [
            "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json",
            "https://margincalculator.angelbroking.com/OpenAPI_ScripMaster.json"
        ]
        
        for url in urls:
            response = None
            try:
                response = requests.get(url, timeout=30)
                
                if response.status_code != 200:
                    continue
                
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    logger.warning(f"⚠️ Non-JSON response from {url}")
                    continue
                
                data = response.json()
                if not data:
                    continue
                
                self._raw_data = data
                self.token_map = {}
                self.symbol_map = {}
                
                for item in data:
                    symbol = item.get('symbol', '').upper()
                    token = item.get('token', '')
                    exchange = item.get('exch_seg', '')
                    
                    if symbol and token and exchange in ['NSE', 'NSEFO']:
                        self.token_map[symbol] = token
                        clean_symbol = symbol.replace('-EQ', '').strip()
                        self.token_map[clean_symbol] = token
                        self.token_map[f"{clean_symbol}.NS"] = token
                        self.symbol_map[token] = clean_symbol
                
                self._loaded = True
                logger.info(f"✅ Loaded {len(self.token_map)} symbols")
                return True
                
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Request error from {url}: {e}")
                continue
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON decode error from {url}: {e}")
                if response:
                    logger.debug(f"   Response preview: {response.text[:200]}")
                continue
            except Exception as e:
                logger.error(f"❌ Unexpected error from {url}: {e}")
                continue
            finally:
                if response:
                    response.close()
        
        return False
    
    def load_cache(self, filepath: str = "token_cache.json") -> bool:
        """
        Load token map from cache file
        """
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.token_map = data.get('token_map', {})
                    self.symbol_map = data.get('symbol_map', {})
                    self.cache_timestamp = data.get('_timestamp', 0)
                    self._loaded = True
                    logger.info(f"✅ Cache loaded: {len(self.token_map)} symbols")
                    return True
        except Exception as e:
            logger.warning(f"⚠️ Cache load error: {e}")
        return False
    
    def save_cache(self, filepath: str = "token_cache.json") -> bool:
        """
        Save token map to cache file with timestamp
        """
        try:
            data = {
                'token_map': self.token_map,
                'symbol_map': self.symbol_map,
                '_timestamp': time.time()
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Cache saved: {len(self.token_map)} symbols")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Could not save cache: {e}")
            return False
    
    def get_token(self, symbol: str) -> Optional[str]:
        """
        Get token for a symbol - Supports multiple formats
        """
        if not self._loaded:
            logger.warning("⚠️ Instruments not loaded")
            return None
        
        symbol_upper = symbol.upper()
        
        lookup_formats = [
            symbol_upper,
            f"{symbol_upper}-EQ",
            f"{symbol_upper}.NS",
            symbol_upper.replace('_', '-'),
            f"{symbol_upper}-BE",
        ]
        
        for fmt in lookup_formats:
            token = self.token_map.get(fmt)
            if token:
                return token
        
        matching_keys = [k for k in self.token_map.keys() if symbol_upper in k or k.startswith(symbol_upper)]
        if matching_keys:
            logger.warning(f"⚠️ Token not found for '{symbol}'. Did you mean: {matching_keys[:3]}")
        else:
            logger.warning(f"⚠️ Token not found: {symbol}")
        
        return None
    
    def get_token_fast(self, symbol: str) -> Optional[str]:
        """
        Fast token lookup - auto adds -EQ suffix
        """
        if not self._loaded:
            return None
        
        symbol_upper = symbol.upper()
        
        token = self.token_map.get(symbol_upper)
        if token:
            return token
        
        token = self.token_map.get(f"{symbol_upper}-EQ")
        if token:
            return token
        
        token = self.token_map.get(f"{symbol_upper}.NS")
        if token:
            return token
        
        return None
    
    def get_symbol(self, token: str) -> Optional[str]:
        """
        Get symbol for a token
        """
        return self.symbol_map.get(token)
    
    def is_loaded(self) -> bool:
        """
        Check if instruments are loaded
        """
        return self._loaded
    
    def get_all_symbols(self) -> list:
        """
        Get all symbols from token map
        """
        return list(self.token_map.keys())