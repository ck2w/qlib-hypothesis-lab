# 命令与运行状态

以下命令从已确认的 `qlib-hypothesis-lab` 仓库根运行。skill 自身不包含计算工具副本；需要目标仓库的 `tools/`、`pyproject.toml`、`uv.lock` 与配置。安装位置可以变化，项目路径由用户工作区确定。

## 校验与测试

选定本次配置后，用实际路径替换示例。配置检查不取数：

```bash
PYTHONPATH=tools uv run --locked python -c 'from lab.config import load_config; load_config("configs/reversal_volume.yaml"); print("config valid")'
```

相关测试可按改动选择；全套为：

```bash
PYTHONPATH=tools uv run --locked python -m pytest -p no:cacheprovider tests -q
```

## 执行

开发模式在配置指定的样本内小片段上运行，输出不能作为样本外证据：

```bash
uv run --locked python tools/manual_experiment.py --config configs/reversal_volume.yaml
```

完整研究命令如下；仅当这个配置与协议是本次要执行的设计时使用：

```bash
uv run --locked python tools/manual_experiment.py --config configs/reversal_volume.yaml --full --protocol examples/reversal-volume/experiment.md
```

完整入口自动创建新的运行目录、冻结和核对输入、执行并生成报告。不要把上面的示例路径当成用户尚未定义假设的完成配置。

可选的输入检查：在完整命令中加 `--freeze-only`，仅冻结，不训练。对这个新目录单独核对：

```bash
uv run --locked python tools/check_freeze.py "$RUN_DIR" --config configs/reversal_volume.yaml
```

RUN_DIR 必须是该次命令实际打印的目录。代码或输入已改变时校验会拒绝，不通过改写旧快照绕过它。

## 已有结果

新运行自动生成报告；旧目录已有完整证据但尚无 report.md 时：

```bash
uv run --locked python tools/generate_report.py "$RUN_DIR"
```

该命令不训练；已有报告不覆盖。只读报告请求直接读取现有文件。

| 状态 | 处理 |
|---|---|
| running | 还未结束，不能提前报告成功 |
| frozen | 仅有输入快照，没有完成研究 |
| completed | 查看run_type区分开发与正式，读取主指标和报告 |
| data_failed | 依据数据路径/读取错误排障，保留失败记录 |
| check_failed | 解决配置、冻结、特征或样本检查问题后新建运行 |
| runtime_failed | 依据失败阶段及traceback定位错误，不填造结果 |

manifest/checks记录阶段、命令、环境及诊断；summary/daily_ic与年度文件提供效果证据。报告中的数字须能定位到这些文件。已看过的测试期间作为复现或探索性结果标记，不称新的独立验证。
