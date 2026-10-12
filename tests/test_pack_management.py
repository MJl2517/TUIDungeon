"""Pack editing validates the graph; deletion retains all files in an archive."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_studio import PackFixture
from tuidungeon.content.packs import PackStore
from tuidungeon.tooling.server import create_app


class PackManagementTests(PackFixture):
    def setUp(self):
        super().setUp()
        self.client = TestClient(create_app(self.root), base_url="http://127.0.0.1")

    def envelope(self, pack):
        response = self.client.get("/api/packs/" + pack)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_dependency_edit_fixes_map_save_without_restarting_session(self):
        self.client.post("/api/packs", json={"id": "test_demo", "name": "Demo"})
        raw = self.store.get("maps", "dev:crafting_lab").model_dump(mode="json")
        raw.update(
            id="demo_dungeon_1",
            objects=[
                dict(
                    id="light",
                    ref="base:light_bright",
                    x=3,
                    y=3,
                )
            ],
        )
        path = "/api/documents/maps/test_demo:demo_dungeon_1"
        response = self.client.put(path, json={"document": raw, "version": None})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("зависимост", response.text)
        envelope = self.envelope("test_demo")
        envelope["document"].update(
            name="Подземелье для тестов", version="1.1.0", dependencies=["base"]
        )
        response = self.client.put(
            "/api/packs/test_demo",
            json={
                "document": envelope["document"],
                "version": envelope["version"],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.put(path, json={"document": raw, "version": None})
        self.assertEqual(response.status_code, 200, response.text)
        updated = self.envelope("test_demo")
        self.assertEqual(updated["document_count"], 1)
        self.assertEqual(updated["document"]["name"], "Подземелье для тестов")
        self.assertEqual(
            PackStore(self.root).get("maps", "test_demo:demo_dungeon_1").id, raw["id"]
        )
        # Dependencies used by saved content cannot be removed.
        updated["document"]["dependencies"] = []
        rejected = self.client.put(
            "/api/packs/test_demo",
            json={
                "document": updated["document"],
                "version": updated["version"],
            },
        )
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(
            self.envelope("test_demo")["document"]["dependencies"], ["base"]
        )

    def test_graph_identity_and_conflicts_are_rejected_without_writes(self):
        self.client.post(
            "/api/packs",
            json={"id": "extra", "name": "Extra", "dependencies": ["base"]},
        )
        envelope = self.envelope("extra")
        path = self.root / "extra" / "manifest.json"
        original = path.read_bytes()
        for patch in (
            {"id": "renamed"},
            {"dependencies": ["missing"]},
            {"dependencies": ["extra"]},
        ):
            document = dict(envelope["document"], **patch)
            response = self.client.put(
                "/api/packs/extra",
                json={"document": document, "version": envelope["version"]},
            )
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(path.read_bytes(), original)
        base = self.envelope("base")
        base["document"]["dependencies"] = ["extra"]
        response = self.client.put(
            "/api/packs/base",
            json={"document": base["document"], "version": base["version"]},
        )
        self.assertEqual(response.status_code, 422)
        # An external edit invalidates both update and delete versions.
        document = dict(envelope["document"], name="Внешнее изменение")
        PackStore.atomic_json(path, document)
        for method, body in (
            ("PUT", {"document": envelope["document"], "version": envelope["version"]}),
            ("DELETE", {"version": envelope["version"]}),
        ):
            response = self.client.request(method, "/api/packs/extra", json=body)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), document)

    def test_delete_blocks_dependents_and_archives_the_entire_pack(self):
        self.client.post("/api/packs", json={"id": "parent", "name": "Parent"})
        self.client.post(
            "/api/packs",
            json={"id": "child", "name": "Child", "dependencies": ["parent"]},
        )
        parent = self.envelope("parent")
        self.assertEqual(parent["dependents"], [{"id": "child", "name": "Child"}])
        response = self.client.request(
            "DELETE", "/api/packs/parent", json={"version": parent["version"]}
        )
        self.assertEqual(response.status_code, 409)
        self.assertTrue((self.root / "parent").exists())
        base = self.envelope("base")
        response = self.client.request(
            "DELETE", "/api/packs/base", json={"version": base["version"]}
        )
        self.assertEqual(response.status_code, 422)
        child = self.envelope("child")
        art = self.store.get("art", "base:goblin").model_dump(mode="json")
        response = self.client.put(
            "/api/documents/art/child:goblin", json={"document": art, "version": None}
        )
        self.assertEqual(response.status_code, 200, response.text)
        # Preserve unrecognised files as well as content, not just manifest JSON.
        marker = self.root / "child" / "author-notes.txt"
        marker.write_text("Заметки автора", encoding="utf-8")
        response = self.client.request(
            "DELETE", "/api/packs/child", json={"version": child["version"]}
        )
        self.assertEqual(response.status_code, 200, response.text)
        archive = Path(response.json()["archive"])
        self.assertTrue(archive.is_relative_to(self.root))
        self.assertEqual(
            (archive / marker.name).read_text(encoding="utf-8"), "Заметки автора"
        )
        self.assertTrue((archive / "manifest.json").exists())
        self.assertTrue((archive / "art" / "goblin.art.json").exists())
        self.assertFalse((self.root / "child").exists())
        self.assertNotIn("child", PackStore(self.root).manifests)
        # Reload ignores the archive, and parent becomes removable.
        parent = self.envelope("parent")
        response = self.client.request(
            "DELETE", "/api/packs/parent", json={"version": parent["version"]}
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_unknown_pack_and_missing_or_stale_versions_are_rejected(self):
        self.assertEqual(self.client.get("/api/packs/missing").status_code, 422)
        self.client.post("/api/packs", json={"id": "safe", "name": "Safe"})
        envelope = self.envelope("safe")
        self.assertEqual(
            self.client.request("DELETE", "/api/packs/safe", json={}).status_code, 422
        )
        self.assertEqual(
            self.client.put(
                "/api/packs/safe",
                json={"document": envelope["document"], "version": "stale"},
            ).status_code,
            409,
        )
