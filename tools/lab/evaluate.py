import numpy as np
import pandas as pd

from .models import MODEL_FEATURES


def evaluate_daily_ic(samples, predictions):
    """Compute paired model ICs on identical finite stock-date observations."""
    if not predictions.index.equals(samples.index):
        raise ValueError("预测和标签的股票日期索引不一致。")
    model_names = list(MODEL_FEATURES)
    evaluation = predictions[model_names].copy()
    evaluation["label"] = samples["label"]
    evaluation = evaluation.loc[np.isfinite(evaluation).all(axis=1)]
    rows = []
    for date, group in evaluation.groupby(level="datetime"):
        row = {"datetime": date, "n_stocks": len(group)}
        for name in model_names:
            if (len(group) < 2 or group[name].nunique() < 2
                    or group["label"].nunique() < 2):
                row[name] = np.nan
            else:
                # Average ranks preserve ties; Pearson of ranks is Spearman IC.
                row[name] = group[name].rank().corr(group["label"].rank())
        rows.append(row)
    daily = pd.DataFrame(
        rows, columns=["datetime", "n_stocks", *model_names]
    ).set_index("datetime")
    daily["delta"] = daily["with_candidate"] - daily["baseline"]
    # A missing IC on either side makes delta missing; never fill it with zero.
    return daily


def bootstrap_delta(delta, block_length=20, n_resamples=1000, seed=42, confidence=0.95):
    """Moving blocks of paired daily IC differences, not stock-date rows."""
    values = delta.sort_index().dropna().to_numpy(dtype="float64")
    result = {
        "n_dates": len(values), "block_length": block_length,
        "n_resamples": n_resamples, "seed": seed, "confidence": confidence,
        "mean_delta": float(values.mean()) if len(values) else None,
        "ci_low": None, "ci_high": None,
    }
    if len(values) < block_length:
        result["status"] = "insufficient_dates"
        return result
    rng = np.random.default_rng(seed)
    blocks_needed = (len(values) + block_length - 1) // block_length
    starts = rng.integers(
        0, len(values) - block_length + 1,
        size=(n_resamples, blocks_needed),
    )
    indices = (starts[:, :, None] + np.arange(block_length)).reshape(n_resamples, -1)
    means = values[indices[:, :len(values)]].mean(axis=1)
    low, high = np.quantile(means, [(1 - confidence) / 2, (1 + confidence) / 2])
    result.update(status="ok", ci_low=float(low), ci_high=float(high))
    return result


def evaluate_auxiliary(signals, samples, calendar):
    """Fix ranks/groups on the signal pool before selecting valid labels."""
    factor_columns = ["z_rev", "z_rv", "candidate"]
    ic_rows = []
    for date, group in samples.groupby(level="datetime"):
        row = {"datetime": date}
        for name in factor_columns:
            valid = group.loc[np.isfinite(group[[name, "label"]]).all(axis=1)]
            row[name] = (
                valid[name].rank().corr(valid["label"].rank())
                if len(valid) >= 2 and valid[name].nunique() > 1
                and valid["label"].nunique() > 1 else np.nan
            )
        ic_rows.append(row)
    factor_ic = pd.DataFrame(
        ic_rows, columns=["datetime", *factor_columns]
    ).set_index("datetime")

    ranks = signals["candidate"].groupby(level="datetime").rank(
        method="average", pct=True
    )
    # Fixed intervals (0,.2], (.2,.4], ...; tied values stay together.
    groups = np.ceil(ranks * 5).clip(1, 5).astype(int)
    grouped_samples = samples[["label"]].copy()
    grouped_samples["quintile"] = groups.reindex(samples.index)
    grouped = grouped_samples.groupby([pd.Grouper(level="datetime"), "quintile"])
    quintile_returns = grouped["label"].mean().unstack("quintile").reindex(columns=range(1, 6))
    quintile_counts = grouped.size().unstack("quintile").reindex(columns=range(1, 6)).fillna(0)
    quintile_returns.columns = [f"q{i}" for i in range(1, 6)]
    quintile_counts.columns = [f"q{i}" for i in range(1, 6)]
    quintile_returns["q5_minus_q1"] = quintile_returns["q5"] - quintile_returns["q1"]

    wide_ranks = ranks.unstack("instrument").sort_index()
    calendar = pd.DatetimeIndex(calendar)
    calendar = calendar[(calendar >= wide_ranks.index.min()) & (calendar <= wide_ranks.index.max())]
    # Reindex prevents changes across a wholly missing date being treated as one day.
    wide_ranks = wide_ranks.reindex(calendar)
    rank_change = wide_ranks.diff().abs().mean(axis=1).rename("rank_change")
    rank_change.index.name = "datetime"
    return {
        "factor_ic": factor_ic,
        "quintile_returns": quintile_returns,
        "quintile_counts": quintile_counts,
        "rank_change": rank_change.to_frame(),
    }
