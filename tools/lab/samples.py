import numpy as np
import pandas as pd


def prepare_model_samples(signals, calendar, config):
    """Apply label validity after signal construction; purge crossing train labels."""
    samples = signals.copy()
    dates = samples.index.get_level_values("datetime")
    calendar = pd.DatetimeIndex(calendar)
    periods = config["periods"]
    date_lookup = pd.Series(calendar, index=calendar)
    samples["label_start"] = date_lookup.shift(-config["label"]["entry_offset"]).reindex(dates).to_numpy()
    samples["label_end"] = date_lookup.shift(-config["label"]["exit_offset"]).reindex(dates).to_numpy()
    label_valid = (
        np.isfinite(samples[["label", "entry_open", "exit_open"]]).all(axis=1)
        & samples["entry_open"].gt(0)
        & samples["exit_open"].gt(0)
        & samples["label_start"].notna()
        & samples["label_end"].notna()
    )
    train_period = (dates >= periods["train_start"]) & (dates < periods["train_end_exclusive"])
    oos_period = (dates >= periods["oos_start"]) & (dates < periods["oos_end_exclusive"])
    crosses_boundary = train_period & samples["label_end"].ge(periods["oos_start"])
    train = samples.loc[label_valid & train_period & ~crosses_boundary].copy()
    oos = samples.loc[label_valid & oos_period].copy()
    # Both model feature sets are selected from these SAME frames later.
    stats = {
        "invalid_labels": int((~label_valid).sum()),
        "purged_train_rows": int((label_valid & crosses_boundary).sum()),
    }
    return train, oos, stats
