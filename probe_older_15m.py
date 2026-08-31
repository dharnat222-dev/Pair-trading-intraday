"""Read-only Angel 15m historical depth probe. RELIANCE only. No DB writes/orders."""

from datetime import datetime
from pathlib import Path
import os
import time

def load_env(path=".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

load_env()

from SmartApi import SmartConnect
import pyotp

api = os.getenv("ANGEL_API_KEY")
client = os.getenv("ANGEL_CLIENT_ID")
password = os.getenv("ANGEL_PASSWORD")
secret = os.getenv("ANGEL_TOTP_SECRET")

if not all([api, client, password, secret]):
    raise SystemExit("CREDENTIALS_MISSING")

obj = SmartConnect(api_key=api)
obj.generateSession(client, password, pyotp.TOTP(secret).now())

TOKEN = "2885"  # RELIANCE NSE

# Deliberately non-overlapping old windows.
windows = [
    ("2025-02-01 09:15", "2025-04-30 15:15"),
    ("2025-05-01 09:15", "2025-07-31 15:15"),
    ("2025-08-01 09:15", "2025-10-31 15:15"),
    ("2025-11-01 09:15", "2026-01-31 15:15"),
]

print("OLDER_15M_PROBE — READ ONLY — RELIANCE")
print("No DB writes. No orders. Secrets not printed.")

all_rows = []

for start, end in windows:
    try:
        raw = obj.getCandleData({
            "exchange": "NSE",
            "symboltoken": TOKEN,
            "interval": "FIFTEEN_MINUTE",
            "fromdate": start,
            "todate": end,
        })

        rows = (raw or {}).get("data") or []

        if rows:
            print(
                start[:10], "to", end[:10],
                "rows", len(rows),
                "first", rows[0][0],
                "last", rows[-1][0]
            )
            all_rows.extend(rows)
        else:
            print(start[:10], "to", end[:10], "EMPTY")

    except Exception as e:
        # Do not print raw exception because SDK may leak auth headers.
        print(start[:10], "to", end[:10], "REQUEST_FAILED")

    time.sleep(5)

if all_rows:
    timestamps = sorted(str(r[0]) for r in all_rows)
    print("\nEARLIEST_OLD_BAR", timestamps[0])
    print("LATEST_OLD_BAR", timestamps[-1])
    print("TOTAL_ROWS_RETURNED", len(all_rows))
else:
    print("\nNO_OLD_15M_DATA_RETURNED")

print("PROBE_DONE")