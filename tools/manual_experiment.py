"""Teaching CLI: orchestrates the reusable lab modules."""
import os
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import qlib

from lab.config import load_config, build_fields
from lab.data import load_research_data
from lab.features import cross_sectional_zscore, prepare_signals
from lab.samples import prepare_model_samples
from lab.models import MODEL_FEATURES, fit_models, predict_models
from lab.evaluate import evaluate_daily_ic, bootstrap_delta, evaluate_auxiliary
from lab.artifacts import create_run, save_run, verify_frozen_run, new_run_directory, canonical_config_hash
from lab.pipeline import track_run
from lab.report import generate_report


def main():
    parser = argparse.ArgumentParser(description="Manual Qlib factor research")
    parser.add_argument("--full", action="store_true", help="Frozen 2018-2023 train / 2024-2025 OOS run")
    parser.add_argument("--freeze-only", action="store_true", help="With --full: freeze and check inputs without loading data")
    parser.add_argument("--protocol", type=Path, help="Protocol Markdown to snapshot before a full run")
    parser.add_argument(
        "--config", type=Path,
        default=Path(__file__).resolve().parents[1] / "configs" / "reversal_volume.yaml",
    )
    args = parser.parse_args()
    if args.freeze_only and not args.full:
        parser.error("--freeze-only requires --full")
    if args.full and (args.protocol is None or not args.protocol.is_file()):
        parser.error("--full requires an existing --protocol file")
    run_dir = new_run_directory(args.full)
    print("本次运行目录:", run_dir, flush=True)
    with track_run(run_dir, args.full, args.config) as tracker:
        execute(args, run_dir, tracker)


def execute(args, run_dir, tracker):
    config = load_config(args.config)
    periods = config["periods"]
    tracker.record(config_canonical_sha256=canonical_config_hash(config),
                   seed=config["bootstrap"]["seed"], periods=periods)
    end_time = (
        str((pd.Timestamp(periods["oos_end_exclusive"]) - pd.Timedelta(days=1)).date())
        if args.full else periods["development_end"]
    )
    tracker.stage("freezing")
    create_run(args.full, args.protocol, args.config, config, run_dir)
    print("运行目录（正式模式已先保存冻结快照）:", run_dir, flush=True)
    if args.full:
        tracker.stage("verification")
        config = verify_frozen_run(run_dir, config)
        freeze = json.loads((run_dir / "freeze.json").read_text())
        tracker.record(protocol_sha256=freeze["hashes"]["protocol.md"],
                       frozen_input_hashes=freeze["hashes"])
        print("运行前冻结一致性检查通过。", flush=True)
        if args.freeze_only:
            print("仅冻结：没有取数、拟合或评价。")
            tracker.frozen_only()
            return
    tracker.stage("data")
    qlib.init(
        provider_uri=os.environ["QLIB_DATA_DIR"],
        region=config["data"]["region"],
        kernels=1,
    )

    panel, membership, calendar = load_research_data(config, end_time)
    tracker.stage("features")
    signals, feature_stats = prepare_signals(panel, membership, config)

    tracker.record(features=feature_stats)
    tracker.stage("samples")
    # Use the full stored trading calendar, not the development slice's end date.
    train, oos, sample_stats = prepare_model_samples(signals, calendar, config)
    assert (train["label_end"] < pd.Timestamp(periods["oos_start"])).all()
    assert train.index.intersection(oos.index).empty
    tracker.record(samples=sample_stats, n_train=len(train), n_oos=len(oos))
    tracker.stage("fit")
    models = fit_models(train, config)
    evaluation_samples = oos if args.full else train
    if evaluation_samples.empty:
        raise ValueError("没有可用于当前模式评价的样本。")
    predictions = predict_models(models, evaluation_samples)
    assert predictions.index.equals(evaluation_samples.index)
    assert np.isfinite(predictions).all().all()
    tracker.stage("evaluation")
    daily_ic = evaluate_daily_ic(evaluation_samples, predictions)
    paired = daily_ic.dropna(subset=["baseline", "with_candidate"])
    interval = bootstrap_delta(paired["delta"], **config["bootstrap"])
    # Ranking still uses the full feature-valid signal pool for each date.
    evaluation_dates = evaluation_samples.index.get_level_values("datetime").unique()
    evaluation_signals = signals.loc[
        signals.index.get_level_values("datetime").isin(evaluation_dates)
    ]
    auxiliary = evaluate_auxiliary(evaluation_signals, evaluation_samples, calendar)
    tracker.stage("save")
    save_run(run_dir, args.full, daily_ic, predictions, models, interval, len(train), auxiliary, config)
    tracker.stage("report")
    report_path = generate_report(run_dir)
    print("自动研究报告:", report_path)
    print("正式样本外评价" if args.full else "训练集开发检查（不是样本外结论）")
    print("共同有效日期数:", len(paired))
    print("无共同有效 IC 的日期数:", len(evaluation_dates) - len(paired))
    print("平均 IC 和配对增量:")
    print(paired[["baseline", "with_candidate", "delta"]].mean())
    print("配对增量 bootstrap:", interval)
    print("单因子平均 IC:")
    print(auxiliary["factor_ic"].mean())
    print("五分位平均未来收益（不是可交易组合回测）:")
    print(auxiliary["quintile_returns"].mean())
    print("平均信号排名变化（不是交易换手）:",
          auxiliary["rank_change"]["rank_change"].mean())
    print("输出目录:", run_dir)

    print("标签无效样本数:", sample_stats["invalid_labels"])
    print("训练边界剔除样本数:", sample_stats["purged_train_rows"])
    print("可用于两个模型的共同训练样本数:", len(train))
    print("样本外样本数:", len(oos))

    print("历史成员筛选后的信号样本数:", len(signals))
    print("特征处理摘要:", feature_stats)


if __name__ == "__main__":
    main()
