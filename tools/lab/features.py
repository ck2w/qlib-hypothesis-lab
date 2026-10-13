import numpy as np
import pandas as pd


def cross_sectional_zscore(values):
    """Standardize within each signal date; constant cross-sections become zero."""
    values = values.astype("float64")
    grouped = values.groupby(level="datetime")
    mean = grouped.transform("mean")
    std = grouped.transform(lambda x: x.std(ddof=0))
    return (values - mean) / std.mask(std.eq(0), 1.0)


def prepare_signals(panel, membership, config):
    """Build date-specific signals without selecting on future labels."""
    panel = panel.copy()
    periods = config["periods"]
    feature_columns = ["rev", "rv", "vol20"]
    panel["feature_valid"] = np.isfinite(panel[feature_columns]).all(axis=1)
    for name, feature in config["features"].items():
        panel["feature_valid"] &= panel[f"count_{name}"].eq(feature["required_count"])
        if "positive_denominator" in feature:
            panel["feature_valid"] &= panel[f"denominator_{name}"].gt(0)

    # Warm-up rows contribute history but are not research signal dates.
    # Do not use future label availability to select feature-valid rows.
    signal_period = (
        panel.index.get_level_values("datetime") >= pd.Timestamp(periods["train_start"])
    )
    eligible = panel.loc[signal_period & panel["feature_valid"]].copy()

    symbols = eligible.index.get_level_values("instrument").str.upper()
    dates = eligible.index.get_level_values("datetime")
    is_member = np.zeros(len(eligible), dtype=bool)
    for symbol, intervals in membership.items():
        # Use the same Yahoo ticker spelling as the download wrapper.
        symbol_matches = symbols == symbol.upper().replace(".", "-")
        for start, end in intervals:
            is_member |= symbol_matches & (dates >= start) & (dates <= end)
    signals = eligible.loc[is_member].copy()
    if signals.empty:
        raise ValueError("历史成员筛选后没有可用信号样本。")

    # Future labels are deliberately absent from all signal eligibility rules.
    z_columns = []
    for name in feature_columns:
        z_name = f"z_{name}"
        signals[z_name] = cross_sectional_zscore(signals[name])
        z_columns.append(z_name)
    candidate = config["candidate"]
    interaction = (signals[f"z_{candidate['left']}"]
                   * signals[f"z_{candidate['right']}"] * candidate["right_sign"])
    signals["candidate"] = cross_sectional_zscore(interaction)

    output_columns = z_columns + ["candidate"]
    daily_mean = signals[output_columns].groupby(level="datetime").mean()
    daily_std = signals[output_columns].groupby(level="datetime").std(ddof=0)
    # These check our transformations, not supplier data quality.
    assert np.isfinite(signals[output_columns]).all().all()
    assert np.allclose(daily_mean, 0, atol=1e-10)
    assert (np.isclose(daily_std, 1, atol=1e-10)
            | np.isclose(daily_std, 0, atol=1e-10)).all()

    stats = {
        "panel_shape": panel.shape,
        "window_valid_rows": len(eligible),
        "invalid_feature_rows": int((signal_period & ~panel["feature_valid"]).sum()),
        "max_abs_daily_mean": float(daily_mean.abs().max().max()),
        "min_daily_std": float(daily_std.min().min()),
        "max_daily_std": float(daily_std.max().max()),
    }
    return signals, stats
