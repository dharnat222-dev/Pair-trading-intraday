# INTRADAY RESEARCH PROTOCOL v1

STATUS: RESEARCH ONLY — NO PAPER/LIVE

## Frozen Dataset Boundaries

Feature Research:
2025-02-01 through 2025-08-31

Internal Validation:
2025-09-01 through 2025-12-31

Confirmation OOS:
2026-01-01 through 2026-06-30

FINAL HOLDOUT:
2026-07-01 through 2026-08-28

Excluded:
2025-10-21 special/truncated session
2026-08-31 incomplete session

No 2026 data may be used for feature or threshold selection.

## Execution Boundary

Signals may use information available through 09:30 close.

Earliest executable entry:
09:45 open.

No same-bar execution.

## Frozen Candidate Feature Families

1. Relative overnight gap
2. First-30-minute market-relative return
3. First-30-minute opening-range width
4. Opening volume surprise
5. Previous-session return
6. Previous-session high-low range
7. Distance from previous close
8. Cross-sectional rank of opening move
9. Sector-relative opening return

Do not add indicators after inspecting validation results.

## Targets

From 09:45 executable entry:

- 30-minute forward return
- 60-minute forward return
- 120-minute forward return

Both:
- raw stock return
- market-relative return

No stop-loss or target is optimized in feature research.

## Research Discipline

Features remain continuous wherever possible.

Forbidden:
- testing dozens of arbitrary RSI/MACD values
- selecting winning sectors after viewing validation
- selecting winning times after viewing validation
- deleting losing stocks based on future results
- using 2026 to tune anything
- Telegram/paper/live alerts

Any candidate relationship must:
1. appear in Research,
2. retain direction in Internal Validation,
3. survive conservative transaction costs,
4. then be frozen before 2026 Confirmation OOS.

FINAL HOLDOUT is opened only after all strategy rules are frozen.

## Multiple Testing

All tested hypotheses must be counted.
Do not report only winners.

Prefer:
- rank correlation (Spearman IC)
- monotonic quintile behavior
- bootstrap confidence intervals by trading day
- validation sign consistency

A feature with tiny effect below realistic costs is rejected even if
statistically significant.

## Security

No broker order-placement code.
No credentials in Git.
No .env commits.