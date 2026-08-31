"""Fetch 15-minute NSE candles for the 46-symbol universe. No orders. Never print secrets."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

INTERVAL = "FIFTEEN_MINUTE"
INTERVAL_DB = "15m"
SLEEP = 0.45
SCRIP_URL = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
)
DB = Path("data/intraday_ohlcv.db")
ENV_NAMES = [
    "ANGEL_API_KEY",
    "ANGEL_CLIENT_ID",
    "ANGEL_PASSWORD",
    "ANGEL_TOTP",
    "ANGEL_TOTP_SECRET",
]


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def load_symbols() -> list[str]:
    import universe as u

    for name in ("UNIVERSE", "SYMBOLS", "TICKERS", "NSE_UNIVERSE", "symbols"):
        v = getattr(u, name, None)
        if isinstance(v, (list, tuple)) and len(v) >= 10:
            return [str(x).replace(".NS", "").strip() for x in v]
    for name in ("get_universe", "load_universe"):
        fn = getattr(u, name, None)
        if callable(fn):
            v = fn()
            if isinstance(v, (list, tuple)) and len(v) >= 10:
                return [str(x).replace(".NS", "").strip() for x in v]
    sys.exit("universe.py: symbol list not found")


def tokens_for(symbols: list[str]) -> dict[str, str]:
    print("Downloading Angel scrip master...")
    with urllib.request.urlopen(SCRIP_URL, timeout=60) as resp:
        rows = json.loads(resp.read().decode("utf-8"))
    want = {s.upper() for s in symbols}
    out: dict[str, str] = {}
    for row in rows:
        if row.get("exch_seg") != "NSE":
            continue
        sym = str(row.get("symbol") or "")
        if not sym.endswith("-EQ"):
            continue
        base = sym[:-3]
        if base in want and base not in out:
            out[base] = str(row.get("token"))
    return out


def session_ok(ts: str) -> bool:
    t = ts.replace("T", " ")[11:16]
    return "09:15" <= t <= "15:15"


def init_db() -> sqlite3.Connection:
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS intraday_ohlcv (
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            PRIMARY KEY (symbol, interval, timestamp)
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_intraday_lookup "
        "ON intraday_ohlcv (symbol, interval, timestamp)"
    )
    return con


def login():
    from SmartApi import SmartConnect
    import pyotp

    key = os.getenv("ANGEL_API_KEY") or ""
    cid = os.getenv("ANGEL_CLIENT_ID") or ""
    password = os.getenv("ANGEL_PASSWORD") or ""
    secret = os.getenv("ANGEL_TOTP_SECRET") or ""
    totp = os.getenv("ANGEL_TOTP") or ""
    if not key or not cid or not password:
        sys.exit("CREDENTIALS_MISSING")
    if secret:
        totp = pyotp.TOTP(secret).now()
    if not totp:
        sys.exit("TOTP_MISSING")
    obj = SmartConnect(api_key=key)
    obj.generateSession(cid, password, totp)
    return obj


def candles(obj, token: str) -> list:
    to_dt = datetime.now()
    from_dt = to_dt - timedelta(days=365)
    raw = obj.getCandleData(
        {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": INTERVAL,
            "fromdate": from_dt.strftime("%Y-%m-%d 09:15"),
            "todate": to_dt.strftime("%Y-%m-%d 15:30"),
        }
    )
    return (raw or {}).get("data") or []


def upsert(con: sqlite3.Connection, symbol: str, rows: list) -> int:
    n = 0
    for row in rows:
        ts = str(row[0]).replace("T", " ")[:19]
        if not session_ok(str(row[0])):
            continue
        o, h, l, c = float(row[1]), float(row[2]), float(row[3]), float(row[4])
        vol = int(float(row[5]))
        if min(o, h, l, c) <= 0 or vol < 0:
            continue
        con.execute(
            """
            INSERT OR REPLACE INTO intraday_ohlcv
            (symbol, interval, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol, INTERVAL_DB, ts, o, h, l, c, vol),
        )
        n += 1
    con.commit()
    return n


def main() -> int:
    load_env(Path(".env"))
    print("Env:", ", ".join(f"{n}={'SET' if os.getenv(n) else 'MISSING'}" for n in ENV_NAMES))
    symbols = load_symbols()
    print(f"Universe: {len(symbols)} symbols")
    tokmap = tokens_for(symbols)
    missing = [s for s in symbols if s.upper() not in {k.upper() for k in tokmap}]
    # case-normalize
    upper = {k.upper(): v for k, v in tokmap.items()}
    obj = login()
    con = init_db()
    ok = 0
    for i, sym in enumerate(symbols, 1):
        token = upper.get(sym.upper())
        if not token:
            print(f"[{i}/{len(symbols)}] {sym}: NO_TOKEN")
            continue
        try:
            rows = candles(obj, token)
            n = upsert(con, sym.upper(), rows)
            print(f"[{i}/{len(symbols)}] {sym}: {n} bars")
            ok += 1
        except Exception as exc:
            print(f"[{i}/{len(symbols)}] {sym}: FAIL {exc}")
        time.sleep(SLEEP)
    con.close()
    print("DONE")
    print(f"tokens_ok={ok} no_token={len(missing)} db={DB}")
    print("No orders placed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())