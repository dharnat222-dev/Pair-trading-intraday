"""
Pair Trading Scanner - Phase 1: SmartAPI Import Test
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os

print("=" * 60)
print("📊 PAIR TRADING SCANNER - IMPORT TEST")
print("=" * 60)
print(f"Python: {sys.version}")

# ========== TEST 1: SmartAPI Import ==========
print("\n🔍 Testing SmartAPI Import...")

try:
    from SmartApi import SmartConnect
    print("✅ SmartApi imported successfully!")
    print(f"   Module: {SmartConnect}")
except ImportError as e:
    print(f"❌ SmartApi import failed: {e}")
    sys.exit(1)

# ========== TEST 2: Check Environment ==========
print("\n🔍 Checking Environment Variables...")
env_vars = ["ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_PASSWORD", "ANGEL_TOTP"]
for var in env_vars:
    value = os.getenv(var)
    if value:
        # Show only last 4 characters for security
        print(f"  ✅ {var}: {'*' * 8}{value[-4:]}")
    else:
        print(f"  ❌ {var}: Not set")

# ========== TEST 3: Try Simple API Call ==========
print("\n🔍 Testing Simple API Connection...")

try:
    # Only if all environment variables are set
    api_key = os.getenv("ANGEL_API_KEY")
    client_id = os.getenv("ANGEL_CLIENT_ID")
    password = os.getenv("ANGEL_PASSWORD")
    totp = os.getenv("ANGEL_TOTP")
    
    if all([api_key, client_id, password, totp]):
        print("  All credentials are set. Ready for login test.")
    else:
        print("  ⚠️ Some credentials missing. Skipping login test.")
except Exception as e:
    print(f"  ❌ Error checking credentials: {e}")

print("\n" + "=" * 60)
print("✅ Import Test Passed! Ready for next step.")
print("=" * 60)