"""Generate a report solely from saved run evidence, without loading Qlib."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .evaluate import hypothesis_verdict


def number(value):
    return "N/A" if value is None or not np.isfinite(value) else f"{value:.6f}"


def interval_text(interval):
    if interval["status"] != "ok":
        return "Unavailable (insufficient valid dates)"
    return f"[{number(interval['ci_low'])}, {number(interval['ci_high'])}]"


def generate_report(run_dir, output=None):
    run_dir = Path(run_dir).resolve()
    manifest_path = run_dir / "manifest.json"
    if manifest_path.is_file():
        state = json.loads(manifest_path.read_text())
        if state["status"] in {"data_failed", "check_failed", "runtime_failed"}:
            return generate_failure_report(run_dir, state)
    summary = json.loads((run_dir / "summary.json").read_text())
    formal = summary["run_type"] == "formal_out_of_sample"
    prediction_file = "oos_predictions.csv" if formal else "train_predictions.csv"
    required = ["daily_ic.csv", "annual_ic.csv", "annual_intervals.json", "factor_ic.csv",
                "quintile_returns.csv", "quintile_counts.csv", "rank_change.csv", prediction_file]
    for name in required:
        if not (run_dir / name).is_file():
            raise FileNotFoundError(f"Missing report evidence: {name}")
    freeze = None
    if formal:
        if not summary["protocol_frozen"]:
            raise ValueError("Formal results have no frozen protocol record.")
        freeze = json.loads((run_dir / "freeze.json").read_text())
        for name, digest in freeze["hashes"].items():
            source = (run_dir / name).resolve()
            if not source.is_relative_to(run_dir):
                raise ValueError("Frozen file path is outside the run directory.")
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Frozen file content has changed: {name}")

    daily = pd.read_csv(run_dir / "daily_ic.csv", index_col="datetime", parse_dates=True)
    paired = daily.dropna(subset=["baseline", "with_candidate"])
    interval = summary["paired_delta_bootstrap"]
    if len(paired) != interval["n_dates"]:
        raise ValueError("Daily IC valid-date count differs from the summary.")
    np.testing.assert_allclose(paired["delta"], paired["with_candidate"] - paired["baseline"], rtol=1e-10, atol=1e-12)
    if len(paired):
        for name in ["baseline", "with_candidate"]:
            np.testing.assert_allclose(paired[name].mean(), summary["mean_ic"][name], rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(paired["delta"].mean(), interval["mean_delta"], rtol=1e-10, atol=1e-12)
    annual = pd.read_csv(run_dir / "annual_ic.csv", index_col="year")
    annual_intervals = json.loads((run_dir / "annual_intervals.json").read_text())
    factors = pd.read_csv(run_dir / "factor_ic.csv", index_col="datetime")
    quintiles = pd.read_csv(run_dir / "quintile_returns.csv", index_col="datetime")
    rank_changes = pd.read_csv(run_dir / "rank_change.csv", index_col="datetime")
    verdict = {
        "development": "In-sample development run: workflow check only, not an out-of-sample hypothesis verdict.",
        "unavailable": "The interval is unavailable; cannot complete the predefined incremental-value assessment.",
        "supported": "Incremental predictive value is supported under this protocol.",
        "not_supported": "Incremental predictive value is not supported under this protocol; this is not evidence of no effect.",
    }[hypothesis_verdict(formal, interval)]
    lines = [
        "# Qlib Research Run Report", "", verdict, "",
        f"Run type: {'Out-of-sample evaluation' if formal else 'In-sample development'}.",
        f"Evaluation signal dates: {summary['signal_start']} to {summary['signal_end']}.",
        f"Training samples: {summary['n_train']:,}; evaluation samples: {summary['n_evaluation']:,}; paired valid dates: {len(paired)}.", "",
    ]
    if summary.get("oos_previously_seen"):
        lines += ["The out-of-sample period has already been inspected. This is workflow reproduction or exploratory evaluation, not new independent validation.", ""]
    lines += ["## Primary metrics", "", "| Period | Valid dates | Baseline IC | With-candidate IC | Paired increment | Bootstrap interval |",
              "|---|---:|---:|---:|---:|---|",
              f"| Pooled | {len(paired)} | {number(summary['mean_ic']['baseline'])} | {number(summary['mean_ic']['with_candidate'])} | {number(interval['mean_delta'])} | {interval_text(interval)} |"]
    for year, row in annual.iterrows():
        lines.append(f"| {year} | {int(row['n_dates'])} | {number(row['baseline'])} | {number(row['with_candidate'])} | {number(row['delta'])} | {interval_text(annual_intervals[str(year)])} |")
    lines += ["", f"Moving date-block length: {interval['block_length']}; resamples: {interval['n_resamples']}; seed={interval['seed']}.",
              f"Confidence level: {interval.get('confidence', .95):.0%}. The pooled out-of-sample comparison is primary; annual results are auxiliary." if formal else "Development intervals are used only to check the calculation workflow.", "",
              "Both models use identical training samples and daily evaluation stocks; the primary increment uses only dates with valid IC for both models.", "",
              "## Auxiliary results", "", "| Standalone factor | Mean daily Rank IC |", "|---|---:|"]
    for name, value in factors.mean().items():
        lines.append(f"| {name} | {number(value)} |")
    lines += ["", "| Candidate quintile | Mean forward return |", "|---|---:|"]
    for name, value in quintiles.mean().items():
        lines.append(f"| {name} | {number(value)} |")
    lines += ["", f"Mean change in signal percentile ranks: {number(rank_changes['rank_change'].mean())}. This is not actual trading turnover.", "",
              "Standalone factor IC does not replace the incremental-value assessment. Group returns exclude transaction costs, borrowing constraints and capacity; they do not represent executable trading returns.", "",
              "## Model parameters", "", "| Model | Alpha | Intercept | Feature coefficients |", "|---|---:|---:|---|"]
    for name, model in summary["models"].items():
        coefficients = "; ".join(f"{key}={number(value)}" for key, value in model["coefficients"].items())
        lines.append(f"| {name} | {model['alpha']} | {number(model['intercept'])} | {coefficients} |")
    lines += ["", "## Evidence files", "", "This report reads only saved evidence from this run. Report generation does not refit models or rerun the experiment.", ""]
    for name in ["summary.json", *required]:
        lines.append(f"- [{name}]({name})")
    for name in ["manifest.json", "checks.json"]:
        if (run_dir / name).is_file():
            lines.append(f"- [{name}]({name})")
    if freeze:
        lines += ["- [freeze.json](freeze.json)", "",
                  f"Protocol SHA-256: `{freeze['hashes']['protocol.md']}`. Frozen file hashes have been verified."]
    lines.append("")
    output = Path(output) if output else run_dir / "report.md"
    # Existing reports remain evidence; use a new output name to regenerate.
    with output.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    return output


def generate_failure_report(run_dir, state):
    """Write an explicit failed result without inventing metrics."""
    run_dir = Path(run_dir)
    evaluation = ("Evaluation ran, but the workflow failed; no valid research conclusion is available."
                  if "evaluation" in state["completed_stages"]
                  else "Not run or incomplete; no IC, intervals or hypothesis verdict are reported.")
    lines = ["# Qlib Research Run Failed", "",
             f"Status: {state['status']}.", f"Failed stage: {state['stage']}.", "",
             f"Error: {state['error']['type']}: {state['error']['message']}", "",
             f"Evaluation: {evaluation}", "",
             "This is not a completed research result. After fixing the cause, create a new run and preserve this failure record.", "",
             "- [manifest.json](manifest.json)", "- [checks.json](checks.json)",
             "- [traceback.txt](traceback.txt)", ""]
    output = run_dir / ("failure-report.md" if (run_dir / "report.md").exists() else "report.md")
    with output.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    return output
