import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


@pytest.mark.parametrize("stage,expected,error", [
    ("data", "data_failed", FileNotFoundError("missing data")),
    ("features", "check_failed", ValueError("invalid features")),
    ("evaluation", "runtime_failed", RuntimeError("evaluation crashed")),
])
def test_failures_save_state_and_report(tmp_path, stage, expected, error):
    pipeline = importlib.import_module("lab.pipeline")
    run = tmp_path / "run"
    run.mkdir()
    with pytest.raises(type(error)):
        with pipeline.track_run(run, False, tmp_path / "config.yaml") as tracker:
            tracker.stage(stage)
            raise error
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["status"] == expected
    assert manifest["stage"] == stage
    assert manifest["error"]["type"] == type(error).__name__
    assert manifest["elapsed_seconds"] >= 0
    assert manifest["command"]
    assert manifest["python"]
    assert (run / "traceback.txt").is_file()
    assert (run / "checks.json").is_file()
    report = (run / "report.md").read_text()
    assert expected in report
    assert "Not run or incomplete" in report
    assert "# Qlib Research Run Failed" in report
    assert not (run / "summary.json").exists()


def test_success_requires_saved_results_and_report(tmp_path):
    pipeline = importlib.import_module("lab.pipeline")
    run = tmp_path / "run"
    run.mkdir()
    with pipeline.track_run(run, False, tmp_path / "config.yaml") as tracker:
        tracker.stage("report")
        (run / "summary.json").write_text("{}")
        (run / "report.md").write_text("development report")
    state = json.loads((run / "manifest.json").read_text())
    assert state["status"] == "completed"
    assert state["run_type"] == "development_in_sample"


def test_no_metrics_cannot_be_marked_complete(tmp_path):
    pipeline = importlib.import_module("lab.pipeline")
    run = tmp_path / "run"
    run.mkdir()
    with pytest.raises(ValueError, match="结果|报告"):
        with pipeline.track_run(run, False, tmp_path / "config.yaml"):
            pass
    assert json.loads((run / "manifest.json").read_text())["status"] != "completed"


def test_freeze_only_is_not_a_completed_experiment(tmp_path):
    pipeline = importlib.import_module("lab.pipeline")
    run = tmp_path / "run"
    run.mkdir()
    with pipeline.track_run(run, True, tmp_path / "config.yaml") as tracker:
        (run / "freeze.json").write_text("{}")
        tracker.frozen_only()
    state = json.loads((run / "manifest.json").read_text())
    assert state["status"] == "frozen"
    assert not (run / "summary.json").exists()


def test_failure_after_evaluation_does_not_claim_it_was_unrun(tmp_path):
    pipeline = importlib.import_module("lab.pipeline")
    run = tmp_path / "run"
    run.mkdir()
    with pytest.raises(RuntimeError):
        with pipeline.track_run(run, True, tmp_path / "config.yaml") as tracker:
            tracker.stage("evaluation")
            tracker.stage("save")
            raise RuntimeError("save failed")
    text = (run / "report.md").read_text()
    assert "Evaluation ran" in text
    assert "no valid research conclusion" in text
