# Полигон интерактивных тайлов

Карта `dev:all_interactive_tiles`, 53×116; 196 образцов.
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
| 004 | Двери | Каменная дверь | `base:door_stone` | Дверь: stone, closed, не заперта, normal/simple | 16 | 6 |
| 005 | Двери | Деревянная дверь | `base:door_wood` | Дверь: wood, closed, не заперта, normal/simple | 20 | 6 |
| 006 | Артефакты | Магический предмет | `base:artifact` | Предмет: `base:terrain_artifact` | 4 | 16 |
| 007 | Артефакты | Амулет | `base:artifact_amulet` | Предмет: `base:terrain_artifact_amulet` | 8 | 16 |
| 008 | Артефакты | Легендарный предмет | `base:artifact_legendary` | Предмет: `base:terrain_artifact_legendary` | 12 | 16 |
| 009 | Артефакты | Магическое зелье | `base:artifact_potion` | Предмет: `base:terrain_artifact_potion` | 16 | 16 |
| 010 | Артефакты | Сильный магический предмет | `base:artifact_powerful` | Предмет: `base:terrain_artifact_powerful` | 20 | 16 |
| 011 | Артефакты | Магическое кольцо | `base:artifact_ring` | Предмет: `base:terrain_artifact_ring` | 24 | 16 |
| 012 | Артефакты | Зачарованное кольцо | `base:artifact_ring_enchanted` | Предмет: `base:terrain_artifact_ring_enchanted` | 28 | 16 |
| 013 | Артефакты | Магический камень | `base:artifact_stone` | Предмет: `base:terrain_artifact_stone` | 32 | 16 |
| 014 | Артефакты | Неопознанный магический предмет | `base:artifact_unidentified` | Предмет: `base:terrain_artifact_unidentified` | 36 | 16 |
| 015 | Артефакты | Неизвестный артефакт | `base:artifact_unknown` | Предмет: `base:terrain_artifact_unknown` | 40 | 16 |
| 016 | Артефакты | Слабый магический предмет | `base:artifact_weak` | Предмет: `base:terrain_artifact_weak` | 44 | 16 |
| 017 | Декорации: оружие | Стрела | `base:decor_arrow` | Предмет: `base:terrain_decor_arrow` | 48 | 16 |
| 018 | Декорации: оружие | Топор | `base:decor_axe` | Предмет: `base:terrain_decor_axe` | 4 | 20 |
| 019 | Декорации: оружие | Болт | `base:decor_bolt` | Предмет: `base:terrain_decor_bolt` | 8 | 20 |
| 020 | Декорации: оружие | Лук | `base:decor_bow` | Предмет: `base:terrain_decor_bow` | 12 | 20 |
| 021 | Декорации: оружие | Кинжал | `base:decor_dagger` | Предмет: `base:terrain_decor_dagger` | 16 | 20 |
| 022 | Декорации: оружие | Двуручный топор | `base:decor_greataxe` | Предмет: `base:terrain_decor_greataxe` | 20 | 20 |
| 023 | Декорации: оружие | Большой меч | `base:decor_greatsword` | Предмет: `base:terrain_decor_greatsword` | 24 | 20 |
| 024 | Декорации: оружие | Алебарда | `base:decor_halberd` | Предмет: `base:terrain_decor_halberd` | 28 | 20 |
| 025 | Декорации: оружие | Молот | `base:decor_hammer` | Предмет: `base:terrain_decor_hammer` | 32 | 20 |
| 026 | Декорации: оружие | Длинный лук | `base:decor_longbow` | Предмет: `base:terrain_decor_longbow` | 36 | 20 |
| 027 | Декорации: оружие | Булава | `base:decor_mace` | Предмет: `base:terrain_decor_mace` | 40 | 20 |
| 028 | Декорации: оружие | Рапира | `base:decor_rapier` | Предмет: `base:terrain_decor_rapier` | 44 | 20 |
| 029 | Декорации: оружие | Серп | `base:decor_sickle` | Предмет: `base:terrain_decor_sickle` | 48 | 20 |
| 030 | Декорации: оружие | Копьё | `base:decor_spear` | Предмет: `base:terrain_decor_spear` | 4 | 24 |
| 031 | Декорации: оружие | Посох | `base:decor_staff` | Предмет: `base:terrain_decor_staff` | 8 | 24 |
| 032 | Декорации: оружие | Меч | `base:decor_sword` | Предмет: `base:terrain_decor_sword` | 12 | 24 |
| 033 | Декорации: припасы | Бутылка | `base:decor_bottle` | Предмет: `base:terrain_decor_bottle` | 16 | 24 |
| 034 | Декорации: припасы | Еда | `base:decor_food` | Предмет: `base:terrain_decor_food` | 20 | 24 |
| 035 | Декорации: припасы | Пища | `base:decor_meal` | Предмет: `base:terrain_decor_meal` | 24 | 24 |
| 036 | Декорации: припасы | Масло | `base:decor_oil` | Предмет: `base:oil` | 28 | 24 |
| 037 | Декорации: припасы | Зелье | `base:decor_potion` | Предмет: `base:terrain_decor_potion` | 32 | 24 |
| 038 | Декорации: припасы | Маленькое зелье | `base:decor_potion_small` | Предмет: `base:terrain_decor_potion_small` | 36 | 24 |
| 039 | Декорации: припасы | Неизвестное зелье | `base:decor_potion_unknown` | Предмет: `base:terrain_decor_potion_unknown` | 40 | 24 |
| 040 | Декорации: припасы | Рацион | `base:decor_rations` | Предмет: `base:terrain_decor_rations` | 44 | 24 |
| 041 | Декорации: снаряжение | Броня | `base:decor_armor` | Предмет: `base:terrain_decor_armor` | 48 | 24 |
| 042 | Декорации: снаряжение | Тяжёлая броня | `base:decor_armor_heavy` | Предмет: `base:terrain_decor_armor_heavy` | 4 | 28 |
| 043 | Декорации: снаряжение | Лёгкая броня | `base:decor_armor_light` | Предмет: `base:terrain_decor_armor_light` | 8 | 28 |
| 044 | Декорации: снаряжение | Сапоги | `base:decor_boots` | Предмет: `base:terrain_decor_boots` | 12 | 28 |
| 045 | Декорации: снаряжение | Плащ | `base:decor_cloak` | Предмет: `base:terrain_decor_cloak` | 16 | 28 |
| 046 | Декорации: снаряжение | Перчатки | `base:decor_gloves` | Предмет: `base:terrain_decor_gloves` | 20 | 28 |
| 047 | Декорации: снаряжение | Шлем | `base:decor_helmet` | Предмет: `base:terrain_decor_helmet` | 24 | 28 |
| 048 | Декорации: снаряжение | Большой щит | `base:decor_shield_large` | Предмет: `base:terrain_decor_shield_large` | 28 | 28 |
| 049 | Декорации: снаряжение | Щит | `base:decor_shield_left` | Предмет: `base:terrain_decor_shield_left` | 32 | 28 |
| 050 | Декорации: снаряжение | Щит | `base:decor_shield_right` | Предмет: `base:terrain_decor_shield_right` | 36 | 28 |
| 051 | Декорации: снаряжение | Круглый щит | `base:decor_shield_round` | Предмет: `base:terrain_decor_shield_round` | 40 | 28 |
| 052 | Замки и ключи | Древний ключ | `base:key_ancient` | Предмет: `base:terrain_key_ancient` | 44 | 28 |
| 053 | Замки и ключи | Ключ | `base:key_decor` | Предмет: `base:terrain_key_decor` | 48 | 28 |
| 054 | Замки и ключи | Важный ключ | `base:key_important` | Предмет: `base:terrain_key_important` | 4 | 32 |
| 055 | Замки и ключи | Особый ключ | `base:key_special` | Предмет: `base:terrain_key_special` | 8 | 32 |
| 056 | Замки и ключи | Ключ | `base:key_unicode` | Предмет: `base:terrain_key_unicode` | 12 | 32 |
| 057 | Алтари и святыни | Алтарь | `base:altar` | Взаимодействие: `base:terrain_altar` | 4 | 42 |
| 058 | Алтари и святыни | Большой алтарь | `base:altar_large` | Взаимодействие: `base:terrain_altar_large` | 8 | 42 |
| 059 | Алтари и святыни | Лунный алтарь | `base:altar_moon` | Взаимодействие: `base:terrain_altar_moon` | 12 | 42 |
| 060 | Алтари и святыни | Солнечный алтарь | `base:altar_sun` | Взаимодействие: `base:terrain_altar_sun` | 16 | 42 |
| 061 | Алтари и святыни | Древний крест | `base:ancient_cross` | Взаимодействие: `base:terrain_ancient_cross` | 20 | 42 |
| 062 | Алтари и святыни | Священный символ | `base:holy_symbol` | Взаимодействие: `base:terrain_holy_symbol` | 24 | 42 |
| 063 | Алтари и святыни | Ритуальный круг | `base:ritual_circle` | Взаимодействие: `base:terrain_ritual_circle` | 28 | 42 |
| 064 | Алтари и святыни | Активный ритуальный круг | `base:ritual_circle_active` | Взаимодействие: `base:terrain_ritual_circle_active`; Свет: 3/6 | 32 | 42 |
| 065 | Алтари и святыни | Жертвенная чаша | `base:sacrificial_bowl` | Взаимодействие: `base:terrain_sacrificial_bowl` | 36 | 42 |
| 066 | Алтари и святыни | Святыня | `base:shrine` | Взаимодействие: `base:terrain_shrine` | 40 | 42 |
| 067 | Алтари и святыни | Храмовый символ | `base:temple_symbol` | Взаимодействие: `base:terrain_temple_symbol` | 44 | 42 |
| 068 | Книги и документы | Книга | `base:book` | Взаимодействие: `base:terrain_book` | 48 | 42 |
| 069 | Книги и документы | Древний том | `base:book_ancient` | Взаимодействие: `base:terrain_book_ancient` | 4 | 46 |
| 070 | Книги и документы | Закрытая книга | `base:book_closed` | Взаимодействие: `base:terrain_book_closed` | 8 | 46 |
| 071 | Книги и документы | Большая книга | `base:book_large` | Взаимодействие: `base:terrain_book_large` | 12 | 46 |
| 072 | Книги и документы | Карта | `base:map_drawing` | Взаимодействие: `base:terrain_map_drawing` | 16 | 46 |
| 073 | Книги и документы | Фрагмент карты | `base:map_fragment` | Взаимодействие: `base:terrain_map_fragment` | 20 | 46 |
| 074 | Книги и документы | Записка | `base:note` | Взаимодействие: `base:terrain_note` | 24 | 46 |
| 075 | Книги и документы | Клочок бумаги | `base:paper_scrap` | Взаимодействие: `base:terrain_paper_scrap` | 28 | 46 |
| 076 | Книги и документы | Свиток | `base:scroll` | Взаимодействие: `base:terrain_scroll` | 32 | 46 |
| 077 | Книги и документы | Магический свиток | `base:scroll_magic` | Взаимодействие: `base:terrain_scroll_magic` | 36 | 46 |
| 078 | Контейнеры | Бочка | `base:barrel` | Взаимодействие: `base:terrain_barrel` | 40 | 46 |
| 079 | Контейнеры | Большая бочка | `base:barrel_large` | Взаимодействие: `base:terrain_barrel_large` | 44 | 46 |
| 080 | Контейнеры | Маленькая бочка | `base:barrel_small` | Взаимодействие: `base:terrain_barrel_small` | 48 | 46 |
| 081 | Контейнеры | Сундук | `base:chest` | Взаимодействие: `base:terrain_chest` | 4 | 50 |
| 082 | Контейнеры | Запертый сундук | `base:chest_locked` | Взаимодействие: `base:terrain_chest_locked` | 8 | 50 |
| 083 | Контейнеры | Открытый сундук | `base:chest_open` | Взаимодействие: `base:terrain_chest_open` | 12 | 50 |
| 084 | Контейнеры | Сундук с сокровищами | `base:chest_treasure` | Взаимодействие: `base:terrain_chest_treasure` | 16 | 50 |
| 085 | Контейнеры | Ящик | `base:crate` | Взаимодействие: `base:terrain_crate` | 20 | 50 |
| 086 | Контейнеры | Закрытый ящик | `base:crate_closed` | Взаимодействие: `base:terrain_crate_closed` | 24 | 50 |
| 087 | Контейнеры | Укреплённый ящик | `base:crate_reinforced` | Взаимодействие: `base:terrain_crate_reinforced` | 28 | 50 |
| 088 | Контейнеры | Кувшин | `base:jug` | Взаимодействие: `base:terrain_jug` | 32 | 50 |
| 089 | Контейнеры | Горшок | `base:pot` | Взаимодействие: `base:terrain_pot` | 36 | 50 |
| 090 | Контейнеры | Мешок | `base:sack` | Взаимодействие: `base:terrain_sack` | 40 | 50 |
| 091 | Контейнеры | Большой мешок | `base:sack_large` | Взаимодействие: `base:terrain_sack_large` | 44 | 50 |
| 092 | Контейнеры | Урна | `base:urn` | Взаимодействие: `base:terrain_urn` | 48 | 50 |
| 093 | Контейнеры | Большой сосуд | `base:vessel_large` | Взаимодействие: `base:terrain_vessel_large` | 4 | 54 |
| 094 | Магические зоны | Положительная энергия | `base:magic_positive` | Взаимодействие: `base:terrain_magic_positive` | 8 | 54 |
| 095 | Магические зоны | Слабая магия | `base:magic_weak` | Взаимодействие: `base:terrain_magic_weak` | 12 | 54 |
| 096 | Магические зоны | Сильная магическая зона | `base:magic_zone` | Взаимодействие: `base:terrain_magic_zone` | 16 | 54 |
| 097 | Метки мест | Важное место | `base:marker_important` | Взаимодействие: `base:terrain_marker_important` | 20 | 54 |
| 098 | Метки мест | Интересный объект | `base:marker_interest` | Взаимодействие: `base:terrain_marker_interest` | 24 | 54 |
| 099 | Метки мест | Сокровище | `base:marker_treasure` | Взаимодействие: `base:terrain_marker_treasure` | 28 | 54 |
| 100 | Метки мест | Уникальное место | `base:marker_unique` | Взаимодействие: `base:terrain_marker_unique` | 32 | 54 |
| 101 | Метки мест | Неизвестное место | `base:marker_unknown` | Взаимодействие: `base:terrain_marker_unknown` | 36 | 54 |
| 102 | Руны | Обычная руна | `base:rune` | Взаимодействие: `base:terrain_rune` | 40 | 54 |
| 103 | Руны | Активная руна | `base:rune_active` | Взаимодействие: `base:terrain_rune_active`; Свет: 3/6 | 44 | 54 |
| 104 | Руны | Руна воздуха | `base:rune_air` | Взаимодействие: `base:terrain_rune_air` | 48 | 54 |
| 105 | Руны | Круглая руна | `base:rune_circle` | Взаимодействие: `base:terrain_rune_circle` | 4 | 58 |
| 106 | Руны | Руна | `base:rune_cross` | Взаимодействие: `base:terrain_rune_cross` | 8 | 58 |
| 107 | Руны | Руна земли | `base:rune_earth` | Взаимодействие: `base:terrain_rune_earth` | 12 | 58 |
| 108 | Руны | Магическая руна | `base:rune_magic` | Взаимодействие: `base:terrain_rune_magic` | 16 | 58 |
| 109 | Руны | Руна наблюдения | `base:rune_observation` | Взаимодействие: `base:terrain_rune_observation` | 20 | 58 |
| 110 | Руны | Запрещающая руна | `base:rune_prohibition` | Взаимодействие: `base:terrain_rune_prohibition` | 24 | 58 |
| 111 | Руны | Защитная руна | `base:rune_protection` | Взаимодействие: `base:terrain_rune_protection` | 28 | 58 |
| 112 | Руны | Руна воды | `base:rune_water` | Взаимодействие: `base:terrain_rune_water` | 32 | 58 |
| 113 | Руны | Слабая руна | `base:rune_weak` | Взаимодействие: `base:terrain_rune_weak` | 36 | 58 |
| 114 | Сокровища | Амулет | `base:amulet` | Взаимодействие: `base:terrain_amulet` | 40 | 58 |
| 115 | Сокровища | Россыпь монет | `base:coin_scatter` | Взаимодействие: `base:terrain_coin_scatter` | 44 | 58 |
| 116 | Сокровища | Драгоценный камень | `base:gem` | Взаимодействие: `base:terrain_gem` | 48 | 58 |
| 117 | Сокровища | Крупный самоцвет | `base:gem_large` | Взаимодействие: `base:terrain_gem_large` | 4 | 62 |
| 118 | Сокровища | Необработанный самоцвет | `base:gem_raw` | Взаимодействие: `base:terrain_gem_raw` | 8 | 62 |
| 119 | Сокровища | Украшение | `base:jewelry` | Взаимодействие: `base:terrain_jewelry` | 12 | 62 |
| 120 | Сокровища | Кольцо | `base:ring` | Взаимодействие: `base:terrain_ring` | 16 | 62 |
| 121 | Сокровища | Монеты | `base:treasure_coins` | Взаимодействие: `base:terrain_treasure_coins` | 20 | 62 |
| 122 | Сокровища | Медь | `base:treasure_copper` | Взаимодействие: `base:terrain_treasure_copper` | 24 | 62 |
| 123 | Сокровища | Золото | `base:treasure_gold` | Взаимодействие: `base:terrain_treasure_gold` | 28 | 62 |
| 124 | Сокровища | Золото | `base:treasure_gold_mark` | Взаимодействие: `base:terrain_treasure_gold_mark` | 32 | 62 |
| 125 | Сокровища | Драгоценности | `base:treasure_jewels` | Взаимодействие: `base:terrain_treasure_jewels` | 36 | 62 |
| 126 | Сокровища | Серебро | `base:treasure_silver` | Взаимодействие: `base:terrain_treasure_silver` | 40 | 62 |
| 127 | Газ, дым и туман | Ядовитый газ | `base:gas_toxic` | Ловушка: `base:terrain_gas_toxic` | 4 | 72 |
| 128 | Кислота и яд | Кислота | `base:acid` | Ловушка: `base:terrain_acid` | 8 | 72 |
| 129 | Кислота и яд | Глубокая кислота | `base:acid_deep` | Ловушка: `base:terrain_acid_deep` | 12 | 72 |
| 130 | Кислота и яд | Яд | `base:poison` | Ловушка: `base:terrain_poison` | 16 | 72 |
| 131 | Кислота и яд | Ядовитая поверхность | `base:poison_surface` | Ловушка: `base:terrain_poison_surface` | 20 | 72 |
| 132 | Кислота и яд | Токсичные споры | `base:toxic_spores` | Ловушка: `base:terrain_toxic_spores` | 24 | 72 |
| 133 | Лава и огонь | Огонь | `base:fire` | Ловушка: `base:terrain_fire`; Свет: 3/6 | 28 | 72 |
| 134 | Лава и огонь | Большое пламя | `base:fire_large` | Ловушка: `base:terrain_fire_large`; Свет: 3/6 | 32 | 72 |
| 135 | Лава и огонь | Небольшое пламя | `base:fire_small` | Ловушка: `base:terrain_fire_small`; Свет: 3/6 | 36 | 72 |
| 136 | Лава и огонь | Лава | `base:lava` | Ловушка: `base:terrain_lava`; Свет: 3/6 | 40 | 72 |
| 137 | Лава и огонь | Бурлящая лава | `base:lava_bubbling` | Ловушка: `base:terrain_lava_bubbling`; Свет: 3/6 | 44 | 72 |
| 138 | Лава и огонь | Поток лавы | `base:lava_flow` | Ловушка: `base:terrain_lava_flow`; Свет: 3/6 | 48 | 72 |
| 139 | Лава и огонь | Магический огонь | `base:magic_fire` | Ловушка: `base:terrain_magic_fire`; Свет: 3/6 | 4 | 76 |
| 140 | Ловушки: рисунки | Стрела из стены | `base:arrow_slit` | Ловушка: `base:terrain_arrow_slit` | 8 | 76 |
| 141 | Ловушки: рисунки | Серия стрел | `base:arrow_slit_barrage` | Ловушка: `base:terrain_arrow_slit_barrage` | 12 | 76 |
| 142 | Ловушки: рисунки | Обвал | `base:cave_in` | Ловушка: `base:terrain_cave_in` | 16 | 76 |
| 143 | Ловушки: рисунки | Ловушка в двери | `base:door_trap` | Ловушка: `base:terrain_door_trap` | 20 | 76 |
| 144 | Ловушки: рисунки | Нажимная плита | `base:pressure_plate` | Ловушка: `base:terrain_pressure_plate` | 24 | 76 |
| 145 | Ловушки: рисунки | Активированная плита | `base:pressure_plate_active` | Ловушка: `base:terrain_pressure_plate_active` | 28 | 76 |
| 146 | Ловушки: рисунки | Каменная нажимная плита | `base:pressure_plate_stone` | Ловушка: `base:terrain_pressure_plate_stone` | 32 | 76 |
| 147 | Ловушки: рисунки | Шипы | `base:spikes` | Ловушка: `base:terrain_spikes` | 36 | 76 |
| 148 | Ловушки: рисунки | Скрытые шипы | `base:spikes_hidden` | Ловушка: `base:terrain_spikes_hidden` | 40 | 76 |
| 149 | Ловушки: рисунки | Большие шипы | `base:spikes_large` | Ловушка: `base:terrain_spikes_large` | 44 | 76 |
| 150 | Ловушки: рисунки | Подозрительное место | `base:suspicious_floor` | Ловушка: `base:terrain_suspicious_floor` | 48 | 76 |
| 151 | Ловушки: рисунки | Кислотная ловушка | `base:trap_acid` | Ловушка: `base:terrain_trap_acid` | 4 | 80 |
| 152 | Ловушки: рисунки | Смертельная ловушка | `base:trap_deadly` | Ловушка: `base:terrain_trap_deadly` | 8 | 80 |
| 153 | Ловушки: рисунки | Затопляющая ловушка | `base:trap_flood` | Ловушка: `base:terrain_trap_flood` | 12 | 80 |
| 154 | Ловушки: рисунки | Магическая ловушка | `base:trap_magic` | Ловушка: `base:terrain_trap_magic` | 16 | 80 |
| 155 | Ловушки: рисунки | Механическая ловушка | `base:trap_mechanical` | Ловушка: `base:terrain_trap_mechanical` | 20 | 80 |
| 156 | Ловушки: рисунки | Магическая руна-ловушка | `base:trap_rune` | Ловушка: `base:terrain_trap_rune` | 24 | 80 |
| 157 | Ловушки: рисунки | Небольшая ловушка | `base:trap_small` | Ловушка: `base:terrain_trap_small` | 28 | 80 |
| 158 | Ловушки: рисунки | Падающая стена | `base:wall_falling` | Ловушка: `base:terrain_wall_falling` | 32 | 80 |
| 159 | Магические зоны | Отрицательная энергия | `base:magic_negative` | Ловушка: `base:terrain_magic_negative` | 36 | 80 |
| 160 | Руны | Руна разрушения | `base:rune_destruction` | Ловушка: `base:terrain_rune_destruction` | 40 | 80 |
| 161 | Руны | Руна огня | `base:rune_fire` | Ловушка: `base:terrain_rune_fire` | 44 | 80 |
| 162 | Грибы | Светящийся гриб | `base:mushroom_glowing` | Свет: 1/3 | 4 | 90 |
| 163 | Источники света: рисунки | Свеча | `base:candle` | Свет: 1/3 | 8 | 90 |
| 164 | Источники света: рисунки | Фонарь | `base:lantern` | Свет: 3/6 | 12 | 90 |
| 165 | Источники света: рисунки | Магический фонарь | `base:lantern_magic` | Свет: 3/6 | 16 | 90 |
| 166 | Источники света: рисунки | Яркий источник света | `base:light_bright` | Свет: 3/6 | 20 | 90 |
| 167 | Источники света: рисунки | Магический свет | `base:light_magic` | Свет: 3/6 | 24 | 90 |
| 168 | Источники света: рисунки | Источник света | `base:light_source` | Свет: 3/6 | 28 | 90 |
| 169 | Источники света: рисунки | Факел | `base:torch_decor` | Свет: 3/6 | 32 | 90 |
| 170 | Источники света: рисунки | Настенный факел | `base:torch_wall` | Свет: 3/6 | 36 | 90 |
| 171 | Лава и огонь | Горячий источник | `base:hot_spring` | Свет: 3/6 | 40 | 90 |
| 172 | Лава и огонь | Искры | `base:sparks` | Свет: 1/3 | 44 | 90 |
| 173 | Магические зоны | Концентрированная магия | `base:magic_concentrated` | Свет: 3/6 | 48 | 90 |
| 174 | Магические зоны | Магическая энергия | `base:magic_energy` | Свет: 3/6 | 4 | 94 |
| 175 | Лестницы и переходы | Спуск глубже | `base:exit_down` | Переход к старту | 4 | 104 |
| 176 | Лестницы и переходы | Выход наверх | `base:exit_up` | Переход к старту | 8 | 104 |
| 177 | Лестницы и переходы | Лестница вниз | `base:stairs_down` | Переход к старту | 12 | 104 |
| 178 | Лестницы и переходы | Лестница вверх | `base:stairs_up` | Переход к старту | 16 | 104 |
| 179 | Лестницы и переходы | Переход вниз | `base:transition_down` | Переход к старту | 20 | 104 |
| 180 | Лестницы и переходы | Переход на следующий уровень | `base:transition_next` | Переход к старту | 24 | 104 |
| 181 | Лестницы и переходы | Переход на предыдущий уровень | `base:transition_previous` | Переход к старту | 28 | 104 |
| 182 | Лестницы и переходы | Переход вверх | `base:transition_up` | Переход к старту | 32 | 104 |
| 183 | Порталы | Магический разлом | `base:magic_rift` | Переход к старту | 36 | 104 |
| 184 | Порталы | Портал | `base:portal` | Переход к старту | 40 | 104 |
| 185 | Порталы | Активный портал | `base:portal_active` | Переход к старту | 44 | 104 |
| 186 | Порталы | Тёмный портал | `base:portal_dark` | Переход к старту | 48 | 104 |
| 187 | Порталы | Великий портал | `base:portal_great` | Переход к старту | 4 | 108 |
| 188 | Порталы | Неактивный портал | `base:portal_inactive` | Переход к старту | 8 | 108 |
| 189 | Порталы | Светлый портал | `base:portal_light` | Переход к старту | 12 | 108 |
| 190 | Порталы | Малый портал | `base:portal_small` | Переход к старту | 16 | 108 |
| 191 | Порталы | Нестабильный портал | `base:portal_unstable` | Переход к старту | 20 | 108 |
| 192 | Телепорты | Телепорт | `base:teleport` | Переход к старту | 24 | 108 |
| 193 | Телепорты | Активный телепорт | `base:teleport_active` | Переход к старту | 28 | 108 |
| 194 | Телепорты | Неактивный телепорт | `base:teleport_inactive` | Переход к старту | 32 | 108 |
| 195 | Телепорты | Большой телепорт | `base:teleport_large` | Переход к старту | 36 | 108 |
| 196 | Телепорты | Нестабильный телепорт | `base:teleport_unstable` | Переход к старту | 40 | 108 |
