import sqlite3
import pandas as pd
import numpy as np
from sector_map import SECTOR_MAP

START="2025-02-01"
END="2025-12-31"

def sector(sym):
    s=sym.upper()
    for k,v in SECTOR_MAP.items():
        x=str(k).replace(".NS","").replace("-EQ","").strip().upper()
        if x==s:
            return str(v)
    return None

con=sqlite3.connect("data/intraday_ohlcv.db")
df=pd.read_sql_query("""
SELECT symbol,timestamp,open,close
FROM intraday_ohlcv
WHERE interval='15m'
AND substr(timestamp,1,10) BETWEEN ? AND ?
ORDER BY timestamp,symbol
""",con,params=(START,END))
con.close()

df["timestamp"]=pd.to_datetime(df.timestamp)
df["date"]=df.timestamp.dt.strftime("%Y-%m-%d")
df["time"]=df.timestamp.dt.strftime("%H:%M")
df["sector"]=df.symbol.map(sector)
df=df[df.sector.notna()].copy()

# Exclude known special short session.
df=df[df.date!="2025-10-21"]

def at(time, col, name):
    return (
        df[df.time==time][["date","symbol","sector",col]]
        .rename(columns={col:name})
    )

# 09:15 open -> 09:30 close defines opening dislocation.
o915=at("09:15","open","open915")
c930=at("09:30","close","close930")

# Executable price AFTER signal known.
o945=at("09:45","open","entry945")

base=o915.merge(c930,on=["date","symbol","sector"])
base=base.merge(o945,on=["date","symbol","sector"])
base=base[(base.open915>0)&(base.entry945>0)].copy()
base["opening_ret"]=base.close930/base.open915-1

# Pick strongest and weakest stock per sector/day.
base["rank"]=base.groupby(["date","sector"])["opening_ret"].rank(
    method="first"
)
base["n"]=base.groupby(["date","sector"])["symbol"].transform("count")

weak=base[base["rank"]==1].copy()
strong=base[base["rank"]==base["n"]].copy()

pairs=weak[["date","sector","symbol","entry945"]].rename(
    columns={"symbol":"weak","entry945":"weak_entry"}
).merge(
    strong[["date","sector","symbol","entry945"]],
    on=["date","sector"],
    suffixes=("","_strong")
).rename(columns={
    "symbol":"strong",
    "entry945":"strong_entry"
})

pairs=pairs[pairs.weak!=pairs.strong].copy()

# Exact forward closes from 09:45 entry.
future_times={
    "30m":"10:15",
    "60m":"10:45",
    "120m":"11:45",
    "eod":"15:15"
}

for label,t in future_times.items():
    p=df[df.time==t][["date","symbol","close"]]

    w=p.rename(columns={"symbol":"weak","close":f"weak_{label}"})
    s=p.rename(columns={"symbol":"strong","close":f"strong_{label}"})

    pairs=pairs.merge(w,on=["date","weak"],how="left")
    pairs=pairs.merge(s,on=["date","strong"],how="left")

    # Fade = LONG weak + SHORT strong, equal-weight legs.
    weak_ret=pairs[f"weak_{label}"]/pairs.weak_entry-1
    strong_ret=pairs[f"strong_{label}"]/pairs.strong_entry-1

    pairs[f"fade_{label}_bps"]=(weak_ret-strong_ret)*0.5*10000

print("DEVELOPMENT ONLY",START,"to",END)
print("2026 NOT READ")
print("Signal known 09:30 close -> entry 09:45 open")
print("pairs",len(pairs),"sessions",pairs.date.nunique())
print("sectors",pairs.sector.nunique())

for h in ["30m","60m","120m","eod"]:
    z=pairs[f"fade_{h}_bps"].dropna()
    print(
        h,
        "n",len(z),
        "mean",round(z.mean(),2),
        "median",round(z.median(),2),
        "positive%",round((z>0).mean()*100,1),
        "p25",round(z.quantile(.25),1),
        "p75",round(z.quantile(.75),1)
    )

print("\nBY SECTOR — 60m")
q=pairs.groupby("sector")["fade_60m_bps"].agg(
    ["count","mean","median"]
)
print(q.round(2).to_string())

print("\nBY MONTH — 60m")
pairs["month"]=pairs.date.str[:7]
q=pairs.groupby("month")["fade_60m_bps"].agg(
    ["count","mean","median"]
)
print(q.round(2).to_string())

print("\nNO COSTS / NO STOPS / NO TARGETS")
print("DIAGNOSTIC ONLY")