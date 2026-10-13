"""Generate a report solely from saved run evidence, without loading Qlib."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def number(value):
    return "N/A" if value is None or not np.isfinite(value) else f"{value:.6f}"


def interval_text(interval):
    if interval["status"] != "ok":
        return "无法估计（有效日期不足）"
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
            raise FileNotFoundError(f"报告证据缺失：{name}")
    freeze = None
    if formal:
        if not summary["protocol_frozen"]:
            raise ValueError("正式结果没有协议冻结记录。")
        freeze = json.loads((run_dir / "freeze.json").read_text())
        for name, digest in freeze["hashes"].items():
            source = (run_dir / name).resolve()
            if not source.is_relative_to(run_dir):
                raise ValueError("冻结文件路径超出运行目录。")
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise ValueError(f"冻结文件内容已改变：{name}")

    daily = pd.read_csv(run_dir / "daily_ic.csv", index_col="datetime", parse_dates=True)
    paired = daily.dropna(subset=["baseline", "with_candidate"])
    interval = summary["paired_delta_bootstrap"]
    if len(paired) != interval["n_dates"]:
        raise ValueError("日度 IC 与摘要的有效日期数不一致。")
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
    if not formal:
        verdict = "样本内开发运行，只检查工作流，不作样本外假设判定。"
    elif interval["status"] != "ok":
        verdict = "区间无法估计，不能完成预设的增量价值判定。"
    elif interval["mean_delta"] > 0 and interval["ci_low"] > 0:
        verdict = "在本协议下，候选的增量预测价值获得支持。"
    else:
        verdict = "在本协议下，候选的增量预测价值未获支持；不等于证明没有效果。"
    lines = [
        "# Qlib 研究运行报告", "", verdict, "",
        f"运行类型：{'样本外评价' if formal else '样本内开发'}。",
        f"评价信号日期：{summary['signal_start']} 至 {summary['signal_end']}。",
        f"训练样本：{summary['n_train']:,}；评价样本：{summary['n_evaluation']:,}；共同有效日期：{len(paired)}。", "",
    ]
    if summary.get("oos_previously_seen"):
        lines += ["本次使用的样本外期间已看过；这是工作流复现或探索性评价，不是新的独立验证。", ""]
    lines += ["## 主指标", "", "| 期间 | 有效日期 | 基准 IC | 加候选 IC | 配对增量 | bootstrap 区间 |",
              "|---|---:|---:|---:|---:|---|",
              f"| 合并 | {len(paired)} | {number(summary['mean_ic']['baseline'])} | {number(summary['mean_ic']['with_candidate'])} | {number(interval['mean_delta'])} | {interval_text(interval)} |"]
    for year, row in annual.iterrows():
        lines.append(f"| {year} | {int(row['n_dates'])} | {number(row['baseline'])} | {number(row['with_candidate'])} | {number(row['delta'])} | {interval_text(annual_intervals[str(year)])} |")
    lines += ["", f"移动日期块长 {interval['block_length']}，重采样 {interval['n_resamples']} 次，seed={interval['seed']}。",
              f"区间置信水平 {interval.get('confidence', .95):.0%}；合并样本外为主判定，年度结果为辅助。" if formal else "开发区间仅用于检查计算流程。", "",
              "两个模型使用相同的训练样本和每日评价股票；主增量只取共同有效 IC 日期。", "",
              "## 辅助结果", "", "| 单因子 | 平均日度 Rank IC |", "|---|---:|"]
    for name, value in factors.mean().items():
        lines.append(f"| {name} | {number(value)} |")
    lines += ["", "| 候选五分位 | 平均未来收益 |", "|---|---:|"]
    for name, value in quintiles.mean().items():
        lines.append(f"| {name} | {number(value)} |")
    lines += ["", f"平均信号百分位排名变化：{number(rank_changes['rank_change'].mean())}。这不是实际交易换手。", "",
              "单因子 IC 不替代组合增量判断。分组收益没有计入成本、借券约束和容量，不代表可实现交易收益。", "",
              "## 模型参数", "", "| 模型 | alpha | 截距 | 特征系数 |", "|---|---:|---:|---|"]
    for name, model in summary["models"].items():
        coefficients = "; ".join(f"{key}={number(value)}" for key, value in model["coefficients"].items())
        lines.append(f"| {name} | {model['alpha']} | {number(model['intercept'])} | {coefficients} |")
    lines += ["", "## 证据文件", "", "报告仅读取本次运行保存的文件；生成报告没有重新拟合模型或重新运行实验。", ""]
    for name in ["summary.json", *required]:
        lines.append(f"- [{name}]({name})")
    for name in ["manifest.json", "checks.json"]:
        if (run_dir / name).is_file():
            lines.append(f"- [{name}]({name})")
    if freeze:
        lines += ["- [freeze.json](freeze.json)", "",
                  f"协议 SHA-256：`{freeze['hashes']['protocol.md']}`。冻结文件哈希已检查。"]
    lines.append("")
    output = Path(output) if output else run_dir / "report.md"
    # Existing reports remain evidence; use a new output name to regenerate.
    with output.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    return output


def generate_failure_report(run_dir, state):
    """Write an explicit failed result without inventing metrics."""
    run_dir = Path(run_dir)
    evaluation = ("已执行，但本次流程失败，不能提供有效研究结论。"
                  if "evaluation" in state["completed_stages"]
                  else "未运行或未完成；不生成 IC、区间或假设结论。")
    lines = ["# Qlib 研究运行失败", "",
             f"状态：{state['status']}。", f"失败阶段：{state['stage']}。", "",
             f"错误：{state['error']['type']}: {state['error']['message']}", "",
             f"效果评价：{evaluation}", "",
             "这不是完成的研究结果；修复后应新建运行，不将失败记录改写成成功。", "",
             "- [manifest.json](manifest.json)", "- [checks.json](checks.json)",
             "- [traceback.txt](traceback.txt)", ""]
    output = run_dir / ("failure-report.md" if (run_dir / "report.md").exists() else "report.md")
    with output.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    return output
