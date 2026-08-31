"""Retry only missing 15m symbols. No orders. Never print secrets."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import fetch_intraday_cache as f
from sector_map import SECTOR_MAP

SKIP = {"HDFC"}
ALIAS = {"M_M": "M&M"}


def main() -> None:
    f.load_env(Path(".env"))
    con = sqlite3.connect("data/intraday_ohlcv.db")
    have = {
        r[0].upper()
        for r in con.execute(
            "SELECT symbol FROM intraday_ohlcv GROUP BY symbol HAVING COUNT(*) > 100"
        )
    }
    print("already", len(have))
    want = []
    for x in SECTOR_MAP:
        s = str(x).replace(".NS", "").replace("-EQ", "").strip()
        if s in SKIP:
            continue
        want.append(ALIAS.get(s, s))
    need = [s for s in want if s.upper() not in have]
    print("need", len(need), need)
    if not need:
        print("RETRY_DONE nothing_missing")
        return
    tokmap = {k.upper(): v for k, v in f.tokens_for(need).items()}
    obj = f.login()
    for i, sym in enumerate(need, 1):
        token = tokmap.get(sym.upper())
        if not token:
            print(f"[{i}/{len(need)}] {sym}: NO_TOKEN")
            continue
        time.sleep(2.5)
        try:
            rows = f.candles(obj, token)
            n = f.upsert(con, sym.upper(), rows)
            print(f"[{i}/{len(need)}] {sym}: {n} bars")
        except Exception as exc:
            print(f"[{i}/{len(need)}] {sym}: FAIL {exc}")
            time.sleep(10)
    con.close()
    print("RETRY_DONE")


if __name__ == "__main__":
    main()