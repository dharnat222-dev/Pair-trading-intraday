"""READ-ONLY 2024 Angel 15m depth probe. RELIANCE only. NO ORDERS / NO DB WRITES."""

from pathlib import Path
import os
import time
import pyotp
from SmartApi import SmartConnect

def load_env():
    p = Path(".env")
    if not p.exists():
        raise SystemExit("CREDENTIALS_MISSING")

    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

load_env()

required = [
    "ANGEL_API_KEY",
    "ANGEL_CLIENT_ID",
    "ANGEL_PASSWORD",
    "ANGEL_TOTP_SECRET"
]

if not all(os.getenv(x) for x in required):
    raise SystemExit("CREDENTIALS_MISSING")

obj = SmartConnect(api_key=os.environ["ANGEL_API_KEY"])
obj.generateSession(
    os.environ["ANGEL_CLIENT_ID"],
    os.environ["ANGEL_PASSWORD"],
    pyotp.TOTP(os.environ["ANGEL_TOTP_SECRET"]).now()
)

TOKEN = "2885"  # RELIANCE NSE

WINDOWS = [
    ("2024-01-01 09:15", "2024-03-31 15:15"),
    ("2024-04-01 09:15", "2024-06-30 15:15"),
    ("2024-07-01 09:15", "2024-09-30 15:15"),
    ("2024-10-01 09:15", "2024-12-31 15:15"),
]

print("2024_15M_PROBE — READ ONLY")
print("RELIANCE ONLY")
print("NO DB WRITES / NO ORDERS")

all_ts = []

for start, end in WINDOWS:
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
            all_ts.extend(str(r[0]) for r in rows)
        else:
            print(start[:10], "to", end[:10], "EMPTY")

    except Exception:
        # Avoid SDK exception dump which may expose auth headers.
        print(start[:10], "to", end[:10], "REQUEST_FAILED")

    time.sleep(5)

if all_ts:
    all_ts.sort()
    print("\nEARLIEST", all_ts[0])
    print("LATEST", all_ts[-1])
    print("TOTAL_ROWS", len(all_ts))
else:
    print("\nNO_2024_DATA")

print("PROBE_DONE")