import pandas as pd
import numpy as np
from scipy.stats import spearmanr

FILE="output/intraday_feature_matrix_research.csv"

FEATURES=[
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

TARGETS=[
    "ret_30m",
    "ret_60m",
    "ret_120m",
    "relret_30m",
    "relret_60m",
    "relret_120m",
]

x=pd.read_csv(FILE)

print("FEATURE_IC — RESEARCH ONLY")
print("rows",len(x),"sessions",x.date.nunique())
print("2026 NOT READ")

results=[]

for feature in FEATURES:
    for target in TARGETS:
        vals=[]

        # Daily cross-sectional IC.
        for date,g in x.groupby("date"):
            z=g[[feature,target]].dropna()

            if len(z)<20:
                continue

            if z[feature].nunique()<3 or z[target].nunique()<3:
                continue

            ic=spearmanr(z[feature],z[target]).statistic

            if np.isfinite(ic):
                vals.append(ic)

        a=np.asarray(vals,float)

        if len(a)==0:
            continue

        mean=float(a.mean())
        median=float(np.median(a))
        pos=float((a>0).mean()*100)

        # Simple day-level t-stat, diagnostic only.
        sd=float(a.std(ddof=1))
        tstat=mean/(sd/np.sqrt(len(a))) if sd>0 else 0.0

        results.append({
            "feature":feature,
            "target":target,
            "days":len(a),
            "mean_ic":mean,
            "median_ic":median,
            "positive_pct":pos,
            "tstat":tstat,
        })

r=pd.DataFrame(results)

# Show ALL hypotheses, not only winners.
for target in TARGETS:
    print("\nTARGET",target)

    q=r[r.target==target].copy()
    q=q.sort_values("mean_ic",ascending=False)

    for z in q.itertuples():
        print(
            f"{z.feature:25s}",
            "IC",round(z.mean_ic,4),
            "median",round(z.median_ic,4),
            "positive%",round(z.positive_pct,1),
            "t",round(z.tstat,2),
        )

print("\nABSOLUTE IC RANK — ALL 72 TESTS")
q=r.assign(abs_ic=r.mean_ic.abs()).sort_values(
    "abs_ic",ascending=False
)

for z in q.head(20).itertuples():
    print(
        z.feature,
        "->",z.target,
        "IC",round(z.mean_ic,4),
        "t",round(z.tstat,2)
    )

r.to_csv("output/feature_ic_research.csv",index=False)

print("\nTESTS_RUN",len(r))
print("No threshold selection.")
print("No P&L.")
print("Internal validation NOT READ.")
print("2026 NOT READ.")