from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from research_config import load_config, build_fields
from manual_experiment import fit_models, prepare_model_samples, bootstrap_delta

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "reversal_volume.yaml"


def write_config(tmp_path, config):
    path = tmp_path / "research.yaml"
    path.write_text(yaml.safe_dump(config))
    return path


def test_rejects_overlapping_periods(tmp_path):
    config = load_config(CONFIG)
    config["periods"]["oos_start"] = "2023-01-01"
    with pytest.raises(ValueError, match="重叠"):
        load_config(write_config(tmp_path, config))


def test_rejects_future_feature(tmp_path):
    config = load_config(CONFIG)
    config["features"]["rev"]["expression"] = "Ref($close, -1) / $close - 1"
    with pytest.raises(ValueError, match="未来"):
        load_config(write_config(tmp_path, config))


def test_formula_is_read_from_config(tmp_path):
    config = load_config(CONFIG)
    config["features"]["rev"].update(
        expression="1 - $close / Ref($close, 10)",
        count_expression="Count($close, 11)", required_count=11,
    )
    fields = build_fields(load_config(write_config(tmp_path, config)))
    assert fields["rev"] == "1 - $close / Ref($close, 10)"
    assert fields["count_rev"] == "Count($close, 11)"


def test_label_offsets_and_split_are_consistent(tmp_path):
    config = load_config(CONFIG)
    config["label"] = {"entry_offset": 2, "exit_offset": 4}
    config = load_config(write_config(tmp_path, config))
    fields = build_fields(config)
    assert fields["label"] == "Ref($open, -4) / Ref($open, -2) - 1"
    calendar = pd.bdate_range("2023-12-01", "2026-01-20")
    dates = pd.to_datetime(["2023-12-01", "2023-12-29", "2024-01-02", "2025-12-31"])
    index = pd.MultiIndex.from_product([["TEST"], dates], names=["instrument", "datetime"])
    signals = pd.DataFrame({"label": .1, "entry_open": 10., "exit_open": 11.}, index=index)
    train, oos, stats = prepare_model_samples(signals, calendar, config)
    assert stats["purged_train_rows"] == 1
    assert train.iloc[0]["label_start"] == calendar[2]
    assert train.iloc[0]["label_end"] == calendar[4]
    assert oos.iloc[-1]["label_end"].year == 2026


def test_model_alpha_changes_actual_fit():
    config = load_config(CONFIG)
    changed = deepcopy(config)
    changed["model"]["alpha"] = 10000.
    frame = pd.DataFrame(
        np.random.default_rng(42).normal(size=(40, 5)),
        columns=["z_rev", "z_rv", "z_vol20", "candidate", "label"],
    )
    original = fit_models(frame, config)
    updated = fit_models(frame, changed)
    assert not np.allclose(original["baseline"].coef_, updated["baseline"].coef_)


def test_configured_confidence_changes_interval():
    config = load_config(CONFIG)
    delta = pd.Series(np.random.default_rng(42).normal(size=80))
    wide = bootstrap_delta(delta, **config["bootstrap"])
    config["bootstrap"]["confidence"] = .5
    narrow = bootstrap_delta(delta, **config["bootstrap"])
    assert narrow["ci_low"] >= wide["ci_low"]
    assert narrow["ci_high"] <= wide["ci_high"]


@pytest.mark.parametrize("expression", [
    "__import__('os').getcwd()", "($close).__class__", "$close[0]",
    "Unknown($close, 5)", "$adjclose", "close / Ref($close, 5)",
    "Mean($close, window=5)", "Mean($close, 0)", "Mean($close, 2.5)",
    "-($close / Ref($close, 5) - 1)", "1e999 * $close",
])
def test_expression_whitelist_rejects_unsupported_syntax(tmp_path, expression):
    config = load_config(CONFIG)
    config["features"]["rev"]["expression"] = expression
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, config))


@pytest.mark.parametrize("change", ["short_count", "count_mismatch", "wrong_field", "wrong_denominator"])
def test_window_conditions_match_feature(tmp_path, change):
    config = load_config(CONFIG)
    if change == "short_count":
        config["features"]["rv"].update(count_expression="Count($volume, 5)", required_count=5)
    elif change == "count_mismatch":
        config["features"]["rv"]["required_count"] = 59
    elif change == "wrong_field":
        config["features"]["rv"]["count_expression"] = "Count($close, 60)"
    else:
        config["features"]["rv"]["positive_denominator"] = "Mean($volume, 5)"
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, config))


def test_block_length_covers_label_holding_period(tmp_path):
    config = load_config(CONFIG)
    config["bootstrap"]["block_length"] = 4
    with pytest.raises(ValueError, match="持有期"):
        load_config(write_config(tmp_path, config))


@pytest.mark.parametrize("value", ["NaT", "not-a-date", "2024-02-30"])
def test_invalid_dates_are_rejected(tmp_path, value):
    config = load_config(CONFIG)
    config["periods"]["train_start"] = value
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, config))


def test_unknown_feature_role_is_rejected(tmp_path):
    config = load_config(CONFIG)
    config["features"]["unknown"] = config["features"].pop("rev")
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, config))
