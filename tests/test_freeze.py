from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from lab import artifacts
from lab.config import load_config
import manual_experiment as cli

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "reversal_volume.yaml"


@pytest.fixture
def frozen_run(tmp_path, monkeypatch):
    root = tmp_path / "project"
    package = root / "tools" / "lab"
    package.mkdir(parents=True)
    for relative in ["tools/manual_experiment.py", "tools/research_config.py", "uv.lock", "pyproject.toml", "tools/lab/features.py"]:
        (root / relative).write_text("original contents")
    protocol = tmp_path / "protocol.md"
    protocol.write_text("approved protocol")
    config_path = tmp_path / "config.yaml"
    config_path.write_bytes(CONFIG.read_bytes())
    monkeypatch.setattr(artifacts, "__file__", str(package / "artifacts.py"))
    original_check_output = artifacts.subprocess.check_output
    def git_state_only(command, **kwargs):
        if command[0] == "git":
            return "test-state\n"
        return original_check_output(command, **kwargs)
    monkeypatch.setattr(artifacts.subprocess, "check_output", git_state_only)
    monkeypatch.setenv("QLIB_DATA_DIR", str(tmp_path / "data"))
    config = load_config(config_path)
    run = artifacts.create_run(True, protocol, config_path, config)
    return run, root, protocol, config_path, config


def test_canonical_hash_ignores_yaml_key_order(tmp_path):
    config = load_config(CONFIG)
    reordered = dict(reversed(list(config.items())))
    path = tmp_path / "reordered.yaml"
    path.write_text(yaml.safe_dump(reordered, sort_keys=False))
    assert artifacts.canonical_config_hash(config) == artifacts.canonical_config_hash(load_config(path))
    changed = deepcopy(config)
    changed["label"]["exit_offset"] = 7
    assert artifacts.canonical_config_hash(config) != artifacts.canonical_config_hash(changed)
    changed = deepcopy(config)
    changed["features"]["rev"]["expression"] = "1 - $close / Ref($close, 4)"
    assert artifacts.canonical_config_hash(config) != artifacts.canonical_config_hash(changed)


def test_verified_execution_uses_frozen_config(frozen_run):
    run, _, _, _, config = frozen_run
    assert artifacts.verify_frozen_run(run, config) == config
    freeze = json.loads((run / "freeze.json").read_text())
    assert freeze["config_canonical_sha256"] == artifacts.canonical_config_hash(config)


def test_changed_execution_config_is_rejected(frozen_run):
    run, _, _, _, config = frozen_run
    changed = deepcopy(config)
    changed["model"]["alpha"] = 2.
    with pytest.raises(ValueError, match="配置"):
        artifacts.verify_frozen_run(run, changed)
    assert not (run / "summary.json").exists()


def test_changed_snapshot_is_rejected(frozen_run):
    run, _, _, _, config = frozen_run
    (run / "protocol.md").write_text("later protocol")
    with pytest.raises(ValueError, match="冻结"):
        artifacts.verify_frozen_run(run, config)


def test_changed_live_code_is_rejected(frozen_run):
    run, root, _, _, config = frozen_run
    (root / "tools/lab/features.py").write_text("changed implementation")
    with pytest.raises(ValueError, match="代码|依赖"):
        artifacts.verify_frozen_run(run, config)


def test_cli_stops_before_data_loading_on_freeze_mismatch(frozen_run, monkeypatch):
    run, _, protocol, config_path, _ = frozen_run
    (run / "protocol.md").write_text("changed before evaluation")
    monkeypatch.setattr(cli, "new_run_directory", lambda full: run)
    monkeypatch.setattr(cli, "create_run", lambda *args: run)
    def unexpected(*args, **kwargs):
        pytest.fail("冻结检查失败时不应初始化或读取数据")
    monkeypatch.setattr(cli.qlib, "init", unexpected)
    monkeypatch.setattr(cli, "load_research_data", unexpected)
    monkeypatch.setattr(sys, "argv", ["manual_experiment.py", "--full", "--protocol", str(protocol), "--config", str(config_path)])
    with pytest.raises(ValueError, match="冻结"):
        cli.main()
    assert not (run / "summary.json").exists()
