# Run a configured research experiment

Run commands from the repository root. Python 3.12 and uv are required. This workflow assumes an existing local Qlib US daily dataset; data acquisition is a separate step. Market data and run outputs remain outside Git.

## Environment and data

```bash
uv sync --locked
export QLIB_DATA_DIR="/absolute/path/to/your/snapshot/qlib"
```

Replace the data path with a dataset containing `calendars/day.txt`, `features/`, `instruments/all.txt` and historical `instruments/sp500.txt`. There is no need to activate a virtual environment when using `uv run`.

## Tests and development run

```bash
PYTHONPATH=tools uv run --locked python -m pytest -p no:cacheprovider tests -q
uv run --locked python tools/manual_experiment.py --config configs/reversal_volume.yaml
```

The default development slice ends on 2018-03-30. It evaluates in-sample predictions to check the workflow, not to establish OOS evidence. Each run prints a new directory under `runs/` and automatically creates a report on success.

## Freeze without running an experiment

```bash
uv run --locked python tools/manual_experiment.py \
  --config configs/reversal_volume.yaml \
  --full --freeze-only \
  --protocol examples/reversal-volume/experiment.md
```

Set RUN_DIR to the directory printed by that command, then check it against current inputs:

```bash
export RUN_DIR="/absolute/path/to/the/printed/run-directory"
uv run --locked python tools/check_freeze.py "$RUN_DIR" \
  --config configs/reversal_volume.yaml
```

The freeze-only state is `frozen`, not a completed experiment. YAML mapping order does not affect the canonical configuration hash. Config changes, frozen-file changes, source/dependency drift or a different data path cause verification to fail. This check targets the current implementation; it is not an automatic replay of old code snapshots.

## Full configured run

```bash
uv run --locked python tools/manual_experiment.py \
  --config configs/reversal_volume.yaml \
  --full \
  --protocol examples/reversal-volume/experiment.md
```

This creates and verifies a new freeze, fits on 2018–2023 and evaluates 2024–2025. These OOS years have already been inspected; the example config records that fact. A subsequent run demonstrates reproducibility, not a new independent discovery.

## Read reports and diagnose failures

Open the printed run directory's `report.md`. To generate a report for an older run that has the required evidence but no report yet:

```bash
uv run --locked python tools/generate_report.py "$RUN_DIR"
```

This reads saved evidence only. Existing reports are never overwritten; normal new runs already generate theirs automatically.

| File | Purpose |
|---|---|
| manifest.json | Command, environment, code state, stage, duration and outcome |
| checks.json | Completed stages and recorded diagnostics |
| config.yaml / resolved-config.json | Requested and parsed experimental rules |
| freeze.json | Formal input snapshot hashes and canonical configuration hash |
| summary.json / daily_ic.csv | Summary metrics and their daily observations |
| annual_ic.csv / annual_intervals.json | Per-year results using the same trained models |
| factor_ic.csv / quintile_returns.csv / quintile_counts.csv | Auxiliary factor and group diagnostics |
| rank_change.csv | Signal rank change, not actual trading turnover |
| report.md | Research result or explicit failure report |
| traceback.txt | Failure details, when an exception occurs |

Run statuses are `running`, `frozen`, `completed`, `data_failed`, `check_failed`, and `runtime_failed`. A completed run can validly conclude that a hypothesis is not supported. Failed runs exit nonzero and preserve diagnostics without inventing metrics. Development and full runs have separate run-type labels.

## Supported scope

The current tool supports three named feature roles (rev/rv/vol20), a standardized product candidate, two Ridge comparisons, future-open return labels, and the fixed evaluation workflow. It accepts configured historical Qlib expressions from an explicit operator/field whitelist. Count conditions must cover the formula's historical dependencies; bootstrap block length must cover label holding time.

It does not implement arbitrary candidate formulas, arbitrary model families or automatic paper-to-experiment conversion. New ideas outside this structure require explicit design and code adaptation. The repository skill guides that decision and calls these tools. It has been tested with three positive discovery prompts, one near-miss, and a full workflow reproduction.

The CLI entry lives in `tools/manual_experiment.py`; reusable implementation lives in `tools/lab/`. Personal course plans and learning notes are intentionally not part of this repository.
