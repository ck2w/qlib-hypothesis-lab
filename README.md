# qlib-hypothesis-lab

Turn a US equity price/volume hypothesis into a defined experiment, a paired factor-combination comparison, and an evidence-backed report using [Microsoft Qlib](https://github.com/microsoft/qlib).

The agent skill guides research judgment; Python tools handle deterministic calculations. It clarifies formulas and signal timing, checks whether the current tools support the idea, freezes the protocol, evaluates the candidate and explains uncertainty. It does not keep tuning until a result becomes significant.

## Start here

- [Worked research result](examples/reversal-volume/results.md): low relative volume × short-term reversal; incremental value was not supported.
- [Research protocol](examples/reversal-volume/experiment.md) and [configuration](configs/reversal_volume.yaml).
- [Skill instructions](skills/qlib-hypothesis-lab/SKILL.md) and [usage / exact commands](docs/usage.md).

Python 3.12 and uv are required. From this repository root:

```bash
uv sync --locked
export QLIB_DATA_DIR="/absolute/path/to/your/snapshot/qlib"
PYTHONPATH=tools uv run --locked python -m pytest -p no:cacheprovider tests -q
uv run --locked python tools/manual_experiment.py \
  --config configs/reversal_volume.yaml --full \
  --protocol examples/reversal-volume/experiment.md
```

Use an existing Qlib US daily dataset with the required fields and historical sp500 instrument intervals. Data preparation is separate; see the [data guide](skills/qlib-hypothesis-lab/references/data-guide.md). Data stays outside the repository; each experiment writes a new ignored runs/ directory containing snapshots, metrics and report.md.

## Use the skill

In Codex, start a chat in this repository. The repository discovery link .agents/skills/qlib-hypothesis-lab points to the canonical skills/qlib-hypothesis-lab directory. For example:

> I want to use Qlib to test whether low relative volume strengthens short-term reversal and adds value to a factor combination. First define the experiment; do not run it yet.

The skill is paired with this repository's tools; copying only the skill does not install the research runtime or data. The current implementation supports three configured feature roles, a standardized product candidate, Ridge comparisons and future-open return labels. Different candidate structures or model families require explicit adaptation.

## Evidence and limits

Three fresh-chat positive prompts selected the skill; a Ref-expression-only near-miss did not. A subsequent skill-driven end-to-end reproduction completed through report generation and freeze verification. The current suite has 55 passing tests; timedelta deprecation warnings remain. These checks establish observed workflow behavior, not a measured improvement over an agent without the skill.

The example's 2024–2025 evaluation period has been seen. Reproducing it is not a new independent discovery. Rank IC and group-return diagnostics do not model transaction costs, borrowing, capacity or executable portfolio returns.

Tested locally on macOS arm64 with Python 3.12, pyqlib 0.9.7 and pandas 2.3.3. Other platforms and a fresh install are not yet verified. Personal course plans and learning notes are kept separately.
