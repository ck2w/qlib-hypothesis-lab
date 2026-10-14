import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from lab.report import generate_report


def make_run(tmp_path, formal=True, seen=False):
    run = tmp_path / "run"
    run.mkdir()
    dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
    daily = pd.DataFrame({"n_stocks": [3, 3], "baseline": [.01, .03],
                          "with_candidate": [.02, .04], "delta": [.01, .01]}, index=dates)
    daily.index.name = "datetime"
    daily.to_csv(run / "daily_ic.csv")
    interval = {"status": "ok", "n_dates": 2, "mean_delta": .01,
                "ci_low": -.005, "ci_high": .02, "block_length": 20,
                "n_resamples": 1000, "seed": 42, "confidence": .95}
    model = {"alpha": 1., "intercept": .001, "fit_intercept": True,
             "coefficients": {"z_rev": .001}}
    summary = {"run_type": "formal_out_of_sample" if formal else "development_in_sample",
               "signal_start": "2024-01-01", "signal_end": "2024-01-03",
               "n_train": 10, "n_evaluation": 6, "protocol_frozen": formal,
               "mean_ic": {"baseline": .02, "with_candidate": .03},
               "paired_delta_bootstrap": interval, "oos_previously_seen": seen,
               "models": {"baseline": model, "with_candidate": model}}
    (run / "summary.json").write_text(json.dumps(summary))
    (run / "annual_intervals.json").write_text(json.dumps({"2024": interval}))
    pd.DataFrame({"year": [2024], "n_dates": [2], "baseline": [.02],
                  "with_candidate": [.03], "delta": [.01]}).to_csv(run / "annual_ic.csv", index=False)
    for filename, values in {
        "factor_ic.csv": {"candidate": [.01, .02]},
        "quintile_returns.csv": {"q1": [.001, .002], "q5": [.003, .004], "q5_minus_q1": [.002, .002]},
        "quintile_counts.csv": {"q1": [1, 1], "q5": [1, 1]},
        "rank_change.csv": {"rank_change": [.1, .2]},
    }.items():
        frame = pd.DataFrame(values, index=dates)
        frame.index.name = "datetime"
        frame.to_csv(run / filename)
    (run / ("oos_predictions.csv" if formal else "train_predictions.csv")).write_text("saved predictions")
    if formal:
        protocol = b"frozen protocol"
        (run / "protocol.md").write_bytes(protocol)
        (run / "freeze.json").write_text(json.dumps({"hashes": {"protocol.md": hashlib.sha256(protocol).hexdigest()}}))
    return run


def test_formal_report_uses_saved_values_and_predefined_verdict(tmp_path):
    run = make_run(tmp_path)
    text = generate_report(run).read_text()
    assert "增量预测价值未获支持" in text
    assert "0.010000" in text and "[-0.005000, 0.020000]" in text
    assert "| 2024 | 2 | 0.020000 | 0.030000" in text
    assert "[daily_ic.csv](daily_ic.csv)" in text


def test_development_output_never_claims_hypothesis_support(tmp_path):
    run = make_run(tmp_path, formal=False)
    path = run / "summary.json"
    summary = json.loads(path.read_text())
    summary["paired_delta_bootstrap"]["ci_low"] = .005
    path.write_text(json.dumps(summary))
    text = generate_report(run).read_text()
    assert "不作样本外假设判定" in text
    assert "增量预测价值获得支持" not in text


def test_previously_seen_oos_is_marked(tmp_path):
    text = generate_report(make_run(tmp_path, seen=True)).read_text()
    assert "不是新的独立验证" in text


def test_missing_evidence_does_not_create_report(tmp_path):
    run = make_run(tmp_path)
    (run / "factor_ic.csv").unlink()
    with pytest.raises(FileNotFoundError, match="factor_ic"):
        generate_report(run)
    assert not (run / "report.md").exists()


def test_modified_frozen_protocol_is_rejected(tmp_path):
    run = make_run(tmp_path)
    (run / "protocol.md").write_text("edited after freeze")
    with pytest.raises(ValueError, match="已改变"):
        generate_report(run)
    assert not (run / "report.md").exists()


def test_existing_report_is_not_overwritten(tmp_path):
    run = make_run(tmp_path)
    output = generate_report(run)
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        generate_report(run)
    assert output.read_bytes() == original


@pytest.mark.parametrize("formal,status,mean_delta,ci_low,expected,report_phrase", [
    (True, "insufficient_dates", .01, None, "Hypothesis verdict unavailable: insufficient dates under this protocol.", "不能完成预设"),
    (True, "ok", .01, .005, "Hypothesis supported under this protocol.", "增量预测价值获得支持"),
    (True, "ok", .01, -.005, "Hypothesis not supported under this protocol.", "增量预测价值未获支持"),
    (True, "ok", 0., .005, "Hypothesis not supported under this protocol.", "增量预测价值未获支持"),
    (False, "ok", .01, .005, "In-sample development output; not an out-of-sample hypothesis verdict.", "不作样本外假设判定"),
])
def test_saved_summary_and_report_share_protocol_verdict(
        tmp_path, formal, status, mean_delta, ci_low, expected, report_phrase):
    # Catch missing insufficient-data handling and support without positive mean.
    from lab.artifacts import save_run
    from lab.config import load_config
    from lab.models import fit_models

    run = make_run(tmp_path, formal=formal)
    config_path = Path(__file__).resolve().parents[1] / "configs/reversal_volume.yaml"
    config = load_config(config_path)
    (run / "config.yaml").write_bytes(config_path.read_bytes())
    train = pd.DataFrame({"z_rev": [0., 1., 2.], "z_rv": [2., 0., 1.],
                          "z_vol20": [1., 2., 0.], "candidate": [0., 2., 1.],
                          "label": [.01, .02, -.01]})
    models = fit_models(train, config)
    daily = pd.read_csv(run / "daily_ic.csv", index_col="datetime", parse_dates=True)
    daily["with_candidate"] = daily["baseline"] + mean_delta
    daily["delta"] = mean_delta
    interval = json.loads((run / "summary.json").read_text())["paired_delta_bootstrap"]
    interval.update(status=status, mean_delta=mean_delta, ci_low=ci_low,
                    ci_high=None if status != "ok" else .02)
    auxiliary = {name: pd.read_csv(run / (name + ".csv"), index_col=0)
                 for name in ["factor_ic", "quintile_returns", "quintile_counts", "rank_change"]}
    save_run(run, formal, daily, pd.DataFrame(), models, interval, len(train), auxiliary, config)
    summary = json.loads((run / "summary.json").read_text())
    assert summary["interpretation"] == expected
    assert report_phrase in generate_report(run).read_text()
