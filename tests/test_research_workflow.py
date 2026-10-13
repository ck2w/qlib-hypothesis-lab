"""Research semantics checks independent of Yahoo and local market data."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from lab.config import load_config
from lab.features import prepare_signals
from lab.evaluate import evaluate_daily_ic, bootstrap_delta
from lab import artifacts

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "reversal_volume.yaml"


def test_signals_use_membership_and_ignore_future_labels():
    dates = pd.to_datetime(["2018-01-02", "2018-01-03"])
    index = pd.MultiIndex.from_product([list("ABC"), dates], names=["instrument", "datetime"])
    panel = pd.DataFrame({
        "rev": [1., 2., 3., 4., 5., 6.], "rv": [2., 1., 4., 2., 6., 3.],
        "vol20": 1., "count_rev": 6, "count_rv": 60, "count_vol20": 20,
        "denominator_rv": 100., "label": .1,
    }, index=index)
    members = {"A": [(dates[0], dates[0])], "B": [(dates[0], dates[1])],
               "C": [(dates[1], dates[1])]}
    signals, _ = prepare_signals(panel, members, load_config(CONFIG))
    assert len(signals) == 4
    assert ("A", dates[1]) not in signals.index
    assert ("C", dates[0]) not in signals.index
    assert signals["z_vol20"].eq(0).all()
    panel["label"] = np.nan
    changed, _ = prepare_signals(panel, members, load_config(CONFIG))
    columns = ["z_rev", "z_rv", "z_vol20", "candidate"]
    pd.testing.assert_frame_equal(signals[columns], changed[columns])


def test_ic_uses_common_stocks_and_keeps_constant_days_missing():
    dates = pd.to_datetime(["2018-01-02", "2018-01-03"])
    index = pd.MultiIndex.from_product([list("ABC"), dates], names=["instrument", "datetime"])
    samples = pd.DataFrame({"label": [1., 1., 2., 2., 3., 3.]}, index=index)
    predictions = pd.DataFrame({"baseline": [1., 1., 2., 1., 3., 1.],
                                "with_candidate": [3., 3., 2., 2., np.nan, 1.]}, index=index)
    daily = evaluate_daily_ic(samples, predictions)
    assert daily.iloc[0]["n_stocks"] == 2
    np.testing.assert_allclose(daily.iloc[0][["baseline", "with_candidate", "delta"]], [1., -1., -2.])
    assert pd.isna(daily.iloc[1]["baseline"])
    assert pd.isna(daily.iloc[1]["delta"])


def test_bootstrap_preserves_constant_difference_and_seed():
    constant = pd.Series(np.full(61, .02))
    result = bootstrap_delta(constant)
    np.testing.assert_allclose([result[k] for k in ["mean_delta", "ci_low", "ci_high"]], [.02] * 3)
    assert bootstrap_delta(constant.iloc[:19])["status"] == "insufficient_dates"
    random = pd.Series(np.random.default_rng(42).normal(size=80))
    assert bootstrap_delta(random) == bootstrap_delta(random)


def test_freeze_includes_modules_and_preserves_snapshot(tmp_path, monkeypatch):
    root = tmp_path / "project"
    package = root / "tools" / "lab"
    package.mkdir(parents=True)
    for relative in ["tools/manual_experiment.py", "tools/research_config.py", "uv.lock", "pyproject.toml", "tools/lab/features.py"]:
        (root / relative).write_text("original contents")
    protocol = tmp_path / "protocol.md"
    protocol.write_text("approved protocol")
    monkeypatch.setattr(artifacts, "__file__", str(package / "artifacts.py"))
    monkeypatch.setattr(artifacts.subprocess, "check_output", lambda *a, **kw: "test-state\n")
    monkeypatch.setenv("QLIB_DATA_DIR", str(tmp_path / "data"))
    run = artifacts.create_run(True, protocol, CONFIG, load_config(CONFIG))
    manifest = json.loads((run / "freeze.json").read_text())
    assert "tools/lab/features.py" in manifest["hashes"]
    assert "config.yaml" in manifest["hashes"]
    for name, digest in manifest["hashes"].items():
        assert hashlib.sha256((run / name).read_bytes()).hexdigest() == digest
    (package / "features.py").write_text("later edits")
    assert (run / "tools/lab/features.py").read_text() == "original contents"
