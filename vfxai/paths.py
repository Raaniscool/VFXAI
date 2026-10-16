"""Persistent per-user data paths, independent of source/build output folders."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _user_data_root() -> Path:
    override = os.environ.get("VFXAI_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "VFXAI"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "VFXAI"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base).expanduser() if base else Path.home() / ".local" / "share") / "VFXAI"


# On Windows this is %LOCALAPPDATA%\\VFXAI. On Linux it follows the XDG data
# directory; developers can explicitly redirect it with VFXAI_DATA_DIR.
STATE_DIR = _user_data_root()
DATASETS_DIR = STATE_DIR / "datasets"
CHECKPOINTS_DIR = STATE_DIR / "checkpoints"
EXPERIMENTS_DIR = STATE_DIR / "experiments"
GENERATIONS_DIR = STATE_DIR / "generations"
FEEDBACK_DIR = STATE_DIR / "feedback"
RUNTIME_DIR = STATE_DIR / "runtime"
LOGS_DIR = STATE_DIR / "logs"
SCHEMA_PATH = ROOT / "schemas" / "plan-v1.schema.json"
DIST_DIR = ROOT / "dist"


def ensure_state_dirs() -> None:
    for path in (
        STATE_DIR,
        DATASETS_DIR,
        CHECKPOINTS_DIR,
        EXPERIMENTS_DIR,
        GENERATIONS_DIR,
        FEEDBACK_DIR,
        RUNTIME_DIR,
        LOGS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
