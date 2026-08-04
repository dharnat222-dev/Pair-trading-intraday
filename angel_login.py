"""
Angel One SmartAPI - Real Connection
Supports: Login, Historical Data, LTP, Orders
"""

import os
import time
import logging
from SmartApi import SmartConnect

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AngelBroker:
    def __init__(self, api_key=None, client_id=None, password=None, totp=None):
        """
        Initialize Angel One Broker
        If credentials not provided, read from environment variables
        """
        self.api_key = api_key or os.getenv("ANGEL_API_KEY")
        self.client_id = client_id or os.getenv("ANGEL_CLIENT_ID")
        self.password = password or os.getenv("ANGEL_PASSWORD")
        self.totp = totp or os.getenv("ANGEL_TOTP")
        
        self.obj = None
        self.auth_token = None
        self.refresh_token = None
        self.feed_token = None
        self.is_logged_in = False
        
        # Token cache for symbols
        self.token_cache = {}
    
    def login(self) -> bool:
        """
        Real login to Angel One using SmartAPI
        """
        try:
            print("🔄 Connecting to Angel One...")
            print(f"   Client ID: {self.client_id}")
            
            # Validate credentials
            if not all([self.api_key, self.client_id, self.password, self.totp]):
                print("❌ Missing credentials. Check .env file")
                return False
            
            # Initialize SmartConnect
            self.obj = SmartConnect(api_key=self.api_key)
            
            # Generate session
            response = self.obj.generateSession(
                clientCode=self.client_id,
                password=self.password,
                totp=self.totp
            )
            
            # Check response
            if not response or 'data' not in response:
                print(f"❌ Login failed: {response}")
                return False
            
            # Extract tokens
            data = response['data']
            self.auth_token = data.get('jwtToken')
            self.refresh_token = data.get('refreshToken')
            self.feed_token = self.obj.getfeedToken()
            
            self.is_logged_in = True
            print("✅ Angel One Login Successful!")
            print(f"   Auth Token: {self.auth_token[:30]}...")
            
            # Load master contract for tokens
            self._load_master_contract()
            
            return True
            
        except Exception as e:
            print(f"❌ Login Exception: {e}")
            self.is_logged_in = False
            return False
    
    def _load_master_contract(self):
        """
        Load master contract for symbol tokens
        """
        try:
            if self.obj:
                master = self.obj.masterContract("NSE")
                if master:
                    for item in master:
                        self.token_cache[item['symbol']] = item['token']
                    print(f"✅ Loaded {len(self.token_cache)} symbols")
        except Exception as e:
            print(f"⚠️ Could not load master contract: {e}")
    
    def get_historical(self, symbol: str, interval: str = "ONE_MINUTE", 
                      from_date: str = None, to_date: str = None):
        """
        Fetch historical OHLC data from Angel One
        
        Args:
            symbol: Stock symbol (e.g., "RELIANCE")
            interval: ONE_MINUTE, FIVE_MINUTE, ONE_DAY
            from_date: "YYYY-MM-DD" (default: 30 days ago)
            to_date: "YYYY-MM-DD" (default: today)
        
        Returns:
            DataFrame with OHLC data or None
        """
        if not self.is_logged_in:
            print("⚠️ Not logged in. Call login() first.")
            return None
        
        try:
            import datetime
            
            if not from_date:
                from_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            if not to_date:
                to_date = datetime.datetime.now().strftime("%Y-%m-%d")
            
            response = self.obj.getCandleData(
                exchange="NSE",
                symbol=symbol,
                interval=interval,
                fromdate=from_date,
                todate=to_date
            )
            
            if response and 'data' in response:
                import pandas as pd
                cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                df = pd.DataFrame(response['data'], columns=cols)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                print(f"📊 Fetched {len(df)} candles for {symbol}")
                return df
            else:
                print(f"⚠️ No data for {symbol}")
                return None
                
        except Exception as e:
            print(f"❌ Historical data error for {symbol}: {e}")
            return None
    
    def get_ltp(self, symbol: str) -> float:
        """
        Get Last Traded Price (LTP) from Angel One
        """
        if not self.is_logged_in:
            return None
        
        try:
            response = self.obj.ltpData("NSE", symbol, "")
            if response and 'data' in response:
                ltp = float(response['data']['ltp'])
                print(f"📈 {symbol}: ₹{ltp}")
                return ltp
            return None
        except Exception as e:
            print(f"❌ LTP error for {symbol}: {e}")
            return None
    
    def place_order(self, symbol: str, qty: int, buy_sell: str, 
                   order_type: str = "MARKET", price: float = 0.0) -> dict:
        """
        Place order via Angel One
        
        Args:
            symbol: Stock symbol
            qty: Quantity
            buy_sell: "BUY" or "SELL"
            order_type: "MARKET" or "LIMIT"
            price: Limit price (for LIMIT orders)
        
        Returns:
            Order response dict
        """
        if not self.is_logged_in:
            return {"status": "error", "message": "Not logged in"}
        
        try:
            # Get symbol token
            token = self.token_cache.get(symbol)
            if not token:
                return {"status": "error", "message": f"Token not found for {symbol}"}
            
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": buy_sell.upper(),
                "exchange": "NSE",
                "ordertype": order_type.upper(),
                "producttype": "INTRADAY",
                "duration": "DAY",
                "price": str(price) if price > 0 else "0",
                "quantity": str(qty)
            }
            
            response = self.obj.placeOrder(order_params)
            print(f"✅ Order placed: {symbol} {buy_sell} {qty} @ {price}")
            return response
            
        except Exception as e:
            print(f"❌ Order error: {e}")
            return {"status": "error", "message": str(e)}
    
    def logout(self):
        """Logout from Angel One"""
        try:
            if self.obj:
                self.obj.logout()
                print("🔌 Logged out from Angel One")
        except:
            pass
        self.is_logged_in = False


# ---------- Singleton instance ----------
_broker = None

def get_broker():
    """Get singleton AngelBroker instance"""
    global _broker
    if _broker is None:
        _broker = AngelBroker()
    return _broker


# ---------- Backward compatibility (for existing code) ----------
def connect():
    """Backward compatibility function"""
    broker = get_broker()
    return broker.login()

def get_data(symbol):
    """Backward compatibility function"""
    broker = get_broker()
    return {"symbol": symbol, "price": broker.get_ltp(symbol)}

def disconnect():
    """Backward compatibility function"""
    broker = get_broker()
    broker.logout()