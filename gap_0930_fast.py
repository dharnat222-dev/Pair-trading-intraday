import sqlite3
import pandas as pd
import numpy as np

START = "2026-02-13"
END = "2026-06-30"

con = sqlite3.connect("data/intraday_ohlcv.db")
df = pd.read_sql_query("""
SELECT symbol,timestamp,open,close
FROM intraday_ohlcv
WHERE interval='15m'
AND substr(timestamp,1,10) <= ?
ORDER BY timestamp,symbol
""", con, params=(END,))
con.close()

df["timestamp"] = pd.to_datetime(df["timestamp"])
df["date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
df["time"] = df["timestamp"].dt.strftime("%H:%M")

# Previous trading-session close for every symbol.
daily_close = (
    df.sort_values("timestamp")
      .groupby(["symbol","date"], as_index=False)
      .tail(1)[["symbol","date","close"]]
      .sort_values(["symbol","date"])
)
daily_close["prev_close"] = daily_close.groupby("symbol")["close"].shift(1)

# Today's 09:15 open.
op0915 = (
    df[df["time"] == "09:15"][["symbol","date","open"]]
    .rename(columns={"open":"gap_open"})
)

# Executable 09:30 open.
op0930 = (
    df[df["time"] == "09:30"][["symbol","date","open"]]
    .rename(columns={"open":"entry"})
)

x = (
    daily_close[["symbol","date","prev_close"]]
    .merge(op0915, on=["symbol","date"], how="inner")
    .merge(op0930, on=["symbol","date"], how="inner")
)

x = x[
    (x["date"] >= START) &
    (x["date"] <= END) &
    (x["prev_close"] > 0) &
    (x["gap_open"] > 0) &
    (x["entry"] > 0)
].copy()

x["gap"] = x["gap_open"] / x["prev_close"] - 1
x["market_gap"] = x.groupby("date")["gap"].transform("mean")
x["rel_gap"] = x["gap"] - x["market_gap"]

x["rank"] = x.groupby("date")["rel_gap"].rank(method="first", pct=True)
x["group"] = np.where(
    x["rank"] <= .20, "NEG_GAP_Q",
    np.where(x["rank"] > .80, "POS_GAP_Q", "MIDDLE")
)

x = x[x["group"] != "MIDDLE"].copy()

# Create exact future-price lookup.
prices = df[
    (df["date"] >= START) &
    (df["date"] <= END)
][["symbol","date","time","close"]].copy()

for label, time_str in [
    ("30m","10:00"),
    ("60m","10:30"),
    ("120m","11:30"),
    ("eod","15:15"),
]:
    p = (
        prices[prices["time"] == time_str]
        [["symbol","date","close"]]
        .rename(columns={"close":f"px_{label}"})
    )

    x = x.merge(p, on=["symbol","date"], how="left")

    x[f"raw_{label}"] = x[f"px_{label}"] / x["entry"] - 1
    x[f"market_{label}"] = x.groupby("date")[f"raw_{label}"].transform("mean")
    x[f"rel_{label}"] = x[f"raw_{label}"] - x[f"market_{label}"]

print("DEVELOPMENT ONLY:", START, "to", END)
print("JULY-AUGUST OOS NOT READ")
print("ENTRY = 09:30 OPEN")
print("sessions", x["date"].nunique(), "observations", len(x))

print("\nGROUP COUNTS")
print(x["group"].value_counts().to_string())

for grp in ["POS_GAP_Q","NEG_GAP_Q"]:
    y = x[x["group"] == grp]

    print("\n"+grp, "n=", len(y))
    print(
        "median relative gap bps",
        round(y["rel_gap"].median()*10000,1)
    )

    for h in ["30m","60m","120m","eod"]:
        z = y[f"rel_{h}"].dropna()*10000

        fade = (
            (z < 0).mean()*100
            if grp == "POS_GAP_Q"
            else (z > 0).mean()*100
        )

        print(
            h,
            "mean", round(z.mean(),2),
            "median", round(z.median(),2),
            "fade%", round(fade,1),
            "n", len(z)
        )

print("\nEXECUTABLE FADE SPREAD (NEG minus POS)")
for h in ["30m","60m","120m","eod"]:
    pos = x[x.group=="POS_GAP_Q"][f"rel_{h}"].dropna()*10000
    neg = x[x.group=="NEG_GAP_Q"][f"rel_{h}"].dropna()*10000

    print(
        h,
        "NEG",round(neg.mean(),2),
        "POS",round(pos.mean(),2),
        "spread",round(neg.mean()-pos.mean(),2)
    )

print("\nNO COSTS / NO STOPS / NO TARGETS")
print("DIAGNOSTIC ONLY — NOT PAPER/LIVE")