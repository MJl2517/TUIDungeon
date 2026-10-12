"""Editor HTTP contracts for spell schemas and content references."""

import unittest

from fastapi.testclient import TestClient

from tests.test_studio import PackFixture
from tuidungeon.content.packs import ContentError, Referenced
from tuidungeon.tooling.server import create_app


class CantripAPITests(PackFixture):
    def test_parameter_schema_and_invalid_class_references_are_checked(self):
        client = TestClient(create_app(self.root), base_url="http://127.0.0.1")
        schemas = client.get("/api/schemas").json()["schemas"]
        world = schemas["spells"]["properties"]["world_effect"]["world_schemas"]
        self.assertEqual(world["hand"]["properties"]["max_weight"]["default"], 2.0)
        for ref in ("base:missing", "base:daylight"):
            raw = self.store.get("classes", "base:wizard").model_dump(mode="json")
            raw["cantrip_choices"][0] = ref
            with self.assertRaises(ContentError):
                self.store.save(
                    "classes",
                    "base:wizard",
                    raw,
                    self.store.versions["classes", "base:wizard"],
                )
        with self.assertRaises(Referenced):
            self.store.delete(
                "spells", "base:light", self.store.versions["spells", "base:light"]
            )


if __name__ == "__main__":
    unittest.main()
