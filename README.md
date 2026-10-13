# qlib-hypothesis-lab

A reproducible Qlib workflow for testing US equity price/volume hypotheses and their incremental value in a factor combination.

The first case asks whether low relative volume strengthens short-term reversal. It includes historical-universe filtering, frozen train/OOS rules, paired Rank IC comparison, date-block bootstrap intervals, and evidence-backed Markdown reports.

- [Usage and supported scope](docs/usage.md)
- [Example research protocol](examples/reversal-volume/experiment.md)
- [Example configuration](configs/reversal_volume.yaml)

The research tools are implemented; the agent skill is still being developed. Local market data and run outputs are not committed.
