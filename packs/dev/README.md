# Полигон разработчика

Второй полигон: [все интерактивные тайлы](interactive_tiles.md).

Карта `dev:all_items`, 53×108. Яркий общий свет, внешние стены, открытые проходы.
Между любыми размещёнными объектами не менее трёх пустых клеток.

```bash
./run.sh --test-map dev:all_items
# Терминал вместо окна:
./run.sh --terminal --test-map dev:all_items
# Windows:
.\run.bat --test-map dev:all_items
```

В студии выберите пакет `dev`, раздел карт и «Полигон разработчика: все предметы».
Предметы: встать на клетку и нажать G (в браузерном тесте — «Подобрать»), затем тестировать в инвентаре.
Точки интереса: Enter с клетки или соседней клетки. Ловушки: вход на клетку.
Скрытые ловушки сохраняют скрытость; найти их помогут номера ниже.
Ловушки наносят настоящий урон. Долгий отдых восстанавливает HP; перезапуск теста возвращает все объекты.
Декоративные тайлы без механики сюда не включены. Предметы лежат поверх пола и не оставляют рисунок после подбора.

Добавили контент? Сохраните его в студии, остановите тест и пересоберите полигон:

```bash
.venv/bin/python -m scripts.build_developer_map --force
# Windows:
.venv\Scripts\python.exe -m scripts.build_developer_map --force
```

Пересборка заменяет только сгенерированные файлы этого полигона и таблицу ниже.
Для переноса скопируйте весь `packs/dev/` вместе с пакетами из `manifest.json`.

Координаты начинаются с нуля и совпадают с инспектором карты.

| № | Раздел | Название | Ссылка | X | Y |
| --- | --- | --- | --- | ---: | ---: |
| 001 | Вооружение | Кинжал | `base:dagger` | 4 | 6 |
| 002 | Вооружение | Посох | `base:staff` | 8 | 6 |
| 003 | Вооружение | Меч | `base:sword` | 12 | 6 |
| 004 | Вооружение | Топор | `base:terrain_decor_axe` | 16 | 6 |
| 005 | Вооружение | Лук | `base:terrain_decor_bow` | 20 | 6 |
| 006 | Вооружение | Кинжал | `base:terrain_decor_dagger` | 24 | 6 |
| 007 | Вооружение | Двуручный топор | `base:terrain_decor_greataxe` | 28 | 6 |
| 008 | Вооружение | Большой меч | `base:terrain_decor_greatsword` | 32 | 6 |
| 009 | Вооружение | Алебарда | `base:terrain_decor_halberd` | 36 | 6 |
| 010 | Вооружение | Молот | `base:terrain_decor_hammer` | 40 | 6 |
| 011 | Вооружение | Длинный лук | `base:terrain_decor_longbow` | 44 | 6 |
| 012 | Вооружение | Булава | `base:terrain_decor_mace` | 48 | 6 |
| 013 | Вооружение | Рапира | `base:terrain_decor_rapier` | 4 | 10 |
| 014 | Вооружение | Серп | `base:terrain_decor_sickle` | 8 | 10 |
| 015 | Вооружение | Копьё | `base:terrain_decor_spear` | 12 | 10 |
| 016 | Вооружение | Посох | `base:terrain_decor_staff` | 16 | 10 |
| 017 | Вооружение | Меч | `base:terrain_decor_sword` | 20 | 10 |
| 018 | Доспехи | Кожаный доспех | `base:leather` | 4 | 20 |
| 019 | Доспехи | Кольчуга | `base:mail` | 8 | 20 |
| 020 | Доспехи | Мантия | `base:robe` | 12 | 20 |
| 021 | Доспехи | Щит | `base:shield` | 16 | 20 |
| 022 | Доспехи | Броня | `base:terrain_decor_armor` | 20 | 20 |
| 023 | Доспехи | Тяжёлая броня | `base:terrain_decor_armor_heavy` | 24 | 20 |
| 024 | Доспехи | Лёгкая броня | `base:terrain_decor_armor_light` | 28 | 20 |
| 025 | Доспехи | Сапоги | `base:terrain_decor_boots` | 32 | 20 |
| 026 | Доспехи | Плащ | `base:terrain_decor_cloak` | 36 | 20 |
| 027 | Доспехи | Перчатки | `base:terrain_decor_gloves` | 40 | 20 |
| 028 | Доспехи | Шлем | `base:terrain_decor_helmet` | 44 | 20 |
| 029 | Доспехи | Большой щит | `base:terrain_decor_shield_large` | 48 | 20 |
| 030 | Доспехи | Щит | `base:terrain_decor_shield_left` | 4 | 24 |
| 031 | Доспехи | Щит | `base:terrain_decor_shield_right` | 8 | 24 |
| 032 | Доспехи | Круглый щит | `base:terrain_decor_shield_round` | 12 | 24 |
| 033 | Расходники | Флакон кислоты | `base:acid_flask` | 4 | 34 |
| 034 | Расходники | Зелье лечения | `base:healing_potion` | 8 | 34 |
| 035 | Расходники | Масло | `base:oil` | 12 | 34 |
| 036 | Расходники | Дорожный паёк | `base:rations` | 16 | 34 |
| 037 | Расходники | Магическое зелье | `base:terrain_artifact_potion` | 20 | 34 |
| 038 | Расходники | Стрела | `base:terrain_decor_arrow` | 24 | 34 |
| 039 | Расходники | Болт | `base:terrain_decor_bolt` | 28 | 34 |
| 040 | Расходники | Еда | `base:terrain_decor_food` | 32 | 34 |
| 041 | Расходники | Пища | `base:terrain_decor_meal` | 36 | 34 |
| 042 | Расходники | Зелье | `base:terrain_decor_potion` | 40 | 34 |
| 043 | Расходники | Маленькое зелье | `base:terrain_decor_potion_small` | 44 | 34 |
| 044 | Расходники | Рацион | `base:terrain_decor_rations` | 48 | 34 |
| 045 | Инструменты | Спальный мешок | `base:bedroll` | 4 | 44 |
| 046 | Инструменты | Ключ от сундука | `base:chest_key` | 8 | 44 |
| 047 | Инструменты | Ломик | `base:crowbar` | 12 | 44 |
| 048 | Инструменты | Кремень и кресало | `base:flint_and_steel` | 16 | 44 |
| 049 | Инструменты | Чернила и перо | `base:ink` | 20 | 44 |
| 050 | Инструменты | Масляная лампа | `base:lamp` | 24 | 44 |
| 051 | Инструменты | Мастерские отмычки | `base:master_lockpicks` | 28 | 44 |
| 052 | Инструменты | Пергамент | `base:parchment` | 32 | 44 |
| 053 | Инструменты | Кирка | `base:pickaxe` | 36 | 44 |
| 054 | Инструменты | Верёвка | `base:rope` | 40 | 44 |
| 055 | Инструменты | Книга заклинаний | `base:spellbook` | 44 | 44 |
| 056 | Инструменты | Магический предмет | `base:terrain_artifact` | 48 | 44 |
| 057 | Инструменты | Амулет | `base:terrain_artifact_amulet` | 4 | 48 |
| 058 | Инструменты | Легендарный предмет | `base:terrain_artifact_legendary` | 8 | 48 |
| 059 | Инструменты | Сильный магический предмет | `base:terrain_artifact_powerful` | 12 | 48 |
| 060 | Инструменты | Магическое кольцо | `base:terrain_artifact_ring` | 16 | 48 |
| 061 | Инструменты | Зачарованное кольцо | `base:terrain_artifact_ring_enchanted` | 20 | 48 |
| 062 | Инструменты | Магический камень | `base:terrain_artifact_stone` | 24 | 48 |
| 063 | Инструменты | Неопознанный магический предмет | `base:terrain_artifact_unidentified` | 28 | 48 |
| 064 | Инструменты | Неизвестный артефакт | `base:terrain_artifact_unknown` | 32 | 48 |
| 065 | Инструменты | Слабый магический предмет | `base:terrain_artifact_weak` | 36 | 48 |
| 066 | Инструменты | Бутылка | `base:terrain_decor_bottle` | 40 | 48 |
| 067 | Инструменты | Неизвестное зелье | `base:terrain_decor_potion_unknown` | 44 | 48 |
| 068 | Инструменты | Древний ключ | `base:terrain_key_ancient` | 48 | 48 |
| 069 | Инструменты | Ключ | `base:terrain_key_decor` | 4 | 52 |
| 070 | Инструменты | Важный ключ | `base:terrain_key_important` | 8 | 52 |
| 071 | Инструменты | Особый ключ | `base:terrain_key_special` | 12 | 52 |
| 072 | Инструменты | Ключ | `base:terrain_key_unicode` | 16 | 52 |
| 073 | Инструменты | Воровские инструменты | `base:thieves_tools` | 20 | 52 |
| 074 | Инструменты | Факел | `base:torch` | 24 | 52 |
| 075 | Точки взаимодействия | Запертый сундук | `base:chest` | 4 | 62 |
| 076 | Точки взаимодействия | Забытый алтарь | `base:shrine` | 8 | 62 |
| 077 | Точки взаимодействия | Алтарь | `base:terrain_altar` | 12 | 62 |
| 078 | Точки взаимодействия | Большой алтарь | `base:terrain_altar_large` | 16 | 62 |
| 079 | Точки взаимодействия | Лунный алтарь | `base:terrain_altar_moon` | 20 | 62 |
| 080 | Точки взаимодействия | Солнечный алтарь | `base:terrain_altar_sun` | 24 | 62 |
| 081 | Точки взаимодействия | Амулет | `base:terrain_amulet` | 28 | 62 |
| 082 | Точки взаимодействия | Древний крест | `base:terrain_ancient_cross` | 32 | 62 |
| 083 | Точки взаимодействия | Бочка | `base:terrain_barrel` | 36 | 62 |
| 084 | Точки взаимодействия | Большая бочка | `base:terrain_barrel_large` | 40 | 62 |
| 085 | Точки взаимодействия | Маленькая бочка | `base:terrain_barrel_small` | 44 | 62 |
| 086 | Точки взаимодействия | Книга | `base:terrain_book` | 48 | 62 |
| 087 | Точки взаимодействия | Древний том | `base:terrain_book_ancient` | 4 | 66 |
| 088 | Точки взаимодействия | Закрытая книга | `base:terrain_book_closed` | 8 | 66 |
| 089 | Точки взаимодействия | Большая книга | `base:terrain_book_large` | 12 | 66 |
| 090 | Точки взаимодействия | Сундук | `base:terrain_chest` | 16 | 66 |
| 091 | Точки взаимодействия | Запертый сундук | `base:terrain_chest_locked` | 20 | 66 |
| 092 | Точки взаимодействия | Открытый сундук | `base:terrain_chest_open` | 24 | 66 |
| 093 | Точки взаимодействия | Сундук с сокровищами | `base:terrain_chest_treasure` | 28 | 66 |
| 094 | Точки взаимодействия | Россыпь монет | `base:terrain_coin_scatter` | 32 | 66 |
| 095 | Точки взаимодействия | Ящик | `base:terrain_crate` | 36 | 66 |
| 096 | Точки взаимодействия | Закрытый ящик | `base:terrain_crate_closed` | 40 | 66 |
| 097 | Точки взаимодействия | Укреплённый ящик | `base:terrain_crate_reinforced` | 44 | 66 |
| 098 | Точки взаимодействия | Драгоценный камень | `base:terrain_gem` | 48 | 66 |
| 099 | Точки взаимодействия | Крупный самоцвет | `base:terrain_gem_large` | 4 | 70 |
| 100 | Точки взаимодействия | Необработанный самоцвет | `base:terrain_gem_raw` | 8 | 70 |
| 101 | Точки взаимодействия | Священный символ | `base:terrain_holy_symbol` | 12 | 70 |
| 102 | Точки взаимодействия | Украшение | `base:terrain_jewelry` | 16 | 70 |
| 103 | Точки взаимодействия | Кувшин | `base:terrain_jug` | 20 | 70 |
| 104 | Точки взаимодействия | Положительная энергия | `base:terrain_magic_positive` | 24 | 70 |
| 105 | Точки взаимодействия | Слабая магия | `base:terrain_magic_weak` | 28 | 70 |
| 106 | Точки взаимодействия | Сильная магическая зона | `base:terrain_magic_zone` | 32 | 70 |
| 107 | Точки взаимодействия | Карта | `base:terrain_map_drawing` | 36 | 70 |
| 108 | Точки взаимодействия | Фрагмент карты | `base:terrain_map_fragment` | 40 | 70 |
| 109 | Точки взаимодействия | Важное место | `base:terrain_marker_important` | 44 | 70 |
| 110 | Точки взаимодействия | Интересный объект | `base:terrain_marker_interest` | 48 | 70 |
| 111 | Точки взаимодействия | Сокровище | `base:terrain_marker_treasure` | 4 | 74 |
| 112 | Точки взаимодействия | Уникальное место | `base:terrain_marker_unique` | 8 | 74 |
| 113 | Точки взаимодействия | Неизвестное место | `base:terrain_marker_unknown` | 12 | 74 |
| 114 | Точки взаимодействия | Записка | `base:terrain_note` | 16 | 74 |
| 115 | Точки взаимодействия | Клочок бумаги | `base:terrain_paper_scrap` | 20 | 74 |
| 116 | Точки взаимодействия | Горшок | `base:terrain_pot` | 24 | 74 |
| 117 | Точки взаимодействия | Кольцо | `base:terrain_ring` | 28 | 74 |
| 118 | Точки взаимодействия | Ритуальный круг | `base:terrain_ritual_circle` | 32 | 74 |
| 119 | Точки взаимодействия | Активный ритуальный круг | `base:terrain_ritual_circle_active` | 36 | 74 |
| 120 | Точки взаимодействия | Обычная руна | `base:terrain_rune` | 40 | 74 |
| 121 | Точки взаимодействия | Активная руна | `base:terrain_rune_active` | 44 | 74 |
| 122 | Точки взаимодействия | Руна воздуха | `base:terrain_rune_air` | 48 | 74 |
| 123 | Точки взаимодействия | Круглая руна | `base:terrain_rune_circle` | 4 | 78 |
| 124 | Точки взаимодействия | Руна | `base:terrain_rune_cross` | 8 | 78 |
| 125 | Точки взаимодействия | Руна земли | `base:terrain_rune_earth` | 12 | 78 |
| 126 | Точки взаимодействия | Магическая руна | `base:terrain_rune_magic` | 16 | 78 |
| 127 | Точки взаимодействия | Руна наблюдения | `base:terrain_rune_observation` | 20 | 78 |
| 128 | Точки взаимодействия | Запрещающая руна | `base:terrain_rune_prohibition` | 24 | 78 |
| 129 | Точки взаимодействия | Защитная руна | `base:terrain_rune_protection` | 28 | 78 |
| 130 | Точки взаимодействия | Руна воды | `base:terrain_rune_water` | 32 | 78 |
| 131 | Точки взаимодействия | Слабая руна | `base:terrain_rune_weak` | 36 | 78 |
| 132 | Точки взаимодействия | Мешок | `base:terrain_sack` | 40 | 78 |
| 133 | Точки взаимодействия | Большой мешок | `base:terrain_sack_large` | 44 | 78 |
| 134 | Точки взаимодействия | Жертвенная чаша | `base:terrain_sacrificial_bowl` | 48 | 78 |
| 135 | Точки взаимодействия | Свиток | `base:terrain_scroll` | 4 | 82 |
| 136 | Точки взаимодействия | Магический свиток | `base:terrain_scroll_magic` | 8 | 82 |
| 137 | Точки взаимодействия | Святыня | `base:terrain_shrine` | 12 | 82 |
| 138 | Точки взаимодействия | Храмовый символ | `base:terrain_temple_symbol` | 16 | 82 |
| 139 | Точки взаимодействия | Монеты | `base:terrain_treasure_coins` | 20 | 82 |
| 140 | Точки взаимодействия | Медь | `base:terrain_treasure_copper` | 24 | 82 |
| 141 | Точки взаимодействия | Золото | `base:terrain_treasure_gold` | 28 | 82 |
| 142 | Точки взаимодействия | Золото | `base:terrain_treasure_gold_mark` | 32 | 82 |
| 143 | Точки взаимодействия | Драгоценности | `base:terrain_treasure_jewels` | 36 | 82 |
| 144 | Точки взаимодействия | Серебро | `base:terrain_treasure_silver` | 40 | 82 |
| 145 | Точки взаимодействия | Урна | `base:terrain_urn` | 44 | 82 |
| 146 | Точки взаимодействия | Большой сосуд | `base:terrain_vessel_large` | 48 | 82 |
| 147 | Ловушки | Шипы | `base:spikes` | 4 | 92 |
| 148 | Ловушки | Кислота | `base:terrain_acid` | 8 | 92 |
| 149 | Ловушки | Глубокая кислота | `base:terrain_acid_deep` | 12 | 92 |
| 150 | Ловушки | Стрела из стены | `base:terrain_arrow_slit` | 16 | 92 |
| 151 | Ловушки | Серия стрел | `base:terrain_arrow_slit_barrage` | 20 | 92 |
| 152 | Ловушки | Обвал | `base:terrain_cave_in` | 24 | 92 |
| 153 | Ловушки | Ловушка в двери | `base:terrain_door_trap` | 28 | 92 |
| 154 | Ловушки | Огонь | `base:terrain_fire` | 32 | 92 |
| 155 | Ловушки | Большое пламя | `base:terrain_fire_large` | 36 | 92 |
| 156 | Ловушки | Небольшое пламя | `base:terrain_fire_small` | 40 | 92 |
| 157 | Ловушки | Ядовитый газ | `base:terrain_gas_toxic` | 44 | 92 |
| 158 | Ловушки | Лава | `base:terrain_lava` | 48 | 92 |
| 159 | Ловушки | Бурлящая лава | `base:terrain_lava_bubbling` | 4 | 96 |
| 160 | Ловушки | Поток лавы | `base:terrain_lava_flow` | 8 | 96 |
| 161 | Ловушки | Магический огонь | `base:terrain_magic_fire` | 12 | 96 |
| 162 | Ловушки | Отрицательная энергия | `base:terrain_magic_negative` | 16 | 96 |
| 163 | Ловушки | Яд | `base:terrain_poison` | 20 | 96 |
| 164 | Ловушки | Ядовитая поверхность | `base:terrain_poison_surface` | 24 | 96 |
| 165 | Ловушки | Нажимная плита | `base:terrain_pressure_plate` | 28 | 96 |
| 166 | Ловушки | Активированная плита | `base:terrain_pressure_plate_active` | 32 | 96 |
| 167 | Ловушки | Каменная нажимная плита | `base:terrain_pressure_plate_stone` | 36 | 96 |
| 168 | Ловушки | Руна разрушения | `base:terrain_rune_destruction` | 40 | 96 |
| 169 | Ловушки | Руна огня | `base:terrain_rune_fire` | 44 | 96 |
| 170 | Ловушки | Шипы | `base:terrain_spikes` | 48 | 96 |
| 171 | Ловушки | Скрытые шипы | `base:terrain_spikes_hidden` | 4 | 100 |
| 172 | Ловушки | Большие шипы | `base:terrain_spikes_large` | 8 | 100 |
| 173 | Ловушки | Подозрительное место | `base:terrain_suspicious_floor` | 12 | 100 |
| 174 | Ловушки | Токсичные споры | `base:terrain_toxic_spores` | 16 | 100 |
| 175 | Ловушки | Кислотная ловушка | `base:terrain_trap_acid` | 20 | 100 |
| 176 | Ловушки | Смертельная ловушка | `base:terrain_trap_deadly` | 24 | 100 |
| 177 | Ловушки | Затопляющая ловушка | `base:terrain_trap_flood` | 28 | 100 |
| 178 | Ловушки | Магическая ловушка | `base:terrain_trap_magic` | 32 | 100 |
| 179 | Ловушки | Механическая ловушка | `base:terrain_trap_mechanical` | 36 | 100 |
| 180 | Ловушки | Магическая руна-ловушка | `base:terrain_trap_rune` | 40 | 100 |
| 181 | Ловушки | Небольшая ловушка | `base:terrain_trap_small` | 44 | 100 |
| 182 | Ловушки | Падающая стена | `base:terrain_wall_falling` | 48 | 100 |
