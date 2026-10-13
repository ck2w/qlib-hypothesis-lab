"""Track lifecycle and failures independently of research calculations."""
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

from .report import generate_failure_report


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


class RunTracker:
    def __init__(self, run_dir, full, config_path):
        self.run_dir = Path(run_dir)
        self.started = time.perf_counter()
        packages = {}
        for name in ["pyqlib", "numpy", "pandas", "scikit-learn", "PyYAML"]:
            try:
                packages[name] = version(name)
            except PackageNotFoundError:
                packages[name] = None
        root = Path(__file__).resolve().parents[2]
        try:
            revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            dirty = subprocess.check_output(["git", "status", "--short"], cwd=root, text=True)
        except (OSError, subprocess.CalledProcessError):
            revision, dirty = None, None
        self.state = {
            "schema_version": 1, "status": "running", "stage": "validation",
            "run_type": "formal_out_of_sample" if full else "development_in_sample",
            "started_at_utc": now(), "command": [sys.executable, *sys.argv],
            "python": sys.version, "platform": platform.platform(), "packages": packages,
            "git_head": revision, "working_tree_status": dirty,
            "config_source": str(Path(config_path).resolve()),
            "data_path": os.environ.get("QLIB_DATA_DIR"),
            "completed_stages": [], "diagnostics": {},
        }
        self.save()

    def save(self):
        self.state["updated_at_utc"] = now()
        self.state["elapsed_seconds"] = time.perf_counter() - self.started
        write_json(self.run_dir / "manifest.json", self.state)
        write_json(self.run_dir / "checks.json", {
            "stage": self.state["stage"], "status": self.state["status"],
            "completed_stages": self.state["completed_stages"],
            "diagnostics": self.state["diagnostics"],
        })

    def stage(self, stage):
        previous = self.state["stage"]
        if previous not in self.state["completed_stages"]:
            self.state["completed_stages"].append(previous)
        self.state["stage"] = stage
        self.save()

    def record(self, **values):
        self.state["diagnostics"].update(values)
        self.save()

    def frozen_only(self):
        if not (self.run_dir / "freeze.json").is_file():
            raise ValueError("没有冻结记录，不能标记仅冻结完成。")
        self.state["status"] = "frozen"

    def complete(self):
        if self.state["status"] != "frozen":
            if not all((self.run_dir / name).is_file() for name in ["summary.json", "report.md"]):
                raise ValueError("缺少结果或报告，不能标记研究完成。")
            self.state["status"] = "completed"
        if self.state["stage"] not in self.state["completed_stages"]:
            self.state["completed_stages"].append(self.state["stage"])
        self.state["finished_at_utc"] = now()
        self.state["output_bytes"] = sum(p.stat().st_size for p in self.run_dir.rglob("*") if p.is_file())
        self.save()

    def fail(self, error):
        stage = self.state["stage"]
        if stage == "data" or (isinstance(error, KeyError) and error.args == ("QLIB_DATA_DIR",)):
            status = "data_failed"
        elif stage in {"validation", "freezing", "verification", "features", "samples"} or isinstance(error, AssertionError):
            status = "check_failed"
        else:
            status = "runtime_failed"
        self.state.update(status=status, finished_at_utc=now(), error={
            "type": type(error).__name__, "message": str(error),
        })
        (self.run_dir / "traceback.txt").write_text(traceback.format_exc())
        self.save()
        generate_failure_report(self.run_dir, self.state)


@contextmanager
def track_run(run_dir, full, config_path):
    tracker = RunTracker(run_dir, full, config_path)
    try:
        yield tracker
        tracker.complete()
    except Exception as error:
        tracker.fail(error)
        raise
