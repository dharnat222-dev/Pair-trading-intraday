"""Fetch daily NSE candles for pair selection. No orders. Never print secrets."""
from __future__ import annotations

import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import fetch_intraday_cache as f
from sector_map import SECTOR_MAP

SKIP = {"HDFC", "TATAMOTORS"}
ALIAS = {"M_M": "M&M"}
DB = Path("data/nse_ohlcv.db")
SLEEP = 2.5


def init_db() -> sqlite3.Connection:
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_ohlcv (
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            PRIMARY KEY (symbol, timestamp)
        )
        """
    )
    return con


def daily_candles(obj, token: str) -> list:
    to_dt = datetime.now()
    from_dt = to_dt - timedelta(days=800)
    raw = obj.getCandleData(
        {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": "ONE_DAY",
            "fromdate": from_dt.strftime("%Y-%m-%d 09:15"),
            "todate": to_dt.strftime("%Y-%m-%d 15:30"),
        }
    )
    return (raw or {}).get("data") or []


def upsert(con: sqlite3.Connection, symbol: str, rows: list) -> int:
    n = 0
    for row in rows:
        ts = str(row[0]).replace("T", " ")[:10]
        o, h, l, c = float(row[1]), float(row[2]), float(row[3]), float(row[4])
        vol = int(float(row[5]))
        if min(o, h, l, c) <= 0 or vol < 0:
            continue
        con.execute(
            """
            INSERT OR REPLACE INTO daily_ohlcv
            (symbol, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol, ts, o, h, l, c, vol),
        )
        n += 1
    con.commit()
    return n


def symbols() -> list[str]:
    out = []
    for x in SECTOR_MAP:
        s = str(x).replace(".NS", "").replace("-EQ", "").strip()
        if s in SKIP:
            continue
        out.append(ALIAS.get(s, s))
    return out


def main() -> int:
    f.load_env(Path(".env"))
    want = symbols()
    print("Universe daily:", len(want))
    tokmap = {k.upper(): v for k, v in f.tokens_for(want).items()}
    obj = f.login()
    con = init_db()
    for i, sym in enumerate(want, 1):
        token = tokmap.get(sym.upper())
        if not token:
            print(f"[{i}/{len(want)}] {sym}: NO_TOKEN")
            continue
        time.sleep(SLEEP)
        try:
            rows = daily_candles(obj, token)
            n = upsert(con, sym.upper(), rows)
            print(f"[{i}/{len(want)}] {sym}: {n} days")
        except Exception as exc:
            print(f"[{i}/{len(want)}] {sym}: FAIL {exc}")
            time.sleep(10)
    nsym = con.execute("SELECT COUNT(DISTINCT symbol) FROM daily_ohlcv").fetchone()[0]
    con.close()
    print("DAILY_DONE symbols=", nsym, "db=", DB)
    print("No orders placed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())