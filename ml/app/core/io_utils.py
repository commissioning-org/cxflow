from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.state import logger


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"Failed to read json {path}: {e}")
    return default


def write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)
