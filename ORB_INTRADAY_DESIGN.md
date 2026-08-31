# NSE CASH INTRADAY ORB + VWAP — PRE-REGISTERED DESIGN

STATUS: RESEARCH ONLY — NO PAPER/LIVE TRADING

## Frozen Dataset

Universe: existing 44 liquid NSE cash stocks.
Interval: 15-minute OHLCV.

Full available period:
2026-02-13 through 2026-08-31 (134 sessions).

Development period:
2026-02-13 through 2026-06-30.

FINAL UNTOUCHED OOS:
2026-07-01 through 2026-08-31.

The final OOS period must NOT be used to select or modify parameters.

## Hypothesis

Stocks showing a confirmed break of the first 30-minute opening range,
in the same direction as session VWAP, may exhibit short-horizon
intraday continuation after transaction costs.

This is a NEW hypothesis. Results from the failed pair-trading strategy
must not influence its parameters.

## Session Rules

NSE session: 09:15–15:30 IST.

Opening range:
09:15–09:45, using the first TWO completed 15-minute bars.

OR High = maximum High of those two bars.
OR Low  = minimum Low of those two bars.

No entry before the opening range is complete.

Last new signal: 14:15 close.
Last possible fill: 14:30 open.
Mandatory square-off: 15:15 open.
No overnight positions.

## VWAP

Session VWAP resets every trading day.

VWAP must use only bars available through signal time:

VWAP = cumulative(TypicalPrice * Volume) / cumulative(Volume)

TypicalPrice = (High + Low + Close) / 3.

No future volume/prices may enter VWAP.

## Entry

LONG signal:
1. 15-minute Close > OR High
2. Close > session VWAP

SHORT signal:
1. 15-minute Close < OR Low
2. Close < session VWAP

Signal at Close(t).
Execution strictly at Open(t+1).

No same-bar fills.

Maximum one completed trade per symbol per session.

## Direction Restrictions

Short trades are research simulations only.
Before any future paper/live stage, each symbol must be verified as
eligible for NSE cash intraday short/MIS with the broker.

## Risk / Exit

Do NOT invent or sweep stop/target values during coding.

Before implementation, perform a read-only DEVELOPMENT-period study
measuring Maximum Favorable Excursion (MFE) and Maximum Adverse
Excursion (MAE) after each raw ORB+VWAP entry.

The MFE/MAE study must:
- use DEVELOPMENT period only
- apply next-bar-open entry
- measure excursions until 15:15
- report distributions in basis points
- separate LONG and SHORT
- report by holding horizon: 30m, 60m, 120m, and 15:15
- NOT optimize a strategy
- NOT inspect July-August OOS

After that diagnostic, freeze ONE stop/target/time-exit rule before
opening the final OOS.

## Portfolio

Starting research capital: ₹1,000,000.
Leverage: 1.0x.
No future live sizing implied.

Daily portfolio circuit breaker:
-1.0% from day-open equity.

No new entries after 14:30.

## Costs

Use conservative all-in transaction-cost/slippage assumptions.
The exact cash-equity intraday cost calculation must be documented
before the final backtest.

Do not lower assumed costs merely to achieve profitability.

## Validation Discipline

Forbidden:
- parameter sweeps over final OOS
- choosing the best Z/ATR/stop/target after looking at July-August
- deleting losing stocks after examining final OOS
- claiming success from development results
- Telegram trading alerts before final OOS + paper stage

Workflow:

RAW SIGNAL
→ DEVELOPMENT MFE/MAE DIAGNOSTIC
→ FREEZE EXIT/RISK RULE
→ INTEGRITY TESTS
→ ONE FINAL OOS RUN
→ if evidence is adequate: PAPER ALERTS
→ only later consider live discretionary execution

Final OOS pass/fail criteria must be frozen BEFORE July-August is run.

No order-placement code is permitted.