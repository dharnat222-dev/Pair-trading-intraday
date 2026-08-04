"""
sector_map.py - NSE Stock Sector Mapping
"""

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
    
    # Real Estate
    "TITAN": "Consumer", "BAJFINANCE": "Finance", "LT": "Infrastructure",
    "ASIANPAINT": "Consumer", "BHARTIARTL": "Telecom", "ADANIPORTS": "Infrastructure",
    "ULTRACEMCO": "Cement", "APOLLOHOSP": "Healthcare", "UPL": "Agro",
    "GRASIM": "Textiles", "HDFC": "Finance"
}

def get_sector(symbol: str) -> str:
    """Get sector for a symbol"""
    clean_symbol = symbol.replace('.NS', '').replace('-EQ', '').strip()
    return SECTOR_MAP.get(clean_symbol, "Unknown")