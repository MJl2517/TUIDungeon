"""Repeated Studio launch reuses only the server for the same pack directory."""

from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tuidungeon.tooling import server


class StudioStartupTests(unittest.TestCase):
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
