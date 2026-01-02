from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.io_utils import read_json, write_json
from app.core.state import EXPERIMENTS_DIR, EXPERIMENTS_INDEX_PATH


def load_experiments_index() -> dict[str, Any]:
    return read_json(EXPERIMENTS_INDEX_PATH, {"experiments": [], "updated_at": None})


def save_experiments_index(idx: dict[str, Any]) -> None:
    idx["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(EXPERIMENTS_INDEX_PATH, idx)


def create_experiment(name: str, description: str | None = None, tags: dict[str, str] | None = None) -> dict[str, Any]:
    exp_id = __import__("uuid").uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    exp = {
        "experiment_id": exp_id,
        "name": name,
        "description": description,
        "tags": tags or {},
        "created_at": created_at,
        "updated_at": created_at,
        "run_count": 0,
    }
    idx = load_experiments_index()
    idx.setdefault("experiments", []).append(exp)
    save_experiments_index(idx)

    (EXPERIMENTS_DIR / exp_id / "runs").mkdir(parents=True, exist_ok=True)
    return exp


def get_experiment(exp_id: str) -> dict[str, Any] | None:
    idx = load_experiments_index()
    for exp in idx.get("experiments", []):
        if exp.get("experiment_id") == exp_id:
            return exp
    return None


def update_experiment(exp: dict[str, Any]) -> None:
    idx = load_experiments_index()
    out = []
    for item in idx.get("experiments", []):
        if item.get("experiment_id") == exp.get("experiment_id"):
            out.append(exp)
        else:
            out.append(item)
    idx["experiments"] = out
    save_experiments_index(idx)


def log_run(
    experiment_id: str,
    run_id: str | None,
    metrics: dict[str, float] | None = None,
    params: dict[str, Any] | None = None,
    tags: dict[str, str] | None = None,
    model_id: str | None = None,
) -> dict[str, Any]:
    exp = get_experiment(experiment_id)
    if not exp:
        raise ValueError("Experiment not found")

    run_id = run_id or __import__("uuid").uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    run_path = EXPERIMENTS_DIR / experiment_id / "runs" / f"{run_id}.json"

    existing = read_json(run_path, None)
    if existing is None:
        run = {
            "run_id": run_id,
            "experiment_id": experiment_id,
            "status": "running",
            "start_time": now,
            "end_time": None,
            "params": params or {},
            "metrics": metrics or {},
            "tags": tags or {},
            "model_id": model_id,
        }
        exp["run_count"] = int(exp.get("run_count", 0)) + 1
    else:
        run = existing
        run["params"].update(params or {})
        run["metrics"].update(metrics or {})
        run["tags"].update(tags or {})
        if model_id:
            run["model_id"] = model_id

    run["updated_at"] = now
    write_json(run_path, run)

    exp["updated_at"] = now
    update_experiment(exp)
    return run


def list_runs(experiment_id: str, limit: int = 100) -> list[dict[str, Any]]:
    runs_dir = EXPERIMENTS_DIR / experiment_id / "runs"
    runs: list[dict[str, Any]] = []
    if runs_dir.exists():
        for p in runs_dir.glob("*.json"):
            r = read_json(p, None)
            if isinstance(r, dict):
                runs.append(r)
    runs.sort(key=lambda r: r.get("start_time", ""), reverse=True)
    return runs[:limit]
