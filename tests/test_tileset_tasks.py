"""Incremental tile requests must not resurrect completed prompts or lose edits."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import runpy
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

VIEWER = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "tools/tileset-viewer/server.py")
)
TaskStore, TaskConflict = VIEWER["TaskStore"], VIEWER["TaskConflict"]
revision = VIEWER["task_revision"]


class TaskQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "tasks.json"
        self.legacy = [
            dict(sheet="mono", tiles=[3, 2], prompt="Готовая листва"),
            dict(sheet="mono", tiles=[9], prompt="Новая стена"),
        ]
        self.path.write_text(
            json.dumps(self.legacy, ensure_ascii=False), encoding="utf-8"
        )
        self.store = TaskStore(self.path)

    def test_legacy_ids_are_stable_and_duplicate_prompts_stay_distinct(self):
        tasks, version = self.store.snapshot()
        self.assertEqual(tasks[0]["tiles"], [2, 3])
        self.assertEqual(tasks, self.store.snapshot()[0])
        self.store.save(tasks, version)
        self.assertEqual(tasks, TaskStore(self.path).snapshot()[0])
        duplicates = VIEWER["validate_tasks"]([self.legacy[0]] * 2)
        self.assertNotEqual(duplicates[0]["id"], duplicates[1]["id"])
        self.assertTrue(all(t["status"] == "pending" for t in tasks))

    def test_only_processed_task_leaves_markdown_and_survives_new_batches(self):
        tasks, version = self.store.snapshot()
        done_id = tasks[0]["id"]
        tasks, version = self.store.complete(
            [done_id], version, note="tiles:foliage_2; проверено"
        )
        md = self.path.with_name("tile-requests.md").read_text(encoding="utf-8")
        self.assertNotIn("Готовая листва", md)
        self.assertIn("Новая стена", md)
        self.assertIn(tasks[1]["id"] + "@" + revision(tasks[1]), md)
        tasks.append(dict(sheet="mono", tiles=[10], prompt="Следующая партия"))
        saved, _ = self.store.save(tasks, version)
        archived = next(t for t in saved if t["id"] == done_id)
        self.assertEqual(archived["prompt"], "Готовая листва")
        self.assertEqual(archived["completion_note"], "tiles:foliage_2; проверено")
        self.assertEqual(archived["status"], "completed")
        self.assertNotIn(
            "Готовая листва",
            self.path.with_name("tile-requests.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "Следующая партия",
            self.path.with_name("tile-requests.md").read_text(encoding="utf-8"),
        )

    def test_stale_browser_and_archive_edit_are_rejected(self):
        original, version = self.store.snapshot()
        completed, new_version = self.store.complete([original[0]["id"]], version)
        with self.assertRaises(TaskConflict):
            self.store.save(original, version)
        with self.assertRaises(TaskConflict):
            self.store.save(completed[1:], new_version)
        completed[0]["prompt"] = "Подмена архива"
        with self.assertRaises(TaskConflict):
            self.store.save(completed, new_version)
        self.assertEqual(self.store.read()[0]["prompt"], "Готовая листва")

    def test_cli_revision_prevents_finishing_changed_prompt_and_is_idempotent(self):
        tasks, version = self.store.snapshot()
        old_revision = revision(tasks[0])
        tasks[0]["prompt"] = "Листва с новыми механиками"
        tasks, _ = self.store.save(tasks, version)
        with self.assertRaises(TaskConflict):
            self.store.complete(
                [tasks[0]["id"]], revisions={tasks[0]["id"]: old_revision}
            )
        self.assertEqual(self.store.read()[0]["status"], "pending")
        revisions = {t["id"]: revision(t) for t in tasks}
        done, _ = self.store.complete(list(revisions), revisions=revisions)
        again, _ = self.store.complete(list(revisions), revisions=revisions)
        self.assertEqual(done, again)
        self.assertIn(
            "Новых заданий нет",
            self.path.with_name("tile-requests.md").read_text(encoding="utf-8"),
        )
        self.assertNotIn(
            "Листва с новыми механиками",
            self.path.with_name("tile-requests.md").read_text(encoding="utf-8"),
        )

    def test_separate_writers_preserve_each_others_completions(self):
        tasks, _ = self.store.snapshot()
        barrier = threading.Barrier(2)

        def complete(task):
            barrier.wait(timeout=5)
            TaskStore(self.path).complete(
                [task["id"]], revisions={task["id"]: revision(task)}
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(complete, tasks))
        self.assertTrue(all(t["status"] == "completed" for t in self.store.read()))

    def test_new_followup_can_target_completed_tiles_without_mutating_archive(self):
        tasks, version = self.store.snapshot()
        tasks, version = self.store.complete([tasks[0]["id"]], version)
        old = dict(tasks[0])
        tasks.append(
            dict(
                id="task_123456789abc",
                sheet=old["sheet"],
                tiles=old["tiles"],
                prompt="Поменять цвет листвы",
                status="pending",
            )
        )
        self.store.save(tasks, version)
        self.assertEqual(self.store.read()[0], old)
        self.assertIn(
            "Поменять цвет",
            self.path.with_name("tile-requests.md").read_text(encoding="utf-8"),
        )


class TaskQueueHttpTests(unittest.TestCase):
    def test_etag_completion_conflicts_and_pending_markdown(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            progress = root / "progress.json"
            progress.write_text(json.dumps(dict(mono=[], color=[], input=[])))
            root.joinpath("tasks.json").write_text(
                json.dumps([dict(sheet="mono", tiles=[1], prompt="Первое задание")])
            )
            server = VIEWER["create_server"](progress)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_port}"

            def request(path, data=None, version=None):
                headers = {"Origin": url, "Content-Type": "application/json"}
                if version:
                    headers["If-Match"] = version
                req = urllib.request.Request(
                    url + path,
                    data=json.dumps(data).encode() if data is not None else None,
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    return json.load(response), response.headers.get("ETag")

            try:
                tasks, version = request("/tasks.json")
                self.assertIsNotNone(version)
                completed, new_version = request(
                    "/tasks/complete", {"ids": [tasks[0]["id"]]}, version
                )
                self.assertEqual(completed[0]["status"], "completed")
                for stale in (None, version):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        request("/tasks.json", tasks, stale)
                    self.assertEqual(error.exception.code, 409)
                completed.append(dict(sheet="mono", tiles=[2], prompt="Новая партия"))
                request("/tasks.json", completed, new_version)
                md = (root / "tile-requests.md").read_text(encoding="utf-8")
                self.assertNotIn("Первое задание", md)
                self.assertIn("Новая партия", md)
                # Checks on the atlas remain independent of completion state.
                self.assertEqual(
                    json.loads(progress.read_text()), dict(mono=[], color=[], input=[])
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
