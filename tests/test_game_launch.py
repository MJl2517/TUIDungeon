"""Studio launches an SDL window without depending on a terminal emulator."""

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tuidungeon.tooling import launcher


class GameLaunchTests(unittest.TestCase):
    def test_launch_argv_and_desktop_requirements(self):
        with (
            patch.object(
                launcher.subprocess, "CREATE_NO_WINDOW", 0x8000000, create=True
            ),
            patch.object(launcher.subprocess, "Popen") as spawn,
            patch.object(launcher.threading, "Thread") as waiter,
        ):
            root = Path("packs with spaces")
            for platform, flags, detached in (
                ("win32", 0x8000000, False),
                ("linux", 0, True),
            ):
                with (
                    patch.object(launcher.sys, "platform", platform),
                    patch.dict(os.environ, {"DISPLAY": ":0"}, clear=True),
                ):
                    launcher.open_test_map(root, "base:crypt", 42)
                command = spawn.call_args.args[0]
                self.assertEqual(
                    command[:5],
                    [launcher.sys.executable, "-X", "utf8", "-m", "tuidungeon"],
                )
                self.assertNotIn("--terminal", command)
                self.assertEqual(command[command.index("--test-map") + 1], "base:crypt")
                self.assertEqual(command[command.index("--packs-dir") + 1], str(root))
                self.assertEqual(command[command.index("--seed") + 1], "42")
                self.assertTrue(Path(command[-1]).name.startswith("studio-"))
                self.assertEqual(spawn.call_args.kwargs["creationflags"], flags)
                self.assertEqual(spawn.call_args.kwargs["start_new_session"], detached)
                self.assertEqual(spawn.call_args.kwargs["cwd"], launcher.PROJECT_ROOT)
                self.assertEqual(
                    waiter.call_args.kwargs,
                    {"target": spawn.return_value.wait, "daemon": True},
                )
            spawn.reset_mock()
            with (
                patch.object(launcher.sys, "platform", "linux"),
                patch.dict(os.environ, {}, clear=True),
            ):
                with self.assertRaisesRegex(OSError, "графический сеанс"):
                    launcher.open_test_map(root, "base:crypt", 42)
            spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
