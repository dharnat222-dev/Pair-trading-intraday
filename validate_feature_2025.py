import sqlite3
import pandas as pd
import numpy as np

START="2025-09-01"
END="2025-12-31"
FEATURE="distance_prev_close"

con=sqlite3.connect("data/intraday_ohlcv.db")
df=pd.read_sql_query("""
SELECT symbol,timestamp,open,close
FROM intraday_ohlcv
WHERE interval='15m'
AND substr(timestamp,1,10) BETWEEN '2025-08-29' AND ?
ORDER BY symbol,timestamp
""",con,params=(END,))
con.close()

df["timestamp"]=pd.to_datetime(df.timestamp)
df["date"]=df.timestamp.dt.strftime("%Y-%m-%d")
df["time"]=df.timestamp.dt.strftime("%H:%M")

# Exclude known truncated special session.
df=df[df.date!="2025-10-21"].copy()

daily=df.groupby(["symbol","date"]).agg(
    close=("close","last")
).reset_index().sort_values(["symbol","date"])

daily["prev_close"]=daily.groupby("symbol")["close"].shift(1)

def snap(t,col,name):
    return df[df.time==t][["symbol","date",col]].rename(columns={col:name})

c930=snap("09:30","close","close930")
e945=snap("09:45","open","entry945")
p1045=snap("10:45","close","px60")
p1145=snap("11:45","close","px120")

x=daily.merge(c930,on=["symbol","date"])
x=x.merge(e945,on=["symbol","date"])
x=x.merge(p1045,on=["symbol","date"])
x=x.merge(p1145,on=["symbol","date"])

x=x[
    (x.date>=START)&
    (x.date<=END)&
    x.prev_close.notna()&
    (x.prev_close>0)&
    (x.entry945>0)
].copy()

x["distance_prev_close"]=x.close930/x.prev_close-1
x["ret60"]=x.px60/x.entry945-1
x["ret120"]=x.px120/x.entry945-1

def daily_ic(target):
    out=[]
    for date,g in x.groupby("date"):
        if len(g)<30: continue
        ic=g[FEATURE].rank().corr(g[target].rank())
        if np.isfinite(ic):
            out.append((date,ic))
    return pd.DataFrame(out,columns=["date","ic"])

a=daily_ic("ret60")
b=daily_ic("ret120")

print("INTERNAL VALIDATION ONLY",START,"to",END)
print("2026 NOT READ")
print("PRIMARY FEATURE",FEATURE)
print("Expected sign: NEGATIVE")

for label,z in [("60m PRIMARY",a),("120m SECONDARY",b)]:
    print("\n"+label)
    print("days",len(z))
    print("mean_ic",round(z.ic.mean(),4))
    print("median_ic",round(z.ic.median(),4))
    print("negative_days_pct",round((z.ic<0).mean()*100,1))

    z["month"]=z.date.str[:7]
    print("monthly:")
    print(z.groupby("month").ic.mean().round(4).to_string())

pass_primary=(
    a.ic.mean() < -0.04
    and (a.ic<0).mean() > 0.55
    and (a.assign(month=a.date.str[:7]).groupby("month").ic.mean()<0).sum() >= 3
)

print("\nPRIMARY_INTERNAL_GATE", "PASS" if pass_primary else "FAIL")
print("No P&L / no thresholds / 2026 untouched")