"""PyInstaller run-time hook for the onedir Windows release.

PySide6 extension modules load Qt6Core.dll while importing QtCore. Registering
these directories before any PySide6 import prevents the Windows loader from
depending on the caller's PATH or current working directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False) and sys.platform == "win32":
    root = Path(sys._MEIPASS)
    directories = (root, root / "PySide6", root / "shiboken6")
    active = [str(directory) for directory in directories if directory.is_dir()]
    for directory in active:
        os.add_dll_directory(directory)
    os.environ["PATH"] = os.pathsep.join([*active, os.environ.get("PATH", "")])
