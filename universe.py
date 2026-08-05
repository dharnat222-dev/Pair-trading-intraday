"""
universe.py - Build trading universe from NSE -EQ stocks
"""

import pandas as pd
import numpy as np
import logging
import sqlite3
import os
from typing import List, Dict, Set, Optional, Tuple

logger = logging.getLogger(__name__)


class StockUniverse:
    def __init__(self, instrument_manager):
        """
        Initialize with instrument manager

        Args:
            instrument_manager: InstrumentManager instance with loaded Scrip Master
        """
        self.instrument_mgr = instrument_manager
        self.all_stocks: List[str] = []
        self.liquid_stocks: List[str] = []
        self.eq_stocks: List[str] = []
        self._loaded = False
        self.db_path = "data/nse_ohlcv.db"

    def load_all_stocks(self) -> List[str]:
        """
        Load ALL NSE equity (-EQ) stocks from Scrip Master

        Returns:
            List of stock symbols (with -EQ suffix)
        """
        if not self.instrument_mgr.is_loaded():
            logger.error("❌ Instruments not loaded. Call load_master_contract() first.")
            return []

        logger.info(f"🔍 Total symbols in token_map: {len(self.instrument_mgr.token_map)}")

        all_symbols = list(self.instrument_mgr.token_map.keys())

        self.eq_stocks = []
        self.all_stocks = []
        seen: Set[str] = set()

        for symbol in all_symbols:
            if not symbol.endswith('-EQ'):
                continue

            if symbol in seen:
                continue

            seen.add(symbol)
            self.eq_stocks.append(symbol)
            self.all_stocks.append(symbol)

        self._loaded = True
        logger.info(f"✅ Loaded {len(self.eq_stocks)} NSE equity (-EQ) stocks")
        logger.info(f"🔍 Sample stocks: {self.eq_stocks[:10]}")

        return self.eq_stocks

    def _get_liquidity_data(self, symbols: List[str], lookback_days: int = 60) -> Dict[str, float]:
        """
        Get average daily traded value for symbols from SQLite cache

        Args:
            symbols: List of stock symbols (with -EQ suffix)
            lookback_days: Number of days to look back

        Returns:
            Dict of {symbol: average_daily_value}
        """
        if not os.path.exists(self.db_path):
            logger.warning("⚠️ SQLite cache not found. No liquidity data available.")
            return {}

        liquidity_data = {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get the latest date range
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(timestamp) FROM daily_ohlcv
                """)
                max_date = cursor.fetchone()[0]

                if max_date is None:
                    logger.warning("⚠️ No data in SQLite cache")
                    return {}

                # Calculate cutoff date
                cutoff_date = pd.Timestamp(max_date) - pd.Timedelta(days=lookback_days)

                # For each symbol, get average daily value
                for symbol in symbols:
                    try:
                        query = """
                            SELECT close, volume
                            FROM daily_ohlcv
                            WHERE symbol = ?
                              AND timestamp >= ?
                            ORDER BY timestamp
                        """
                        df = pd.read_sql_query(query, conn, params=(symbol, cutoff_date))

                        if df.empty or len(df) < 10:
                            continue

                        # Calculate daily value (close * volume)
                        df['value'] = df['close'] * df['volume']
                        avg_value = df['value'].mean()

                        if avg_value > 0 and not pd.isna(avg_value):
                            liquidity_data[symbol] = avg_value

                    except Exception as e:
                        logger.debug(f"Liquidity data error for {symbol}: {e}")
                        continue

        except Exception as e:
            logger.warning(f"⚠️ Error reading SQLite cache: {e}")
            return {}

        return liquidity_data

    def filter_liquid_stocks(self, max_stocks: int = 100, mode: str = "FAST") -> List[str]:
        """
        Filter liquid stocks from -EQ list using SQLite cache data

        Args:
            max_stocks: Maximum number of liquid stocks to return (ignored in FULL mode)
            mode: "FAST" (100), "MEDIUM" (500), or "FULL" (all)

        Returns:
            List of liquid stock symbols (with -EQ suffix)
        """
        if not self._loaded:
            logger.warning("⚠️ Universe not loaded. Call load_all_stocks() first.")
            return []

        # Determine how many stocks to return based on mode
        if mode == "FULL":
            logger.info("🔍 FULL mode: Returning all NSE equity stocks")
            self.liquid_stocks = self.eq_stocks.copy()
            return self.liquid_stocks

        target_count = 500 if mode == "MEDIUM" else 100

        # Try to get liquidity data from SQLite cache
        liquidity_data = self._get_liquidity_data(self.eq_stocks, lookback_days=60)

        if liquidity_data:
            # Sort by average daily value (descending)
            sorted_symbols = sorted(liquidity_data.items(), key=lambda x: x[1], reverse=True)
            sorted_symbols = [symbol for symbol, _ in sorted_symbols]

            # Take top N
            self.liquid_stocks = sorted_symbols[:target_count]

            # If we have enough, return
            if len(self.liquid_stocks) >= target_count:
                logger.info(f"✅ Filtered {len(self.liquid_stocks)} liquid stocks from cache")
                logger.info(f"🔍 Top liquid samples: {self.liquid_stocks[:10]}")
                return self.liquid_stocks

            logger.warning(f"⚠️ Only {len(self.liquid_stocks)} liquid stocks found from cache")

        # Fallback: use hardcoded liquid stocks
        logger.warning("⚠️ Using fallback hardcoded liquid stocks")

        # Hardcoded F&O list (most liquid stocks) - fallback only
        fo_stocks = [
            "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS",
            "HINDUNILVR", "ITC", "KOTAKBANK", "LT", "AXISBANK", "WIPRO",
            "MARUTI", "SUNPHARMA", "TITAN", "BAJFINANCE", "BHARTIARTL",
            "ASIANPAINT", "HCLTECH", "NTPC", "ONGC", "POWERGRID",
            "ULTRACEMCO", "NESTLEIND", "M_M", "TATASTEEL", "TECHM",
            "INDUSINDBK", "ADANIPORTS", "GRASIM", "DIVISLAB", "HDFCLIFE",
            "DRREDDY", "EICHERMOT", "SBILIFE", "BPCL", "COALINDIA",
            "BRITANNIA", "HINDALCO", "APOLLOHOSP", "UPL", "TATAMOTORS",
            "CIPLA", "ICICIPRULI", "HDFC", "ADANIENT", "VEDL",
            "JSWSTEEL", "BAJAJFINSV", "TATACONSUM"
        ]

        fo_stocks_eq = [f"{s}-EQ" for s in fo_stocks]
        self.liquid_stocks = [s for s in fo_stocks_eq if s in self.eq_stocks]

        if len(self.liquid_stocks) > target_count:
            self.liquid_stocks = self.liquid_stocks[:target_count]

        if not self.liquid_stocks:
            logger.warning("⚠️ No liquid stocks found. Using first 100 -EQ stocks.")
            self.liquid_stocks = self.eq_stocks[:target_count]

        logger.info(f"✅ Filtered {len(self.liquid_stocks)} liquid stocks (fallback)")
        logger.info(f"🔍 Liquid samples: {self.liquid_stocks[:10]}")

        return self.liquid_stocks

    def get_all_stocks(self) -> List[str]:
        """Get all NSE equity stocks"""
        if not self._loaded:
            self.load_all_stocks()

        if not self.eq_stocks:
            logger.warning("⚠️ No stocks loaded. Check instrument manager.")

        return self.eq_stocks

    def is_loaded(self) -> bool:
        """Check if universe is loaded"""
        return self._loaded

    def get_liquid_by_mode(self, mode: str = "FAST") -> List[str]:
        """
        Get liquid stocks based on scan mode

        Args:
            mode: "FAST" (100), "MEDIUM" (500), or "FULL" (all)

        Returns:
            List of stock symbols
        """
        if mode == "FULL":
            return self.get_all_stocks()
        elif mode == "MEDIUM":
            return self.filter_liquid_stocks(max_stocks=500, mode=mode)
        else:  # FAST
            return self.filter_liquid_stocks(max_stocks=100, mode=mode)