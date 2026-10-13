# Relative volume and short-term reversal

## Question

Does low relative volume strengthen short-term reversal, and does the interaction improve an existing factor combination?

This example uses US daily price/volume data, a historical S&P 500 signal universe, and the configuration in `configs/reversal_volume.yaml`. The previously inspected 2024–2025 period is marked as seen in that configuration; subsequent runs are workflow reproductions or exploratory studies.

## Features and timing

- rev: `1 - $close / Ref($close, 5)`; require six valid consecutive closes.
- rv: `Mean($volume, 5) / Mean($volume, 60)`; require 60 valid volume observations and a positive denominator.
- vol20: `Std($close / Ref($close, 1) - 1, 20)`; require 20 valid daily returns; sample standard deviation, ddof=1.
- Standardize each feature within the feature-valid historical member pool on each date, ddof=0. Constant cross-sections become zero.
- Candidate: standardize `z(rev) * (-z(rv))` again on the same date and pool. Include both rising and falling stocks.
- Signal is known after day t close. Label is open(t+6)/open(t+1)-1. Compute labels from continuous individual histories, then select membership by signal date.
- Do not use label availability to choose the signal standardization pool. Only later exclude invalid labels or nonpositive entry/exit prices.

## Comparison and periods

Fit two Ridge models with alpha=1 and an intercept on identical pooled stock-date training rows. Baseline inputs are z(rev), z(rv), z(vol20); the second model adds candidate. Use equal weight per stock-date row.

Train on 2018–2023 signal dates, excluding labels ending on or after 2024-01-01. Evaluate 2024–2025 using the same frozen models, with combined and separate-year reports. Do not refit after 2024. Pre-2018 data is warm-up; 2026 can supply label prices but contributes no formal signal dates.

## Evaluation

Primary measure: mean daily Spearman IC difference, added-candidate minus baseline, on common stocks and common valid dates. Constant prediction/label days are NA, not zero.

Moving-block bootstrap: 20 valid trading dates per block, 1,000 resamples, seed=42, percentile 95% interval. Insufficient dates produce no interval. Support requires mean delta>0 and interval lower bound>0. Otherwise report not supported, without asserting no effect exists.

Auxiliary outputs: individual factor IC, candidate quintile future returns and q5-q1 spread, annual IC and intervals, mean absolute change in percentile signal ranks on common stocks across adjacent trading dates. Define quintiles using fixed percentile intervals and average ranks; do not split ties by ticker. These are prediction diagnostics, not a costed tradable portfolio backtest.

## Execution record

Before full execution, freeze this protocol, the configuration, implementation modules and dependency lock. Record the actual command, versions, hashes, diagnostics and outcome in the run directory. Changes made after viewing OOS results are exploratory. The first manual case did not support incremental value; reproduce results without tuning the design to reverse that outcome.
