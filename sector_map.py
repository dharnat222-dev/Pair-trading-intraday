"""
sector_map.py - NSE Stock Sector Mapping
Auto-generates from Scrip Master if available
"""

# ========== HARDCODED SECTORS (Fallback) ==========
SECTOR_MAP = {
    # Energy
    "RELIANCE": "Energy", "ONGC": "Energy", "BPCL": "Energy", 
    "COALINDIA": "Energy", "POWERGRID": "Energy", "NTPC": "Energy",

    # Banking
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking",
    "KOTAKBANK": "Banking", "AXISBANK": "Banking", "INDUSINDBK": "Banking",
    "HDFCLIFE": "Banking", "SBILIFE": "Banking", "ICICIPRULI": "Banking",

    # IT
    "INFY": "IT", "TCS": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT",

    # FMCG
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",

    # Auto
    "MARUTI": "Auto", "TATAMOTORS": "Auto", "M_M": "Auto", "EICHERMOT": "Auto",

    # Pharma
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma", "DIVISLAB": "Pharma",

    # Metals
    "TATASTEEL": "Metals", "HINDALCO": "Metals", "JSWSTEEL": "Metals",

    # Others
    "TITAN": "Consumer", "BAJFINANCE": "Finance", "LT": "Infrastructure",
    "ASIANPAINT": "Consumer", "BHARTIARTL": "Telecom", "ADANIPORTS": "Infrastructure",
    "ULTRACEMCO": "Cement", "APOLLOHOSP": "Healthcare", "UPL": "Agro",
    "GRASIM": "Textiles", "HDFC": "Finance"
}

# ========== AUTO-GENERATE SECTORS ==========
def load_sectors_from_scrip_master(instrument_mgr) -> dict:
    """
    Auto-generate sector mapping from Scrip Master
    """
    sector_map = SECTOR_MAP.copy()
    
    if not instrument_mgr or not instrument_mgr._loaded:
        print("⚠️ Instrument manager not loaded. Using fallback sectors.")
        return sector_map
    
    # Try to get sectors from raw data
    if hasattr(instrument_mgr, '_raw_data') and instrument_mgr._raw_data:
        print("📥 Auto-generating sector map from Scrip Master...")
        
        for item in instrument_mgr._raw_data:
            symbol = item.get('symbol', '').upper()
            sector = item.get('industry', '')
            
            if symbol and sector and symbol not in sector_map:
                sector_map[symbol] = sector
        
        print(f"✅ Sector map expanded: {len(sector_map)} symbols")
    
    return sector_map

def get_sector(symbol: str) -> str:
    """Get sector for a symbol"""
    clean_symbol = symbol.replace('.NS', '').replace('-EQ', '').strip()
    return SECTOR_MAP.get(clean_symbol, "Unknown")