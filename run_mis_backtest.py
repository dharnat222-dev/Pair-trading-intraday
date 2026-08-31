"""MIS 15m walk-forward on local SQLite. No orders. Not paper/live permission."""
from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sector_map import SECTOR_MAP

BANNER = "FIRST_MIS_RUN — NOT PAPER / NOT LIVE"
CAPITAL = 1_000_000.0
MAX_NOTIONAL = 150_000.0
COST = 0.0012
L = 20
ENTRY_Z = 2.0
EXIT_Z = 0.5
STOP_Z = 2.75
TIME_STOP = 16
MAX_PAIRS = 4
MAX_CAND = 6
DAILY_HL_MAX = 12.0
INTRA_HL = (4.0, 24.0)
CORR_MIN = 0.55
BETA_LO, BETA_HI = 0.4, 2.0
CIRCUIT = -0.01
TRAIN_DAYS = 252
WARMUP = 2
BLOCK = 5


def sector_of(sym: str) -> str:
    for k, v in SECTOR_MAP.items():
        kk = str(k).replace(".NS", "").replace("-EQ", "").strip().upper()
        if kk == sym.upper() or kk.replace("&", "_") == sym.upper().replace("&", "_"):
            return str(v)
    return "UNK"


def half_life(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < 30:
        return 1e9
    y, z = x[1:], x[:-1]
    v = np.var(z)
    if v < 1e-12:
        return 1e9
    phi = float(np.cov(y - z, z, bias=True)[0, 1] / v + 1.0)
    if phi <= 0 or phi >= 1:
        return 1e9
    return float(-math.log(2) / math.log(phi))


def load_daily() -> pd.DataFrame:
    con = sqlite3.connect("data/nse_ohlcv.db")
    df = pd.read_sql_query("SELECT symbol, timestamp, close FROM daily_ohlcv", con)
    con.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    px = df.pivot(index="timestamp", columns="symbol", values="close").sort_index()
    px.columns = [str(c).upper() for c in px.columns]
    return px


def load_intra() -> pd.DataFrame:
    con = sqlite3.connect("data/intraday_ohlcv.db")
    df = pd.read_sql_query(
        "SELECT symbol, timestamp, open, close FROM intraday_ohlcv WHERE interval='15m'",
        con,
    )
    con.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["symbol"] = df["symbol"].str.upper()
    return df.sort_values(["timestamp", "symbol"])


def select_pairs(daily: pd.DataFrame, intra_week: pd.DataFrame, banned: set) -> list:
    cols = list(daily.columns)
    scored = []
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            key = "|".join(sorted([a, b]))
            if key in banned:
                continue
            if sector_of(a) == sector_of(b) == "UNK":
                pass
            if sector_of(a) == sector_of(b):
                continue
            s = daily[[a, b]].dropna()
            if len(s) < 180:
                continue
            corr = float(s[a].corr(s[b]))
            if abs(corr) < CORR_MIN:
                continue
            x, y = s[a].values, s[b].values
            varx = float(np.var(x))
            if varx < 1e-12:
                continue
            beta = float(np.cov(y, x, bias=True)[0, 1] / varx)
            if not (BETA_LO <= abs(beta) <= BETA_HI):
                continue
            spread = y - beta * x
            dhl = half_life(spread)
            if dhl > DAILY_HL_MAX:
                continue
            ia = intra_week[intra_week.symbol == a].set_index("timestamp")["close"]
            ib = intra_week[intra_week.symbol == b].set_index("timestamp")["close"]
            j = pd.concat([ia, ib], axis=1, keys=["a", "b"]).dropna()
            if len(j) < 80:
                continue
            ihl = half_life((j["b"] - beta * j["a"]).values)
            if not (INTRA_HL[0] <= ihl <= INTRA_HL[1]):
                continue
            scored.append((abs(corr) / (dhl + 1.0), a, b, float(beta), key, sector_of(a), sector_of(b)))
    scored.sort(reverse=True)
    picked, used_sec = [], set()
    for _, a, b, beta, key, sa, sb in scored:
        if sa in used_sec or sb in used_sec:
            continue
        picked.append((a, b, beta, key, sa, sb))
        used_sec.add(sa)
        used_sec.add(sb)
        if len(picked) >= MAX_CAND:
            break
    return picked


def zscore(arr: np.ndarray) -> float:
    if arr.size < L:
        return float("nan")
    w = arr[-L:]
    sd = float(np.std(w, ddof=0))
    if sd < 1e-9:
        return 0.0
    return float((w[-1] - np.mean(w)) / sd)


def qty(p1, p2, beta):
    q1 = int(MAX_NOTIONAL / (p1 + abs(beta) * p2))
    q2 = max(1, int(round(abs(beta) * q1)))
    if q1 < 1:
        return 0, 0
    while q1 * p1 + q2 * p2 > MAX_NOTIONAL and q1 > 1:
        q1 -= 1
        q2 = max(1, int(round(abs(beta) * q1)))
    return q1, q2


def main() -> None:
    print(BANNER)
    print("No orders. Local SQLite only.")
    daily = load_daily()
    intra = load_intra()
    sessions = sorted(intra["timestamp"].dt.date.unique())
    print("daily_days", len(daily), "sessions", len(sessions), "symbols", daily.shape[1])
    if len(sessions) < WARMUP + BLOCK:
        print("NOT_ENOUGH_SESSIONS")
        return
    oos = sessions[WARMUP:]
    blocks = [oos[i : i + BLOCK] for i in range(0, len(oos), BLOCK)]
    cash = CAPITAL
    equity = CAPITAL
    peak = CAPITAL
    maxdd = 0.0
    trades = []
    banned = {}
    pos = []
    day_open_eq = None
    halt = False
    last_date = None
    spread_hist = defaultdict(list)

    def flatten(rowmap, reason, ts):
        nonlocal cash, equity
        closed = []
        for p in pos:
            r1, r2 = rowmap.get(p["a"]), rowmap.get(p["b"])
            if r1 is None or r2 is None:
                continue
            px1, px2 = float(r1["open"]), float(r2["open"])
            pnl = p["side"] * ((px2 - p["e2"]) * p["q2"] - (px1 - p["e1"]) * p["q1"])
            notion = p["e1"] * p["q1"] + p["e2"] * p["q2"]
            cost = notion * COST
            net = pnl - cost
            cash += net
            trades.append({**p, "exit": ts, "reason": reason, "pnl": net})
            closed.append(p)
        for p in closed:
            pos.remove(p)

    for bi, block in enumerate(blocks, 1):
        start = pd.Timestamp(block[0])
        dtrain = daily.loc[: start - pd.Timedelta(days=1)].tail(TRAIN_DAYS)
        pre = intra[intra["timestamp"].dt.date < block[0]]
        last_dates = sorted(pre["timestamp"].dt.date.unique())[-10:]
        intra_train = pre[pre["timestamp"].dt.date.isin(last_dates)]
        lose_keys = {k for k, v in banned.items() if v > 0}
        cands = select_pairs(dtrain, intra_train, lose_keys)
        print(f"block {bi}/{len(blocks)} {block[0]} pairs {len(cands)}")
        block_pnl = defaultdict(float)
        spread_hist.clear()

        block_rows = intra[intra["timestamp"].dt.date.isin(block)].sort_values("timestamp")
        for ts, g in block_rows.groupby("timestamp", sort=True):
            d = ts.date()
            tstr = ts.strftime("%H:%M")
            rowmap = {r.symbol: r for r in g.itertuples()}
            if last_date != d:
                halt = False
                day_open_eq = equity
                last_date = d
                if pos:
                    flatten(rowmap, "OVERNIGHT_BUG", ts)
            if tstr == "15:15" and pos:
                flatten(rowmap, "FORCED_1515", ts)
            if day_open_eq and (equity - day_open_eq) / day_open_eq <= CIRCUIT and pos:
                flatten(rowmap, "CIRCUIT", ts)
                halt = True
            for p in list(pos):
                r1, r2 = rowmap.get(p["a"]), rowmap.get(p["b"])
                if r1 is None or r2 is None:
                    continue
                s = float(r2.close) - p["beta"] * float(r1.close)
                z0 = (s - p["mu0"]) / p["sd0"] if p["sd0"] > 1e-9 else 0.0
                p["bars"] += 1
                reason = None
                if abs(z0) >= STOP_Z:
                    reason = "STOP"
                elif abs(z0) < EXIT_Z:
                    reason = "TARGET"
                elif p["bars"] >= TIME_STOP:
                    reason = "TIME"
                if reason:
                    flatten({p["a"]: r1, p["b"]: r2}, reason, ts)
            if halt or tstr < "09:30" or tstr > "14:15" or tstr == "09:15":
                mtm = cash
                for p in pos:
                    r1, r2 = rowmap.get(p["a"]), rowmap.get(p["b"])
                    if r1 is None:
                        continue
                    mtm += p["side"] * (
                        (float(r2.close) - p["e2"]) * p["q2"]
                        - (float(r1.close) - p["e1"]) * p["q1"]
                    )
                equity = mtm
                peak = max(peak, equity)
                maxdd = min(maxdd, (equity - peak) / peak if peak else 0)
                continue
            nxt = None
            times = sorted(block_rows["timestamp"].unique())
            try:
                j = times.get_loc(ts) if hasattr(times, "get_loc") else list(times).index(ts)
                if j + 1 < len(times):
                    nxt = pd.Timestamp(list(times)[j + 1])
            except Exception:
                nxt = None
            if nxt is None:
                continue
            nstr = nxt.strftime("%H:%M")
            if nstr < "09:45" or nstr > "14:30":
                continue
            ng = block_rows[block_rows["timestamp"] == nxt]
            nmap = {r.symbol: r for r in ng.itertuples()}
            for a, b, beta, key, sa, sb in cands:
                if any(p["key"] == key for p in pos):
                    continue
                if len(pos) >= MAX_PAIRS:
                    break
                if any(sector_of(p["a"]) in (sa, sb) or sector_of(p["b"]) in (sa, sb) for p in pos):
                    continue
                r1, r2 = rowmap.get(a), rowmap.get(b)
                if r1 is None or r2 is None:
                    continue
                s = float(r2.close) - beta * float(r1.close)
                spread_hist[key].append(s)
                z = zscore(np.array(spread_hist[key], float))
                if abs(z) < ENTRY_Z or not np.isfinite(z):
                    continue
                f1, f2 = nmap.get(a), nmap.get(b)
                if f1 is None or f2 is None:
                    continue
                p1, p2 = float(f1.open), float(f2.open)
                q1, q2 = qty(p1, p2, beta)
                if q1 < 1:
                    continue
                w = np.array(spread_hist[key][-L:], float)
                mu0, sd0 = float(np.mean(w)), float(np.std(w, ddof=0))
                if sd0 < 1e-9:
                    continue
                side = -1 if z > 0 else 1
                pos.append(
                    dict(
                        a=a, b=b, beta=beta, key=key, q1=q1, q2=q2,
                        e1=p1, e2=p2, side=side, mu0=mu0, sd0=sd0,
                        bars=0, entry=nxt, block=bi,
                    )
                )
            mtm = cash
            for p in pos:
                r1, r2 = rowmap.get(p["a"]), rowmap.get(p["b"])
                if r1 is None:
                    continue
                mtm += p["side"] * (
                    (float(r2.close) - p["e2"]) * p["q2"]
                    - (float(r1.close) - p["e1"]) * p["q1"]
                )
            equity = mtm
            peak = max(peak, equity)
            maxdd = min(maxdd, (equity - peak) / peak if peak else 0)

        if pos:
            last_ts = block_rows["timestamp"].max()
            g = block_rows[block_rows["timestamp"] == last_ts]
            flatten({r.symbol: r for r in g.itertuples()}, "FORCED_1515", last_ts)
        for t in trades:
            if t.get("block") == bi:
                block_pnl[t["key"]] += t["pnl"]
        for key, pnl in block_pnl.items():
            if pnl < 0:
                banned[key] = banned.get(key, 0) + 1
            else:
                banned[key] = 0
        for k in list(banned):
            if banned[k] >= 2:
                banned[k] = -3
            elif banned[k] < 0:
                banned[k] += 1
                if banned[k] == 0:
                    del banned[k]

    n = len(trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    gp = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gl = -sum(t["pnl"] for t in trades if t["pnl"] <= 0)
    pf = (gp / gl) if gl > 1e-9 else 0
    reasons = defaultdict(int)
    for t in trades:
        reasons[t["reason"]] += 1
    Path("output").mkdir(exist_ok=True)
    lines = [
        BANNER,
        f"net_pnl {cash - CAPITAL:.2f}",
        f"final_equity {cash:.2f}",
        f"maxdd {maxdd*100:.2f}%",
        f"trades {n} wins {wins} winrate {100*wins/max(n,1):.1f}%",
        f"profit_factor {pf:.2f}",
        f"exits {dict(reasons)}",
        "This is not permission to paper or live trade.",
    ]
    Path("output/mis_first_run.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()