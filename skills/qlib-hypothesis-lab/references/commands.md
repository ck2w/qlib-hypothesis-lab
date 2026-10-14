# Commands and run states

Run these commands from the confirmed `qlib-hypothesis-lab` repository root. The skill does not bundle copies of the calculation tools; it requires the target repository's `tools/`, `pyproject.toml`, `uv.lock` and configurations. The skill can be installed elsewhere; locate the project through the user's workspace.

## Validation and tests

Use the actual selected configuration path in place of the example. Configuration validation does not load market data:

```bash
PYTHONPATH=tools uv run --locked python -c 'from lab.config import load_config; load_config("configs/reversal_volume.yaml"); print("config valid")'
```

Select tests relevant to the change. The core suite requires no upstream collector checkout:

```bash
PYTHONPATH=tools uv run --locked python -m pytest -p no:cacheprovider tests --ignore=tests/test_collect_yahoo.py -q
```

For changes to collection tools, also run `tests/test_collect_yahoo.py` after preparing the separate upstream checkout as described in the target repository's `docs/reproducibility.md`. With that checkout available, omit `--ignore` to run the full suite.

## Execution

Development mode uses the configured small in-sample slice. Its output is not out-of-sample evidence:

```bash
uv run --locked python tools/manual_experiment.py --config configs/reversal_volume.yaml
```

Use the full research command only when this configuration and protocol represent the intended experiment:

```bash
uv run --locked python tools/manual_experiment.py --config configs/reversal_volume.yaml --full --protocol examples/reversal-volume/experiment.md
```

The full entry point creates a new run directory, freezes and verifies inputs, executes the experiment and generates a report. These example paths are not a completed configuration for a hypothesis that has yet to be defined.

For an optional input-only check, add `--freeze-only` to the full command. This freezes inputs without training. Verify the new directory separately:

```bash
uv run --locked python tools/check_freeze.py "$RUN_DIR" --config configs/reversal_volume.yaml
```

Set `RUN_DIR` to the directory actually printed by the command. Verification rejects changed code or inputs; resolve the drift rather than rewriting an old snapshot to bypass the check.

## Existing results

New runs generate reports automatically. For an older directory with complete evidence but no `report.md`:

```bash
uv run --locked python tools/generate_report.py "$RUN_DIR"
```

This command does not train or overwrite an existing report. For a read-only report request, read the existing files directly.

| State | Action |
|---|---|
| `running` | Wait for completion before reporting success. |
| `frozen` | Input snapshots exist; research has not completed. |
| `completed` | Check `run_type` to distinguish development from a full run; read the primary metrics and report. |
| `data_failed` | Diagnose the data path or loading error and retain the failure record. |
| `check_failed` | Resolve configuration, freeze, feature or sample checks before creating a new run. |
| `runtime_failed` | Diagnose the failed stage and traceback; report unavailable results as unavailable. |

The manifest and checks record stages, commands, environment and diagnostics. Summary, daily IC and annual files provide effect estimates. Every reported number must be traceable to these files. Label results from a previously inspected test period as reproduction or exploration, not new independent validation.
