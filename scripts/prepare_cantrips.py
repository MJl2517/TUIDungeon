"""Install reviewed cantrip definitions; existing authored spells stay untouched."""

import argparse
from pathlib import Path
from tuidungeon.content.packs import DEFAULT_PACKS, PackStore
from tuidungeon.content.schemas import SpellDocument


DESCRIPTIONS = {
    "light": "Предмет в инвентаре светится 10 ходов: яркий радиус 3, общий 6 клеток. Рука не нужна. Свет следует за предметом; новый Свет заменяет предыдущий.",
    "fire_bolt": "Атака заклинанием: 1d10 огнём. Явный поджог деревянной двери; масло добавляет 5 урона. Разрушение остальной мебели пока не реализовано.",
    "mending": "Починка переносимого предмета: инструмент +1 стойкости, оружие или доспех +1d4. Можно починить сохранённый сломанный предмет (0 стойкости), но не вернуть уничтоженный.",
    "toll_the_dead": "Спасбросок Мудрости: при провале 1d8 некротического урона, либо 1d12 по раненой цели. Успех полностью избегает урона.",
    "acid_splash": "Спасбросок Ловкости каждой цели: при провале 1d6 кислотой. До двух соседних целей; размещение боевых целей подключит будущий JRPG-режим.",
    "ray_of_frost": "Атака заклинанием: 1d8 холодом. Попадание гасит горящую дверь. Замедление и замораживание жидкостей появятся позже.",
    "shocking_grasp": "Атака заклинанием по соседней клетке: 1d8 молнией. Блокировка реакций и электрические устройства появятся позже.",
    "mage_hand": "Рука на 5 ходов, дальность 4 клетки, предметы до 2 кг. Действия → 4: принести предмет, открыть незапертую дверь, достать лёгкий предмет из контейнера или активировать ловушку. Не атакует и не взламывает.",
    "minor_illusion": "Неподвижная иллюзия на выбранной клетке (5 ходов) или событие звука. Пока это видимая метка/звук; отвлечение патрулей и боевой контроль появятся вместе с AI и боем.",
    "prestidigitation": "Выберите эффект: поджечь деревянную дверь/масло, погасить горящую дверь, оставить метку на 5 ходов или создать звук. AI на звук пока не реагирует.",
    "poison_spray": "Спасбросок Телосложения против СЛ заклинателя; провал — 1d12 ядом, успех — без урона. Дальность 3 клетки. Не накладывает отравление автоматически.",
    "chill_touch": "Атака заклинанием по соседней цели: 1d10 некротического урона. Блокировка лечения появится в будущем бою.",
    "thunderclap": "В боевом адаптере: спасбросок Телосложения каждой цели, провал — 1d6 громом. В исследовании создаёт событие шума, без урона и реакции ещё отсутствующего AI.",
    "blade_ward": "Задел для будущего боя: сопротивление дробящему, колющему и рубящему урону до следующего боевого хода. Пока применение недоступно и заряд не тратится.",
    "dancing_lights": "Тусклый свет вокруг выбранной клетки на 5 ходов, радиус 3. Нужна концентрация; новый концентрируемый эффект заменяет предыдущий. Потеря сознания или отдых гасят огоньки.",
    "elementalism": "Поджечь деревянную дверь/масло, погасить горящую дверь, создать метку или звук. Работа с жидкостями, грунтом и дымом появится после соответствующих систем мира.",
    "true_strike": "Задел для будущего боя: преимущество следующей атаки оружием. Пока применение недоступно и заряд не тратится.",
}


def definitions():
    def spell(
        identifier,
        name,
        school,
        modes,
        *,
        damage=None,
        kind=None,
        resolution="automatic",
        save=None,
        target="other",
        world=None,
        params=None,
        pending=(),
        tags=(),
        range=6,
        **extra,
    ):
        return dict(
            id=identifier,
            name=name,
            level=0,
            school=school,
            modes=modes,
            range=range,
            target=target,
            resolution=resolution,
            save_ability=save,
            effects=[dict(kind="damage", dice=damage, damage_type=kind)]
            if damage
            else [],
            world_effect=world,
            world_parameters=params or {},
            pending_effects=list(pending),
            tags=list(tags),
            description=DESCRIPTIONS[identifier]
            + " Стоимость: 1 общий заряд заговора.",
            cantrip_scaling=bool(damage),
            **extra,
        )

    both = ["combat", "exploration"]
    return [
        spell(
            "light",
            "Свет",
            "evocation",
            ["exploration"],
            target="item",
            world="light",
            params=dict(duration=10, radius=6, bright_radius=3),
            range=1,
            tags=["light"],
        ),
        spell(
            "fire_bolt",
            "Огненный снаряд",
            "evocation",
            both,
            damage="1d10",
            kind="fire",
            resolution="attack",
            target="cell",
            world="projectile",
            tags=["ignite", "fire"],
        ),
        spell(
            "mending",
            "Починка",
            "transmutation",
            ["exploration"],
            target="item",
            world="repair",
            params=dict(tool_amount=1, equipment_dice="1d4"),
            range=1,
            tags=["repair"],
        ),
        spell(
            "toll_the_dead",
            "Погребальный звон",
            "necromancy",
            ["combat"],
            damage="1d8",
            kind="necrotic",
            resolution="save",
            save="wisdom",
            wounded_dice="1d12",
        ),
        spell(
            "acid_splash",
            "Кислотная сфера",
            "evocation",
            ["combat"],
            damage="1d6",
            kind="acid",
            resolution="save",
            save="dexterity",
            max_targets=2,
            tags=["aoe"],
        ),
        spell(
            "ray_of_frost",
            "Луч холода",
            "evocation",
            both,
            damage="1d8",
            kind="cold",
            resolution="attack",
            target="cell",
            world="projectile",
            tags=["cool"],
            pending=["замедление в очереди боя", "замораживание жидкостей"],
        ),
        spell(
            "shocking_grasp",
            "Электрическое касание",
            "evocation",
            both,
            damage="1d8",
            kind="lightning",
            resolution="attack",
            target="cell",
            world="projectile",
            range=1,
            pending=["блокировка реакций", "электрические механизмы"],
        ),
        spell(
            "mage_hand",
            "Волшебная рука",
            "conjuration",
            ["exploration"],
            target="cell",
            world="hand",
            range=4,
            params=dict(duration=5, max_weight=2.0),
            tags=["interaction"],
        ),
        spell(
            "minor_illusion",
            "Малая иллюзия",
            "illusion",
            both,
            target="cell",
            world="illusion",
            params=dict(duration=5),
            pending=["отвлечение патрулей и боевой контроль"],
            tags=["illusion"],
        ),
        spell(
            "prestidigitation",
            "Фокусы",
            "transmutation",
            ["exploration"],
            target="cell",
            world="tricks",
            params=dict(duration=5),
            tags=["ignite", "utility"],
        ),
        spell(
            "poison_spray",
            "Ядовитые брызги",
            "necromancy",
            ["combat"],
            damage="1d12",
            kind="poison",
            resolution="save",
            save="constitution",
            range=3,
        ),
        spell(
            "chill_touch",
            "Холодное прикосновение",
            "necromancy",
            ["combat"],
            damage="1d10",
            kind="necrotic",
            resolution="attack",
            range=1,
            pending=["блокировка лечения"],
        ),
        spell(
            "thunderclap",
            "Раскат грома",
            "evocation",
            both,
            damage="1d6",
            kind="thunder",
            resolution="save",
            save="constitution",
            world="noise",
            max_targets=32,
            range=1,
            tags=["noise", "aoe"],
            pending=["передний фланг JRPG-боя", "реакции патрулей на шум"],
        ),
        spell(
            "blade_ward",
            "Защитный клинок",
            "abjuration",
            ["combat"],
            target="self",
            pending=[
                "временное сопротивление физическому урону до следующего хода боя"
            ],
        ),
        spell(
            "dancing_lights",
            "Пляшущие огоньки",
            "evocation",
            ["exploration"],
            target="cell",
            world="dancing_lights",
            params=dict(duration=5, radius=3, bright_radius=0),
            concentration=True,
            tags=["light"],
        ),
        spell(
            "elementalism",
            "Элементализм",
            "transmutation",
            ["exploration"],
            target="cell",
            world="elementalism",
            params=dict(duration=5),
            tags=["ignite", "utility"],
            pending=["изменение жидкостей, грунта и дыма"],
        ),
        spell(
            "true_strike",
            "Истинный удар",
            "divination",
            ["combat"],
            target="self",
            pending=["преимущество следующей атаки оружием в бою"],
        ),
    ]


def run(write=False):
    docs = [SpellDocument.model_validate(raw) for raw in definitions()]
    legacy = Path(__file__).resolve().parents[1] / "tuidungeon/content/data"
    changed = []
    for root in (DEFAULT_PACKS / "base", legacy):
        for doc in docs:
            path = root / "spells" / (doc.id + ".json")
            if not path.exists():
                changed.append(path)
                if write:
                    raw_spell = doc.model_dump(mode="json")
                    if root == legacy:
                        for key in (
                            "glyph",
                            "foreground",
                            "background",
                            "art",
                            "variants",
                        ):
                            raw_spell.pop(key, None)
                    PackStore.atomic_json(path, raw_spell)
        path = root / "classes/wizard.json"
        raw = PackStore.read_json(path)
        if "cantrip_choices" not in raw:
            raw.update(
                cantrip_choices=[
                    ("base:" if root != legacy else "") + doc.id for doc in docs
                ],
                cantrips_known=3,
                spellcasting_ability="intelligence",
            )
            changed.append(path)
            if write:
                PackStore.atomic_json(path, raw)
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for path in run(args.write):
        print(path)
