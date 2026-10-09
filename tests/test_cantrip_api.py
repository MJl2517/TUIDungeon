"""HTTP contracts for the shared spell schemas and isolated playtests."""

import unittest

from fastapi.testclient import TestClient

from tests.test_studio import PackFixture
from tuidungeon.content.packs import ContentError, Referenced
from tuidungeon.tooling.server import create_app
from tuidungeon.domain.equipment import Equipment


class CantripAPITests(PackFixture):
    def test_repair_target_ids_are_authoritative_and_refresh_after_repair(self):
        app = create_app(self.root)
        client = TestClient(app, base_url="http://127.0.0.1")
        state = client.post(
            "/api/sessions",
            json={"map_ref": "base:crypt", "character_class": "base:wizard"},
        ).json()
        session = app.state.sessions[state["id"]]
        hero = session.engine.state.hero
        tools = [
            Equipment.create(hero.catalog.equipment[s])
            for s in ("crowbar", "thieves_tools")
        ]
        for item in tools:
            item.wear(1)
        hero.inventory.extend(tools)
        url = f"/api/sessions/{state['id']}/commands"
        state = client.post(url, json={"command": "wait"}).json()
        mending = next(s for s in state["hero"]["spells"] if s["id"] == "mending")
        self.assertEqual(mending["item_targets"], [i.instance_id for i in tools])
        result = client.post(
            url,
            json={
                "command": "cast",
                "spell_id": "base:mending",
                "item": tools[0].instance_id,
            },
        )
        self.assertEqual(result.status_code, 200, result.text)
        state = result.json()
        mending = next(s for s in state["hero"]["spells"] if s["id"] == "mending")
        self.assertEqual(mending["item_targets"], [tools[1].instance_id])
        light = next(s for s in state["hero"]["spells"] if s["id"] == "light")
        self.assertEqual(light["item_targets"], [i.instance_id for i in hero.inventory])

    def test_cast_item_cell_and_reset_via_http(self):
        client = TestClient(create_app(self.root), base_url="http://127.0.0.1")
        start = client.post(
            "/api/sessions",
            json=dict(
                map_ref="base:crypt",
                character_class="base:wizard",
                cantrips=["base:light", "base:dancing_lights", "base:mage_hand"],
                seed=3,
            ),
        )
        self.assertEqual(start.status_code, 200, start.text)
        state = start.json()
        identifier = state["id"]
        url = f"/api/sessions/{identifier}/commands"
        initial_charges = state["hero"]["cantrip_uses"]
        item = state["hero"]["inventory"][0]["id"]
        invalid = client.post(url, json=dict(command="cast", spell_id="base:light"))
        self.assertEqual(invalid.status_code, 200, invalid.text)
        self.assertEqual(invalid.json()["turns"], 0)
        lit = client.post(
            url, json=dict(command="cast", spell_id="base:light", item=item)
        )
        self.assertEqual(lit.status_code, 200, lit.text)
        self.assertEqual(lit.json()["hero"]["cantrip_uses"], initial_charges - 1)
        glowing = next(i for i in lit.json()["hero"]["inventory"] if i["id"] == item)
        self.assertIn("glowing", glowing["tags"])
        self.assertEqual(
            glowing["glow"], {"remaining_turns": 10, "radius": 6, "bright_radius": 3}
        )
        position = lit.json()["position"]
        dancing = client.post(
            url, json=dict(command="cast", spell_id="base:dancing_lights", **position)
        )
        self.assertEqual(dancing.status_code, 200, dancing.text)
        self.assertTrue(dancing.json()["hero"]["concentrating"])
        rested = client.post(url, json=dict(command="short_rest")).json()
        self.assertFalse(rested["hero"]["concentrating"])
        self.assertTrue(
            all(
                i["glow"] is None and "glowing" not in i["tags"]
                for i in rested["hero"]["inventory"]
            )
        )
        reset = client.post(f"/api/sessions/{identifier}/reset").json()
        self.assertEqual(reset["hero"]["cantrip_uses"], initial_charges)
        self.assertEqual(reset["turns"], 0)
        self.assertFalse(reset["hero"]["concentrating"])

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
