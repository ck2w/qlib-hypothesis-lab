---
name: qlib-hypothesis-lab
description: Use when a user wants to test a US equity price/volume factor hypothesis with Qlib. Translate a natural-language hypothesis or factor description into precise formulas, signal timing and a research protocol; evaluate the factor and its incremental value in an existing factor combination using configured historical data; produce a traceable report. Clarify ambiguous definitions or identify required adaptations when the design exceeds the tools' supported scope.
---

# Qlib Hypothesis Lab

Turn a US equity price/volume research question into a reproducible experiment and an evidence-backed conclusion. Standalone factor predictiveness and incremental value in an existing combination are separate questions.

This skill uses `tools/` in the companion `qlib-hypothesis-lab` repository. It requires Python 3.12, uv and configured Qlib US daily data. Locate the user's target repository and confirm `pyproject.toml`, `tools/manual_experiment.py` and `configs/` exist. The skill's installation directory or a course repository is not necessarily the target project. Requests to explain an API or read an existing report do not start a new experiment.

## 1. Define a testable question

From the hypothesis or factor description, specify the economic rationale, exact formula and windows, signal availability, label and holding period, universe, baseline and incremental comparison. For a paper, retain its source and original definition. For a whole paper, first list attributed candidate hypotheses and let the user select one before designing the experiment.

Clarify missing details together when they change the economic meaning or trading timing. If the user has already authorized project conventions, state those conventions and continue without asking again. Once the definition is complete, assess feasibility against [Research protocol and supported scope](references/research-protocol.md). Identify required adaptations when the tools cannot express the design; preserve the user's hypothesis rather than substituting the example factor.

## 2. Fix the research protocol

Save the experiment's YAML and protocol. Specify train/out-of-sample dates, raw and candidate formulas, model comparisons on identical samples, the primary decision rule and auxiliary metrics. Before reusing inputs, check that their contents match this hypothesis.

Proceed within the user's existing authorization. Resolve substantive research ambiguities in a new definition before execution. If the out-of-sample period has already been inspected, record `oos_previously_seen: true`; subsequent changes are exploratory research or workflow reproduction.

## 3. Check and run

Read [Data and environment](references/data-guide.md) for a new environment or an unclear data path. Follow [Commands and run states](references/commands.md) to validate the configuration, run necessary tests and execute. Run relevant tests after configuration or code changes, and the full suite for changes across the tool implementation. Reading an existing report requires neither training nor the full test suite.

The full-run entry point freezes and verifies the configuration, protocol, code and dependencies before loading data, constructing features and labels, fitting models and evaluating results. Use `--freeze-only` only for a separate input check; it does not complete an experiment.

Explain failures using the manifest, failure report and traceback. Create a new run after resolving the actual failure. Propose data downloads, definition substitutions or model changes as adaptations when the current task does not authorize them.

## 4. Report and interpret

Read `report.md`, `manifest.json` and the corresponding metric files from the actual run directory. Distinguish in-sample development, freeze-only, completed research and failure. A hypothesis that is not supported can still be a successfully completed study.

Base the primary conclusion on the predefined paired IC increment and its interval. Use standalone factor IC, annual results, group returns and rank changes as auxiliary evidence. Explain the difference between “not supported” and “proven to have no effect.” Preserve the predefined sign, windows and observed results when the outcome is unfavorable.

Return the research question, actual method, key numbers and uncertainty, conclusion, and paths to the report and evidence. For failures, identify the last stage reached and evaluations left unfinished. Group returns and signal rank changes are not cost-adjusted tradable returns or portfolio turnover.
