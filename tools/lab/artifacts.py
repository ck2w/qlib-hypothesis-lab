import os
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import load_config
from .models import MODEL_FEATURES
from .evaluate import bootstrap_delta, hypothesis_verdict


def canonical_config_hash(config):
    """Hash semantic YAML content, independent of mapping order/whitespace."""
    data = json.dumps(config, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def verify_frozen_run(run_dir, execution_config):
    """Reject drift before loading data; return the validated frozen config."""
    run_dir = Path(run_dir).resolve()
    root = Path(__file__).resolve().parents[2]
    freeze = json.loads((run_dir / "freeze.json").read_text())
    if "config_canonical_sha256" not in freeze:
        raise ValueError("旧快照没有规范化配置哈希，不能视为通过新的运行前检查。")
    for name, digest in freeze["hashes"].items():
        path = (run_dir / name).resolve()
        if not path.is_relative_to(run_dir) or not path.is_file():
            raise ValueError(f"冻结文件缺失或路径无效：{name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"冻结文件发生变化：{name}")
    config = load_config(run_dir / "config.yaml")
    resolved = json.loads((run_dir / "resolved-config.json").read_text())
    expected = freeze["config_canonical_sha256"]
    if any(canonical_config_hash(value) != expected
           for value in [config, resolved, execution_config]):
        raise ValueError("实际执行配置与冻结配置不一致。")
    for name, digest in freeze["runtime_files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"当前代码或依赖文件缺失：{name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"当前代码或依赖与冻结版本不一致：{name}")
    frozen_modules = {name for name in freeze["runtime_files"] if name.startswith("tools/lab/")}
    current_modules = {str(path.relative_to(root)) for path in (root / "tools/lab").glob("*.py")}
    if current_modules != frozen_modules:
        raise ValueError("当前代码模块集合与冻结版本不一致。")
    if str(Path(os.environ["QLIB_DATA_DIR"]).resolve()) != freeze["data_path"]:
        raise ValueError("实际数据路径与冻结记录不一致。")
    return config


def new_run_directory(full):
    root = Path(__file__).resolve().parents[2]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = root / "runs" / f"{'full' if full else 'dev'}-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def create_run(full, protocol, config_path, config, run_dir=None):
    """Freeze input snapshots in a fresh run or tracker-owned empty directory."""
    root = Path(__file__).resolve().parents[2]
    if run_dir is None:
        run_dir = new_run_directory(full)
    else:
        run_dir = Path(run_dir)
        if any(p.name not in {"manifest.json", "checks.json"} for p in run_dir.iterdir()):
            raise ValueError("目标运行目录已有产物，不能覆盖。")
    source_config = load_config(config_path)
    if canonical_config_hash(source_config) != canonical_config_hash(config):
        raise ValueError("配置在读取后、冻结前发生变化。")
    config_bytes = config_path.read_bytes()
    (run_dir / "config.yaml").write_bytes(config_bytes)
    (run_dir / "resolved-config.json").write_text(
        json.dumps(config, sort_keys=True, indent=2) + "\n"
    )
    if full:
        files = {
            "protocol.md": protocol,
            "config.yaml": run_dir / "config.yaml",
            "tools/research_config.py": root / "tools" / "research_config.py",
            "resolved-config.json": run_dir / "resolved-config.json",
            "tools/manual_experiment.py": root / "tools" / "manual_experiment.py",
            "uv.lock": root / "uv.lock", "pyproject.toml": root / "pyproject.toml",
        }
        # Freeze every implementation module, not only the CLI wrapper.
        files.update({str(path.relative_to(root)): path for path in
                      (root / "tools" / "lab").glob("*.py")})
        hashes = {}
        for name, source in files.items():
            data = source.read_bytes()
            target = run_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            hashes[name] = hashlib.sha256(data).hexdigest()
        freeze = {
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "hashes": hashes,
            "config_canonical_sha256": canonical_config_hash(config),
            "runtime_files": {name: digest for name, digest in hashes.items()
                              if name.startswith("tools/") or name in ["uv.lock", "pyproject.toml"]},
            "git_head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "working_tree_status": subprocess.check_output(
                ["git", "status", "--short"], cwd=root, text=True
            ),
            "data_path": str(Path(os.environ["QLIB_DATA_DIR"]).resolve()),
            "periods": config["periods"],
            "oos_previously_seen": config["research"]["oos_previously_seen"],
        }
        (run_dir / "freeze.json").write_text(json.dumps(freeze, indent=2) + "\n")
    return run_dir


def save_run(run_dir, full, daily_ic, predictions, models, interval, n_train, auxiliary, config):
    """Save evidence into the run directory created before calculation."""
    daily_ic.to_csv(run_dir / "daily_ic.csv")
    predictions.to_csv(run_dir / ("oos_predictions.csv" if full else "train_predictions.csv"))
    for name, table in auxiliary.items():
        table.to_csv(run_dir / f"{name}.csv")
    paired_dates = daily_ic.dropna(subset=["baseline", "with_candidate"])
    annual = paired_dates.groupby(paired_dates.index.year).agg(
        n_dates=("delta", "count"), baseline=("baseline", "mean"),
        with_candidate=("with_candidate", "mean"), delta=("delta", "mean"),
    )
    annual.index.name = "year"
    annual.to_csv(run_dir / "annual_ic.csv")
    annual_intervals = {
        str(year): bootstrap_delta(group["delta"], **config["bootstrap"])
        for year, group in paired_dates.groupby(paired_dates.index.year)
    }
    (run_dir / "annual_intervals.json").write_text(
        json.dumps(annual_intervals, indent=2, allow_nan=False) + "\n"
    )
    paired = daily_ic.dropna(subset=["baseline", "with_candidate"])
    summary = {
        "run_type": "formal_out_of_sample" if full else "development_in_sample",
        "signal_start": config["periods"]["oos_start"] if full else config["periods"]["train_start"],
        "signal_end": str((pd.Timestamp(config["periods"]["oos_end_exclusive"]) - pd.Timedelta(days=1)).date())
        if full else config["periods"]["development_end"],
        "oos_previously_seen": config["research"]["oos_previously_seen"],
        "config_sha256": hashlib.sha256((run_dir / "config.yaml").read_bytes()).hexdigest(),
        "config_canonical_sha256": canonical_config_hash(config),
        "protocol_frozen": full, "n_train": n_train, "n_evaluation": len(predictions),
        "mean_ic": {
            name: float(paired[name].mean()) if len(paired) else None
            for name in MODEL_FEATURES
        },
        "paired_delta_bootstrap": interval,
        "models": {
            name: {
                "alpha": model.alpha, "fit_intercept": model.fit_intercept,
                "intercept": float(model.intercept_),
                "coefficients": dict(zip(MODEL_FEATURES[name], model.coef_.tolist())),
            }
            for name, model in models.items()
        },
        "interpretation": {
            "development": "In-sample development output; not an out-of-sample hypothesis verdict.",
            "unavailable": "Hypothesis verdict unavailable: insufficient dates under this protocol.",
            "supported": "Hypothesis supported under this protocol.",
            "not_supported": "Hypothesis not supported under this protocol.",
        }[hypothesis_verdict(full, interval)],
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    return run_dir
