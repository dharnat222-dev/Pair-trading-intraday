import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np
from sector_map import SECTOR_MAP

RESEARCH_END = "2025-08-31"
SPECIAL_EXCLUDE = {"2025-10-21"}

def sector_of(symbol):
    s = str(symbol).upper()
    for k, v in SECTOR_MAP.items():
        kk = str(k).replace(".NS","").replace("-EQ","").strip().upper()
        if kk == s:
            return str(v)
    return "UNKNOWN"

con = sqlite3.connect("data/intraday_ohlcv.db")
df = pd.read_sql_query("""
SELECT symbol,timestamp,open,high,low,close,volume
FROM intraday_ohlcv
WHERE interval='15m'
AND substr(timestamp,1,10) <= ?
ORDER BY symbol,timestamp
""", con, params=(RESEARCH_END,))
con.close()

df["timestamp"] = pd.to_datetime(df.timestamp)
df["date"] = df.timestamp.dt.strftime("%Y-%m-%d")
df["time"] = df.timestamp.dt.strftime("%H:%M")
df = df[~df.date.isin(SPECIAL_EXCLUDE)].copy()
df["sector"] = df.symbol.map(sector_of)

# Session-level previous day features.
daily = df.groupby(["symbol","date"]).agg(
    day_open=("open","first"),
    day_high=("high","max"),
    day_low=("low","min"),
    day_close=("close","last"),
    day_volume=("volume","sum")
).reset_index().sort_values(["symbol","date"])

daily["prev_close"] = daily.groupby("symbol").day_close.shift(1)
daily["prev_open"] = daily.groupby("symbol").day_open.shift(1)
daily["prev_high"] = daily.groupby("symbol").day_high.shift(1)
daily["prev_low"] = daily.groupby("symbol").day_low.shift(1)
daily["prev_volume"] = daily.groupby("symbol").day_volume.shift(1)

daily["prev_return"] = daily.prev_close / daily.prev_open - 1
daily["prev_range"] = daily.prev_high / daily.prev_low - 1

def snap(t, cols, ren):
    x = df[df.time == t][["symbol","date"] + cols].copy()
    return x.rename(columns=ren)

b0915 = snap("09:15",
             ["open","high","low","close","volume"],
             {"open":"open915","high":"h915","low":"l915",
              "close":"c915","volume":"v915"})

b0930 = snap("09:30",
             ["open","high","low","close","volume"],
             {"open":"open930","high":"h930","low":"l930",
              "close":"c930","volume":"v930"})

entry = snap("09:45", ["open"], {"open":"entry945"})

x = daily.merge(b0915,on=["symbol","date"],how="inner")
x = x.merge(b0930,on=["symbol","date"],how="inner")
x = x.merge(entry,on=["symbol","date"],how="inner")

x = x[
    x.prev_close.notna() &
    (x.prev_close > 0) &
    (x.entry945 > 0)
].copy()

# Features available by 09:30 close.
x["gap"] = x.open915 / x.prev_close - 1
x["opening_ret"] = x.c930 / x.open915 - 1

x["or_high"] = x[["h915","h930"]].max(axis=1)
x["or_low"] = x[["l915","l930"]].min(axis=1)
x["opening_range"] = x.or_high / x.or_low - 1

x["opening_volume"] = x.v915 + x.v930
x["opening_volume_ratio"] = (
    x.opening_volume / (x.prev_volume / 25.0)
).replace([np.inf,-np.inf],np.nan)

x["distance_prev_close"] = x.c930 / x.prev_close - 1

# Market-relative features.
for c in ["gap","opening_ret","distance_prev_close"]:
    market = x.groupby("date")[c].transform("mean")
    x[f"rel_{c}"] = x[c] - market

# Sector-relative opening move.
x["sector_open_mean"] = x.groupby(
    ["date","sector"]
).opening_ret.transform("mean")

x["sector_rel_opening"] = x.opening_ret - x.sector_open_mean

# Cross-sectional rank.
x["opening_rank"] = x.groupby("date").opening_ret.rank(pct=True)

# Forward target prices.
future_times = {
    "30m":"10:15",
    "60m":"10:45",
    "120m":"11:45",
}

for label,t in future_times.items():
    p = snap(t, ["close"], {"close":f"px_{label}"})
    x = x.merge(p,on=["symbol","date"],how="left")
    x[f"ret_{label}"] = x[f"px_{label}"] / x.entry945 - 1

    market = x.groupby("date")[f"ret_{label}"].transform("mean")
    x[f"relret_{label}"] = x[f"ret_{label}"] - market

features = [
    "gap",
    "rel_gap",
    "opening_ret",
    "rel_opening_ret",
    "opening_range",
    "opening_volume_ratio",
    "prev_return",
    "prev_range",
    "distance_prev_close",
    "rel_distance_prev_close",
    "opening_rank",
    "sector_rel_opening",
]

targets = [
    "ret_30m","ret_60m","ret_120m",
    "relret_30m","relret_60m","relret_120m",
]

keep = ["date","symbol","sector","entry945"] + features + targets
out = x[keep].replace([np.inf,-np.inf],np.nan).copy()

# Research boundary assertion.
assert out.date.max() <= RESEARCH_END
assert not any(out.date.str.startswith("2026"))

Path("output").mkdir(exist_ok=True)
out.to_csv("output/intraday_feature_matrix_research.csv", index=False)

print("FEATURE_MATRIX_RESEARCH_ONLY")
print("rows",len(out))
print("sessions",out.date.nunique())
print("symbols",out.symbol.nunique())
print("min_date",out.date.min())
print("max_date",out.date.max())
print("features",len(features))
print("targets",len(targets))

print("\nMISSING %")
for c in features + targets:
    print(c, round(out[c].isna().mean()*100,2))

print("\nWROTE output/intraday_feature_matrix_research.csv")
print("NO STRATEGY / NO P&L / 2026 NOT READ")