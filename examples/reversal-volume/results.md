# Reversal × relative volume: worked result

This is a completed workflow reproduction on 2026-10-14, not a new independent test. The 2024–2025 evaluation period had already been inspected. The [protocol](experiment.md) fixes the hypothesis, timing, model comparison and decision rule; the [configuration](../../configs/reversal_volume.yaml) implements them.

Two Ridge models are fitted once on identical 2018–2023 rows: z(reversal), z(relative volume), z(volatility), with or without the standardized reversal × negative-relative-volume interaction. Signals are available after close; labels run from next-day open to open five trading days later.

| Measure | Result |
|---|---:|
| Training rows | 693258 |
| Evaluation rows | 247233 |
| Paired evaluation dates | 502 |
| Baseline mean Rank IC | 0.017001 |
| With-candidate mean Rank IC | 0.017098 |
| Paired mean IC difference | +0.000097 |
| 95% moving-block bootstrap interval | [-0.000173, 0.000470] |

The predeclared incremental-value criterion was not met: the interval crosses zero. This is a completed research workflow with an unsupported hypothesis, not a failed software run. The result does not establish an absence of effect, nor a profitable trading strategy.

The candidate's standalone mean IC was -0.005095, with q5−q1 mean forward return -0.000888. These auxiliary diagnostics do not replace the paired-model criterion or represent cost-adjusted portfolio returns.

[Saved summary](results.json) includes model coefficients, interval settings and configuration hashes. [Run status](run-status.json) records completed stages. The local run full-20261014T043420007266Z also contains frozen code/dependencies/protocol, daily metrics, predictions and the generated report. Local data and individual-stock predictions are excluded from this showcase.

## Reproduce

Follow [usage](../../docs/usage.md) with your existing Qlib dataset. Each full command creates a new run and freezes inputs before loading data. Data contents are not embedded in the code freeze; retain your dataset version. The showcased environment is macOS arm64, Python 3.12, pyqlib 0.9.7 and pandas 2.3.3. Other platforms and a fresh installation have not been tested.
