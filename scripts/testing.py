"""Stable test maps; authoring the real base maps must not change test scenarios."""

from pathlib import Path
import shutil

from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.content.schemas import MapDocument

CRYPT_FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/crypt.json"
STORAGE_FIXTURE = (
    Path(__file__).resolve().parents[1] / "tests/fixtures/storage_lab.json"
)


def install_test_maps(root):
    root = Path(root).resolve()
    if root == DEFAULT_PACKS.resolve():
        raise ValueError("Тестовые карты нельзя устанавливать поверх рабочего контента")
    shutil.copyfile(CRYPT_FIXTURE, root / "base/maps/crypt.json")
    if (root / "dev/manifest.json").exists():
        shutil.copyfile(STORAGE_FIXTURE, root / "dev/maps/storage_lab.json")


def fixture_store():
    """Read content normally and substitute the fixed map only in this store."""
    store = PackStore()
    store.documents[("maps", "base:crypt")] = MapDocument.model_validate(
        PackStore.read_json(CRYPT_FIXTURE)
    )
    return store


def lay_bedroll(engine):
    """Set up a real sleeping place without spending the tested action's turn."""
    from tuidungeon.domain.equipment import Equipment
    from tuidungeon.world.state import ItemPlacement

    item = Equipment.create(engine.catalog.equipment["bedroll"])
    p = engine.state.position
    engine.state.items.append(
        (ItemPlacement(item.instance_id, "base:bedroll", p.x, p.y), item)
    )
