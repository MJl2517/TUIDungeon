"""Repeated Studio launch reuses only the server for the same pack directory."""

from io import BytesIO
import json
from pathlib import Path
import unittest
import tempfile
import os
import subprocess
from unittest.mock import patch

from fastapi.testclient import TestClient

from tuidungeon.tooling import server


class StudioStartupTests(unittest.TestCase):
    def test_stale_frontend_rebuilds_once_and_missing_tools_explain_setup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            studio = root / "studio"
            (studio / "src").mkdir(parents=True)
            (studio / "dist/assets").mkdir(parents=True)
            (studio / "node_modules").mkdir()
            source = studio / "src/MapEditor.tsx"
            source.write_text("new UI", encoding="utf-8")
            index = studio / "dist/index.html"
            index.write_text("old UI", encoding="utf-8")
            os.utime(index, ns=(1, 1))
            with patch.object(server.shutil, "which", return_value=None):
                with self.assertRaisesRegex(ValueError, "setup"):
                    server.ensure_studio_build(root)

            def built(*args, **kwargs):
                index.write_text("new UI", encoding="utf-8")
                os.utime(
                    index,
                    ns=(
                        source.stat().st_mtime_ns + 1000000,
                        source.stat().st_mtime_ns + 1000000,
                    ),
                )

            with (
                patch.object(server.shutil, "which", return_value="npm"),
                patch.object(server.subprocess, "run", side_effect=built) as run,
            ):
                server.ensure_studio_build(root)
                server.ensure_studio_build(root)
                run.assert_called_once_with(
                    ["npm", "run", "build"], cwd=studio, check=True
                )
            os.utime(index, ns=(1, 1))
            with (
                patch.object(server.shutil, "which", return_value="npm"),
                patch.object(
                    server.subprocess,
                    "run",
                    side_effect=subprocess.CalledProcessError(1, "npm"),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "Не удалось собрать"):
                    server.ensure_studio_build(root)

    def test_status_identifies_pack_directory(self):
        client = TestClient(server.create_app(), base_url="http://127.0.0.1")
        self.assertEqual(
            client.get("/api/status").json(),
            {
                "studio": "TUI Dungeon Studio",
                "packs_dir": str(server.DEFAULT_PACKS.resolve()),
            },
        )

    def test_repeat_launch_reuses_matching_server_and_respects_no_browser(self):
        for root in (None, Path("packs with spaces")):
            for open_browser in (False, True):
                with (
                    self.subTest(root=root, open_browser=open_browser),
                    patch.object(server.socket, "socket") as socket,
                    patch.object(server, "urlopen") as request,
                    patch.object(server.webbrowser, "open") as browser,
                    patch.object(server, "create_app") as create,
                    patch("uvicorn.run") as run,
                ):
                    socket.return_value.__enter__.return_value.connect_ex.return_value = 0
                    request.return_value = BytesIO(
                        json.dumps(
                            {
                                "studio": "TUI Dungeon Studio",
                                "packs_dir": str(
                                    (root or server.DEFAULT_PACKS).resolve()
                                ),
                            }
                        ).encode()
                    )
                    server.serve(8765, open_browser, root)
                    self.assertEqual(browser.call_count, int(open_browser))
                    create.assert_not_called()
                    run.assert_not_called()

    def test_occupied_port_does_not_reuse_another_project_or_service(self):
        for payload in (
            b"not JSON",
            b'{"studio": "another app"}',
            json.dumps({"studio": "TUI Dungeon Studio", "packs_dir": "other"}).encode(),
        ):
            with (
                self.subTest(payload=payload),
                patch.object(server.socket, "socket") as socket,
                patch.object(server, "urlopen", return_value=BytesIO(payload)),
                patch.object(server.webbrowser, "open") as browser,
                patch("uvicorn.run") as run,
            ):
                socket.return_value.__enter__.return_value.connect_ex.return_value = 0
                with self.assertRaisesRegex(OSError, "Порт 8765 занят"):
                    server.serve()
                browser.assert_not_called()
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
