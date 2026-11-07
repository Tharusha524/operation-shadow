"""Central place for file-system locations.

Works both when running from source (python main.py) and from a PyInstaller .exe.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    """Folder that contains main.py, data/ and assets/ (or the unpacked .exe bundle)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


ROOT_DIR = project_root()
ASSETS_DIR = ROOT_DIR / "assets"
DATA_DIR = ROOT_DIR / "data"
MAPS_DIR = DATA_DIR / "maps"


def user_data_dir() -> Path:
    """Writable folder for settings, saves and logs.

    From source: the project's data/ folder.
    As an .exe:  %LOCALAPPDATA%/OperationShadow (the install folder may be read-only).
    """
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OperationShadow"
    else:
        base = DATA_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base
