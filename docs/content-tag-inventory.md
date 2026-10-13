# Полная классификация игрового контента

Создано `python -m scripts.tag_gameplay --write` из проверенных документов `packs/base`. Пользовательские пакеты не изменяются. Теги не заменяют игровые поля и не включают новую механику.

Каталог и правила: [gameplay-tags.md](gameplay-tags.md). Машиночитаемые данные: [gameplay-tags.json](gameplay-tags.json).

Проверено документов: **737**. equipment: 149; spells: 20; actions: 5; monsters: 2; tiles: 192; objects: 110; points_of_interest: 77; traps: 36; challenges: 72; races: 3; classes: 3; backgrounds: 6; recipes: 62.

## Содержимое сосудов

Это признаки жидкости отдельно от материала тары. Объём и вид хранятся в экземпляре; опасное питьё и лечение используют текущие правила движка.

| Вид | Название | Признаки |
| --- | --- | --- |
| `clean_water` | Чистая вода | `liquid`, `water` |
| `dirty_water` | Грязная вода | `applies_poison`, `liquid`, `water` |
| `swamp_water` | Болотная вода | `applies_poison`, `liquid`, `water` |
| `salt_water` | Солёная вода | `liquid`, `water` |
| `poisoned_water` | Отравленная вода | `applies_poison`, `liquid`, `poison`, `water` |
| `holy_water` | Святая вода | `holy`, `liquid`, `water` |
| `healing_broth` | Лечебный отвар | `healing`, `liquid` |
| `healing_potion` | Лечебное зелье | `healing`, `liquid` |
| `antidote` | Противоядный отвар | `antidote`, `liquid` |
| `cactus_juice` | Сок кактуса | `food`, `liquid`, `organic`, `plants` |

## equipment

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:acid_flask: Флакон кислоты](../packs/base/equipment/acid_flask.json) | `acid`, `attack`, `damage`, `glass`, `liquid`, `weapon` | `consumable`, `throwable` |
| [base:arcane_dust: Связанный реагент](../packs/base/equipment/arcana/arcane_dust.json) | `magic` | — |
| [base:arcane_focus: Рунный фокус](../packs/base/equipment/arcana/arcane_focus.json) | `destructible`, `magic`, `repairable`, `stone` | — |
| [base:binding_resin: Связующая смола](../packs/base/equipment/arcana/binding_resin.json) | `flammable`, `organic`, `sticky` | — |
| [base:dragon_hide: Драконья кожа](../packs/base/equipment/arcana/dragon_hide.json) | `flammable`, `leather`, `organic` | — |
| [base:dragon_leather: Доспех из драконьей кожи](../packs/base/equipment/arcana/dragon_leather.json) | `armor`, `destructible`, `flammable`, `leather`, `organic`, `protection`, `repairable` | — |
| [base:improvised_club: Связанная дубинка](../packs/base/equipment/arcana/improvised_club.json) | `attack`, `damage`, `destructible`, `flammable`, `organic`, `repairable`, `weapon`, `wooden` | — |
| [base:inscribed_page: Лист с надписью](../packs/base/equipment/arcana/inscribed_page.json) | `flammable`, `paper`, `readable` | — |
| [base:ironwood: Железное дерево](../packs/base/equipment/arcana/ironwood.json) | `flammable`, `organic`, `wooden` | — |
| [base:ironwood_club: Дубинка из железного дерева](../packs/base/equipment/arcana/ironwood_club.json) | `attack`, `damage`, `destructible`, `flammable`, `organic`, `repairable`, `weapon`, `wooden` | — |
| [base:mithril: Мифрил](../packs/base/equipment/arcana/mithril.json) | `metal` | — |
| [base:mithril_shield: Мифриловый щит](../packs/base/equipment/arcana/mithril_shield.json) | `destructible`, `metal`, `protection`, `repairable` | — |
| [base:pigment: Пигмент](../packs/base/equipment/arcana/pigment.json) | `stone` | — |
| [base:rune_dagger: Рунный клинок](../packs/base/equipment/arcana/rune_dagger.json) | `attack`, `damage`, `destructible`, `iron`, `magic`, `metal`, `piercing`, `repairable`, `weapon` | — |
| [base:rune_leather: Рунный кожаный доспех](../packs/base/equipment/arcana/rune_leather.json) | `armor`, `destructible`, `flammable`, `leather`, `magic`, `organic`, `protection`, `repairable` | — |
| [base:scroll_fire_bolt: Свиток огненного снаряда](../packs/base/equipment/arcana/scroll_fire_bolt.json) | `flammable`, `magic`, `paper` | — |
| [base:scroll_light: Свиток света](../packs/base/equipment/arcana/scroll_light.json) | `flammable`, `magic`, `paper` | — |
| [base:scroll_mending: Свиток починки](../packs/base/equipment/arcana/scroll_mending.json) | `flammable`, `magic`, `paper` | — |
| [base:writing_paper: Лист пергамента](../packs/base/equipment/arcana/writing_paper.json) | `flammable`, `paper` | — |
| [base:bedroll: Спальный мешок](../packs/base/equipment/bedroll.json) | `camping`, `cloth`, `flammable`, `rest_spot` | — |
| [base:candle: Свеча](../packs/base/equipment/candle.json) | `flammable`, `ignite`, `light_source` | `поджог` |
| [base:chest_key: Ключ от сундука](../packs/base/equipment/chest_key.json) | `key`, `metal` | `chest_key` |
| [base:cooking_pot: Походный котелок](../packs/base/equipment/cooking_pot.json) | `heat_safe`, `iron`, `metal`, `vessel` | — |
| [base:acid_reagent: Кислотный реагент](../packs/base/equipment/crafting/acid_reagent.json) | `acid` | — |
| [base:alchemist_tools: Алхимические принадлежности](../packs/base/equipment/crafting/alchemist_tools.json) | `alchemist_tools`, `tool` | — |
| [base:alchemy_reagent: Алхимический реагент](../packs/base/equipment/crafting/alchemy_reagent.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:bandage: Бинт](../packs/base/equipment/crafting/bandage.json) | `cloth`, `flammable`, `healing` | `consumable` |
| [base:bitter_herb: Горькая трава](../packs/base/equipment/crafting/bitter_herb.json) | `flammable`, `organic`, `plants` | — |
| [base:brewer_tools: Принадлежности пивовара](../packs/base/equipment/crafting/brewer_tools.json) | `brewer_tools`, `tool` | — |
| [base:calligrapher_tools: Принадлежности каллиграфа](../packs/base/equipment/crafting/calligrapher_tools.json) | `calligrapher_tools`, `tool` | — |
| [base:carpenter_tools: Инструменты плотника](../packs/base/equipment/crafting/carpenter_tools.json) | `carpenter_tools`, `tool` | — |
| [base:cartographer_tools: Инструменты картографа](../packs/base/equipment/crafting/cartographer_tools.json) | `cartographer_tools`, `tool` | — |
| [base:clay: Глина](../packs/base/equipment/crafting/clay.json) | `clay` | — |
| [base:cloth: Тряпка](../packs/base/equipment/crafting/cloth.json) | `cloth`, `flammable`, `organic` | — |
| [base:club: Простая дубинка](../packs/base/equipment/crafting/club.json) | `attack`, `damage`, `destructible`, `flammable`, `repairable`, `weapon`, `wooden` | — |
| [base:cobbler_tools: Инструменты сапожника](../packs/base/equipment/crafting/cobbler_tools.json) | `cobbler_tools`, `tool` | — |
| [base:cook_tools: Кухонные принадлежности](../packs/base/equipment/crafting/cook_tools.json) | `cook_tools`, `tool` | — |
| [base:craft_workpiece: Заготовка](../packs/base/equipment/crafting/craft_workpiece.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:furniture_hardware: Фурнитура](../packs/base/equipment/crafting/furniture_hardware.json) | `metal` | — |
| [base:glass_material: Стекольное сырьё](../packs/base/equipment/crafting/glass_material.json) | `glass` | — |
| [base:glassblower_tools: Инструменты стеклодува](../packs/base/equipment/crafting/glassblower_tools.json) | `glassblower_tools`, `tool` | — |
| [base:herbalism_kit: Набор травника](../packs/base/equipment/crafting/herbalism_kit.json) | `herbalism_kit`, `tool` | — |
| [base:improvised_rope: Импровизированная верёвка](../packs/base/equipment/crafting/improvised_rope.json) | `fiber`, `flammable`, `rope` | — |
| [base:jeweler_tools: Инструменты ювелира](../packs/base/equipment/crafting/jeweler_tools.json) | `jeweler_tools`, `tool` | — |
| [base:leatherworker_tools: Инструменты кожевника](../packs/base/equipment/crafting/leatherworker_tools.json) | `leatherworker_tools`, `tool` | — |
| [base:mason_tools: Инструменты каменщика](../packs/base/equipment/crafting/mason_tools.json) | `mason_tools`, `tool` | — |
| [base:mechanical_part: Механическая деталь](../packs/base/equipment/crafting/mechanical_part.json) | `metal` | — |
| [base:medicinal_herb: Лекарственная трава](../packs/base/equipment/crafting/medicinal_herb.json) | `flammable`, `medicinal`, `organic`, `plants` | — |
| [base:metal: Металл](../packs/base/equipment/crafting/metal.json) | `metal` | — |
| [base:mushroom: Грибы](../packs/base/equipment/crafting/mushroom.json) | `edible`, `flammable`, `food`, `fungi`, `organic` | — |
| [base:packed_furniture: Мебель](../packs/base/equipment/crafting/packed_furniture.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:painter_tools: Принадлежности художника](../packs/base/equipment/crafting/painter_tools.json) | `painter_tools`, `tool` | — |
| [base:plant_fiber: Растительное волокно](../packs/base/equipment/crafting/plant_fiber.json) | `fiber`, `flammable`, `organic`, `plants` | — |
| [base:poison_herb: Ядовитая трава](../packs/base/equipment/crafting/poison_herb.json) | `flammable`, `organic`, `plants`, `poison` | — |
| [base:poisoner_kit: Набор отравителя](../packs/base/equipment/crafting/poisoner_kit.json) | `poisoner_kit`, `tool` | — |
| [base:potter_tools: Инструменты гончара](../packs/base/equipment/crafting/potter_tools.json) | `potter_tools`, `tool` | — |
| [base:raw_leather: Кожа](../packs/base/equipment/crafting/raw_leather.json) | `flammable`, `leather`, `organic` | — |
| [base:smith_tools: Инструменты кузнеца](../packs/base/equipment/crafting/smith_tools.json) | `smith_tools`, `tool` | — |
| [base:stake: Кол](../packs/base/equipment/crafting/stake.json) | `attack`, `damage`, `destructible`, `door_brace`, `flammable`, `piercing`, `repairable`, `stake`, `weapon`, `wooden` | — |
| [base:stone: Камень](../packs/base/equipment/crafting/stone.json) | `stone` | — |
| [base:tinder: Растопка](../packs/base/equipment/crafting/tinder.json) | `fiber`, `flammable`, `fuel`, `organic`, `tinder` | — |
| [base:tinker_tools: Инструменты жестянщика](../packs/base/equipment/crafting/tinker_tools.json) | `tinker_tools`, `tool` | — |
| [base:weaver_tools: Инструменты ткача](../packs/base/equipment/crafting/weaver_tools.json) | `tool`, `weaver_tools` | — |
| [base:wood: Древесина](../packs/base/equipment/crafting/wood.json) | `flammable`, `fuel`, `wooden` | — |
| [base:woodcarver_tools: Инструменты резчика](../packs/base/equipment/crafting/woodcarver_tools.json) | `tool`, `woodcarver_tools` | — |
| [base:crowbar: Ломик](../packs/base/equipment/crowbar.json) | `lever`, `metal`, `tool` | — |
| [base:dagger: Кинжал](../packs/base/equipment/dagger.json) | `attack`, `blade`, `damage`, `destructible`, `metal`, `piercing`, `repairable`, `weapon` | `transparent`, `weapon_decor` |
| [base:dried_herbs: Сухие травы](../packs/base/equipment/dried_herbs.json) | `flammable`, `medicinal`, `organic`, `plants` | — |
| [base:animal_bone: Кость животного](../packs/base/equipment/expansion/animal_bone.json) | `bone`, `organic` | — |
| [base:battering_ram: Переносной таран](../packs/base/equipment/expansion/battering_ram.json) | `attack`, `battering_ram`, `damage`, `destructible`, `flammable`, `repairable`, `weapon`, `wooden` | — |
| [base:carved_staff: Резной посох](../packs/base/equipment/expansion/carved_staff.json) | `attack`, `damage`, `destructible`, `flammable`, `repairable`, `weapon`, `wooden` | — |
| [base:chitin: Хитин](../packs/base/equipment/expansion/chitin.json) | `organic` | — |
| [base:clay_pot: Глиняный сосуд](../packs/base/equipment/expansion/clay_pot.json) | `ceramic`, `fragile`, `heat_safe`, `vessel` | — |
| [base:cooked_meat: Приготовленное мясо](../packs/base/equipment/expansion/cooked_meat.json) | `food`, `healing`, `organic` | `consumable` |
| [base:glass_flask: Стеклянный флакон](../packs/base/equipment/expansion/glass_flask.json) | `fragile`, `glass`, `vessel` | — |
| [base:herbal_extract: Травяной экстракт](../packs/base/equipment/expansion/herbal_extract.json) | `organic` | `reagent` |
| [base:improvised_lockpicks: Простые отмычки](../packs/base/equipment/expansion/improvised_lockpicks.json) | `destructible`, `lockpicks`, `metal`, `repairable`, `tool` | — |
| [base:leather_boots: Кожаные сапоги](../packs/base/equipment/expansion/leather_boots.json) | `destructible`, `flammable`, `leather`, `repairable` | — |
| [base:leather_strip: Кожаная лента](../packs/base/equipment/expansion/leather_strip.json) | `flammable`, `leather`, `organic` | — |
| [base:metal_shield: Металлический щит](../packs/base/equipment/expansion/metal_shield.json) | `armor`, `destructible`, `metal`, `protection`, `repairable` | — |
| [base:poison_gland: Ядовитая железа](../packs/base/equipment/expansion/poison_gland.json) | `organic`, `poison` | `reagent` |
| [base:raw_meat: Сырое мясо](../packs/base/equipment/expansion/raw_meat.json) | `food`, `organic` | — |
| [base:simple_poison: Простой яд](../packs/base/equipment/expansion/simple_poison.json) | `poison` | `reagent` |
| [base:spider_silk: Паутина](../packs/base/equipment/expansion/spider_silk.json) | `fiber`, `flammable`, `organic` | — |
| [base:stone_block: Каменный блок](../packs/base/equipment/expansion/stone_block.json) | `stone` | — |
| [base:stone_wedge: Каменный клин](../packs/base/equipment/expansion/stone_wedge.json) | `door_brace`, `stone` | — |
| [base:trap_kit: Импровизированная ловушка (набор)](../packs/base/equipment/expansion/trap_kit.json) | `metal`, `tool`, `trap` | — |
| [base:uncut_gem: Необработанный самоцвет](../packs/base/equipment/expansion/uncut_gem.json) | `stone` | — |
| [base:wooden_pole: Деревянный шест](../packs/base/equipment/expansion/wooden_pole.json) | `attack`, `damage`, `destructible`, `flammable`, `pole`, `repairable`, `weapon`, `wooden` | — |
| [base:wooden_shield: Деревянный щит](../packs/base/equipment/expansion/wooden_shield.json) | `armor`, `destructible`, `flammable`, `protection`, `repairable`, `wooden` | — |
| [base:flint_and_steel: Кремень и кресало](../packs/base/equipment/flint_and_steel.json) | `ignite`, `metal`, `tool` | `поджог` |
| [base:gold: Золотая монета](../packs/base/equipment/gold.json) | `gold`, `metal` | — |
| [base:healing_potion: Зелье лечения](../packs/base/equipment/healing_potion.json) | `fragile`, `glass`, `healing`, `liquid`, `potion`, `vessel` | `artifacts`, `consumable`, `supplies_decor`, `transparent` |
| [base:healing_poultice: Лечебная припарка](../packs/base/equipment/healing_poultice.json) | `healing`, `medicinal`, `organic` | — |
| [base:ink: Чернила и перо](../packs/base/equipment/ink.json) | `flammable`, `liquid`, `writing` | — |
| [base:lamp: Масляная лампа](../packs/base/equipment/lamp.json) | `light_source`, `metal` | — |
| [base:leather: Кожаный доспех](../packs/base/equipment/leather.json) | `armor`, `destructible`, `flammable`, `leather`, `organic`, `protection`, `repairable` | — |
| [base:mail: Кольчуга](../packs/base/equipment/mail.json) | `armor`, `destructible`, `iron`, `metal`, `protection`, `repairable` | — |
| [base:master_lockpicks: Мастерские отмычки](../packs/base/equipment/master_lockpicks.json) | `destructible`, `lockpicks`, `repairable`, `tool` | — |
| [base:oil: Масло](../packs/base/equipment/oil.json) | `flammable`, `fuel`, `lamp_oil`, `liquid`, `oil` | `consumable`, `supplies_decor`, `throwable`, `transparent` |
| [base:parchment: Пергамент](../packs/base/equipment/parchment.json) | `flammable`, `paper` | — |
| [base:pickaxe: Кирка](../packs/base/equipment/pickaxe.json) | `attack`, `damage`, `flammable`, `metal`, `pickaxe`, `piercing`, `tool`, `weapon`, `wooden` | — |
| [base:rations: Дорожный паёк](../packs/base/equipment/rations.json) | `edible`, `flammable`, `food`, `organic` | `supplies_decor`, `transparent` |
| [base:robe: Мантия](../packs/base/equipment/robe.json) | `cloth`, `clothing`, `flammable` | — |
| [base:rope: Верёвка](../packs/base/equipment/rope.json) | `fiber`, `flammable`, `rope` | — |
| [base:shield: Щит](../packs/base/equipment/shield.json) | `destructible`, `flammable`, `protection`, `repairable`, `shield`, `wooden` | `armor_decor`, `transparent` |
| [base:spellbook: Книга заклинаний](../packs/base/equipment/spellbook.json) | `arcane`, `book`, `flammable`, `paper` | — |
| [base:staff: Посох](../packs/base/equipment/staff.json) | `attack`, `bludgeoning`, `damage`, `destructible`, `flammable`, `focus`, `repairable`, `weapon`, `wooden` | `transparent`, `weapon_decor` |
| [base:sword: Меч](../packs/base/equipment/sword.json) | `attack`, `blade`, `damage`, `destructible`, `metal`, `repairable`, `slashing`, `weapon` | `transparent`, `weapon_decor` |
| [base:terrain_artifact: Магический предмет](../packs/base/equipment/terrain/terrain_artifact.json) | `magic` | `artifact`, `artifacts`, `transparent` |
| [base:terrain_artifact_amulet: Магический амулет](../packs/base/equipment/terrain/terrain_artifact_amulet.json) | `magic` | `artifact_amulet`, `artifacts`, `transparent` |
| [base:terrain_artifact_legendary: Легендарный предмет](../packs/base/equipment/terrain/terrain_artifact_legendary.json) | `magic` | `artifact_legendary`, `artifacts`, `transparent` |
| [base:terrain_artifact_powerful: Сильный магический предмет](../packs/base/equipment/terrain/terrain_artifact_powerful.json) | `magic` | `artifact_powerful`, `artifacts`, `transparent` |
| [base:terrain_artifact_ring: Магическое кольцо](../packs/base/equipment/terrain/terrain_artifact_ring.json) | `magic` | `artifact_ring`, `artifacts`, `transparent` |
| [base:terrain_artifact_ring_enchanted: Зачарованное кольцо](../packs/base/equipment/terrain/terrain_artifact_ring_enchanted.json) | `magic` | `artifact_ring_enchanted`, `artifacts`, `transparent` |
| [base:terrain_artifact_stone: Магический камень](../packs/base/equipment/terrain/terrain_artifact_stone.json) | `magic` | `artifact_stone`, `artifacts`, `transparent` |
| [base:terrain_artifact_unidentified: Неопознанный магический предмет](../packs/base/equipment/terrain/terrain_artifact_unidentified.json) | `magic` | `artifact_unidentified`, `artifacts`, `transparent` |
| [base:terrain_artifact_unknown: Неизвестный артефакт](../packs/base/equipment/terrain/terrain_artifact_unknown.json) | `magic` | `artifact_unknown`, `artifacts`, `transparent` |
| [base:terrain_artifact_weak: Слабый магический предмет](../packs/base/equipment/terrain/terrain_artifact_weak.json) | `magic` | `artifact_weak`, `artifacts`, `transparent` |
| [base:terrain_decor_armor: Броня](../packs/base/equipment/terrain/terrain_decor_armor.json) | `armor`, `protection` | `armor_decor`, `decor_armor`, `transparent` |
| [base:terrain_decor_armor_heavy: Тяжёлая броня](../packs/base/equipment/terrain/terrain_decor_armor_heavy.json) | `armor`, `metal`, `protection` | `armor_decor`, `decor_armor_heavy`, `transparent` |
| [base:terrain_decor_armor_light: Лёгкая броня](../packs/base/equipment/terrain/terrain_decor_armor_light.json) | `armor`, `flammable`, `leather`, `protection` | `armor_decor`, `decor_armor_light`, `transparent` |
| [base:terrain_decor_arrow: Стрела](../packs/base/equipment/terrain/terrain_decor_arrow.json) | `ammunition`, `flammable`, `metal`, `wooden` | `decor_arrow`, `transparent`, `weapon_decor` |
| [base:terrain_decor_axe: Топор](../packs/base/equipment/terrain/terrain_decor_axe.json) | `attack`, `damage`, `destructible`, `flammable`, `metal`, `repairable`, `slashing`, `weapon`, `wooden` | `decor_axe`, `transparent`, `weapon_decor` |
| [base:terrain_decor_bolt: Болт](../packs/base/equipment/terrain/terrain_decor_bolt.json) | `ammunition`, `flammable`, `metal`, `wooden` | `decor_bolt`, `transparent`, `weapon_decor` |
| [base:terrain_decor_boots: Сапоги](../packs/base/equipment/terrain/terrain_decor_boots.json) | `clothing`, `flammable`, `leather` | `armor_decor`, `decor_boots`, `transparent` |
| [base:terrain_decor_bottle: Бутылка](../packs/base/equipment/terrain/terrain_decor_bottle.json) | `glass` | `decor_bottle`, `supplies_decor`, `transparent` |
| [base:terrain_decor_bow: Лук](../packs/base/equipment/terrain/terrain_decor_bow.json) | `attack`, `damage`, `destructible`, `flammable`, `piercing`, `repairable`, `weapon`, `wooden` | `decor_bow`, `transparent`, `weapon_decor` |
| [base:terrain_decor_cloak: Плащ](../packs/base/equipment/terrain/terrain_decor_cloak.json) | `cloth`, `clothing`, `flammable` | `armor_decor`, `decor_cloak`, `transparent` |
| [base:terrain_decor_gloves: Перчатки](../packs/base/equipment/terrain/terrain_decor_gloves.json) | `cloth`, `clothing`, `flammable` | `armor_decor`, `decor_gloves`, `transparent` |
| [base:terrain_decor_greataxe: Двуручный топор](../packs/base/equipment/terrain/terrain_decor_greataxe.json) | `attack`, `damage`, `destructible`, `flammable`, `metal`, `repairable`, `slashing`, `weapon`, `wooden` | `decor_greataxe`, `transparent`, `weapon_decor` |
| [base:terrain_decor_greatsword: Большой меч](../packs/base/equipment/terrain/terrain_decor_greatsword.json) | `attack`, `damage`, `destructible`, `metal`, `repairable`, `slashing`, `weapon` | `decor_greatsword`, `transparent`, `weapon_decor` |
| [base:terrain_decor_halberd: Алебарда](../packs/base/equipment/terrain/terrain_decor_halberd.json) | `attack`, `damage`, `destructible`, `flammable`, `metal`, `repairable`, `slashing`, `weapon`, `wooden` | `decor_halberd`, `transparent`, `weapon_decor` |
| [base:terrain_decor_hammer: Молот](../packs/base/equipment/terrain/terrain_decor_hammer.json) | `attack`, `bludgeoning`, `damage`, `destructible`, `flammable`, `metal`, `repairable`, `weapon`, `wooden` | `decor_hammer`, `transparent`, `weapon_decor` |
| [base:terrain_decor_helmet: Шлем](../packs/base/equipment/terrain/terrain_decor_helmet.json) | `metal` | `armor_decor`, `decor_helmet`, `transparent` |
| [base:terrain_decor_longbow: Длинный лук](../packs/base/equipment/terrain/terrain_decor_longbow.json) | `attack`, `damage`, `destructible`, `flammable`, `piercing`, `repairable`, `weapon`, `wooden` | `decor_longbow`, `transparent`, `weapon_decor` |
| [base:terrain_decor_mace: Булава](../packs/base/equipment/terrain/terrain_decor_mace.json) | `attack`, `bludgeoning`, `damage`, `destructible`, `flammable`, `metal`, `repairable`, `weapon`, `wooden` | `decor_mace`, `transparent`, `weapon_decor` |
| [base:terrain_decor_potion_unknown: Неизвестное зелье](../packs/base/equipment/terrain/terrain_decor_potion_unknown.json) | `glass` | `decor_potion_unknown`, `supplies_decor`, `transparent` |
| [base:terrain_decor_rapier: Рапира](../packs/base/equipment/terrain/terrain_decor_rapier.json) | `attack`, `damage`, `destructible`, `metal`, `piercing`, `repairable`, `weapon` | `decor_rapier`, `transparent`, `weapon_decor` |
| [base:terrain_decor_sickle: Серп](../packs/base/equipment/terrain/terrain_decor_sickle.json) | `attack`, `damage`, `destructible`, `flammable`, `metal`, `repairable`, `slashing`, `weapon`, `wooden` | `decor_sickle`, `transparent`, `weapon_decor` |
| [base:terrain_decor_spear: Копьё](../packs/base/equipment/terrain/terrain_decor_spear.json) | `attack`, `damage`, `destructible`, `flammable`, `metal`, `piercing`, `repairable`, `weapon`, `wooden` | `decor_spear`, `transparent`, `weapon_decor` |
| [base:terrain_key_ancient: Древний ключ](../packs/base/equipment/terrain/terrain_key_ancient.json) | `key`, `metal` | `key_ancient`, `keys`, `transparent` |
| [base:terrain_key_decor: Ключ](../packs/base/equipment/terrain/terrain_key_decor.json) | `key`, `metal` | `key_decor`, `keys`, `transparent` |
| [base:terrain_key_important: Важный ключ](../packs/base/equipment/terrain/terrain_key_important.json) | `key`, `metal` | `key_important`, `keys`, `transparent` |
| [base:terrain_key_special: Особый ключ](../packs/base/equipment/terrain/terrain_key_special.json) | `key`, `metal` | `key_special`, `keys`, `transparent` |
| [base:thieves_tools: Воровские инструменты](../packs/base/equipment/thieves_tools.json) | `destructible`, `lockpicks`, `repairable`, `tool` | — |
| [base:torch: Факел](../packs/base/equipment/torch.json) | `flammable`, `ignite`, `light_source`, `wooden` | `поджог` |
| [base:water_flask: Флакон](../packs/base/equipment/water_flask.json) | `fragile`, `glass`, `vessel` | — |
| [base:waterskin: Бурдюк](../packs/base/equipment/waterskin.json) | `flammable`, `leather`, `organic`, `vessel` | — |

### base:dragon_leather — Доспех из драконьей кожи

- `properties[0]` / `armor_class` → `protection`

### base:mithril_shield — Мифриловый щит

- `properties[0]` / `armor_bonus` → `protection`

### base:rune_leather — Рунный кожаный доспех

- `properties[0]` / `armor_class` → `protection`
- `properties[1]` / `armor_bonus` → `protection`

### base:bandage — Бинт

- `properties[0]` / `heal` → `healing`

### base:cooked_meat — Приготовленное мясо

- `properties[0]` / `heal` → `healing`

### base:metal_shield — Металлический щит

- `properties[0]` / `armor_bonus` → `protection`

### base:wooden_shield — Деревянный щит

- `properties[0]` / `armor_bonus` → `protection`

### base:healing_potion — Зелье лечения

- `properties[0]` / `heal` → `healing`

### base:healing_poultice — Лечебная припарка

- `properties[0]` / `heal` → `healing`

### base:leather — Кожаный доспех

- `properties[0]` / `armor_class` → `protection`

### base:mail — Кольчуга

- `properties[0]` / `armor_class` → `protection`

### base:shield — Щит

- `properties[0]` / `armor_bonus` → `protection`

### base:terrain_decor_armor — Броня

- `properties[0]` / `armor_class` → `protection`

### base:terrain_decor_armor_heavy — Тяжёлая броня

- `properties[0]` / `armor_class` → `protection`

### base:terrain_decor_armor_light — Лёгкая броня

- `properties[0]` / `armor_class` → `protection`

## spells

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:acid_splash: Кислотная сфера](../packs/base/spells/acid_splash.json) | `acid`, `aoe`, `damage`, `magic` | — |
| [base:blade_ward: Защитный клинок](../packs/base/spells/blade_ward.json) | `magic` | — |
| [base:chill_touch: Холодное прикосновение](../packs/base/spells/chill_touch.json) | `damage`, `magic`, `necrotic` | — |
| [base:dancing_lights: Пляшущие огоньки](../packs/base/spells/dancing_lights.json) | `light_source`, `magic` | `light` |
| [base:daylight: Дневной свет](../packs/base/spells/daylight.json) | `magic` | — |
| [base:detect_magic: Обнаружение магии](../packs/base/spells/detect_magic.json) | `condition`, `detect_magic`, `magic` | — |
| [base:elementalism: Элементализм](../packs/base/spells/elementalism.json) | `ignite`, `magic`, `utility` | — |
| [base:fire_bolt: Огненный снаряд](../packs/base/spells/fire_bolt.json) | `damage`, `fire`, `ignite`, `magic` | — |
| [base:light: Свет](../packs/base/spells/light.json) | `light_source`, `magic` | `light` |
| [base:mage_hand: Волшебная рука](../packs/base/spells/mage_hand.json) | `interaction`, `magic` | — |
| [base:magic_missile: Волшебная стрела](../packs/base/spells/magic_missile.json) | `damage`, `force`, `magic` | — |
| [base:mending: Починка](../packs/base/spells/mending.json) | `magic`, `repair` | — |
| [base:minor_illusion: Малая иллюзия](../packs/base/spells/minor_illusion.json) | `illusion`, `magic` | — |
| [base:poison_spray: Ядовитые брызги](../packs/base/spells/poison_spray.json) | `damage`, `magic`, `poison` | — |
| [base:prestidigitation: Фокусы](../packs/base/spells/prestidigitation.json) | `ignite`, `magic`, `utility` | — |
| [base:ray_of_frost: Луч холода](../packs/base/spells/ray_of_frost.json) | `cold`, `damage`, `magic` | `cool` |
| [base:shocking_grasp: Электрическое касание](../packs/base/spells/shocking_grasp.json) | `damage`, `lightning`, `magic` | — |
| [base:thunderclap: Раскат грома](../packs/base/spells/thunderclap.json) | `aoe`, `damage`, `magic`, `noise`, `thunder` | — |
| [base:toll_the_dead: Погребальный звон](../packs/base/spells/toll_the_dead.json) | `damage`, `magic`, `necrotic` | — |
| [base:true_strike: Истинный удар](../packs/base/spells/true_strike.json) | `magic` | — |

### base:acid_splash — Кислотная сфера

- `effects[0]` / `damage` → `acid`, `damage`

### base:chill_touch — Холодное прикосновение

- `effects[0]` / `damage` → `damage`, `necrotic`

### base:detect_magic — Обнаружение магии

- `effects[0]` / `condition` → `condition`, `detect_magic`

### base:fire_bolt — Огненный снаряд

- `effects[0]` / `damage` → `damage`, `fire`

### base:magic_missile — Волшебная стрела

- `effects[0]` / `damage` → `damage`, `force`

### base:poison_spray — Ядовитые брызги

- `effects[0]` / `damage` → `damage`, `poison`

### base:ray_of_frost — Луч холода

- `effects[0]` / `damage` → `cold`, `damage`

### base:shocking_grasp — Электрическое касание

- `effects[0]` / `damage` → `damage`, `lightning`

### base:thunderclap — Раскат грома

- `effects[0]` / `damage` → `damage`, `thunder`

### base:toll_the_dead — Погребальный звон

- `effects[0]` / `damage` → `damage`, `necrotic`

## actions

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:attack: Атака](../packs/base/actions/attack.json) | `attack` | — |
| [base:dodge: Уклонение](../packs/base/actions/dodge.json) | `dodge` | — |
| [base:influence: Влияние](../packs/base/actions/influence.json) | `applies_persuasion`, `condition`, `influence` | — |
| [base:magic: Магия](../packs/base/actions/magic.json) | `magic` | — |
| [base:stealth: Скрытность](../packs/base/actions/stealth.json) | `stealth` | — |

### base:influence — Влияние

- `effects[0]` / `condition` → `applies_persuasion`, `condition`

## monsters

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:goblin: Гоблин](../packs/base/monsters/goblin.json) | `humanoid`, `living`, `organic` | `goblin` |
| [base:skeleton: Скелет](../packs/base/monsters/skeleton.json) | `bone`, `undead` | — |

### base:goblin — Гоблин

- `special_actions[0].effects[0]` / `condition` → `applies_poison`, `condition`, `poison`
- Особое действие `dirty_strike` (Подлый удар) → `applies_poison`, `attack`, `condition`, `damage`, `piercing`, `poison`
- `actions`: `base:attack`, `base:dodge`, `base:stealth`, `base:magic`, `base:influence`

### base:skeleton — Скелет

- Особое действие `bone_strike` (Костяной удар) → `attack`, `bludgeoning`, `damage`
- `actions`: `base:attack`, `base:dodge`, `base:stealth`, `base:magic`, `base:influence`

## tiles

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:blood_drops: Капли крови](../packs/base/tiles/blood/blood_drops.json) | `blood` | `transparent`, `walkable` |
| [base:blood_fresh: Свежие брызги](../packs/base/tiles/blood/blood_fresh.json) | `blood` | `transparent`, `walkable` |
| [base:blood_pool: Лужа крови](../packs/base/tiles/blood/blood_pool.json) | `blood`, `liquid` | `transparent`, `walkable` |
| [base:blood_pool_large: Большая лужа крови](../packs/base/tiles/blood/blood_pool_large.json) | `blood`, `liquid` | `transparent`, `walkable` |
| [base:blood_splashes: Брызги крови](../packs/base/tiles/blood/blood_splashes.json) | `blood` | `transparent`, `walkable` |
| [base:blood_tracks: Следы крови](../packs/base/tiles/blood/blood_tracks.json) | `blood` | `transparent`, `walkable` |
| [base:cave_wall: Стена пещены](../packs/base/tiles/cave_wall.json) | `stone` | — |
| [base:boulder: Валун](../packs/base/tiles/earth/boulder.json) | `stone` | `earth`, `obstacle`, `opaque` |
| [base:boulder_large: Крупный валун](../packs/base/tiles/earth/boulder_large.json) | `stone` | `earth`, `obstacle`, `opaque` |
| [base:cliff: Большая скала](../packs/base/tiles/earth/cliff.json) | `stone` | `earth`, `obstacle`, `opaque` |
| [base:earth: Земля](../packs/base/tiles/earth/earth.json) | `soil` | `earth`, `transparent`, `walkable` |
| [base:earth_gravel: Гравийная почва](../packs/base/tiles/earth/earth_gravel.json) | `soil` | `earth`, `transparent`, `walkable` |
| [base:earth_loose: Рыхлая земля](../packs/base/tiles/earth/earth_loose.json) | `soil` | `earth`, `transparent`, `walkable` |
| [base:earth_packed: Утоптанная земля](../packs/base/tiles/earth/earth_packed.json) | `soil` | `earth`, `transparent`, `walkable` |
| [base:mud: Грязь](../packs/base/tiles/earth/mud.json) | `soil` | `earth`, `mud`, `transparent`, `walkable` |
| [base:mud_deep: Вязкая грязь](../packs/base/tiles/earth/mud_deep.json) | `soil` | `earth`, `transparent`, `walkable` |
| [base:soil: Земля](../packs/base/tiles/earth/soil.json) | `soil` | — |
| [base:stone_dark: Тёмный камень](../packs/base/tiles/earth/stone_dark.json) | `stone` | `earth`, `obstacle`, `opaque` |
| [base:stone_pale: Светлый камень](../packs/base/tiles/earth/stone_pale.json) | `stone` | `earth`, `obstacle`, `opaque` |
| [base:stone_small: Небольшой камень](../packs/base/tiles/earth/stone_small.json) | `stone` | `earth`, `transparent`, `walkable` |
| [base:swamp: Болото](../packs/base/tiles/earth/swamp.json) | `soil` | `earth`, `transparent`, `walkable` |
| [base:fence_planks: Деревянный забор](../packs/base/tiles/fences/fence_planks.json) | `flammable`, `wooden` | `fences`, `obstacle`, `transparent` |
| [base:fence_wooden: Деревянная ограда](../packs/base/tiles/fences/fence_wooden.json) | `flammable`, `wooden` | `fences`, `obstacle`, `transparent` |
| [base:gate_grated: Решётчатая дверь](../packs/base/tiles/fences/gate_grated.json) | `metal` | `fences`, `obstacle`, `transparent` |
| [base:grate_dense: Плотная решётка](../packs/base/tiles/fences/grate_dense.json) | `metal` | `fences`, `obstacle`, `transparent` |
| [base:grate_horizontal: Горизонтальная решётка](../packs/base/tiles/fences/grate_horizontal.json) | `metal` | `fences`, `obstacle`, `transparent` |
| [base:grate_iron: Железная решётка](../packs/base/tiles/fences/grate_iron.json) | `iron`, `metal` | `fences`, `obstacle`, `transparent` |
| [base:grate_partition: Железная перегородка](../packs/base/tiles/fences/grate_partition.json) | `iron`, `metal` | `fences`, `obstacle`, `transparent` |
| [base:grate_vertical: Вертикальная решётка](../packs/base/tiles/fences/grate_vertical.json) | `metal` | `fences`, `obstacle`, `transparent` |
| [base:metal_bar: Одиночный металлический прут](../packs/base/tiles/fences/metal_bar.json) | `iron`, `metal` | `fences`, `obstacle`, `transparent` |
| [base:floor: Каменный пол](../packs/base/tiles/floor.json) | `stone` | — |
| [base:floor_boardwalk: Настил](../packs/base/tiles/floors/floor_boardwalk.json) | `flammable`, `wooden` | `floors`, `transparent`, `walkable` |
| [base:floor_dark: Тёмный каменный пол](../packs/base/tiles/floors/floor_dark.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_diagonal_tiles: Диагональная плитка](../packs/base/tiles/floors/floor_diagonal_tiles.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_dirty: Грязный пол](../packs/base/tiles/floors/floor_dirty.json) | `soil` | `floors`, `transparent`, `walkable` |
| [base:floor_dusty: Пыльный пол](../packs/base/tiles/floors/floor_dusty.json) | Нет физических признаков; см. поля/ссылки ниже | `floors`, `transparent`, `walkable` |
| [base:floor_gravel: Гравийный пол](../packs/base/tiles/floors/floor_gravel.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_litter: Мелкий мусор на полу](../packs/base/tiles/floors/floor_litter.json) | `flammable` | `floors`, `transparent`, `walkable` |
| [base:floor_mosaic: Мозаичный пол](../packs/base/tiles/floors/floor_mosaic.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_ornate_tiles: Узорная плитка](../packs/base/tiles/floors/floor_ornate_tiles.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_pavers: Плиточный пол](../packs/base/tiles/floors/floor_pavers.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_pebbles: Мелкие камни](../packs/base/tiles/floors/floor_pebbles.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_planks: Деревянные доски](../packs/base/tiles/floors/floor_planks.json) | `flammable`, `wooden` | `floors`, `transparent`, `walkable` |
| [base:floor_polished: Гладкая поверхность](../packs/base/tiles/floors/floor_polished.json) | Нет физических признаков; см. поля/ссылки ниже | `floors`, `transparent`, `walkable` |
| [base:floor_rough: Грубый каменный пол](../packs/base/tiles/floors/floor_rough.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_sand: Песок](../packs/base/tiles/floors/floor_sand.json) | `sand` | `floors`, `transparent`, `walkable` |
| [base:floor_slab: Напольная плита](../packs/base/tiles/floors/floor_slab.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_smooth: Гладкий каменный пол](../packs/base/tiles/floors/floor_smooth.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_striped_tiles: Полосатые плиты](../packs/base/tiles/floors/floor_striped_tiles.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_tiles: Каменная плитка](../packs/base/tiles/floors/floor_tiles.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:floor_uneven_planks: Неровный настил](../packs/base/tiles/floors/floor_uneven_planks.json) | `flammable`, `wooden` | `floors`, `transparent`, `walkable` |
| [base:floor_worn_tiles: Грубая плитка](../packs/base/tiles/floors/floor_worn_tiles.json) | `stone` | `floors`, `transparent`, `walkable` |
| [base:mushroom: Гриб](../packs/base/tiles/fungi/mushroom.json) | `flammable`, `fungi`, `organic` | `transparent`, `walkable` |
| [base:mushroom_cap: Грибная шляпка](../packs/base/tiles/fungi/mushroom_cap.json) | `flammable`, `fungi`, `organic` | `obstacle`, `transparent` |
| [base:mushroom_large: Большой гриб](../packs/base/tiles/fungi/mushroom_large.json) | `flammable`, `fungi`, `organic` | `obstacle`, `opaque` |
| [base:mushroom_small: Маленький гриб](../packs/base/tiles/fungi/mushroom_small.json) | `flammable`, `fungi`, `organic` | `transparent`, `walkable` |
| [base:mushroom_thin: Тонкий гриб](../packs/base/tiles/fungi/mushroom_thin.json) | `flammable`, `fungi`, `organic` | `transparent`, `walkable` |
| [base:dust_cloud: Облако пыли](../packs/base/tiles/gas/dust_cloud.json) | `gas` | `transparent`, `walkable` |
| [base:fog: Туман](../packs/base/tiles/gas/fog.json) | `gas` | `transparent`, `walkable` |
| [base:fog_dense: Густой туман](../packs/base/tiles/gas/fog_dense.json) | `gas` | `opaque`, `walkable` |
| [base:smoke: Дым](../packs/base/tiles/gas/smoke.json) | `gas` | `opaque`, `walkable` |
| [base:smoke_dense: Густой дым](../packs/base/tiles/gas/smoke_dense.json) | `gas` | `opaque`, `walkable` |
| [base:ascent: Подъём](../packs/base/tiles/height/ascent.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:chasm_bottomless: Бездонная пропасть](../packs/base/tiles/height/chasm_bottomless.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `obstacle`, `transparent` |
| [base:chasm_deep: Глубокая пропасть](../packs/base/tiles/height/chasm_deep.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `obstacle`, `transparent` |
| [base:depression: Углубление](../packs/base/tiles/height/depression.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:descent: Спуск](../packs/base/tiles/height/descent.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:fissure: Глубокая расщелина](../packs/base/tiles/height/fissure.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `obstacle`, `transparent` |
| [base:height_stairs_down: Ступени вниз (рельеф)](../packs/base/tiles/height/height_stairs_down.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:height_stairs_up: Ступени вверх (рельеф)](../packs/base/tiles/height/height_stairs_up.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:pit_dangerous: Опасная яма](../packs/base/tiles/height/pit_dangerous.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `obstacle`, `transparent` |
| [base:pit_debris: Яма с чем-то внутри](../packs/base/tiles/height/pit_debris.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `obstacle`, `transparent` |
| [base:pit_deep: Глубокая яма](../packs/base/tiles/height/pit_deep.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `obstacle`, `transparent` |
| [base:pit_large: Большая яма](../packs/base/tiles/height/pit_large.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `obstacle`, `transparent` |
| [base:pit_small: Небольшая яма](../packs/base/tiles/height/pit_small.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `obstacle`, `transparent` |
| [base:slope_down: Спуск вниз](../packs/base/tiles/height/slope_down.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:slope_left: Склон влево](../packs/base/tiles/height/slope_left.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:slope_right: Склон вправо](../packs/base/tiles/height/slope_right.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:slope_steep_down: Крутой спуск](../packs/base/tiles/height/slope_steep_down.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:slope_steep_up: Крутой подъём](../packs/base/tiles/height/slope_steep_up.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:slope_up: Подъём вверх](../packs/base/tiles/height/slope_up.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:steps_left: Ступени влево](../packs/base/tiles/height/steps_left.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:steps_right: Ступени вправо](../packs/base/tiles/height/steps_right.json) | Нет физических признаков; см. поля/ссылки ниже | `height`, `transparent`, `walkable` |
| [base:frost: Иней](../packs/base/tiles/ice/frost.json) | `ice` | `transparent`, `walkable` |
| [base:ice: Лёд](../packs/base/tiles/ice/ice.json) | `ice` | `transparent`, `walkable` |
| [base:ice_cracked: Потрескавшийся лёд](../packs/base/tiles/ice/ice_cracked.json) | `ice` | `transparent`, `walkable` |
| [base:ice_crystals: Ледяная область](../packs/base/tiles/ice/ice_crystals.json) | `ice` | `transparent`, `walkable` |
| [base:ice_thick: Толстый лёд](../packs/base/tiles/ice/ice_thick.json) | `ice` | `transparent`, `walkable` |
| [base:snow: Снег](../packs/base/tiles/ice/snow.json) | `ice` | `transparent`, `walkable` |
| [base:snow_deep: Глубокий снег](../packs/base/tiles/ice/snow_deep.json) | `ice` | `transparent`, `walkable` |
| [base:snow_packed: Плотный снег](../packs/base/tiles/ice/snow_packed.json) | `ice` | `transparent`, `walkable` |
| [base:lock: Замок](../packs/base/tiles/keys/lock.json) | `metal` | `keys`, `transparent`, `walkable` |
| [base:mechanism_locked: Запертый механизм](../packs/base/tiles/keys/mechanism_locked.json) | `metal` | `keys`, `transparent`, `walkable` |
| [base:magic_unstable: Нестабильная магия](../packs/base/tiles/magic/magic_unstable.json) | `magic` | `transparent`, `walkable` |
| [base:bush: Куст](../packs/base/tiles/plants/bush.json) | `flammable`, `organic`, `plants` | `transparent`, `walkable` |
| [base:bush_dry: Сухой куст](../packs/base/tiles/plants/bush_dry.json) | `flammable`, `organic`, `plants` | `transparent`, `walkable` |
| [base:flower_blooming: Цветущее растение](../packs/base/tiles/plants/flower_blooming.json) | `flammable`, `organic`, `plants` | `transparent`, `walkable` |
| [base:flowers: Цветы](../packs/base/tiles/plants/flowers.json) | `flammable`, `organic`, `plants` | `transparent`, `walkable` |
| [base:grass_dry: Сухая трава](../packs/base/tiles/plants/grass_dry.json) | `flammable`, `organic`, `plants` | `transparent`, `walkable` |
| [base:grass_short: Низкая трава](../packs/base/tiles/plants/grass_short.json) | `flammable`, `organic`, `plants` | `transparent`, `walkable` |
| [base:grass_tall: Высокая трава](../packs/base/tiles/plants/grass_tall.json) | `flammable`, `organic`, `plants` | `transparent`, `walkable` |
| [base:shrubs: Кустарник](../packs/base/tiles/plants/shrubs.json) | `flammable`, `organic`, `plants` | `transparent`, `walkable` |
| [base:vines: Лианы](../packs/base/tiles/plants/vines.json) | `flammable`, `organic`, `plants` | `transparent`, `walkable` |
| [base:vines_dense: Густые лианы](../packs/base/tiles/plants/vines_dense.json) | `flammable`, `organic`, `plants` | `obstacle`, `opaque` |
| [base:broken_objects: Сломанные предметы](../packs/base/tiles/ruins/broken_objects.json) | `flammable` | `ruins`, `transparent`, `walkable` |
| [base:litter: Мелкий мусор](../packs/base/tiles/ruins/litter.json) | `flammable` | `ruins`, `transparent`, `walkable` |
| [base:refuse: Груда мусора](../packs/base/tiles/ruins/refuse.json) | `flammable` | `ruins`, `transparent`, `walkable` |
| [base:rubble: Обломки](../packs/base/tiles/ruins/rubble.json) | `stone` | `ruins`, `transparent`, `walkable` |
| [base:rubble_blocked: Завал прохода](../packs/base/tiles/ruins/rubble_blocked.json) | `stone` | `obstacle`, `opaque`, `ruins` |
| [base:rubble_dust: Пыль и щебень](../packs/base/tiles/ruins/rubble_dust.json) | `stone` | `ruins`, `transparent`, `walkable` |
| [base:ruined_masonry: Разрушенная кладка](../packs/base/tiles/ruins/ruined_masonry.json) | `stone` | `obstacle`, `opaque`, `ruins` |
| [base:shards: Осколки](../packs/base/tiles/ruins/shards.json) | Нет физических признаков; см. поля/ссылки ниже | `ruins`, `transparent`, `walkable` |
| [base:stone_chips: Каменная крошка](../packs/base/tiles/ruins/stone_chips.json) | `stone` | `ruins`, `transparent`, `walkable` |
| [base:service_lock_complex: Сложный замок (индикатор)](../packs/base/tiles/service_lock_complex.json) | `lock_complex`, `lock_indicator` | — |
| [base:service_lock_simple: Простой замок (индикатор)](../packs/base/tiles/service_lock_simple.json) | `lock_indicator`, `lock_simple` | — |
| [base:statue: Статуя](../packs/base/tiles/statues/statue.json) | `stone` | `obstacle`, `opaque`, `statues` |
| [base:statue_beast: Статуя зверя](../packs/base/tiles/statues/statue_beast.json) | `stone` | `obstacle`, `opaque`, `statues` |
| [base:statue_dark: Тёмная статуя](../packs/base/tiles/statues/statue_dark.json) | `stone` | `obstacle`, `opaque`, `statues` |
| [base:statue_human: Статуя человека](../packs/base/tiles/statues/statue_human.json) | `stone` | `obstacle`, `opaque`, `statues` |
| [base:statue_massive: Массивная статуя](../packs/base/tiles/statues/statue_massive.json) | `stone` | `obstacle`, `opaque`, `statues` |
| [base:statue_small: Маленькая статуя](../packs/base/tiles/statues/statue_small.json) | `stone` | `obstacle`, `statues`, `transparent` |
| [base:tracks: Следы](../packs/base/tiles/tracks/tracks.json) | Нет физических признаков; см. поля/ссылки ниже | `tracks`, `transparent`, `walkable` |
| [base:tracks_east: Следы вправо](../packs/base/tiles/tracks/tracks_east.json) | Нет физических признаков; см. поля/ссылки ниже | `tracks`, `transparent`, `walkable` |
| [base:tracks_faint: Слабые следы](../packs/base/tiles/tracks/tracks_faint.json) | Нет физических признаков; см. поля/ссылки ниже | `tracks`, `transparent`, `walkable` |
| [base:tracks_muddy: Грязные следы](../packs/base/tiles/tracks/tracks_muddy.json) | Нет физических признаков; см. поля/ссылки ниже | `tracks`, `transparent`, `walkable` |
| [base:tracks_north: Следы вверх](../packs/base/tiles/tracks/tracks_north.json) | Нет физических признаков; см. поля/ссылки ниже | `tracks`, `transparent`, `walkable` |
| [base:tracks_south: Следы вниз](../packs/base/tiles/tracks/tracks_south.json) | Нет физических признаков; см. поля/ссылки ниже | `tracks`, `transparent`, `walkable` |
| [base:tracks_west: Следы влево](../packs/base/tiles/tracks/tracks_west.json) | Нет физических признаков; см. поля/ссылки ниже | `tracks`, `transparent`, `walkable` |
| [base:danger_mark: Обнаруженная опасность](../packs/base/tiles/trap_decor/danger_mark.json) | Нет физических признаков; см. поля/ссылки ниже | `transparent`, `trap_decor`, `walkable` |
| [base:wall: Каменная стена](../packs/base/tiles/wall.json) | `stone` | — |
| [base:pillar: Колонна](../packs/base/tiles/walls/pillar.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:pillar_carved: Резная колонна](../packs/base/tiles/walls/pillar_carved.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:pillar_massive: Массивная колонна](../packs/base/tiles/walls/pillar_massive.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:pillar_ornate: Украшенная колонна](../packs/base/tiles/walls/pillar_ornate.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:pillar_round: Круглая колонна](../packs/base/tiles/walls/pillar_round.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:reinforced_support: Укреплённая конструкция](../packs/base/tiles/walls/reinforced_support.json) | Нет физических признаков; см. поля/ссылки ниже | `obstacle`, `opaque`, `walls` |
| [base:tower_support: Башня или массивная опора](../packs/base/tiles/walls/tower_support.json) | Нет физических признаков; см. поля/ссылки ниже | `obstacle`, `opaque`, `walls` |
| [base:wall_beams: Перекрещенные балки](../packs/base/tiles/walls/wall_beams.json) | `flammable`, `wooden` | `obstacle`, `transparent`, `walls` |
| [base:wall_block: Каменный блок](../packs/base/tiles/walls/wall_block.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_branch_e: Стена с ответвлением вправо](../packs/base/tiles/walls/wall_branch_e.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_branch_n: Стена с ответвлением вверх](../packs/base/tiles/walls/wall_branch_n.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_branch_s: Стена с ответвлением вниз](../packs/base/tiles/walls/wall_branch_s.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_branch_w: Стена с ответвлением влево](../packs/base/tiles/walls/wall_branch_w.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_corner_ne: Угол стены, верх-право](../packs/base/tiles/walls/wall_corner_ne.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_corner_nw: Угол стены, верх-лево](../packs/base/tiles/walls/wall_corner_nw.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_corner_se: Угол стены, низ-право](../packs/base/tiles/walls/wall_corner_se.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_corner_sw: Угол стены, низ-лево](../packs/base/tiles/walls/wall_corner_sw.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_cross: Пересечение стен](../packs/base/tiles/walls/wall_cross.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_crumbling: Очень разрушенная стена](../packs/base/tiles/walls/wall_crumbling.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_damaged: Повреждённая стена](../packs/base/tiles/walls/wall_damaged.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_diagonal_down: Диагональная стена \](../packs/base/tiles/walls/wall_diagonal_down.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_diagonal_up: Диагональная стена /](../packs/base/tiles/walls/wall_diagonal_up.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_branch_e: Толстое ответвление вправо](../packs/base/tiles/walls/wall_double_branch_e.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_branch_n: Толстое ответвление вверх](../packs/base/tiles/walls/wall_double_branch_n.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_branch_s: Толстое ответвление вниз](../packs/base/tiles/walls/wall_double_branch_s.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_branch_w: Толстое ответвление влево](../packs/base/tiles/walls/wall_double_branch_w.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_corner_ne: Толстый угол, верх-право](../packs/base/tiles/walls/wall_double_corner_ne.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_corner_nw: Толстый угол, верх-лево](../packs/base/tiles/walls/wall_double_corner_nw.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_corner_se: Толстый угол, низ-право](../packs/base/tiles/walls/wall_double_corner_se.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_corner_sw: Толстый угол, низ-лево](../packs/base/tiles/walls/wall_double_corner_sw.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_cross: Толстое пересечение](../packs/base/tiles/walls/wall_double_cross.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_horizontal: Толстая горизонтальная стена](../packs/base/tiles/walls/wall_double_horizontal.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_double_vertical: Толстая вертикальная стена](../packs/base/tiles/walls/wall_double_vertical.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_hollow_block: Пустой каменный блок](../packs/base/tiles/walls/wall_hollow_block.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_horizontal: Горизонтальная стена](../packs/base/tiles/walls/wall_horizontal.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_lattice: Решётчатая кладка](../packs/base/tiles/walls/wall_lattice.json) | `stone` | `obstacle`, `transparent`, `walls` |
| [base:wall_massive: Сплошная массивная стена](../packs/base/tiles/walls/wall_massive.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_reinforced: Укреплённая стена](../packs/base/tiles/walls/wall_reinforced.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_stub_e: Короткий участок стены слева](../packs/base/tiles/walls/wall_stub_e.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_stub_n: Короткий участок стены сверху](../packs/base/tiles/walls/wall_stub_n.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_stub_s: Короткий участок стены снизу](../packs/base/tiles/walls/wall_stub_s.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_stub_w: Короткий участок стены справа](../packs/base/tiles/walls/wall_stub_w.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_thick: Толстая каменная стена](../packs/base/tiles/walls/wall_thick.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wall_vertical: Вертикальная стена](../packs/base/tiles/walls/wall_vertical.json) | `stone` | `obstacle`, `opaque`, `walls` |
| [base:wooden_support: Деревянные подпорки](../packs/base/tiles/walls/wooden_support.json) | `flammable`, `wooden` | `obstacle`, `transparent`, `walls` |
| [base:current_east: Течение вправо](../packs/base/tiles/water/current_east.json) | `liquid`, `water` | `transparent`, `walkable` |
| [base:current_north: Течение вверх](../packs/base/tiles/water/current_north.json) | `liquid`, `water` | `transparent`, `walkable` |
| [base:current_south: Течение вниз](../packs/base/tiles/water/current_south.json) | `liquid`, `water` | `transparent`, `walkable` |
| [base:current_west: Течение влево](../packs/base/tiles/water/current_west.json) | `liquid`, `water` | `transparent`, `walkable` |
| [base:water_calm: Спокойная вода](../packs/base/tiles/water/water_calm.json) | `liquid`, `water` | `transparent`, `walkable` |
| [base:water_deep: Глубокая вода](../packs/base/tiles/water/water_deep.json) | `liquid`, `water` | `obstacle`, `transparent` |
| [base:water_flowing: Текущая вода](../packs/base/tiles/water/water_flowing.json) | `liquid`, `water` | `transparent`, `walkable` |
| [base:water_muddy: Мутная вода](../packs/base/tiles/water/water_muddy.json) | `liquid`, `water` | `transparent`, `walkable` |
| [base:water_ripple: Мелкая вода](../packs/base/tiles/water/water_ripple.json) | `liquid`, `water` | `transparent`, `walkable` |
| [base:water_shallow: Вода](../packs/base/tiles/water/water_shallow.json) | `liquid`, `water` | `transparent`, `walkable` |
| [base:waterfall: Водопад](../packs/base/tiles/water/waterfall.json) | `liquid`, `water` | `obstacle`, `opaque` |
| [base:slime: Слизь](../packs/base/tiles/webs/slime.json) | `sticky` | `transparent`, `walkable`, `webs` |
| [base:slime_deep: Глубокая слизь](../packs/base/tiles/webs/slime_deep.json) | `sticky` | `obstacle`, `transparent`, `webs` |
| [base:slime_trail: Слизистый след](../packs/base/tiles/webs/slime_trail.json) | `sticky` | `transparent`, `walkable`, `webs` |
| [base:web: Паутина](../packs/base/tiles/webs/web.json) | `flammable`, `sticky` | `transparent`, `walkable`, `webs` |
| [base:web_dense: Плотная паутина](../packs/base/tiles/webs/web_dense.json) | `flammable`, `sticky` | `transparent`, `walkable`, `webs` |
| [base:web_sticky: Липкая паутина](../packs/base/tiles/webs/web_sticky.json) | `flammable`, `sticky` | `transparent`, `walkable`, `webs` |

## objects

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:alchemy_table: Алхимический стол](../packs/base/objects/alchemy_table.json) | `alchemy_table`, `destructible`, `flammable`, `repairable`, `station`, `wooden` | — |
| [base:anvil: Наковальня](../packs/base/objects/anvil.json) | `anvil`, `destructible`, `iron`, `metal`, `repairable`, `station` | — |
| [base:campfire: Костёр](../packs/base/objects/campfire.json) | `campfire`, `destructible`, `heat`, `light_source`, `repairable`, `station` | — |
| [base:cracked_barrier: Потрескавшаяся преграда](../packs/base/objects/cracked_barrier.json) | `destructible`, `dismantlable`, `repairable`, `stone` | `obstacle` |
| [base:door_adamantine: Адамантиевая дверь](../packs/base/objects/doors/door_adamantine.json) | `adamantine`, `destructible`, `door`, `metal` | `doors`, `opaque` |
| [base:door_barricaded: Забаррикадированная дверь](../packs/base/objects/doors/door_barricaded.json) | `destructible`, `dismantlable`, `flammable`, `repairable`, `wooden` | `doors`, `obstacle`, `opaque` |
| [base:door_bars: Дверь из прутьев](../packs/base/objects/doors/door_bars.json) | `destructible`, `door`, `iron`, `metal` | `doors`, `transparent` |
| [base:door_broken: Разрушенная дверь](../packs/base/objects/doors/door_broken.json) | `flammable`, `wooden` | `doors`, `transparent`, `walkable` |
| [base:door_secret: Секретная дверь](../packs/base/objects/doors/door_secret.json) | Нет физических признаков; см. поля/ссылки ниже | `doors`, `obstacle`, `opaque` |
| [base:door_steel: Стальная дверь](../packs/base/objects/doors/door_steel.json) | `destructible`, `door`, `iron`, `metal` | `doors`, `opaque` |
| [base:door_stone: Каменная плита](../packs/base/objects/doors/door_stone.json) | `destructible`, `door`, `stone` | `doors`, `opaque` |
| [base:door_wood: Деревянная дверь](../packs/base/objects/doors/door_wood.json) | `destructible`, `door`, `flammable`, `wooden` | `doors`, `opaque` |
| [base:passage_blocked: Заваленный проход](../packs/base/objects/doors/passage_blocked.json) | Нет физических признаков; см. поля/ссылки ниже | `doors`, `obstacle`, `opaque` |
| [base:barricade: Деревянная баррикада](../packs/base/objects/expansion/barricade.json) | `destructible`, `dismantlable`, `flammable`, `repairable`, `wooden` | `obstacle` |
| [base:craft_mechanism: Разбираемый механизм](../packs/base/objects/expansion/craft_mechanism.json) | `destructible`, `dismantlable`, `mechanism`, `metal`, `repairable` | — |
| [base:snake_remains: Останки змеи](../packs/base/objects/expansion/snake_remains.json) | `destructible`, `dismantlable`, `organic`, `remains`, `repairable`, `storage` | `containers` |
| [base:spider_remains: Останки паука](../packs/base/objects/expansion/spider_remains.json) | `destructible`, `dismantlable`, `organic`, `remains`, `repairable`, `storage` | `containers` |
| [base:tangled_branches: Спутанные ветви](../packs/base/objects/expansion/tangled_branches.json) | `destructible`, `dismantlable`, `flammable`, `pole_reachable`, `repairable`, `wooden` | — |
| [base:wolf_remains: Останки волка](../packs/base/objects/expansion/wolf_remains.json) | `destructible`, `dismantlable`, `organic`, `remains`, `repairable`, `storage` | `containers` |
| [base:hot_spring: Горячий источник](../packs/base/objects/fire/hot_spring.json) | `liquid`, `water` | `transparent`, `walkable` |
| [base:sparks: Искры](../packs/base/objects/fire/sparks.json) | `fire` | `transparent`, `walkable` |
| [base:forge: Горн](../packs/base/objects/forge.json) | `destructible`, `forge`, `heat`, `repairable`, `station`, `stone` | — |
| [base:mushroom_glowing: Светящийся гриб](../packs/base/objects/fungi/mushroom_glowing.json) | `flammable`, `fungi`, `organic` | `transparent`, `walkable` |
| [base:bed: Кровать](../packs/base/objects/furniture/bed.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `rest_spot`, `wooden` | `obstacle`, `transparent` |
| [base:bedroll: Лежанка](../packs/base/objects/furniture/bedroll.json) | `cloth`, `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `rest_spot` | `obstacle`, `transparent` |
| [base:bench: Скамья](../packs/base/objects/furniture/bench.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:bookcase: Книжный шкаф](../packs/base/objects/furniture/bookcase.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `storage`, `wooden` | `obstacle`, `opaque` |
| [base:cabinet: Шкаф](../packs/base/objects/furniture/cabinet.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `storage`, `wooden` | `obstacle`, `opaque` |
| [base:cart: Телега](../packs/base/objects/furniture/cart.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:chair: Стул](../packs/base/objects/furniture/chair.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:desk: Письменный стол](../packs/base/objects/furniture/desk.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:nightstand: Тумба](../packs/base/objects/furniture/nightstand.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:shelf: Полка](../packs/base/objects/furniture/shelf.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `storage`, `wooden` | `obstacle`, `transparent` |
| [base:stool: Табурет](../packs/base/objects/furniture/stool.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:table: Стол](../packs/base/objects/furniture/table.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:table_long: Длинный стол](../packs/base/objects/furniture/table_long.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:table_small: Маленький стол](../packs/base/objects/furniture/table_small.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:throne: Трон](../packs/base/objects/furniture/throne.json) | `destructible`, `dismantlable`, `flammable`, `furniture`, `movable`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:candle: Свеча](../packs/base/objects/lighting_decor/candle.json) | `flammable`, `storage` | `lighting_decor`, `transparent`, `walkable` |
| [base:lantern: Фонарь](../packs/base/objects/lighting_decor/lantern.json) | `storage` | `lighting_decor`, `transparent`, `walkable` |
| [base:lantern_magic: Магический фонарь](../packs/base/objects/lighting_decor/lantern_magic.json) | `magic` | `lighting_decor`, `transparent`, `walkable` |
| [base:light_bright: Яркий источник света](../packs/base/objects/lighting_decor/light_bright.json) | Нет физических признаков; см. поля/ссылки ниже | `lighting_decor`, `transparent`, `walkable` |
| [base:light_magic: Магический свет](../packs/base/objects/lighting_decor/light_magic.json) | `magic` | `lighting_decor`, `transparent`, `walkable` |
| [base:light_source: Источник света](../packs/base/objects/lighting_decor/light_source.json) | Нет физических признаков; см. поля/ссылки ниже | `lighting_decor`, `transparent`, `walkable` |
| [base:torch_decor: Стационарный факел](../packs/base/objects/lighting_decor/torch_decor.json) | `flammable`, `storage`, `wooden` | `lighting_decor`, `transparent`, `walkable` |
| [base:torch_wall: Настенный факел](../packs/base/objects/lighting_decor/torch_wall.json) | `flammable`, `storage`, `wooden` | `lighting_decor`, `transparent`, `walkable` |
| [base:magic_concentrated: Концентрированная магия](../packs/base/objects/magic/magic_concentrated.json) | `magic` | `transparent`, `walkable` |
| [base:magic_energy: Магическая энергия](../packs/base/objects/magic/magic_energy.json) | `magic` | `transparent`, `walkable` |
| [base:button: Кнопка](../packs/base/objects/mechanisms/button.json) | `mechanism` | `mechanisms`, `transparent`, `walkable` |
| [base:button_pressed: Нажатая кнопка](../packs/base/objects/mechanisms/button_pressed.json) | `mechanism` | `mechanisms`, `transparent`, `walkable` |
| [base:button_round: Круглая кнопка](../packs/base/objects/mechanisms/button_round.json) | `mechanism` | `mechanisms`, `transparent`, `walkable` |
| [base:chain: Цепь](../packs/base/objects/mechanisms/chain.json) | `mechanism`, `metal` | `mechanisms`, `transparent`, `walkable` |
| [base:chain_heavy: Тяжёлая цепь](../packs/base/objects/mechanisms/chain_heavy.json) | `mechanism`, `metal` | `mechanisms`, `transparent`, `walkable` |
| [base:gears: Механизм / шестерня](../packs/base/objects/mechanisms/gears.json) | `mechanism`, `metal` | `mechanisms`, `transparent`, `walkable` |
| [base:lever: Рычаг](../packs/base/objects/mechanisms/lever.json) | `mechanism` | `mechanisms`, `transparent`, `walkable` |
| [base:lever_lowered: Опущенный рычаг](../packs/base/objects/mechanisms/lever_lowered.json) | `mechanism` | `mechanisms`, `transparent`, `walkable` |
| [base:lever_off: Рычаг выключен](../packs/base/objects/mechanisms/lever_off.json) | `mechanism` | `mechanisms`, `transparent`, `walkable` |
| [base:lever_on: Рычаг включён](../packs/base/objects/mechanisms/lever_on.json) | `mechanism` | `mechanisms`, `transparent`, `walkable` |
| [base:mechanism: Механизм](../packs/base/objects/mechanisms/mechanism.json) | `mechanism` | `mechanisms`, `transparent`, `walkable` |
| [base:mechanism_wheel: Колесо механизма](../packs/base/objects/mechanisms/mechanism_wheel.json) | `mechanism` | `mechanisms`, `transparent`, `walkable` |
| [base:rope_decor: Закреплённая верёвка](../packs/base/objects/mechanisms/rope_decor.json) | `fiber`, `flammable` | `mechanisms`, `transparent`, `walkable` |
| [base:rope_taut: Натянутая верёвка](../packs/base/objects/mechanisms/rope_taut.json) | `fiber`, `flammable` | `mechanisms`, `transparent`, `walkable` |
| [base:muddy_spring: Мутный источник](../packs/base/objects/muddy_spring.json) | `water_source` | — |
| [base:oven: Печь](../packs/base/objects/oven.json) | `ceramic`, `destructible`, `heat`, `oven`, `repairable`, `station` | — |
| [base:alchemy_flower: Лиловый эфирник](../packs/base/objects/plants/alchemy_flower.json) | `destructible`, `dismantlable`, `flammable`, `organic`, `plants`, `repairable` | — |
| [base:bitter_flower: Золототысячник](../packs/base/objects/plants/bitter_flower.json) | `destructible`, `dismantlable`, `flammable`, `organic`, `plants`, `repairable` | — |
| [base:fiber_flower: Лазурный лён](../packs/base/objects/plants/fiber_flower.json) | `destructible`, `dismantlable`, `fiber`, `flammable`, `organic`, `plants`, `repairable` | — |
| [base:medicinal_flower: Зеленолист](../packs/base/objects/plants/medicinal_flower.json) | `destructible`, `dismantlable`, `flammable`, `medicinal`, `organic`, `plants`, `repairable` | — |
| [base:poison_flower: Алый паслён](../packs/base/objects/plants/poison_flower.json) | `destructible`, `dismantlable`, `flammable`, `organic`, `plants`, `poison`, `repairable` | — |
| [base:tree: Обычное дерево](../packs/base/objects/plants/tree.json) | `destructible`, `dismantlable`, `flammable`, `organic`, `plants`, `repairable`, `wooden` | `obstacle`, `opaque` |
| [base:tree_branches: Дерево с ветвями](../packs/base/objects/plants/tree_branches.json) | `destructible`, `dismantlable`, `flammable`, `organic`, `plants`, `repairable`, `wooden` | `obstacle`, `opaque` |
| [base:tree_clover: Дерево](../packs/base/objects/plants/tree_clover.json) | `destructible`, `dismantlable`, `flammable`, `organic`, `plants`, `repairable`, `wooden` | `obstacle`, `opaque` |
| [base:tree_dead: Мёртвое дерево](../packs/base/objects/plants/tree_dead.json) | `destructible`, `dismantlable`, `flammable`, `organic`, `plants`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:tree_large: Крупное дерево](../packs/base/objects/plants/tree_large.json) | `destructible`, `dismantlable`, `flammable`, `organic`, `plants`, `repairable`, `wooden` | `obstacle`, `opaque` |
| [base:tree_young: Молодое дерево](../packs/base/objects/plants/tree_young.json) | `destructible`, `dismantlable`, `flammable`, `organic`, `plants`, `repairable`, `wooden` | `obstacle`, `transparent` |
| [base:magic_rift: Магический разлом](../packs/base/objects/portals/magic_rift.json) | `magic`, `portal` | `portals`, `transparent`, `walkable` |
| [base:portal: Портал](../packs/base/objects/portals/portal.json) | `magic`, `portal` | `portals`, `transparent`, `walkable` |
| [base:portal_active: Активный портал](../packs/base/objects/portals/portal_active.json) | `magic`, `portal` | `portals`, `transparent`, `walkable` |
| [base:portal_dark: Тёмный портал](../packs/base/objects/portals/portal_dark.json) | `magic`, `portal` | `portals`, `transparent`, `walkable` |
| [base:portal_great: Великий портал](../packs/base/objects/portals/portal_great.json) | `magic`, `portal` | `portals`, `transparent`, `walkable` |
| [base:portal_inactive: Неактивный портал](../packs/base/objects/portals/portal_inactive.json) | `magic`, `portal` | `portals`, `transparent`, `walkable` |
| [base:portal_light: Светлый портал](../packs/base/objects/portals/portal_light.json) | `magic`, `portal` | `portals`, `transparent`, `walkable` |
| [base:portal_small: Малый портал](../packs/base/objects/portals/portal_small.json) | `magic`, `portal` | `portals`, `transparent`, `walkable` |
| [base:portal_unstable: Нестабильный портал](../packs/base/objects/portals/portal_unstable.json) | `magic`, `portal` | `portals`, `transparent`, `walkable` |
| [base:bones: Кости](../packs/base/objects/remains/bones.json) | `bone`, `destructible`, `organic`, `remains`, `repairable`, `storage` | `containers`, `transparent`, `walkable` |
| [base:bones_pile: Груда костей](../packs/base/objects/remains/bones_pile.json) | `bone`, `destructible`, `organic`, `remains`, `repairable`, `storage` | `containers`, `transparent`, `walkable` |
| [base:carcass: Туша монстра](../packs/base/objects/remains/carcass.json) | `destructible`, `flammable`, `organic`, `remains`, `repairable`, `storage` | `containers`, `transparent`, `walkable` |
| [base:corpse: Труп](../packs/base/objects/remains/corpse.json) | `destructible`, `flammable`, `organic`, `remains`, `repairable`, `storage` | `containers`, `transparent`, `walkable` |
| [base:remains: Останки](../packs/base/objects/remains/remains.json) | `bone`, `destructible`, `remains`, `repairable`, `storage` | `containers`, `transparent`, `walkable` |
| [base:skeleton_large: Крупный скелет](../packs/base/objects/remains/skeleton_large.json) | `bone`, `destructible`, `organic`, `remains`, `repairable`, `storage` | `containers`, `transparent`, `walkable` |
| [base:skeleton_remains: Скелет](../packs/base/objects/remains/skeleton_remains.json) | `bone`, `destructible`, `organic`, `remains`, `repairable`, `storage` | `containers`, `transparent`, `walkable` |
| [base:skull: Череп](../packs/base/objects/remains/skull.json) | `bone`, `destructible`, `organic`, `remains`, `repairable`, `storage` | `containers`, `transparent`, `walkable` |
| [base:rubble_large: Крупный завал](../packs/base/objects/ruins/rubble_large.json) | `destructible`, `dismantlable`, `repairable`, `stone` | `obstacle`, `opaque`, `ruins` |
| [base:exit_down: Спуск глубже](../packs/base/objects/stairs/exit_down.json) | Нет физических признаков; см. поля/ссылки ниже | `stairs`, `transparent`, `walkable` |
| [base:exit_up: Выход наверх](../packs/base/objects/stairs/exit_up.json) | Нет физических признаков; см. поля/ссылки ниже | `stairs`, `transparent`, `walkable` |
| [base:stairs_down: Лестница вниз](../packs/base/objects/stairs/stairs_down.json) | Нет физических признаков; см. поля/ссылки ниже | `stairs`, `transparent`, `walkable` |
| [base:stairs_up: Лестница вверх](../packs/base/objects/stairs/stairs_up.json) | Нет физических признаков; см. поля/ссылки ниже | `stairs`, `transparent`, `walkable` |
| [base:transition_down: Переход вниз](../packs/base/objects/stairs/transition_down.json) | Нет физических признаков; см. поля/ссылки ниже | `stairs`, `transparent`, `walkable` |
| [base:transition_next: Переход на следующий уровень](../packs/base/objects/stairs/transition_next.json) | Нет физических признаков; см. поля/ссылки ниже | `stairs`, `transparent`, `walkable` |
| [base:transition_previous: Переход на предыдущий уровень](../packs/base/objects/stairs/transition_previous.json) | Нет физических признаков; см. поля/ссылки ниже | `stairs`, `transparent`, `walkable` |
| [base:transition_up: Переход вверх](../packs/base/objects/stairs/transition_up.json) | Нет физических признаков; см. поля/ссылки ниже | `stairs`, `transparent`, `walkable` |
| [base:teleport: Телепорт](../packs/base/objects/teleports/teleport.json) | `magic`, `portal` | `teleports`, `transparent`, `walkable` |
| [base:teleport_active: Активный телепорт](../packs/base/objects/teleports/teleport_active.json) | `magic`, `portal` | `teleports`, `transparent`, `walkable` |
| [base:teleport_inactive: Неактивный телепорт](../packs/base/objects/teleports/teleport_inactive.json) | `magic`, `portal` | `teleports`, `transparent`, `walkable` |
| [base:teleport_large: Большой телепорт](../packs/base/objects/teleports/teleport_large.json) | `magic`, `portal` | `teleports`, `transparent`, `walkable` |
| [base:teleport_unstable: Нестабильный телепорт](../packs/base/objects/teleports/teleport_unstable.json) | `magic`, `portal` | `teleports`, `transparent`, `walkable` |
| [base:puddle: Лужа](../packs/base/objects/water/puddle.json) | `liquid`, `water`, `water_source` | `transparent`, `walkable` |
| [base:puddle_small: Мелкая лужа](../packs/base/objects/water/puddle_small.json) | `liquid`, `water`, `water_source` | `transparent`, `walkable` |
| [base:water_well: Колодец](../packs/base/objects/water_well.json) | `water_source` | — |
| [base:workbench: Верстак](../packs/base/objects/workbench.json) | `destructible`, `flammable`, `repairable`, `station`, `wooden`, `workbench` | — |

## points_of_interest

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:chest: Запертый сундук](../packs/base/points_of_interest/chest.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage`, `wooden` | `containers`, `transparent` |
| [base:crafting_expansion_manual: Руководство ремесленника](../packs/base/points_of_interest/expansion/crafting_expansion_manual.json) | `readable`, `recipe_source` | — |
| [base:crafting_manual: Памятка плотника](../packs/base/points_of_interest/reading/crafting_manual.json) | `book`, `flammable`, `paper`, `readable`, `recipe_source` | — |
| [base:crafting_workshop: Мастерская плотника](../packs/base/points_of_interest/reading/crafting_workshop.json) | `recipe_source` | — |
| [base:paper_note: Листы с записями](../packs/base/points_of_interest/reading/paper_note.json) | `flammable`, `paper`, `readable` | — |
| [base:quest_board: Доска с заданиями](../packs/base/points_of_interest/reading/quest_board.json) | `flammable`, `readable`, `wooden` | — |
| [base:stone_tablet: Каменная табличка](../packs/base/points_of_interest/reading/stone_tablet.json) | `readable`, `stone` | — |
| [base:strangers_diary: Чужой дневник](../packs/base/points_of_interest/reading/strangers_diary.json) | `book`, `flammable`, `paper`, `readable` | — |
| [base:shrine: Забытый алтарь](../packs/base/points_of_interest/shrine.json) | `stone` | — |
| [base:terrain_altar: Алтарь](../packs/base/points_of_interest/terrain/terrain_altar.json) | Нет физических признаков; см. поля/ссылки ниже | `shrines`, `transparent` |
| [base:terrain_altar_large: Большой алтарь](../packs/base/points_of_interest/terrain/terrain_altar_large.json) | Нет физических признаков; см. поля/ссылки ниже | `shrines`, `transparent` |
| [base:terrain_altar_moon: Лунный алтарь](../packs/base/points_of_interest/terrain/terrain_altar_moon.json) | Нет физических признаков; см. поля/ссылки ниже | `shrines`, `transparent` |
| [base:terrain_altar_sun: Солнечный алтарь](../packs/base/points_of_interest/terrain/terrain_altar_sun.json) | Нет физических признаков; см. поля/ссылки ниже | `shrines`, `transparent` |
| [base:terrain_amulet: Тайник с амулетом](../packs/base/points_of_interest/terrain/terrain_amulet.json) | Нет физических признаков; см. поля/ссылки ниже | `transparent`, `treasure` |
| [base:terrain_ancient_cross: Древний крест](../packs/base/points_of_interest/terrain/terrain_ancient_cross.json) | Нет физических признаков; см. поля/ссылки ниже | `shrines`, `transparent` |
| [base:terrain_barrel: Бочка](../packs/base/points_of_interest/terrain/terrain_barrel.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage`, `wooden` | `containers`, `transparent` |
| [base:terrain_barrel_large: Большая бочка](../packs/base/points_of_interest/terrain/terrain_barrel_large.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage`, `wooden` | `containers`, `transparent` |
| [base:terrain_barrel_small: Маленькая бочка](../packs/base/points_of_interest/terrain/terrain_barrel_small.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage`, `wooden` | `containers`, `transparent` |
| [base:terrain_book: Книга](../packs/base/points_of_interest/terrain/terrain_book.json) | `book`, `flammable`, `paper` | `books`, `transparent` |
| [base:terrain_book_ancient: Древний том](../packs/base/points_of_interest/terrain/terrain_book_ancient.json) | `book`, `flammable`, `paper` | `books`, `transparent` |
| [base:terrain_book_closed: Закрытая книга](../packs/base/points_of_interest/terrain/terrain_book_closed.json) | `book`, `flammable`, `paper` | `books`, `transparent` |
| [base:terrain_book_large: Большая книга](../packs/base/points_of_interest/terrain/terrain_book_large.json) | `book`, `flammable`, `paper` | `books`, `transparent` |
| [base:terrain_chest: Сундук](../packs/base/points_of_interest/terrain/terrain_chest.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage`, `wooden` | `containers`, `transparent` |
| [base:terrain_chest_open: Открытый сундук](../packs/base/points_of_interest/terrain/terrain_chest_open.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage`, `wooden` | `containers`, `transparent` |
| [base:terrain_chest_treasure: Сундук с сокровищами](../packs/base/points_of_interest/terrain/terrain_chest_treasure.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage`, `wooden` | `containers`, `transparent` |
| [base:terrain_coin_scatter: Россыпь монет](../packs/base/points_of_interest/terrain/terrain_coin_scatter.json) | `metal` | `transparent`, `treasure` |
| [base:terrain_crate: Ящик](../packs/base/points_of_interest/terrain/terrain_crate.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage`, `wooden` | `containers`, `transparent` |
| [base:terrain_crate_closed: Закрытый ящик](../packs/base/points_of_interest/terrain/terrain_crate_closed.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage`, `wooden` | `containers`, `transparent` |
| [base:terrain_crate_reinforced: Укреплённый ящик](../packs/base/points_of_interest/terrain/terrain_crate_reinforced.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage`, `wooden` | `containers`, `transparent` |
| [base:terrain_gem: Драгоценный камень](../packs/base/points_of_interest/terrain/terrain_gem.json) | Нет физических признаков; см. поля/ссылки ниже | `transparent`, `treasure` |
| [base:terrain_gem_large: Крупный самоцвет](../packs/base/points_of_interest/terrain/terrain_gem_large.json) | Нет физических признаков; см. поля/ссылки ниже | `transparent`, `treasure` |
| [base:terrain_gem_raw: Необработанный самоцвет](../packs/base/points_of_interest/terrain/terrain_gem_raw.json) | Нет физических признаков; см. поля/ссылки ниже | `transparent`, `treasure` |
| [base:terrain_holy_symbol: Священный символ](../packs/base/points_of_interest/terrain/terrain_holy_symbol.json) | `holy` | `shrines`, `transparent` |
| [base:terrain_jewelry: Украшение](../packs/base/points_of_interest/terrain/terrain_jewelry.json) | Нет физических признаков; см. поля/ссылки ниже | `transparent`, `treasure` |
| [base:terrain_jug: Кувшин](../packs/base/points_of_interest/terrain/terrain_jug.json) | `ceramic`, `storage` | `containers`, `transparent` |
| [base:terrain_magic_positive: Положительная энергия](../packs/base/points_of_interest/terrain/terrain_magic_positive.json) | `magic` | `transparent` |
| [base:terrain_magic_weak: Слабая магия](../packs/base/points_of_interest/terrain/terrain_magic_weak.json) | `magic` | `transparent` |
| [base:terrain_magic_zone: Сильная магическая зона](../packs/base/points_of_interest/terrain/terrain_magic_zone.json) | `magic` | `transparent` |
| [base:terrain_map_drawing: Карта](../packs/base/points_of_interest/terrain/terrain_map_drawing.json) | `flammable`, `paper` | `books`, `transparent` |
| [base:terrain_map_fragment: Фрагмент карты](../packs/base/points_of_interest/terrain/terrain_map_fragment.json) | `flammable`, `paper` | `books`, `transparent` |
| [base:terrain_marker_important: Важное место](../packs/base/points_of_interest/terrain/terrain_marker_important.json) | Нет физических признаков; см. поля/ссылки ниже | `markers`, `transparent` |
| [base:terrain_marker_interest: Интересный объект](../packs/base/points_of_interest/terrain/terrain_marker_interest.json) | Нет физических признаков; см. поля/ссылки ниже | `markers`, `transparent` |
| [base:terrain_marker_treasure: Сокровище](../packs/base/points_of_interest/terrain/terrain_marker_treasure.json) | Нет физических признаков; см. поля/ссылки ниже | `markers`, `transparent` |
| [base:terrain_marker_unique: Уникальное место](../packs/base/points_of_interest/terrain/terrain_marker_unique.json) | Нет физических признаков; см. поля/ссылки ниже | `markers`, `transparent` |
| [base:terrain_marker_unknown: Неизвестное место](../packs/base/points_of_interest/terrain/terrain_marker_unknown.json) | Нет физических признаков; см. поля/ссылки ниже | `markers`, `transparent` |
| [base:terrain_note: Записка](../packs/base/points_of_interest/terrain/terrain_note.json) | `flammable`, `paper` | `books`, `transparent` |
| [base:terrain_paper_scrap: Клочок бумаги](../packs/base/points_of_interest/terrain/terrain_paper_scrap.json) | `flammable`, `paper` | `books`, `transparent` |
| [base:terrain_pot: Горшок](../packs/base/points_of_interest/terrain/terrain_pot.json) | `ceramic`, `storage` | `containers`, `transparent` |
| [base:terrain_ring: Кольцо](../packs/base/points_of_interest/terrain/terrain_ring.json) | Нет физических признаков; см. поля/ссылки ниже | `transparent`, `treasure` |
| [base:terrain_ritual_circle: Ритуальный круг](../packs/base/points_of_interest/terrain/terrain_ritual_circle.json) | `magic` | `shrines`, `transparent` |
| [base:terrain_ritual_circle_active: Активный ритуальный круг](../packs/base/points_of_interest/terrain/terrain_ritual_circle_active.json) | `light_source`, `magic` | `shrines`, `transparent` |
| [base:terrain_rune: Обычная руна](../packs/base/points_of_interest/terrain/terrain_rune.json) | `magic` | `runes`, `transparent` |
| [base:terrain_rune_active: Активная руна](../packs/base/points_of_interest/terrain/terrain_rune_active.json) | `light_source`, `magic` | `runes`, `transparent` |
| [base:terrain_rune_air: Руна воздуха](../packs/base/points_of_interest/terrain/terrain_rune_air.json) | `magic` | `runes`, `transparent` |
| [base:terrain_rune_circle: Круглая руна](../packs/base/points_of_interest/terrain/terrain_rune_circle.json) | `magic` | `runes`, `transparent` |
| [base:terrain_rune_cross: Руна](../packs/base/points_of_interest/terrain/terrain_rune_cross.json) | `magic` | `runes`, `transparent` |
| [base:terrain_rune_earth: Руна земли](../packs/base/points_of_interest/terrain/terrain_rune_earth.json) | `magic` | `runes`, `transparent` |
| [base:terrain_rune_magic: Магическая руна](../packs/base/points_of_interest/terrain/terrain_rune_magic.json) | `magic` | `runes`, `transparent` |
| [base:terrain_rune_observation: Руна наблюдения](../packs/base/points_of_interest/terrain/terrain_rune_observation.json) | `magic` | `runes`, `transparent` |
| [base:terrain_rune_prohibition: Запрещающая руна](../packs/base/points_of_interest/terrain/terrain_rune_prohibition.json) | `magic` | `runes`, `transparent` |
| [base:terrain_rune_protection: Защитная руна](../packs/base/points_of_interest/terrain/terrain_rune_protection.json) | `magic` | `runes`, `transparent` |
| [base:terrain_rune_water: Руна воды](../packs/base/points_of_interest/terrain/terrain_rune_water.json) | `magic` | `runes`, `transparent` |
| [base:terrain_rune_weak: Слабая руна](../packs/base/points_of_interest/terrain/terrain_rune_weak.json) | `magic` | `runes`, `transparent` |
| [base:terrain_sack: Мешок](../packs/base/points_of_interest/terrain/terrain_sack.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage` | `containers`, `transparent` |
| [base:terrain_sack_large: Большой мешок](../packs/base/points_of_interest/terrain/terrain_sack_large.json) | `destructible`, `dismantlable`, `flammable`, `movable`, `repairable`, `storage` | `containers`, `transparent` |
| [base:terrain_sacrificial_bowl: Жертвенная чаша](../packs/base/points_of_interest/terrain/terrain_sacrificial_bowl.json) | Нет физических признаков; см. поля/ссылки ниже | `shrines`, `transparent` |
| [base:terrain_scroll: Свиток](../packs/base/points_of_interest/terrain/terrain_scroll.json) | `flammable`, `paper` | `books`, `transparent` |
| [base:terrain_scroll_magic: Магический свиток](../packs/base/points_of_interest/terrain/terrain_scroll_magic.json) | `flammable`, `magic`, `paper` | `books`, `transparent` |
| [base:terrain_shrine: Святыня](../packs/base/points_of_interest/terrain/terrain_shrine.json) | `holy`, `stone` | `shrines`, `transparent` |
| [base:terrain_temple_symbol: Храмовый символ](../packs/base/points_of_interest/terrain/terrain_temple_symbol.json) | Нет физических признаков; см. поля/ссылки ниже | `shrines`, `transparent` |
| [base:terrain_treasure_coins: Монеты](../packs/base/points_of_interest/terrain/terrain_treasure_coins.json) | `metal` | `transparent`, `treasure` |
| [base:terrain_treasure_copper: Медь](../packs/base/points_of_interest/terrain/terrain_treasure_copper.json) | `copper`, `metal` | `transparent`, `treasure` |
| [base:terrain_treasure_gold: Золото](../packs/base/points_of_interest/terrain/terrain_treasure_gold.json) | `gold`, `metal` | `transparent`, `treasure` |
| [base:terrain_treasure_jewels: Драгоценности](../packs/base/points_of_interest/terrain/terrain_treasure_jewels.json) | Нет физических признаков; см. поля/ссылки ниже | `transparent`, `treasure` |
| [base:terrain_treasure_silver: Серебро](../packs/base/points_of_interest/terrain/terrain_treasure_silver.json) | `metal`, `silver` | `transparent`, `treasure` |
| [base:terrain_urn: Урна](../packs/base/points_of_interest/terrain/terrain_urn.json) | `ceramic`, `storage` | `containers`, `transparent` |
| [base:terrain_vessel_large: Большой сосуд](../packs/base/points_of_interest/terrain/terrain_vessel_large.json) | `storage` | `containers`, `transparent` |

## traps

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:improvised_trap: Импровизированная ловушка](../packs/base/traps/expansion/improvised_trap.json) | `damage`, `dismantlable`, `mechanism`, `metal`, `piercing`, `trap` | — |
| [base:spikes: Шипы](../packs/base/traps/spikes.json) | `damage`, `dismantlable`, `metal`, `piercing`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_acid: Кислота](../packs/base/traps/terrain/terrain_acid.json) | `acid`, `applies_poison`, `condition`, `damage`, `liquid`, `poison`, `trap` | `transparent` |
| [base:terrain_acid_deep: Глубокая кислота](../packs/base/traps/terrain/terrain_acid_deep.json) | `acid`, `applies_poison`, `condition`, `damage`, `liquid`, `poison`, `trap` | `transparent` |
| [base:terrain_arrow_slit: Стрела из стены](../packs/base/traps/terrain/terrain_arrow_slit.json) | `damage`, `dismantlable`, `piercing`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_arrow_slit_barrage: Серия стрел](../packs/base/traps/terrain/terrain_arrow_slit_barrage.json) | `damage`, `dismantlable`, `piercing`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_cave_in: Обвал](../packs/base/traps/terrain/terrain_cave_in.json) | `bludgeoning`, `damage`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_door_trap: Ловушка в двери](../packs/base/traps/terrain/terrain_door_trap.json) | `damage`, `dismantlable`, `flammable`, `trap`, `wooden` | `transparent`, `trap_decor` |
| [base:terrain_fire: Огонь](../packs/base/traps/terrain/terrain_fire.json) | `damage`, `fire`, `light_source`, `trap` | `transparent` |
| [base:terrain_fire_large: Большое пламя](../packs/base/traps/terrain/terrain_fire_large.json) | `damage`, `fire`, `light_source`, `trap` | `transparent` |
| [base:terrain_fire_small: Небольшое пламя](../packs/base/traps/terrain/terrain_fire_small.json) | `damage`, `fire`, `light_source`, `trap` | `transparent` |
| [base:terrain_gas_toxic: Ядовитый газ](../packs/base/traps/terrain/terrain_gas_toxic.json) | `applies_poison`, `condition`, `damage`, `gas`, `poison`, `trap` | `transparent` |
| [base:terrain_lava: Лава](../packs/base/traps/terrain/terrain_lava.json) | `damage`, `fire`, `light_source`, `trap` | `transparent` |
| [base:terrain_lava_bubbling: Бурлящая лава](../packs/base/traps/terrain/terrain_lava_bubbling.json) | `damage`, `fire`, `light_source`, `trap` | `transparent` |
| [base:terrain_lava_flow: Поток лавы](../packs/base/traps/terrain/terrain_lava_flow.json) | `damage`, `fire`, `light_source`, `trap` | `transparent` |
| [base:terrain_magic_fire: Магический огонь](../packs/base/traps/terrain/terrain_magic_fire.json) | `damage`, `fire`, `light_source`, `magic`, `trap` | `transparent` |
| [base:terrain_magic_negative: Отрицательная энергия](../packs/base/traps/terrain/terrain_magic_negative.json) | `damage`, `magic`, `necrotic`, `trap` | `transparent` |
| [base:terrain_poison: Яд](../packs/base/traps/terrain/terrain_poison.json) | `applies_poison`, `condition`, `damage`, `liquid`, `poison`, `trap` | `transparent` |
| [base:terrain_poison_surface: Ядовитая поверхность](../packs/base/traps/terrain/terrain_poison_surface.json) | `applies_poison`, `condition`, `damage`, `liquid`, `poison`, `trap` | `transparent` |
| [base:terrain_pressure_plate: Нажимная плита](../packs/base/traps/terrain/terrain_pressure_plate.json) | `damage`, `dismantlable`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_pressure_plate_active: Активированная плита](../packs/base/traps/terrain/terrain_pressure_plate_active.json) | `damage`, `dismantlable`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_pressure_plate_stone: Каменная нажимная плита](../packs/base/traps/terrain/terrain_pressure_plate_stone.json) | `damage`, `dismantlable`, `stone`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_rune_destruction: Руна разрушения](../packs/base/traps/terrain/terrain_rune_destruction.json) | `damage`, `magic`, `trap` | `runes`, `transparent` |
| [base:terrain_rune_fire: Руна огня](../packs/base/traps/terrain/terrain_rune_fire.json) | `damage`, `fire`, `magic`, `trap` | `runes`, `transparent` |
| [base:terrain_spikes_hidden: Скрытые шипы](../packs/base/traps/terrain/terrain_spikes_hidden.json) | `damage`, `dismantlable`, `metal`, `piercing`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_spikes_large: Большие шипы](../packs/base/traps/terrain/terrain_spikes_large.json) | `damage`, `dismantlable`, `metal`, `piercing`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_suspicious_floor: Подозрительное место](../packs/base/traps/terrain/terrain_suspicious_floor.json) | `damage`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_toxic_spores: Токсичные споры](../packs/base/traps/terrain/terrain_toxic_spores.json) | `applies_poison`, `condition`, `damage`, `poison`, `trap` | `transparent` |
| [base:terrain_trap_acid: Кислотная ловушка](../packs/base/traps/terrain/terrain_trap_acid.json) | `acid`, `damage`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_trap_deadly: Смертельная ловушка](../packs/base/traps/terrain/terrain_trap_deadly.json) | `damage`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_trap_flood: Затопляющая ловушка](../packs/base/traps/terrain/terrain_trap_flood.json) | `damage`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_trap_magic: Магическая ловушка](../packs/base/traps/terrain/terrain_trap_magic.json) | `damage`, `magic`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_trap_mechanical: Механическая ловушка](../packs/base/traps/terrain/terrain_trap_mechanical.json) | `damage`, `dismantlable`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_trap_rune: Магическая руна-ловушка](../packs/base/traps/terrain/terrain_trap_rune.json) | `damage`, `magic`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_trap_small: Небольшая ловушка](../packs/base/traps/terrain/terrain_trap_small.json) | `damage`, `trap` | `transparent`, `trap_decor` |
| [base:terrain_wall_falling: Падающая стена](../packs/base/traps/terrain/terrain_wall_falling.json) | `bludgeoning`, `damage`, `trap` | `transparent`, `trap_decor` |

### base:improvised_trap — Импровизированная ловушка

- `failure[0]` / `damage` → `damage`, `piercing`

### base:spikes — Шипы

- `failure[0]` / `damage` → `damage`, `piercing`

### base:terrain_acid — Кислота

- `failure[0]` / `damage` → `acid`, `damage`
- `failure[1]` / `condition` → `applies_poison`, `condition`, `poison`

### base:terrain_acid_deep — Глубокая кислота

- `failure[0]` / `damage` → `acid`, `damage`
- `failure[1]` / `condition` → `applies_poison`, `condition`, `poison`

### base:terrain_arrow_slit — Стрела из стены

- `failure[0]` / `damage` → `damage`, `piercing`

### base:terrain_arrow_slit_barrage — Серия стрел

- `failure[0]` / `damage` → `damage`, `piercing`

### base:terrain_cave_in — Обвал

- `failure[0]` / `damage` → `bludgeoning`, `damage`

### base:terrain_door_trap — Ловушка в двери

- `failure[0]` / `damage` → `damage`

### base:terrain_fire — Огонь

- `failure[0]` / `damage` → `damage`, `fire`

### base:terrain_fire_large — Большое пламя

- `failure[0]` / `damage` → `damage`, `fire`

### base:terrain_fire_small — Небольшое пламя

- `failure[0]` / `damage` → `damage`, `fire`

### base:terrain_gas_toxic — Ядовитый газ

- `failure[0]` / `damage` → `damage`, `poison`
- `failure[1]` / `condition` → `applies_poison`, `condition`, `poison`

### base:terrain_lava — Лава

- `failure[0]` / `damage` → `damage`, `fire`

### base:terrain_lava_bubbling — Бурлящая лава

- `failure[0]` / `damage` → `damage`, `fire`

### base:terrain_lava_flow — Поток лавы

- `failure[0]` / `damage` → `damage`, `fire`

### base:terrain_magic_fire — Магический огонь

- `failure[0]` / `damage` → `damage`, `fire`

### base:terrain_magic_negative — Отрицательная энергия

- `failure[0]` / `damage` → `damage`, `necrotic`

### base:terrain_poison — Яд

- `failure[0]` / `damage` → `damage`, `poison`
- `failure[1]` / `condition` → `applies_poison`, `condition`, `poison`

### base:terrain_poison_surface — Ядовитая поверхность

- `failure[0]` / `damage` → `damage`, `poison`
- `failure[1]` / `condition` → `applies_poison`, `condition`, `poison`

### base:terrain_pressure_plate — Нажимная плита

- `failure[0]` / `damage` → `damage`

### base:terrain_pressure_plate_active — Активированная плита

- `failure[0]` / `damage` → `damage`

### base:terrain_pressure_plate_stone — Каменная нажимная плита

- `failure[0]` / `damage` → `damage`

### base:terrain_rune_destruction — Руна разрушения

- `failure[0]` / `damage` → `damage`

### base:terrain_rune_fire — Руна огня

- `failure[0]` / `damage` → `damage`, `fire`

### base:terrain_spikes_hidden — Скрытые шипы

- `failure[0]` / `damage` → `damage`, `piercing`

### base:terrain_spikes_large — Большие шипы

- `failure[0]` / `damage` → `damage`, `piercing`

### base:terrain_suspicious_floor — Подозрительное место

- `failure[0]` / `damage` → `damage`

### base:terrain_toxic_spores — Токсичные споры

- `failure[0]` / `damage` → `damage`, `poison`
- `failure[1]` / `condition` → `applies_poison`, `condition`, `poison`

### base:terrain_trap_acid — Кислотная ловушка

- `failure[0]` / `damage` → `acid`, `damage`

### base:terrain_trap_deadly — Смертельная ловушка

- `failure[0]` / `damage` → `damage`

### base:terrain_trap_flood — Затопляющая ловушка

- `failure[0]` / `damage` → `damage`

### base:terrain_trap_magic — Магическая ловушка

- `failure[0]` / `damage` → `damage`

### base:terrain_trap_mechanical — Механическая ловушка

- `failure[0]` / `damage` → `damage`

### base:terrain_trap_rune — Магическая руна-ловушка

- `failure[0]` / `damage` → `damage`

### base:terrain_trap_small — Небольшая ловушка

- `failure[0]` / `damage` → `damage`

### base:terrain_wall_falling — Падающая стена

- `failure[0]` / `damage` → `bludgeoning`, `damage`

## challenges

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:locked_chest: Запертый сундук](../packs/base/challenges/locked_chest.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:ruined_shrine: Забытое святилище](../packs/base/challenges/ruined_shrine.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_altar: Алтарь](../packs/base/challenges/terrain/terrain_altar.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_altar_large: Большой алтарь](../packs/base/challenges/terrain/terrain_altar_large.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_altar_moon: Лунный алтарь](../packs/base/challenges/terrain/terrain_altar_moon.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_altar_sun: Солнечный алтарь](../packs/base/challenges/terrain/terrain_altar_sun.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_amulet: Амулет](../packs/base/challenges/terrain/terrain_amulet.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_ancient_cross: Древний крест](../packs/base/challenges/terrain/terrain_ancient_cross.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_barrel: Бочка](../packs/base/challenges/terrain/terrain_barrel.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_barrel_large: Большая бочка](../packs/base/challenges/terrain/terrain_barrel_large.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_barrel_small: Маленькая бочка](../packs/base/challenges/terrain/terrain_barrel_small.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_book: Книга](../packs/base/challenges/terrain/terrain_book.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_book_ancient: Древний том](../packs/base/challenges/terrain/terrain_book_ancient.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_book_closed: Закрытая книга](../packs/base/challenges/terrain/terrain_book_closed.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_book_large: Большая книга](../packs/base/challenges/terrain/terrain_book_large.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_chest: Сундук](../packs/base/challenges/terrain/terrain_chest.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_chest_locked: Запертый сундук](../packs/base/challenges/terrain/terrain_chest_locked.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_chest_open: Открытый сундук](../packs/base/challenges/terrain/terrain_chest_open.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_chest_treasure: Сундук с сокровищами](../packs/base/challenges/terrain/terrain_chest_treasure.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_coin_scatter: Россыпь монет](../packs/base/challenges/terrain/terrain_coin_scatter.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_crate: Ящик](../packs/base/challenges/terrain/terrain_crate.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_crate_closed: Закрытый ящик](../packs/base/challenges/terrain/terrain_crate_closed.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_crate_reinforced: Укреплённый ящик](../packs/base/challenges/terrain/terrain_crate_reinforced.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_gem: Драгоценный камень](../packs/base/challenges/terrain/terrain_gem.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_gem_large: Крупный самоцвет](../packs/base/challenges/terrain/terrain_gem_large.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_gem_raw: Необработанный самоцвет](../packs/base/challenges/terrain/terrain_gem_raw.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_holy_symbol: Священный символ](../packs/base/challenges/terrain/terrain_holy_symbol.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_jewelry: Украшение](../packs/base/challenges/terrain/terrain_jewelry.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_jug: Кувшин](../packs/base/challenges/terrain/terrain_jug.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_magic_positive: Положительная энергия](../packs/base/challenges/terrain/terrain_magic_positive.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_magic_weak: Слабая магия](../packs/base/challenges/terrain/terrain_magic_weak.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_magic_zone: Сильная магическая зона](../packs/base/challenges/terrain/terrain_magic_zone.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_map_drawing: Карта](../packs/base/challenges/terrain/terrain_map_drawing.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_map_fragment: Фрагмент карты](../packs/base/challenges/terrain/terrain_map_fragment.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_marker_important: Важное место](../packs/base/challenges/terrain/terrain_marker_important.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_marker_interest: Интересный объект](../packs/base/challenges/terrain/terrain_marker_interest.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_marker_treasure: Сокровище](../packs/base/challenges/terrain/terrain_marker_treasure.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_marker_unique: Уникальное место](../packs/base/challenges/terrain/terrain_marker_unique.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_marker_unknown: Неизвестное место](../packs/base/challenges/terrain/terrain_marker_unknown.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_note: Записка](../packs/base/challenges/terrain/terrain_note.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_paper_scrap: Клочок бумаги](../packs/base/challenges/terrain/terrain_paper_scrap.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_pot: Горшок](../packs/base/challenges/terrain/terrain_pot.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_ring: Кольцо](../packs/base/challenges/terrain/terrain_ring.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_ritual_circle: Ритуальный круг](../packs/base/challenges/terrain/terrain_ritual_circle.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_ritual_circle_active: Активный ритуальный круг](../packs/base/challenges/terrain/terrain_ritual_circle_active.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune: Обычная руна](../packs/base/challenges/terrain/terrain_rune.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_active: Активная руна](../packs/base/challenges/terrain/terrain_rune_active.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_air: Руна воздуха](../packs/base/challenges/terrain/terrain_rune_air.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_circle: Круглая руна](../packs/base/challenges/terrain/terrain_rune_circle.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_cross: Руна](../packs/base/challenges/terrain/terrain_rune_cross.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_earth: Руна земли](../packs/base/challenges/terrain/terrain_rune_earth.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_magic: Магическая руна](../packs/base/challenges/terrain/terrain_rune_magic.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_observation: Руна наблюдения](../packs/base/challenges/terrain/terrain_rune_observation.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_prohibition: Запрещающая руна](../packs/base/challenges/terrain/terrain_rune_prohibition.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_protection: Защитная руна](../packs/base/challenges/terrain/terrain_rune_protection.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_water: Руна воды](../packs/base/challenges/terrain/terrain_rune_water.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_rune_weak: Слабая руна](../packs/base/challenges/terrain/terrain_rune_weak.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_sack: Мешок](../packs/base/challenges/terrain/terrain_sack.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_sack_large: Большой мешок](../packs/base/challenges/terrain/terrain_sack_large.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_sacrificial_bowl: Жертвенная чаша](../packs/base/challenges/terrain/terrain_sacrificial_bowl.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_scroll: Свиток](../packs/base/challenges/terrain/terrain_scroll.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_scroll_magic: Магический свиток](../packs/base/challenges/terrain/terrain_scroll_magic.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_shrine: Святыня](../packs/base/challenges/terrain/terrain_shrine.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_temple_symbol: Храмовый символ](../packs/base/challenges/terrain/terrain_temple_symbol.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_treasure_coins: Монеты](../packs/base/challenges/terrain/terrain_treasure_coins.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_treasure_copper: Медь](../packs/base/challenges/terrain/terrain_treasure_copper.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_treasure_gold: Золото](../packs/base/challenges/terrain/terrain_treasure_gold.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_treasure_gold_mark: Золото](../packs/base/challenges/terrain/terrain_treasure_gold_mark.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_treasure_jewels: Драгоценности](../packs/base/challenges/terrain/terrain_treasure_jewels.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_treasure_silver: Серебро](../packs/base/challenges/terrain/terrain_treasure_silver.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_urn: Урна](../packs/base/challenges/terrain/terrain_urn.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:terrain_vessel_large: Большой сосуд](../packs/base/challenges/terrain/terrain_vessel_large.json) | Нет физических признаков; см. поля/ссылки ниже | — |

### base:locked_chest — Запертый сундук

- `choices[0].success[0]` / `gold` → `reward`
- `choices[0].success[1]` / `experience` → `reward`
- `choices[0].failure[0]` / `damage` → `damage`
- `choices[1].success[0]` / `gold` → `reward`
- `choices[1].success[1]` / `experience` → `reward`
- `choices[1].failure[0]` / `damage` → `damage`
- `choices[2].success[0]` / `gold` → `reward`
- `choices[2].success[1]` / `experience` → `reward`

### base:ruined_shrine — Забытое святилище

- `choices[0].success[0]` / `heal` → `healing`
- `choices[0].success[1]` / `experience` → `reward`
- `choices[0].failure[0]` / `condition` → `applies_fear`, `condition`
- `choices[1].success[0]` / `experience` → `reward`
- `choices[2].success[0]` / `experience` → `reward`
- `choices[3].success[0]` / `experience` → `reward`
- `choices[4].success[0]` / `experience` → `reward`

### base:terrain_altar — Алтарь

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_altar_large — Большой алтарь

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_altar_moon — Лунный алтарь

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_altar_sun — Солнечный алтарь

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_amulet — Амулет

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_ancient_cross — Древний крест

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_barrel — Бочка

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_barrel_large — Большая бочка

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_barrel_small — Маленькая бочка

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_book — Книга

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_book_ancient — Древний том

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_book_closed — Закрытая книга

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_book_large — Большая книга

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_chest — Сундук

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_chest_locked — Запертый сундук

- `choices[0].success[0]` / `gold` → `reward`
- `choices[0].success[1]` / `experience` → `reward`
- `choices[0].failure[0]` / `damage` → `damage`
- `choices[1].success[0]` / `gold` → `reward`
- `choices[1].success[1]` / `experience` → `reward`
- `choices[1].failure[0]` / `damage` → `damage`
- `choices[2].success[0]` / `gold` → `reward`
- `choices[2].success[1]` / `experience` → `reward`

### base:terrain_chest_open — Открытый сундук

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_chest_treasure — Сундук с сокровищами

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_coin_scatter — Россыпь монет

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_crate — Ящик

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_crate_closed — Закрытый ящик

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_crate_reinforced — Укреплённый ящик

- `choices[0].success[0]` / `gold` → `reward`
- `choices[0].success[1]` / `experience` → `reward`
- `choices[0].failure[0]` / `damage` → `damage`
- `choices[1].success[0]` / `gold` → `reward`
- `choices[1].success[1]` / `experience` → `reward`
- `choices[1].failure[0]` / `damage` → `damage`
- `choices[2].success[0]` / `gold` → `reward`
- `choices[2].success[1]` / `experience` → `reward`

### base:terrain_gem — Драгоценный камень

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_gem_large — Крупный самоцвет

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_gem_raw — Необработанный самоцвет

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_holy_symbol — Священный символ

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_jewelry — Украшение

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_jug — Кувшин

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_magic_positive — Положительная энергия

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_magic_weak — Слабая магия

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_magic_zone — Сильная магическая зона

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_map_drawing — Карта

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_map_fragment — Фрагмент карты

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_marker_important — Важное место

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_marker_interest — Интересный объект

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_marker_treasure — Сокровище

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_marker_unique — Уникальное место

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_marker_unknown — Неизвестное место

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_note — Записка

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_paper_scrap — Клочок бумаги

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_pot — Горшок

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_ring — Кольцо

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_ritual_circle — Ритуальный круг

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_ritual_circle_active — Активный ритуальный круг

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_rune — Обычная руна

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_active — Активная руна

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_air — Руна воздуха

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_circle — Круглая руна

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_cross — Руна

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_earth — Руна земли

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_magic — Магическая руна

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_observation — Руна наблюдения

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_prohibition — Запрещающая руна

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_protection — Защитная руна

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_water — Руна воды

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_rune_weak — Слабая руна

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_sack — Мешок

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_sack_large — Большой мешок

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_sacrificial_bowl — Жертвенная чаша

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_scroll — Свиток

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_scroll_magic — Магический свиток

- `choices[0].success[0]` / `experience` → `reward`

### base:terrain_shrine — Святыня

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_temple_symbol — Храмовый символ

- `choices[0].success[0]` / `heal` → `healing`

### base:terrain_treasure_coins — Монеты

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_treasure_copper — Медь

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_treasure_gold — Золото

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_treasure_gold_mark — Золото

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_treasure_jewels — Драгоценности

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_treasure_silver — Серебро

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_urn — Урна

- `choices[0].success[0]` / `gold` → `reward`

### base:terrain_vessel_large — Большой сосуд

- `choices[0].success[0]` / `gold` → `reward`

## races

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:dwarf: Дварф](../packs/base/races/dwarf.json) | `humanoid`, `living`, `organic` | — |
| [base:elf: Эльф](../packs/base/races/elf.json) | `humanoid`, `living`, `organic` | — |
| [base:human: Человек](../packs/base/races/human.json) | `humanoid`, `living`, `organic` | — |

### base:elf — Эльф

- `racial_spell`: `base:detect_magic`

## classes

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:rogue: Плут](../packs/base/classes/rogue.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:warrior: Воин](../packs/base/classes/warrior.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:wizard: Волшебник](../packs/base/classes/wizard.json) | Нет физических признаков; см. поля/ссылки ниже | — |

### base:rogue — Плут

- `actions`: `base:attack`, `base:dodge`, `base:stealth`, `base:magic`, `base:influence`

### base:warrior — Воин

- `actions`: `base:attack`, `base:dodge`, `base:stealth`, `base:magic`, `base:influence`

### base:wizard — Волшебник

- `actions`: `base:attack`, `base:dodge`, `base:stealth`, `base:magic`, `base:influence`
- `spells`: `base:magic_missile`, `base:detect_magic`
- `cantrip_choices`: `base:light`, `base:fire_bolt`, `base:mending`, `base:toll_the_dead`, `base:acid_splash`, `base:ray_of_frost`, `base:shocking_grasp`, `base:mage_hand`, `base:minor_illusion`, `base:prestidigitation`, `base:poison_spray`, `base:chill_touch`, `base:thunderclap`, `base:blade_ward`, `base:dancing_lights`, `base:elementalism`, `base:true_strike`

## backgrounds

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:artisan: Ремесленник](../packs/base/backgrounds/crafting/artisan.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:sage: Мудрец](../packs/base/backgrounds/sage.json) | Нет физических признаков; см. поля/ссылки ниже | `sage` |
| [base:scholar: Учёный](../packs/base/backgrounds/scholar.json) | Нет физических признаков; см. поля/ссылки ниже | `lore`, `scholar` |
| [base:soldier: Солдат](../packs/base/backgrounds/soldier.json) | Нет физических признаков; см. поля/ссылки ниже | `soldier` |
| [base:thief: Вор](../packs/base/backgrounds/thief.json) | Нет физических признаков; см. поля/ссылки ниже | `thief` |
| [base:wanderer: Странник](../packs/base/backgrounds/wanderer.json) | Нет физических признаков; см. поля/ссылки ниже | `outdoors` |

### base:artisan — Ремесленник

- `tool_proficiencies`: `carpenter_tools`, `smith_tools`
- `starting_recipes`: `base:craft_torch`

## recipes

| Ссылка / название | Признаки для взаимодействий | Существующие служебные / сюжетные теги |
| --- | --- | --- |
| [base:craft_dragon_leather: Доспех из драконьей кожи](../packs/base/recipes/arcana/craft_dragon_leather.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_focus: Рунный фокус](../packs/base/recipes/arcana/craft_focus.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_ironwood_club: Дубинка из железного дерева](../packs/base/recipes/arcana/craft_ironwood_club.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_mithril_shield: Мифриловый щит](../packs/base/recipes/arcana/craft_mithril_shield.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_rune_dagger: Рунный клинок](../packs/base/recipes/arcana/craft_rune_dagger.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_rune_leather: Рунный кожаный доспех](../packs/base/recipes/arcana/craft_rune_leather.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:experiment_binding: Опыт: связывание реагента](../packs/base/recipes/arcana/experiment_binding.json) | `recipe_source` | — |
| [base:mix_ink: Приготовить чернила](../packs/base/recipes/arcana/mix_ink.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:scribe_fire_bolt: Свиток огненного снаряда](../packs/base/recipes/arcana/scribe_fire_bolt.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:scribe_light: Свиток света](../packs/base/recipes/arcana/scribe_light.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:scribe_mending: Свиток починки](../packs/base/recipes/arcana/scribe_mending.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:write_inscription: Написать памятку](../packs/base/recipes/arcana/write_inscription.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:antidote_broth: Противоядный отвар](../packs/base/recipes/crafting/antidote_broth.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:boil_water: Кипячение воды](../packs/base/recipes/crafting/boil_water.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:build_campfire: Развести костёр](../packs/base/recipes/crafting/build_campfire.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:cook_ration: Приготовить рацион](../packs/base/recipes/crafting/cook_ration.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_bandage: Бинт](../packs/base/recipes/crafting/craft_bandage.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_club: Простая дубинка](../packs/base/recipes/crafting/craft_club.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_rope: Импровизированная верёвка](../packs/base/recipes/crafting/craft_rope.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_stake: Кол](../packs/base/recipes/crafting/craft_stake.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_tinder: Растопка](../packs/base/recipes/crafting/craft_tinder.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_torch: Факел](../packs/base/recipes/crafting/craft_torch.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_workshop_torch: Факел плотника](../packs/base/recipes/crafting/craft_workshop_torch.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:dry_herbs: Сушка трав](../packs/base/recipes/crafting/dry_herbs.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:healing_broth: Лечебный отвар](../packs/base/recipes/crafting/healing_broth.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:make_poultice: Лечебная припарка](../packs/base/recipes/crafting/make_poultice.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:repair_metal: Ремонт металлического предмета](../packs/base/recipes/crafting/repair_metal.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:repair_wood: Ремонт деревянного предмета](../packs/base/recipes/crafting/repair_wood.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:repair_wood_object: Ремонт деревянного объекта](../packs/base/recipes/crafting/repair_wood_object.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:appraise_gem: Оценить самоцвет](../packs/base/recipes/expansion/appraise_gem.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:blow_glass_flask: Выдуть флакон](../packs/base/recipes/expansion/blow_glass_flask.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:brew_antidote: Противоядный напиток](../packs/base/recipes/expansion/brew_antidote.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:build_barricade: Построить баррикаду](../packs/base/recipes/expansion/build_barricade.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:carve_staff: Вырезать посох](../packs/base/recipes/expansion/carve_staff.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:coat_weapon: Нанести яд](../packs/base/recipes/expansion/coat_weapon.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:cook_meat: Приготовить мясо](../packs/base/recipes/expansion/cook_meat.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_acid: Приготовить кислоту](../packs/base/recipes/expansion/craft_acid.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_boots: Сшить сапоги](../packs/base/recipes/expansion/craft_boots.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_healing_potion: Сварить лечебное зелье](../packs/base/recipes/expansion/craft_healing_potion.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_iron_blade: Железный клинок](../packs/base/recipes/expansion/craft_iron_blade.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_leather_armor: Кожаный доспех](../packs/base/recipes/expansion/craft_leather_armor.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_leather_strip: Кожаная лента](../packs/base/recipes/expansion/craft_leather_strip.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_lockpicks: Простые отмычки](../packs/base/recipes/expansion/craft_lockpicks.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_metal_shield: Металлический щит](../packs/base/recipes/expansion/craft_metal_shield.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_parts: Детали из лома](../packs/base/recipes/expansion/craft_parts.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_poison: Простой растительный яд](../packs/base/recipes/expansion/craft_poison.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_pole: Деревянный шест](../packs/base/recipes/expansion/craft_pole.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_ram: Переносной таран](../packs/base/recipes/expansion/craft_ram.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_trap: Импровизированная ловушка](../packs/base/recipes/expansion/craft_trap.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_waterskin: Бурдюк](../packs/base/recipes/expansion/craft_waterskin.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_wedge: Каменный клин](../packs/base/recipes/expansion/craft_wedge.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:craft_wooden_shield: Деревянный щит](../packs/base/recipes/expansion/craft_wooden_shield.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:cut_stone_block: Обтесать каменный блок](../packs/base/recipes/expansion/cut_stone_block.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:extract_venom: Извлечь животный яд](../packs/base/recipes/expansion/extract_venom.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:fire_clay_pot: Обжечь сосуд](../packs/base/recipes/expansion/fire_clay_pot.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:install_trap: Установить ловушку](../packs/base/recipes/expansion/install_trap.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:make_extract: Травяной экстракт](../packs/base/recipes/expansion/make_extract.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:repair_boots: Ремонт обуви](../packs/base/recipes/expansion/repair_boots.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:repair_mechanism: Ремонт механизма](../packs/base/recipes/expansion/repair_mechanism.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:repair_stone_object: Ремонт каменного объекта](../packs/base/recipes/expansion/repair_stone_object.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:weave_cloth: Соткать ткань](../packs/base/recipes/expansion/weave_cloth.json) | Нет физических признаков; см. поля/ссылки ниже | — |
| [base:weave_rope: Сплести верёвку](../packs/base/recipes/expansion/weave_rope.json) | Нет физических признаков; см. поля/ссылки ниже | — |
