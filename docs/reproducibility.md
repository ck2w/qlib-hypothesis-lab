# Reproduce the worked research case

This guide reproduces the **configured workflow** and shows how to compare a new run with the published aggregate result. No agent session is required to execute the Python experiment.

Exact numerical reproduction also requires the original market-data snapshot and a compatible numerical environment. The repository does not distribute that snapshot or the complete original run. A fresh download may contain revised prices, volume, calendars or membership intervals and produce different numbers.

## 1. Prepare the environment

Clone this repository, enter its root and use Python 3.12 with uv available:

```bash
git rev-parse HEAD
uv --version
uv sync --locked
uv run --locked python --version
```

Keep `uv.lock` unchanged. The documented local environment is macOS arm64, Python 3.12, pyqlib 0.9.7 and pandas 2.3.3; a fresh installation and other platforms have not been verified.

Validate the example configuration and run the 54 core tests with synthetic data before attaching market data:

```bash
PYTHONPATH=tools uv run --locked python -c 'from lab.config import load_config; load_config("configs/reversal_volume.yaml"); print("config valid")'
PYTHONPATH=tools uv run --locked python -m pytest -p no:cacheprovider tests --ignore=tests/test_collect_yahoo.py -q
```

The quickstart excludes `test_collect_yahoo.py` because it imports scripts from an upstream Qlib checkout that is not tracked here. To run all 55 tests, prepare that optional checkout at the revision used locally (requires network access):

```bash
git clone --no-checkout https://github.com/microsoft/qlib.git upstream/qlib
git -C upstream/qlib checkout --detach da920b7f954f48ab1bb64117c976710de198373e
PYTHONPATH=tools uv run --locked python -m pytest -p no:cacheprovider tests -q
```

Clone only if `upstream/qlib` does not already exist; inspect an existing checkout before changing it. The full research CLI does not require these upstream collector scripts.

Passing tests validates covered software behavior. It does not reproduce the market-data result.

## 2. Attach an existing Qlib dataset

`QLIB_DATA_DIR` must point to a Qlib binary provider directory, not a CSV download folder:

```text
qlib/
├── calendars/
│   └── day.txt
├── features/
│   └── <instrument>/...day.bin
└── instruments/
    ├── all.txt
    └── sp500.txt
```

Required inputs:

| Input | Requirement |
|---|---|
| Region / frequency | US equities, daily data. |
| Fields | Qlib `$close`, `$open` and `$volume`, with consistent price/volume normalization. |
| Price coverage | All instruments needed by historical membership, including former members; `all.txt` describes imported histories. |
| Universe | Historical S&P 500 membership intervals in `sp500.txt`, selected by signal date. Today's constituent list is not a substitute. |
| Warm-up | Data from 2017-09-01 for the configured historical windows. |
| Train / evaluation | 2018–2023 training signals and 2024–2025 evaluation signals. |
| Label tail | Calendar and opening prices through six trading days after the last evaluation signal, including early 2026 for late-2025 signals. |

Export your actual path explicitly. The CLI does not automatically load `.env`:

```bash
export QLIB_DATA_DIR="/absolute/path/to/your/snapshot/qlib"
uv run --locked python - <<'PY'
import os
from pathlib import Path
root = Path(os.environ["QLIB_DATA_DIR"]).expanduser().resolve()
for name in ("calendars/day.txt", "features", "instruments/all.txt", "instruments/sp500.txt"):
    path = root / name
    assert path.exists(), f"Missing: {path}"
print(f"Provider layout found: {root}")
PY
```

This checks layout only. Field readability, windows and valid samples are checked during execution. Preserve a versioned copy of the dataset and record its source, acquisition date, normalization procedure and membership source. The freeze records its path, not its contents; use your own snapshot identifier or content hashes to track data revisions.

There is no bundled command that prepares the full historical research dataset. `tools/collect_yahoo.py` is a raw-data collection helper that depends on a separate `upstream/qlib` checkout; it neither creates the complete binary provider nor reconstructs historical S&P 500 membership. A three-stock pilot cannot reproduce this case.

## 3. Run the fixed experiment

Read the [protocol](../examples/reversal-volume/experiment.md) and [configuration](../configs/reversal_volume.yaml) before execution. Run the unchanged example:

```bash
uv run --locked python tools/manual_experiment.py \
  --config configs/reversal_volume.yaml \
  --full \
  --protocol examples/reversal-volume/experiment.md
```

The command creates a fresh `runs/full-<UTC timestamp>/` directory and prints its absolute path. It freezes and verifies inputs, loads data, constructs signals and labels, purges training labels crossing the evaluation boundary, fits two Ridge models on identical samples, evaluates paired daily IC and generates `report.md`.

Set `RUN_DIR` to **the directory printed by your command**:

```bash
export RUN_DIR="/absolute/path/to/printed/runs/full-<UTC timestamp>"
uv run --locked python tools/check_freeze.py "$RUN_DIR" \
  --config configs/reversal_volume.yaml
```

Check `manifest.json` for `status: completed`, `summary.json` for `run_type: formal_out_of_sample`, and read `report.md`. A `frozen` state means input checking only. Development-mode output is in-sample and is not comparable to the published full result. See [usage](usage.md) for input-only freezing and failure diagnosis.

## 4. Compare with the published result

The public reference is [results.json](../examples/reversal-volume/results.json). Expected headline values, rounded for display:

| Measure | Published value |
|---|---:|
| Training rows | 693,258 |
| Evaluation rows | 247,233 |
| Paired IC dates | 502 |
| Baseline mean Rank IC | 0.017001 |
| With-candidate mean Rank IC | 0.017098 |
| Mean paired IC increment | +0.000097 |
| 95% interval | [−0.000173, +0.000470] |
| Decision | Hypothesis not supported under this protocol. |

Print the actual values side by side without relying on rounded README numbers:

```bash
uv run --locked python - <<'PY'
import json
import os
from pathlib import Path
reference = json.loads(Path("examples/reversal-volume/results.json").read_text())
actual = json.loads((Path(os.environ["RUN_DIR"]) / "summary.json").read_text())
paths = [
    ("config_canonical_sha256",),
    ("n_train",), ("n_evaluation",),
    ("mean_ic", "baseline"), ("mean_ic", "with_candidate"),
    ("paired_delta_bootstrap", "n_dates"),
    ("paired_delta_bootstrap", "mean_delta"),
    ("paired_delta_bootstrap", "ci_low"),
    ("paired_delta_bootstrap", "ci_high"),
    ("interpretation",),
]
for path in paths:
    expected_value, actual_value = reference, actual
    for key in path:
        expected_value, actual_value = expected_value[key], actual_value[key]
    print(f'{".".join(path)}\n  published: {expected_value}\n  your run:  {actual_value}')
PY
```

This is a comparison, not an automatic pass/fail test with an invented numerical tolerance. With identical data and environment, compare full-precision metrics, sample counts and model coefficients. For discrepancies, first inspect the configuration hash, dataset version, historical membership, calendar/label tail and missing-value coverage; then compare environment versions and saved diagnostics. Preserve differences as evidence rather than tuning parameters to match the table.

The decision rule requires a positive mean paired increment **and** a 95% interval lower bound above zero. The saved interval crosses zero. The 2024–2025 period has already been seen (`oos_previously_seen: true`), so reproducing it does not create new independent evidence.

## 5. Know what is preserved

| Artifact | What it establishes |
|---|---|
| `config.yaml`, `resolved-config.json`, `protocol.md` | Requested rules and their frozen definitions. |
| Frozen `tools/`, `pyproject.toml`, `uv.lock` | Implementation and dependency inputs used by the full run. |
| `freeze.json` | Snapshot hashes, canonical configuration hash, Git state and resolved data path. |
| `manifest.json`, `checks.json` | Environment, command, stages, outcome and diagnostics. |
| `summary.json`, `daily_ic.csv`, annual files | Aggregate estimates and daily/yearly evidence. |
| `oos_predictions.csv` | Per-stock predictions in your local full run. |
| `report.md` | Generated interpretation of saved evidence. |

`check_freeze.py` rejects input tampering, current code/dependency drift and a different resolved data path. It does not detect changes to data at the same path or automatically replay old code snapshots.

The public showcase includes the protocol, configuration, aggregate summary and completed-stage status. The full local run and dataset are excluded from Git. The public files allow inspection of the reported result, but cannot independently establish the original daily observations or recover the original data snapshot.
