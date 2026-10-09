"""Launch the saved Studio map in the current runtime's SDL game window."""

import os
from pathlib import Path
import subprocess
import sys
import threading
from uuid import uuid4

from ..content.packs import PROJECT_ROOT


def open_test_map(
    root: Path, map_ref: str, seed: int, character_class: str = "base:warrior"
):
    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        raise OSError("Для игрового окна нужен графический сеанс Linux")
    command = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "tuidungeon",
        "--test-map",
        map_ref,
        "--test-class",
        character_class,
        "--packs-dir",
        str(root),
        "--seed",
        str(seed),
        "--save-file",
        str(PROJECT_ROOT / "saves" / f"studio-{uuid4().hex}.json"),
    ]
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        start_new_session=sys.platform.startswith("linux"),
    )
    threading.Thread(target=process.wait, daemon=True).start()
