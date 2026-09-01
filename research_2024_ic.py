"""2024 research IC only. 24 full-year stocks. No 2025/2026. No orders."""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sector_map import SECTOR_MAP

UNIVERSE = {
    "AXISBANK", "BPCL", "BRITANNIA", "COALINDIA", "EICHERMOT",
    "HCLTECH", "HDFCBANK", "HDFCLIFE", "HINDUNILVR", "ICICIBANK",
    "ICICIPRULI", "INDUSINDBK", "INFY", "ITC", "KOTAKBANK",
    "M&M", "NTPC", "ONGC", "POWERGRID", "RELIANCE",
    "SBILIFE", "SBIN", "TCS", "WIPRO",
}

START = "2024-01-02"
END = "2024-12-31"

FEATURES = [
    "gap", "rel_gap", "opening_ret", "rel_opening_ret",
    "opening_range", "opening_volume_ratio", "prev_return", "prev_range",
    "distance_prev_close", "rel_distance_prev_close",
    "opening_rank", "sector_rel_opening",
]
TARGETS = [
    "ret_30m", "ret_60m", "ret_120m",
    "relret_30m", "relret_60m", "relret_120m",
]


def sector_of(symbol):
    s = str(symbol).upper()
    for k, v in SECTOR_MAP.items():
        kk = str(k).replace(".NS", "").replace("-EQ", "").strip().upper()
        if kk == s:
            return str(v)
    return "UNKNOWN"


con = sqlite3.connect("data/intraday_ohlcv.db")
df = pd.read_sql_query(
    """
    SELECT symbol, timestamp, open, high, low, close, volume
    FROM intraday_ohlcv
    WHERE interval='15m'
      AND substr(timestamp,1,10) BETWEEN '2023-12-01' AND ?
    ORDER BY symbol, timestamp
    """,
    con,
    params=(END,),
)
con.close()

df["timestamp"] = pd.to_datetime(df["timestamp"])
df["date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
df["time"] = df["timestamp"].dt.strftime("%H:%M")
df["symbol"] = df["symbol"].str.upper()
df = df[df["symbol"].isin(UNIVERSE)].copy()
df["sector"] = df["symbol"].map(sector_of)

daily = (
    df.groupby(["symbol", "date"])
    .agg(
        day_open=("open", "first"),
        day_high=("high", "max"),
        day_low=("low", "min"),
        day_close=("close", "last"),
        day_volume=("volume", "sum"),
    )
    .reset_index()
    .sort_values(["symbol", "date"])
)
daily["prev_close"] = daily.groupby("symbol").day_close.shift(1)
daily["prev_open"] = daily.groupby("symbol").day_open.shift(1)
daily["prev_high"] = daily.groupby("symbol").day_high.shift(1)
daily["prev_low"] = daily.groupby("symbol").day_low.shift(1)
daily["prev_volume"] = daily.groupby("symbol").day_volume.shift(1)
daily["prev_return"] = daily.prev_close / daily.prev_open - 1
daily["prev_range"] = daily.prev_high / daily.prev_low - 1


def snap(t, cols, ren):
    x = df[df.time == t][["symbol", "date"] + cols].copy()
    return x.rename(columns=ren)


b0915 = snap(
    "09:15",
    ["open", "high", "low", "close", "volume"],
    {"open": "open915", "high": "h915", "low": "l915", "close": "c915", "volume": "v915"},
)
b0930 = snap(
    "09:30",
    ["open", "high", "low", "close", "volume"],
    {"open": "open930", "high": "h930", "low": "l930", "close": "c930", "volume": "v930"},
)
entry = snap("09:45", ["open"], {"open": "entry945"})

x = daily.merge(b0915, on=["symbol", "date"], how="inner")
x = x.merge(b0930, on=["symbol", "date"], how="inner")
x = x.merge(entry, on=["symbol", "date"], how="inner")
x["sector"] = x["symbol"].map(sector_of)

x = x[
    x.prev_close.notna()
    & (x.prev_close > 0)
    & (x.entry945 > 0)
    & (x.date >= START)
    & (x.date <= END)
].copy()

x["gap"] = x.open915 / x.prev_close - 1
x["opening_ret"] = x.c930 / x.open915 - 1
x["or_high"] = x[["h915", "h930"]].max(axis=1)
x["or_low"] = x[["l915", "l930"]].min(axis=1)
x["opening_range"] = x.or_high / x.or_low - 1
x["opening_volume"] = x.v915 + x.v930
x["opening_volume_ratio"] = x.opening_volume / (x.prev_volume / 25.0)
x["distance_prev_close"] = x.c930 / x.prev_close - 1

for c in ["gap", "opening_ret", "distance_prev_close"]:
    x[f"rel_{c}"] = x[c] - x.groupby("date")[c].transform("mean")

x["sector_open_mean"] = x.groupby(["date", "sector"]).opening_ret.transform("mean")
x["sector_rel_opening"] = x.opening_ret - x.sector_open_mean
x["opening_rank"] = x.groupby("date").opening_ret.rank(pct=True)

for label, t in {"30m": "10:15", "60m": "10:45", "120m": "11:45"}.items():
    p = snap(t, ["close"], {"close": f"px_{label}"})
    x = x.merge(p, on=["symbol", "date"], how="left")
    x[f"ret_{label}"] = x[f"px_{label}"] / x.entry945 - 1
    x[f"relret_{label}"] = x[f"ret_{label}"] - x.groupby("date")[f"ret_{label}"].transform("mean")

x = x.replace([np.inf, -np.inf], np.nan)
assert x.date.max() <= END
assert not any(x.date.str.startswith("2025"))
assert not any(x.date.str.startswith("2026"))

results = []
for feature in FEATURES:
    for target in TARGETS:
        vals = []
        for _, g in x.groupby("date"):
            z = g[[feature, target]].dropna()
            if len(z) < 15:
                continue
            if z[feature].nunique() < 3 or z[target].nunique() < 3:
                continue
            ic = z[feature].rank().corr(z[target].rank())
            if np.isfinite(ic):
                vals.append(ic)
        a = np.asarray(vals, float)
        if not len(a):
            continue
        mean = float(a.mean())
        sd = float(a.std(ddof=1)) if len(a) > 1 else 0.0
        tstat = mean / (sd / np.sqrt(len(a))) if sd > 0 else 0.0
        results.append((abs(mean), feature, target, mean, float(np.median(a)), float((a > 0).mean() * 100), tstat, len(a)))

results.sort(reverse=True)

print("2024_RESEARCH_ONLY")
print("universe", len(UNIVERSE), "rows", len(x), "sessions", x.date.nunique())
print("min", x.date.min(), "max", x.date.max())
print("2025/2026 NOT READ")
print("\nTOP_20_ABS_IC")
for rec in results[:20]:
    _, feature, target, mean, median, pos, tstat, days = rec
    print(
        f"{feature:25s} -> {target:12s} IC {mean:7.4f} median {median:7.4f} pos% {pos:5.1f} t {tstat:6.2f} days {days}"
    )

print("\nTESTS_RUN", len(results))
print("No P&L / no Telegram / no live")
Path("output").mkdir(exist_ok=True)
x.to_csv("output/feature_matrix_2024.csv", index=False)