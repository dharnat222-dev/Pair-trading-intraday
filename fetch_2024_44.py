"""Resumable old 15m Angel downloader. Historical data only. NO ORDERS."""

import json
import os
import sqlite3
import time
import urllib.request
from pathlib import Path

import pyotp
from SmartApi import SmartConnect
from sector_map import SECTOR_MAP

DB = "data/intraday_ohlcv.db"
SCRIP_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

WINDOWS = [
    ("2024-01-01 09:15", "2024-03-31 15:15"),
    ("2024-04-01 09:15", "2024-06-30 15:15"),
    ("2024-07-01 09:15", "2024-09-30 15:15"),
    ("2024-10-01 09:15", "2024-12-31 15:15"),
]

SKIP = {"HDFC", "TATAMOTORS"}
ALIAS = {"M_M": "M&M"}

def load_env():
    p = Path(".env")
    if not p.exists():
        raise SystemExit("CREDENTIALS_MISSING")
    for line in p.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k,v=line.split("=",1)
        os.environ.setdefault(k.strip(),v.strip())

def universe():
    out=[]
    for x in SECTOR_MAP:
        s=str(x).replace(".NS","").replace("-EQ","").strip()
        if s in SKIP:
            continue
        out.append(ALIAS.get(s,s))
    return out

def tokens(symbols):
    print("Loading Angel scrip master...")
    with urllib.request.urlopen(SCRIP_URL,timeout=60) as r:
        data=json.loads(r.read().decode())
    want={x.upper() for x in symbols}
    out={}
    for row in data:
        if row.get("exch_seg")!="NSE":
            continue
        sym=str(row.get("symbol") or "")
        if not sym.endswith("-EQ"):
            continue
        base=sym[:-3]
        if base.upper() in want:
            out[base.upper()]=str(row.get("token"))
    return out

def login():
    key=os.getenv("ANGEL_API_KEY")
    cid=os.getenv("ANGEL_CLIENT_ID")
    pwd=os.getenv("ANGEL_PASSWORD")
    sec=os.getenv("ANGEL_TOTP_SECRET")
    if not all([key,cid,pwd,sec]):
        raise SystemExit("CREDENTIALS_MISSING")
    obj=SmartConnect(api_key=key)
    obj.generateSession(cid,pwd,pyotp.TOTP(sec).now())
    return obj

def init_db():
    Path("data").mkdir(exist_ok=True)
    con=sqlite3.connect(DB)
    con.execute("""
    CREATE TABLE IF NOT EXISTS intraday_ohlcv(
      symbol TEXT NOT NULL,
      interval TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      open REAL NOT NULL,
      high REAL NOT NULL,
      low REAL NOT NULL,
      close REAL NOT NULL,
      volume INTEGER NOT NULL,
      PRIMARY KEY(symbol,interval,timestamp)
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS old_fetch_progress(
      symbol TEXT NOT NULL,
      window_start TEXT NOT NULL,
      window_end TEXT NOT NULL,
      status TEXT NOT NULL,
      rows INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(symbol,window_start,window_end)
    )
    """)
    con.commit()
    return con

def done(con,sym,start,end):
    r=con.execute("""
      SELECT status FROM old_fetch_progress
      WHERE symbol=? AND window_start=? AND window_end=?
    """,(sym,start,end)).fetchone()
    return bool(r and r[0]=="DONE")

def mark(con,sym,start,end,status,n):
    con.execute("""
      INSERT OR REPLACE INTO old_fetch_progress
      (symbol,window_start,window_end,status,rows)
      VALUES(?,?,?,?,?)
    """,(sym,start,end,status,n))
    con.commit()

def save(con,sym,rows):
    n=0
    for r in rows:
        try:
            ts=str(r[0]).replace("T"," ")[:19]
            hh=ts[11:16]
            if not ("09:15" <= hh <= "15:15"):
                continue
            o,h,l,c=map(float,r[1:5])
            vol=int(float(r[5]))
            if min(o,h,l,c)<=0 or vol<0:
                continue
            con.execute("""
              INSERT OR REPLACE INTO intraday_ohlcv
              (symbol,interval,timestamp,open,high,low,close,volume)
              VALUES(?,?,?,?,?,?,?,?)
            """,(sym,"15m",ts,o,h,l,c,vol))
            n+=1
        except Exception:
            continue
    con.commit()
    return n

def fetch_with_retry(obj,token,start,end):
    waits=[0,10,20,40,60]
    for attempt,wait in enumerate(waits,1):
        if wait:
            print(f"    retry wait {wait}s")
            time.sleep(wait)
        try:
            raw=obj.getCandleData({
                "exchange":"NSE",
                "symboltoken":token,
                "interval":"FIFTEEN_MINUTE",
                "fromdate":start,
                "todate":end,
            })
            rows=(raw or {}).get("data") or []
            return rows, True
        except Exception:
            # Never print SDK exception; it may contain auth headers.
            print(f"    request failed attempt {attempt}/{len(waits)}")
    return [],False

def main():
    load_env()
    syms=universe()
    print("OLD_15M_FETCH — NO ORDERS")
    print("symbols",len(syms),"windows",len(WINDOWS))
    tok=tokens(syms)
    obj=login()
    con=init_db()

    for si,sym in enumerate(syms,1):
        token=tok.get(sym.upper())
        if not token:
            print(f"[{si}/{len(syms)}] {sym}: NO_TOKEN")
            continue

        for wi,(start,end) in enumerate(WINDOWS,1):
            if done(con,sym,start,end):
                print(f"[{si}/{len(syms)}] {sym} W{wi}: SKIP_DONE")
                continue

            print(f"[{si}/{len(syms)}] {sym} W{wi}: fetching")
            time.sleep(5)

            rows,ok=fetch_with_retry(obj,token,start,end)

            if not ok:
                mark(con,sym,start,end,"FAILED",0)
                print("    FAILED")
                continue

            n=save(con,sym,rows)
            mark(con,sym,start,end,"DONE",n)
            print(f"    DONE rows={n}")

    print("\nCOVERAGE")
    q=con.execute("""
      SELECT symbol,MIN(timestamp),MAX(timestamp),COUNT(*)
      FROM intraday_ohlcv
      WHERE interval='15m'
      GROUP BY symbol
      ORDER BY symbol
    """).fetchall()

    for r in q:
        print(r)

    failed=con.execute("""
      SELECT COUNT(*) FROM old_fetch_progress WHERE status='FAILED'
    """).fetchone()[0]

    print("symbols_cached",len(q))
    print("failed_chunks",failed)
    print("FETCH_COMPLETE")
    print("NO ORDERS / NO BACKTEST")

    con.close()

if __name__=="__main__":
    main()