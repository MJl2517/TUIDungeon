# Полигон интерактивных тайлов

Карта `dev:all_interactive_tiles`, 69×124; 282 образцов.
Между тайлами три пустые клетки. Номер расположен над образцом.
Образцы сгруппированы по основной механике, внутри — по группе и ID.
Если тайл совмещает несколько механик, включены все: например, огонь одновременно светит и наносит урон.

```bash
./run.sh --test-map dev:all_interactive_tiles
./run.sh --terminal --test-map dev:all_interactive_tiles
# Windows:
.\run.bat --test-map dev:all_interactive_tiles
```

В студии: пакет `dev` → карты → «Полигон разработчика: интерактивные тайлы».
G на клетке предмета: подобрать. Enter рядом с точкой интереса: взаимодействовать.
Двери: Enter рядом. + закрыта, X заперта, / открыта; материал обозначен цветом. Долгий взлом: Space — ход, Backspace — отмена.
Ловушки срабатывают при входе и наносят настоящий урон; скрытые сохраняют скрытость.
Порталы, лестницы и телепорты возвращают к старту этого же полигона, сохраняя состояние образцов.
Общий свет тусклый: источники создают яркие области. Для проверки тьмы можно переключить общий свет карты в студии.
У предметных кистей рисунок принадлежит подбираемому предмету; после подбора остаётся пол.
Перезапуск теста восстанавливает размещения. Все эффекты используют обычные правила движка.

Пересборка после добавления новых тайлов (заменяет только файлы этого полигона):

```bash
.venv/bin/python -m scripts.build_developer_tiles --force
# Windows:
.venv\Scripts\python.exe -m scripts.build_developer_tiles --force
```

Для переноса скопируйте `packs/dev/` и пакеты из его `manifest.json`.
Координаты начинаются с нуля и совпадают с инспектором.

| № | Группа | Тайл | Ссылка | Механики | X | Y |
| --- | --- | --- | --- | --- | ---: | ---: |
| 001 | Двери | Адамантиевая дверь | `base:door_adamantine` | Дверь: adamantine, closed, не заперта, normal/simple | 4 | 6 |
| 002 | Двери | Дверь из прутьев | `base:door_bars` | Дверь: bars, closed, не заперта, normal/simple | 8 | 6 |
| 003 | Двери | Стальная дверь | `base:door_steel` | Дверь: steel, closed, не заперта, normal/simple | 12 | 6 |
| 004 | Двери | Каменная плита | `base:door_stone` | Дверь: stone, closed, не заперта, normal/simple | 16 | 6 |
| 005 | Двери | Деревянная дверь | `base:door_wood` | Дверь: wood, closed, не заперта, normal/simple | 20 | 6 |
| 006 | Артефакты | Магический предмет | `base:terrain_artifact` | Предмет: `base:terrain_artifact` | 4 | 16 |
| 007 | Артефакты | Магический амулет | `base:terrain_artifact_amulet` | Предмет: `base:terrain_artifact_amulet` | 8 | 16 |
| 008 | Артефакты | Легендарный предмет | `base:terrain_artifact_legendary` | Предмет: `base:terrain_artifact_legendary` | 12 | 16 |
| 009 | Артефакты | Сильный магический предмет | `base:terrain_artifact_powerful` | Предмет: `base:terrain_artifact_powerful` | 16 | 16 |
| 010 | Артефакты | Магическое кольцо | `base:terrain_artifact_ring` | Предмет: `base:terrain_artifact_ring` | 20 | 16 |
| 011 | Артефакты | Зачарованное кольцо | `base:terrain_artifact_ring_enchanted` | Предмет: `base:terrain_artifact_ring_enchanted` | 24 | 16 |
| 012 | Артефакты | Магический камень | `base:terrain_artifact_stone` | Предмет: `base:terrain_artifact_stone` | 28 | 16 |
| 013 | Артефакты | Неопознанный магический предмет | `base:terrain_artifact_unidentified` | Предмет: `base:terrain_artifact_unidentified` | 32 | 16 |
| 014 | Артефакты | Неизвестный артефакт | `base:terrain_artifact_unknown` | Предмет: `base:terrain_artifact_unknown` | 36 | 16 |
| 015 | Артефакты | Слабый магический предмет | `base:terrain_artifact_weak` | Предмет: `base:terrain_artifact_weak` | 40 | 16 |
| 016 | Вооружение | Простая дубинка | `base:club` | Предмет: `base:club` | 44 | 16 |
| 017 | Вооружение | Кол | `base:stake` | Предмет: `base:stake` | 48 | 16 |
| 018 | Декорации: оружие | Кинжал | `base:dagger` | Предмет: `base:dagger` | 52 | 16 |
| 019 | Декорации: оружие | Посох | `base:staff` | Предмет: `base:staff` | 56 | 16 |
| 020 | Декорации: оружие | Меч | `base:sword` | Предмет: `base:sword` | 60 | 16 |
| 021 | Декорации: оружие | Стрела | `base:terrain_decor_arrow` | Предмет: `base:terrain_decor_arrow` | 64 | 16 |
| 022 | Декорации: оружие | Топор | `base:terrain_decor_axe` | Предмет: `base:terrain_decor_axe` | 4 | 20 |
| 023 | Декорации: оружие | Болт | `base:terrain_decor_bolt` | Предмет: `base:terrain_decor_bolt` | 8 | 20 |
| 024 | Декорации: оружие | Лук | `base:terrain_decor_bow` | Предмет: `base:terrain_decor_bow` | 12 | 20 |
| 025 | Декорации: оружие | Двуручный топор | `base:terrain_decor_greataxe` | Предмет: `base:terrain_decor_greataxe` | 16 | 20 |
| 026 | Декорации: оружие | Большой меч | `base:terrain_decor_greatsword` | Предмет: `base:terrain_decor_greatsword` | 20 | 20 |
| 027 | Декорации: оружие | Алебарда | `base:terrain_decor_halberd` | Предмет: `base:terrain_decor_halberd` | 24 | 20 |
| 028 | Декорации: оружие | Молот | `base:terrain_decor_hammer` | Предмет: `base:terrain_decor_hammer` | 28 | 20 |
| 029 | Декорации: оружие | Длинный лук | `base:terrain_decor_longbow` | Предмет: `base:terrain_decor_longbow` | 32 | 20 |
| 030 | Декорации: оружие | Булава | `base:terrain_decor_mace` | Предмет: `base:terrain_decor_mace` | 36 | 20 |
| 031 | Декорации: оружие | Рапира | `base:terrain_decor_rapier` | Предмет: `base:terrain_decor_rapier` | 40 | 20 |
| 032 | Декорации: оружие | Серп | `base:terrain_decor_sickle` | Предмет: `base:terrain_decor_sickle` | 44 | 20 |
| 033 | Декорации: оружие | Копьё | `base:terrain_decor_spear` | Предмет: `base:terrain_decor_spear` | 48 | 20 |
| 034 | Декорации: припасы | Зелье лечения | `base:healing_potion` | Предмет: `base:healing_potion` | 52 | 20 |
| 035 | Декорации: припасы | Масло | `base:oil` | Предмет: `base:oil` | 56 | 20 |
| 036 | Декорации: припасы | Дорожный паёк | `base:rations` | Предмет: `base:rations` | 60 | 20 |
| 037 | Декорации: припасы | Бутылка | `base:terrain_decor_bottle` | Предмет: `base:terrain_decor_bottle` | 64 | 20 |
| 038 | Декорации: припасы | Неизвестное зелье | `base:terrain_decor_potion_unknown` | Предмет: `base:terrain_decor_potion_unknown` | 4 | 24 |
| 039 | Декорации: снаряжение | Щит | `base:shield` | Предмет: `base:shield` | 8 | 24 |
| 040 | Декорации: снаряжение | Броня | `base:terrain_decor_armor` | Предмет: `base:terrain_decor_armor` | 12 | 24 |
| 041 | Декорации: снаряжение | Тяжёлая броня | `base:terrain_decor_armor_heavy` | Предмет: `base:terrain_decor_armor_heavy` | 16 | 24 |
| 042 | Декорации: снаряжение | Лёгкая броня | `base:terrain_decor_armor_light` | Предмет: `base:terrain_decor_armor_light` | 20 | 24 |
| 043 | Декорации: снаряжение | Сапоги | `base:terrain_decor_boots` | Предмет: `base:terrain_decor_boots` | 24 | 24 |
| 044 | Декорации: снаряжение | Плащ | `base:terrain_decor_cloak` | Предмет: `base:terrain_decor_cloak` | 28 | 24 |
| 045 | Декорации: снаряжение | Перчатки | `base:terrain_decor_gloves` | Предмет: `base:terrain_decor_gloves` | 32 | 24 |
| 046 | Декорации: снаряжение | Шлем | `base:terrain_decor_helmet` | Предмет: `base:terrain_decor_helmet` | 36 | 24 |
| 047 | Замки и ключи | Древний ключ | `base:terrain_key_ancient` | Предмет: `base:terrain_key_ancient` | 40 | 24 |
| 048 | Замки и ключи | Ключ | `base:terrain_key_decor` | Предмет: `base:terrain_key_decor` | 44 | 24 |
| 049 | Замки и ключи | Важный ключ | `base:terrain_key_important` | Предмет: `base:terrain_key_important` | 48 | 24 |
| 050 | Замки и ключи | Особый ключ | `base:terrain_key_special` | Предмет: `base:terrain_key_special` | 52 | 24 |
| 051 | Материалы | Кислотный реагент | `base:acid_reagent` | Предмет: `base:acid_reagent` | 56 | 24 |
| 052 | Материалы | Алхимический реагент | `base:alchemy_reagent` | Предмет: `base:alchemy_reagent` | 60 | 24 |
| 053 | Материалы | Горькая трава | `base:bitter_herb` | Предмет: `base:bitter_herb` | 64 | 24 |
| 054 | Материалы | Глина | `base:clay` | Предмет: `base:clay` | 4 | 28 |
| 055 | Материалы | Тряпка | `base:cloth` | Предмет: `base:cloth` | 8 | 28 |
| 056 | Материалы | Заготовка | `base:craft_workpiece` | Предмет: `base:craft_workpiece` | 12 | 28 |
| 057 | Материалы | Стекольное сырьё | `base:glass_material` | Предмет: `base:glass_material` | 16 | 28 |
| 058 | Материалы | Металл | `base:metal` | Предмет: `base:metal` | 20 | 28 |
| 059 | Материалы | Механическая деталь | `base:mechanical_part` | Предмет: `base:mechanical_part` | 24 | 28 |
| 060 | Материалы | Лекарственная трава | `base:medicinal_herb` | Предмет: `base:medicinal_herb` | 28 | 28 |
| 061 | Материалы | Металл | `base:metal` | Предмет: `base:metal` | 32 | 28 |
| 062 | Материалы | Грибы | `base:mushroom` | Предмет: `base:mushroom` | 36 | 28 |
| 063 | Материалы | Растительное волокно | `base:plant_fiber` | Предмет: `base:plant_fiber` | 40 | 28 |
| 064 | Материалы | Ядовитая трава | `base:poison_herb` | Предмет: `base:poison_herb` | 44 | 28 |
| 065 | Материалы | Кожа | `base:raw_leather` | Предмет: `base:raw_leather` | 48 | 28 |
| 066 | Материалы | Камень | `base:stone` | Предмет: `base:stone` | 52 | 28 |
| 067 | Материалы | Растопка | `base:tinder` | Предмет: `base:tinder` | 56 | 28 |
| 068 | Материалы | Древесина | `base:wood` | Предмет: `base:wood` | 60 | 28 |
| 069 | Мебель | Мебель | `base:packed_furniture` | Предмет: `base:packed_furniture` | 64 | 28 |
| 070 | Припасы | Бинт | `base:bandage` | Предмет: `base:bandage` | 4 | 32 |
| 071 | Ремесленные инструменты | Алхимические принадлежности | `base:alchemist_tools` | Предмет: `base:alchemist_tools` | 8 | 32 |
| 072 | Ремесленные инструменты | Принадлежности пивовара | `base:brewer_tools` | Предмет: `base:brewer_tools` | 12 | 32 |
| 073 | Ремесленные инструменты | Принадлежности каллиграфа | `base:calligrapher_tools` | Предмет: `base:calligrapher_tools` | 16 | 32 |
| 074 | Ремесленные инструменты | Инструменты плотника | `base:carpenter_tools` | Предмет: `base:carpenter_tools` | 20 | 32 |
| 075 | Ремесленные инструменты | Инструменты картографа | `base:cartographer_tools` | Предмет: `base:cartographer_tools` | 24 | 32 |
| 076 | Ремесленные инструменты | Инструменты сапожника | `base:cobbler_tools` | Предмет: `base:cobbler_tools` | 28 | 32 |
| 077 | Ремесленные инструменты | Кухонные принадлежности | `base:cook_tools` | Предмет: `base:cook_tools` | 32 | 32 |
| 078 | Ремесленные инструменты | Инструменты стеклодува | `base:glassblower_tools` | Предмет: `base:glassblower_tools` | 36 | 32 |
| 079 | Ремесленные инструменты | Набор травника | `base:herbalism_kit` | Предмет: `base:herbalism_kit` | 40 | 32 |
| 080 | Ремесленные инструменты | Инструменты ювелира | `base:jeweler_tools` | Предмет: `base:jeweler_tools` | 44 | 32 |
| 081 | Ремесленные инструменты | Инструменты кожевника | `base:leatherworker_tools` | Предмет: `base:leatherworker_tools` | 48 | 32 |
| 082 | Ремесленные инструменты | Инструменты каменщика | `base:mason_tools` | Предмет: `base:mason_tools` | 52 | 32 |
| 083 | Ремесленные инструменты | Принадлежности художника | `base:painter_tools` | Предмет: `base:painter_tools` | 56 | 32 |
| 084 | Ремесленные инструменты | Набор отравителя | `base:poisoner_kit` | Предмет: `base:poisoner_kit` | 60 | 32 |
| 085 | Ремесленные инструменты | Инструменты гончара | `base:potter_tools` | Предмет: `base:potter_tools` | 64 | 32 |
| 086 | Ремесленные инструменты | Инструменты кузнеца | `base:smith_tools` | Предмет: `base:smith_tools` | 4 | 36 |
| 087 | Ремесленные инструменты | Инструменты жестянщика | `base:tinker_tools` | Предмет: `base:tinker_tools` | 8 | 36 |
| 088 | Ремесленные инструменты | Инструменты ткача | `base:weaver_tools` | Предмет: `base:weaver_tools` | 12 | 36 |
| 089 | Ремесленные инструменты | Инструменты резчика | `base:woodcarver_tools` | Предмет: `base:woodcarver_tools` | 16 | 36 |
| 090 | Ремёсла и добыча | Кость животного | `base:animal_bone` | Предмет: `base:animal_bone` | 20 | 36 |
| 091 | Ремёсла и добыча | Переносной таран | `base:battering_ram` | Предмет: `base:battering_ram` | 24 | 36 |
| 092 | Ремёсла и добыча | Резной посох | `base:carved_staff` | Предмет: `base:carved_staff` | 28 | 36 |
| 093 | Ремёсла и добыча | Хитин | `base:chitin` | Предмет: `base:chitin` | 32 | 36 |
| 094 | Ремёсла и добыча | Глиняный сосуд | `base:clay_pot` | Предмет: `base:clay_pot` | 36 | 36 |
| 095 | Ремёсла и добыча | Приготовленное мясо | `base:cooked_meat` | Предмет: `base:cooked_meat` | 40 | 36 |
| 096 | Ремёсла и добыча | Стеклянный флакон | `base:glass_flask` | Предмет: `base:glass_flask` | 44 | 36 |
| 097 | Ремёсла и добыча | Травяной экстракт | `base:herbal_extract` | Предмет: `base:herbal_extract` | 48 | 36 |
| 098 | Ремёсла и добыча | Простые отмычки | `base:improvised_lockpicks` | Предмет: `base:improvised_lockpicks` | 52 | 36 |
| 099 | Ремёсла и добыча | Кожаные сапоги | `base:leather_boots` | Предмет: `base:leather_boots` | 56 | 36 |
| 100 | Ремёсла и добыча | Кожаная лента | `base:leather_strip` | Предмет: `base:leather_strip` | 60 | 36 |
| 101 | Ремёсла и добыча | Металлический щит | `base:metal_shield` | Предмет: `base:metal_shield` | 64 | 36 |
| 102 | Ремёсла и добыча | Ядовитая железа | `base:poison_gland` | Предмет: `base:poison_gland` | 4 | 40 |
| 103 | Ремёсла и добыча | Сырое мясо | `base:raw_meat` | Предмет: `base:raw_meat` | 8 | 40 |
| 104 | Ремёсла и добыча | Простой яд | `base:simple_poison` | Предмет: `base:simple_poison` | 12 | 40 |
| 105 | Ремёсла и добыча | Паутина | `base:spider_silk` | Предмет: `base:spider_silk` | 16 | 40 |
| 106 | Ремёсла и добыча | Каменный блок | `base:stone_block` | Предмет: `base:stone_block` | 20 | 40 |
| 107 | Ремёсла и добыча | Каменный клин | `base:stone_wedge` | Предмет: `base:stone_wedge` | 24 | 40 |
| 108 | Ремёсла и добыча | Импровизированная ловушка (набор) | `base:trap_kit` | Предмет: `base:trap_kit` | 28 | 40 |
| 109 | Ремёсла и добыча | Необработанный самоцвет | `base:uncut_gem` | Предмет: `base:uncut_gem` | 32 | 40 |
| 110 | Ремёсла и добыча | Деревянный шест | `base:wooden_pole` | Предмет: `base:wooden_pole` | 36 | 40 |
| 111 | Ремёсла и добыча | Деревянный щит | `base:wooden_shield` | Предмет: `base:wooden_shield` | 40 | 40 |
| 112 | Снаряжение | Флакон кислоты | `base:acid_flask` | Предмет: `base:acid_flask` | 44 | 40 |
| 113 | Снаряжение | Спальный мешок | `base:bedroll` | Предмет: `base:bedroll` | 48 | 40 |
| 114 | Снаряжение | Ключ от сундука | `base:chest_key` | Предмет: `base:chest_key` | 52 | 40 |
| 115 | Снаряжение | Походный котелок | `base:cooking_pot` | Предмет: `base:cooking_pot` | 56 | 40 |
| 116 | Снаряжение | Ломик | `base:crowbar` | Предмет: `base:crowbar` | 60 | 40 |
| 117 | Снаряжение | Сухие травы | `base:dried_herbs` | Предмет: `base:dried_herbs` | 64 | 40 |
| 118 | Снаряжение | Кремень и кресало | `base:flint_and_steel` | Предмет: `base:flint_and_steel` | 4 | 44 |
| 119 | Снаряжение | Лечебная припарка | `base:healing_poultice` | Предмет: `base:healing_poultice` | 8 | 44 |
| 120 | Снаряжение | Импровизированная верёвка | `base:improvised_rope` | Предмет: `base:improvised_rope` | 12 | 44 |
| 121 | Снаряжение | Чернила и перо | `base:ink` | Предмет: `base:ink` | 16 | 44 |
| 122 | Снаряжение | Масляная лампа | `base:lamp` | Предмет: `base:lamp` | 20 | 44 |
| 123 | Снаряжение | Кожаный доспех | `base:leather` | Предмет: `base:leather` | 24 | 44 |
| 124 | Снаряжение | Кольчуга | `base:mail` | Предмет: `base:mail` | 28 | 44 |
| 125 | Снаряжение | Мастерские отмычки | `base:master_lockpicks` | Предмет: `base:master_lockpicks` | 32 | 44 |
| 126 | Снаряжение | Пергамент | `base:parchment` | Предмет: `base:parchment` | 36 | 44 |
| 127 | Снаряжение | Кирка | `base:pickaxe` | Предмет: `base:pickaxe` | 40 | 44 |
| 128 | Снаряжение | Мантия | `base:robe` | Предмет: `base:robe` | 44 | 44 |
| 129 | Снаряжение | Верёвка | `base:rope` | Предмет: `base:rope` | 48 | 44 |
| 130 | Снаряжение | Книга заклинаний | `base:spellbook` | Предмет: `base:spellbook` | 52 | 44 |
| 131 | Снаряжение | Воровские инструменты | `base:thieves_tools` | Предмет: `base:thieves_tools` | 56 | 44 |
| 132 | Снаряжение | Факел | `base:torch` | Предмет: `base:torch` | 60 | 44 |
| 133 | Снаряжение | Флакон | `base:water_flask` | Предмет: `base:water_flask` | 64 | 44 |
| 134 | Снаряжение | Бурдюк | `base:waterskin` | Предмет: `base:waterskin` | 4 | 48 |
| 135 | Алтари и святыни | Алтарь | `base:terrain_altar` | Взаимодействие: `base:terrain_altar` | 4 | 58 |
| 136 | Алтари и святыни | Большой алтарь | `base:terrain_altar_large` | Взаимодействие: `base:terrain_altar_large` | 8 | 58 |
| 137 | Алтари и святыни | Лунный алтарь | `base:terrain_altar_moon` | Взаимодействие: `base:terrain_altar_moon` | 12 | 58 |
| 138 | Алтари и святыни | Солнечный алтарь | `base:terrain_altar_sun` | Взаимодействие: `base:terrain_altar_sun` | 16 | 58 |
| 139 | Алтари и святыни | Древний крест | `base:terrain_ancient_cross` | Взаимодействие: `base:terrain_ancient_cross` | 20 | 58 |
| 140 | Алтари и святыни | Священный символ | `base:terrain_holy_symbol` | Взаимодействие: `base:terrain_holy_symbol` | 24 | 58 |
| 141 | Алтари и святыни | Ритуальный круг | `base:terrain_ritual_circle` | Взаимодействие: `base:terrain_ritual_circle` | 28 | 58 |
| 142 | Алтари и святыни | Активный ритуальный круг | `base:terrain_ritual_circle_active` | Взаимодействие: `base:terrain_ritual_circle_active`; Свет: 3/6 | 32 | 58 |
| 143 | Алтари и святыни | Жертвенная чаша | `base:terrain_sacrificial_bowl` | Взаимодействие: `base:terrain_sacrificial_bowl` | 36 | 58 |
| 144 | Алтари и святыни | Святыня | `base:terrain_shrine` | Взаимодействие: `base:terrain_shrine` | 40 | 58 |
| 145 | Алтари и святыни | Храмовый символ | `base:terrain_temple_symbol` | Взаимодействие: `base:terrain_temple_symbol` | 44 | 58 |
| 146 | Записки | Памятка плотника | `base:crafting_manual` | Взаимодействие: `base:crafting_manual` | 48 | 58 |
| 147 | Записки | Листы с записями | `base:paper_note` | Взаимодействие: `base:paper_note` | 52 | 58 |
| 148 | Записки | Доска с заданиями | `base:quest_board` | Взаимодействие: `base:quest_board` | 56 | 58 |
| 149 | Записки | Каменная табличка | `base:stone_tablet` | Взаимодействие: `base:stone_tablet` | 60 | 58 |
| 150 | Записки | Чужой дневник | `base:strangers_diary` | Взаимодействие: `base:strangers_diary` | 64 | 58 |
| 151 | Книги и документы | Книга | `base:terrain_book` | Взаимодействие: `base:terrain_book` | 4 | 62 |
| 152 | Книги и документы | Древний том | `base:terrain_book_ancient` | Взаимодействие: `base:terrain_book_ancient` | 8 | 62 |
| 153 | Книги и документы | Закрытая книга | `base:terrain_book_closed` | Взаимодействие: `base:terrain_book_closed` | 12 | 62 |
| 154 | Книги и документы | Большая книга | `base:terrain_book_large` | Взаимодействие: `base:terrain_book_large` | 16 | 62 |
| 155 | Книги и документы | Карта | `base:terrain_map_drawing` | Взаимодействие: `base:terrain_map_drawing` | 20 | 62 |
| 156 | Книги и документы | Фрагмент карты | `base:terrain_map_fragment` | Взаимодействие: `base:terrain_map_fragment` | 24 | 62 |
| 157 | Книги и документы | Записка | `base:terrain_note` | Взаимодействие: `base:terrain_note` | 28 | 62 |
| 158 | Книги и документы | Клочок бумаги | `base:terrain_paper_scrap` | Взаимодействие: `base:terrain_paper_scrap` | 32 | 62 |
| 159 | Книги и документы | Свиток | `base:terrain_scroll` | Взаимодействие: `base:terrain_scroll` | 36 | 62 |
| 160 | Книги и документы | Магический свиток | `base:terrain_scroll_magic` | Взаимодействие: `base:terrain_scroll_magic` | 40 | 62 |
| 161 | Контейнеры | Запертый сундук | `base:chest` | Взаимодействие: `base:chest` | 44 | 62 |
| 162 | Контейнеры | Бочка | `base:terrain_barrel` | Взаимодействие: `base:terrain_barrel` | 48 | 62 |
| 163 | Контейнеры | Большая бочка | `base:terrain_barrel_large` | Взаимодействие: `base:terrain_barrel_large` | 52 | 62 |
| 164 | Контейнеры | Маленькая бочка | `base:terrain_barrel_small` | Взаимодействие: `base:terrain_barrel_small` | 56 | 62 |
| 165 | Контейнеры | Сундук | `base:terrain_chest` | Взаимодействие: `base:terrain_chest` | 60 | 62 |
| 166 | Контейнеры | Открытый сундук | `base:terrain_chest_open` | Взаимодействие: `base:terrain_chest_open` | 64 | 62 |
| 167 | Контейнеры | Сундук с сокровищами | `base:terrain_chest_treasure` | Взаимодействие: `base:terrain_chest_treasure` | 4 | 66 |
| 168 | Контейнеры | Ящик | `base:terrain_crate` | Взаимодействие: `base:terrain_crate` | 8 | 66 |
| 169 | Контейнеры | Закрытый ящик | `base:terrain_crate_closed` | Взаимодействие: `base:terrain_crate_closed` | 12 | 66 |
| 170 | Контейнеры | Укреплённый ящик | `base:terrain_crate_reinforced` | Взаимодействие: `base:terrain_crate_reinforced` | 16 | 66 |
| 171 | Контейнеры | Кувшин | `base:terrain_jug` | Взаимодействие: `base:terrain_jug` | 20 | 66 |
| 172 | Контейнеры | Горшок | `base:terrain_pot` | Взаимодействие: `base:terrain_pot` | 24 | 66 |
| 173 | Контейнеры | Мешок | `base:terrain_sack` | Взаимодействие: `base:terrain_sack` | 28 | 66 |
| 174 | Контейнеры | Большой мешок | `base:terrain_sack_large` | Взаимодействие: `base:terrain_sack_large` | 32 | 66 |
| 175 | Контейнеры | Урна | `base:terrain_urn` | Взаимодействие: `base:terrain_urn` | 36 | 66 |
| 176 | Контейнеры | Большой сосуд | `base:terrain_vessel_large` | Взаимодействие: `base:terrain_vessel_large` | 40 | 66 |
| 177 | Магические зоны | Положительная энергия | `base:terrain_magic_positive` | Взаимодействие: `base:terrain_magic_positive` | 44 | 66 |
| 178 | Магические зоны | Слабая магия | `base:terrain_magic_weak` | Взаимодействие: `base:terrain_magic_weak` | 48 | 66 |
| 179 | Магические зоны | Сильная магическая зона | `base:terrain_magic_zone` | Взаимодействие: `base:terrain_magic_zone` | 52 | 66 |
| 180 | Метки мест | Важное место | `base:terrain_marker_important` | Взаимодействие: `base:terrain_marker_important` | 56 | 66 |
| 181 | Метки мест | Интересный объект | `base:terrain_marker_interest` | Взаимодействие: `base:terrain_marker_interest` | 60 | 66 |
| 182 | Метки мест | Сокровище | `base:terrain_marker_treasure` | Взаимодействие: `base:terrain_marker_treasure` | 64 | 66 |
| 183 | Метки мест | Уникальное место | `base:terrain_marker_unique` | Взаимодействие: `base:terrain_marker_unique` | 4 | 70 |
| 184 | Метки мест | Неизвестное место | `base:terrain_marker_unknown` | Взаимодействие: `base:terrain_marker_unknown` | 8 | 70 |
| 185 | Руны | Обычная руна | `base:terrain_rune` | Взаимодействие: `base:terrain_rune` | 12 | 70 |
| 186 | Руны | Активная руна | `base:terrain_rune_active` | Взаимодействие: `base:terrain_rune_active`; Свет: 3/6 | 16 | 70 |
| 187 | Руны | Руна воздуха | `base:terrain_rune_air` | Взаимодействие: `base:terrain_rune_air` | 20 | 70 |
| 188 | Руны | Круглая руна | `base:terrain_rune_circle` | Взаимодействие: `base:terrain_rune_circle` | 24 | 70 |
| 189 | Руны | Руна | `base:terrain_rune_cross` | Взаимодействие: `base:terrain_rune_cross` | 28 | 70 |
| 190 | Руны | Руна земли | `base:terrain_rune_earth` | Взаимодействие: `base:terrain_rune_earth` | 32 | 70 |
| 191 | Руны | Магическая руна | `base:terrain_rune_magic` | Взаимодействие: `base:terrain_rune_magic` | 36 | 70 |
| 192 | Руны | Руна наблюдения | `base:terrain_rune_observation` | Взаимодействие: `base:terrain_rune_observation` | 40 | 70 |
| 193 | Руны | Запрещающая руна | `base:terrain_rune_prohibition` | Взаимодействие: `base:terrain_rune_prohibition` | 44 | 70 |
| 194 | Руны | Защитная руна | `base:terrain_rune_protection` | Взаимодействие: `base:terrain_rune_protection` | 48 | 70 |
| 195 | Руны | Руна воды | `base:terrain_rune_water` | Взаимодействие: `base:terrain_rune_water` | 52 | 70 |
| 196 | Руны | Слабая руна | `base:terrain_rune_weak` | Взаимодействие: `base:terrain_rune_weak` | 56 | 70 |
| 197 | События | Руководство ремесленника | `base:crafting_expansion_manual` | Взаимодействие: `base:crafting_expansion_manual` | 60 | 70 |
| 198 | События | Мастерская плотника | `base:crafting_workshop` | Взаимодействие: `base:crafting_workshop` | 64 | 70 |
| 199 | События | Забытый алтарь | `base:shrine` | Взаимодействие: `base:shrine` | 4 | 74 |
| 200 | Сокровища | Тайник с амулетом | `base:terrain_amulet` | Взаимодействие: `base:terrain_amulet` | 8 | 74 |
| 201 | Сокровища | Россыпь монет | `base:terrain_coin_scatter` | Взаимодействие: `base:terrain_coin_scatter` | 12 | 74 |
| 202 | Сокровища | Драгоценный камень | `base:terrain_gem` | Взаимодействие: `base:terrain_gem` | 16 | 74 |
| 203 | Сокровища | Крупный самоцвет | `base:terrain_gem_large` | Взаимодействие: `base:terrain_gem_large` | 20 | 74 |
| 204 | Сокровища | Необработанный самоцвет | `base:terrain_gem_raw` | Взаимодействие: `base:terrain_gem_raw` | 24 | 74 |
| 205 | Сокровища | Украшение | `base:terrain_jewelry` | Взаимодействие: `base:terrain_jewelry` | 28 | 74 |
| 206 | Сокровища | Кольцо | `base:terrain_ring` | Взаимодействие: `base:terrain_ring` | 32 | 74 |
| 207 | Сокровища | Монеты | `base:terrain_treasure_coins` | Взаимодействие: `base:terrain_treasure_coins` | 36 | 74 |
| 208 | Сокровища | Медь | `base:terrain_treasure_copper` | Взаимодействие: `base:terrain_treasure_copper` | 40 | 74 |
| 209 | Сокровища | Золото | `base:terrain_treasure_gold` | Взаимодействие: `base:terrain_treasure_gold` | 44 | 74 |
| 210 | Сокровища | Драгоценности | `base:terrain_treasure_jewels` | Взаимодействие: `base:terrain_treasure_jewels` | 48 | 74 |
| 211 | Сокровища | Серебро | `base:terrain_treasure_silver` | Взаимодействие: `base:terrain_treasure_silver` | 52 | 74 |
| 212 | Газ, дым и туман | Ядовитый газ | `base:terrain_gas_toxic` | Ловушка: `base:terrain_gas_toxic` | 4 | 84 |
| 213 | Кислота и яд | Кислота | `base:terrain_acid` | Ловушка: `base:terrain_acid` | 8 | 84 |
| 214 | Кислота и яд | Глубокая кислота | `base:terrain_acid_deep` | Ловушка: `base:terrain_acid_deep` | 12 | 84 |
| 215 | Кислота и яд | Яд | `base:terrain_poison` | Ловушка: `base:terrain_poison` | 16 | 84 |
| 216 | Кислота и яд | Ядовитая поверхность | `base:terrain_poison_surface` | Ловушка: `base:terrain_poison_surface` | 20 | 84 |
| 217 | Кислота и яд | Токсичные споры | `base:terrain_toxic_spores` | Ловушка: `base:terrain_toxic_spores` | 24 | 84 |
| 218 | Лава и огонь | Огонь | `base:terrain_fire` | Ловушка: `base:terrain_fire`; Свет: 3/6 | 28 | 84 |
| 219 | Лава и огонь | Большое пламя | `base:terrain_fire_large` | Ловушка: `base:terrain_fire_large`; Свет: 3/6 | 32 | 84 |
| 220 | Лава и огонь | Небольшое пламя | `base:terrain_fire_small` | Ловушка: `base:terrain_fire_small`; Свет: 3/6 | 36 | 84 |
| 221 | Лава и огонь | Лава | `base:terrain_lava` | Ловушка: `base:terrain_lava`; Свет: 3/6 | 40 | 84 |
| 222 | Лава и огонь | Бурлящая лава | `base:terrain_lava_bubbling` | Ловушка: `base:terrain_lava_bubbling`; Свет: 3/6 | 44 | 84 |
| 223 | Лава и огонь | Поток лавы | `base:terrain_lava_flow` | Ловушка: `base:terrain_lava_flow`; Свет: 3/6 | 48 | 84 |
| 224 | Лава и огонь | Магический огонь | `base:terrain_magic_fire` | Ловушка: `base:terrain_magic_fire`; Свет: 3/6 | 52 | 84 |
| 225 | Ловушки | Импровизированная ловушка | `base:improvised_trap` | Ловушка: `base:improvised_trap` | 56 | 84 |
| 226 | Ловушки: рисунки | Шипы | `base:spikes` | Ловушка: `base:spikes` | 60 | 84 |
| 227 | Ловушки: рисунки | Стрела из стены | `base:terrain_arrow_slit` | Ловушка: `base:terrain_arrow_slit` | 64 | 84 |
| 228 | Ловушки: рисунки | Серия стрел | `base:terrain_arrow_slit_barrage` | Ловушка: `base:terrain_arrow_slit_barrage` | 4 | 88 |
| 229 | Ловушки: рисунки | Обвал | `base:terrain_cave_in` | Ловушка: `base:terrain_cave_in` | 8 | 88 |
| 230 | Ловушки: рисунки | Ловушка в двери | `base:terrain_door_trap` | Ловушка: `base:terrain_door_trap` | 12 | 88 |
| 231 | Ловушки: рисунки | Нажимная плита | `base:terrain_pressure_plate` | Ловушка: `base:terrain_pressure_plate` | 16 | 88 |
| 232 | Ловушки: рисунки | Активированная плита | `base:terrain_pressure_plate_active` | Ловушка: `base:terrain_pressure_plate_active` | 20 | 88 |
| 233 | Ловушки: рисунки | Каменная нажимная плита | `base:terrain_pressure_plate_stone` | Ловушка: `base:terrain_pressure_plate_stone` | 24 | 88 |
| 234 | Ловушки: рисунки | Скрытые шипы | `base:terrain_spikes_hidden` | Ловушка: `base:terrain_spikes_hidden` | 28 | 88 |
| 235 | Ловушки: рисунки | Большие шипы | `base:terrain_spikes_large` | Ловушка: `base:terrain_spikes_large` | 32 | 88 |
| 236 | Ловушки: рисунки | Подозрительное место | `base:terrain_suspicious_floor` | Ловушка: `base:terrain_suspicious_floor` | 36 | 88 |
| 237 | Ловушки: рисунки | Кислотная ловушка | `base:terrain_trap_acid` | Ловушка: `base:terrain_trap_acid` | 40 | 88 |
| 238 | Ловушки: рисунки | Смертельная ловушка | `base:terrain_trap_deadly` | Ловушка: `base:terrain_trap_deadly` | 44 | 88 |
| 239 | Ловушки: рисунки | Затопляющая ловушка | `base:terrain_trap_flood` | Ловушка: `base:terrain_trap_flood` | 48 | 88 |
| 240 | Ловушки: рисунки | Магическая ловушка | `base:terrain_trap_magic` | Ловушка: `base:terrain_trap_magic` | 52 | 88 |
| 241 | Ловушки: рисунки | Механическая ловушка | `base:terrain_trap_mechanical` | Ловушка: `base:terrain_trap_mechanical` | 56 | 88 |
| 242 | Ловушки: рисунки | Магическая руна-ловушка | `base:terrain_trap_rune` | Ловушка: `base:terrain_trap_rune` | 60 | 88 |
| 243 | Ловушки: рисунки | Небольшая ловушка | `base:terrain_trap_small` | Ловушка: `base:terrain_trap_small` | 64 | 88 |
| 244 | Ловушки: рисунки | Падающая стена | `base:terrain_wall_falling` | Ловушка: `base:terrain_wall_falling` | 4 | 92 |
| 245 | Магические зоны | Отрицательная энергия | `base:terrain_magic_negative` | Ловушка: `base:terrain_magic_negative` | 8 | 92 |
| 246 | Руны | Руна разрушения | `base:terrain_rune_destruction` | Ловушка: `base:terrain_rune_destruction` | 12 | 92 |
| 247 | Руны | Руна огня | `base:terrain_rune_fire` | Ловушка: `base:terrain_rune_fire` | 16 | 92 |
| 248 | Грибы | Светящийся гриб | `base:mushroom_glowing` | Свет: 1/3 | 4 | 102 |
| 249 | Источники света: рисунки | Свеча | `base:candle` | Свет: 1/3 | 8 | 102 |
| 250 | Источники света: рисунки | Фонарь | `base:lantern` | Свет: 3/6 | 12 | 102 |
| 251 | Источники света: рисунки | Магический фонарь | `base:lantern_magic` | Свет: 3/6 | 16 | 102 |
| 252 | Источники света: рисунки | Яркий источник света | `base:light_bright` | Свет: 3/6 | 20 | 102 |
| 253 | Источники света: рисунки | Магический свет | `base:light_magic` | Свет: 3/6 | 24 | 102 |
| 254 | Источники света: рисунки | Источник света | `base:light_source` | Свет: 3/6 | 28 | 102 |
| 255 | Источники света: рисунки | Стационарный факел | `base:torch_decor` | Свет: 3/6 | 32 | 102 |
| 256 | Источники света: рисунки | Настенный факел | `base:torch_wall` | Свет: 3/6 | 36 | 102 |
| 257 | Лава и огонь | Горячий источник | `base:hot_spring` | Свет: 3/6 | 40 | 102 |
| 258 | Лава и огонь | Искры | `base:sparks` | Свет: 1/3 | 44 | 102 |
| 259 | Магические зоны | Концентрированная магия | `base:magic_concentrated` | Свет: 3/6 | 48 | 102 |
| 260 | Магические зоны | Магическая энергия | `base:magic_energy` | Свет: 3/6 | 52 | 102 |
| 261 | Лестницы и переходы | Спуск глубже | `base:exit_down` | Переход к старту | 4 | 112 |
| 262 | Лестницы и переходы | Выход наверх | `base:exit_up` | Переход к старту | 8 | 112 |
| 263 | Лестницы и переходы | Лестница вниз | `base:stairs_down` | Переход к старту | 12 | 112 |
| 264 | Лестницы и переходы | Лестница вверх | `base:stairs_up` | Переход к старту | 16 | 112 |
| 265 | Лестницы и переходы | Переход вниз | `base:transition_down` | Переход к старту | 20 | 112 |
| 266 | Лестницы и переходы | Переход на следующий уровень | `base:transition_next` | Переход к старту | 24 | 112 |
| 267 | Лестницы и переходы | Переход на предыдущий уровень | `base:transition_previous` | Переход к старту | 28 | 112 |
| 268 | Лестницы и переходы | Переход вверх | `base:transition_up` | Переход к старту | 32 | 112 |
| 269 | Порталы | Магический разлом | `base:magic_rift` | Переход к старту | 36 | 112 |
| 270 | Порталы | Портал | `base:portal` | Переход к старту | 40 | 112 |
| 271 | Порталы | Активный портал | `base:portal_active` | Переход к старту | 44 | 112 |
| 272 | Порталы | Тёмный портал | `base:portal_dark` | Переход к старту | 48 | 112 |
| 273 | Порталы | Великий портал | `base:portal_great` | Переход к старту | 52 | 112 |
| 274 | Порталы | Неактивный портал | `base:portal_inactive` | Переход к старту | 56 | 112 |
| 275 | Порталы | Светлый портал | `base:portal_light` | Переход к старту | 60 | 112 |
| 276 | Порталы | Малый портал | `base:portal_small` | Переход к старту | 64 | 112 |
| 277 | Порталы | Нестабильный портал | `base:portal_unstable` | Переход к старту | 4 | 116 |
| 278 | Телепорты | Телепорт | `base:teleport` | Переход к старту | 8 | 116 |
| 279 | Телепорты | Активный телепорт | `base:teleport_active` | Переход к старту | 12 | 116 |
| 280 | Телепорты | Неактивный телепорт | `base:teleport_inactive` | Переход к старту | 16 | 116 |
| 281 | Телепорты | Большой телепорт | `base:teleport_large` | Переход к старту | 20 | 116 |
| 282 | Телепорты | Нестабильный телепорт | `base:teleport_unstable` | Переход к старту | 24 | 116 |
