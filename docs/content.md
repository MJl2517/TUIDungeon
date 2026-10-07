# Пакеты и формат документов

Рабочий контент находится в `packs/`. Источник проверки и JSON Schema —
`tuidungeon/content/schemas.py`; перечисление `MODELS` связывает категории с
моделями. Схемы строгие: лишние поля, неверные типы, ширина символа, размеры,
кубики и ссылки отклоняются до сохранения.

## Манифест и ссылки

```text
packs/my_pack/
  manifest.json
  art/ tiles/ maps/ monsters/ equipment/ spells/ actions/
  classes/ races/ backgrounds/ challenges/ traps/ points_of_interest/
```

```json
{
  "schema_version": 1,
  "id": "my_pack",
  "name": "Мои подземелья",
  "version": "1.0.0",
  "dependencies": ["base"]
}
```

ID — строчные латинские буквы, цифры и `_`, первый символ — буква.
ID пакета совпадает с папкой. Документ задаёт локальный `id`; ссылка —
`pack_id:local_id`, например `base:goblin`. Категория определяется полем:
`art` ищет рисунок, `challenge` — испытание, `actions` — действия.
В одной категории одного пакета повторные ID запрещены, даже если имена файлов разные.
Разные категории могут использовать один local_id: арт и монстр `base:goblin`.

Проверяются существование ссылки, категория и доступность целевого пакета через
зависимости. Зависимости транзитивны; отсутствующие пакеты и циклы запрещены.
Контент в подпапках категории тоже загружается. Новые документы студия записывает
как `<id>.json`, рисунки — `<id>.art.json`. Версия формата сейчас `schema_version: 1`;
несовместимые версии не преобразуются молча.

## Механические объекты

Пример монстра:

```json
{
  "schema_version": 1,
  "id": "scout",
  "name": "Разведчик",
  "glyph": "g",
  "foreground": 10,
  "background": null,
  "art": "base:goblin",
  "stats": {
    "strength": 8, "dexterity": 14, "constitution": 10,
    "intelligence": 10, "wisdom": 8, "charisma": 8
  },
  "hit_points": 7, "armor_class": 13, "speed": 2, "initiative_bonus": 1,
  "actions": ["base:attack", "base:dodge"],
  "special_actions": [{
    "id": "dirty_strike", "name": "Подлый удар", "kind": "attack",
    "ability": "dexterity", "damage": "1d4",
    "effects": [{"kind": "condition", "condition": "poisoned", "duration": 2}]
  }]
}
```

HP и характеристики положительные, скорость и КД неотрицательные.
Инициатива — `d20 + мод. ЛОВ + initiative_bonus`. Большой арт не меняет
занимаемую клетку. Обычные действия — ссылки, особые — встроенные определения
с локальными ID. `inventory`, `spells`, `spell_slots`, `tags` необязательны.

Снаряжение: `weight`, `tags`, `durability`, `charges`, `slot`,
`weapon_damage`, `weapon_ability`, `properties`, `check_aids`.
`durability: null` означает неразрушаемый предмет, `charges: null` — без
ограничения применений. Сломанный/исчерпанный предмет не даёт свойств и тегов.
Броня `{"kind":"armor_class","amount":16}` заменяет КД; щит
`{"kind":"armor_bonus","amount":2}` прибавляет 2. Эти свойства работают
только у пригодного экипированного предмета.

```json
{"check_tag": "lockpicking", "mode": "advantage"}
```

В `check_aids` это даёт преимущество проверки с соответствующим тегом.
`automatic` даёт успех без броска и имеет приоритет над преимуществом.
Грузоподъёмность — сила × `carry_per_strength` класса, обычно 5 кг.
Перегрузка уже вычисляется, штраф движения пока не применяется.

Заклинание: `level` 0–9, `target` self/other/any, `effects`.
Класс: `hit_points`, `starting_items`, `actions`, `spells`, `spell_slots`
(например `{"1":2}`), `carry_per_strength`, `order`.
Раса: `ability_bonuses`, `hp_per_level`, `speed`, `racial_spell` вместе с
положительным `racial_uses`. Предыстория: бонусы, стартовые предметы и теги;
выбирается в браузерной/API-сессии, отдельного шага TUI пока нет.

Действия: attack/dodge/stealth/magic/influence/special. Поля:
`ability`, `bonus`, `damage`, `effects`, `difficulty`.
Эффекты damage/heal/gold/experience суммируют `amount` и бросок `dice`;
condition задаёт `condition` и `duration`. Кубики имеют вид `1d6`, `2d4+2`,
до 100 кубиков и 2–1000 граней. Новые эффекты используют `params` и общий
Python-реестр: [пример регистрации](studio.md#добавление-зарегистрированного-эффекта).

## Арты

```json
{
  "schema_version": 1, "id": "torch", "name": "Факел",
  "width": 2, "height": 2,
  "layers": [{
    "id": "base", "name": "Основной", "visible": true, "locked": false,
    "cells": [
      [{"char":"*","foreground":208,"background":null}, null],
      [{"char":"|","foreground":130,"background":null}, null]
    ]
  }]
}
```

`null` — прозрачная клетка. `background: null` — прозрачный фон символа:
символ/его цвет заменяются, фон нижнего слоя сохраняется.
Слои композируются в порядке списка; скрытые не рисуются, блокировка относится
к редактированию. Размер каждой матрицы точно совпадает с холстом.
Один печатный символ занимает одну терминальную колонку; emoji, CJK,
комбинируемые последовательности и управляющие коды не проходят проверку.
TXT импортируется в один слой, строки дополняются пробелами до прямоугольника.
Экспорт TXT сохраняет видимые символы и теряет цвета/редактируемые слои.

## Карты, ловушки и взаимодействия

`MapDocument` содержит `width`, `height`, три одинаковые по размеру матрицы:
`tiles` (ссылка на тайл или null), `walkability` и `blocks_sight` (bool).
`spawn` — `{x,y}`; координаты отсчитываются от нуля. `decorations` — размещения
артов; `traps`, `points_of_interest`, `monsters`, `equipment` — размещения шаблонов:

```json
{"id":"spikes_1", "ref":"base:spikes", "x":5, "y":3}
```

ID размещений уникальны на карте. Арт должен помещаться в карту; остальные
объекты размещаются на проходимых клетках. Старт не может совпасть с монстром,
два монстра не могут занимать одну клетку. Пересечение разных типов разрешено.
`transitions` задают `{id,x,y,target}` с ссылкой на карту; вход на клетку
переносит героя на её старт с сохранением ресурсов и часов.

Тайл задаёт glyph/цвета и начальные walkable/blocks_sight. Независимые маски
карты определяют движение; изменение рисунка не делает стену проходимой или наоборот.
Карта целиком открыта; маска обзора зарезервирована для FOV.

Ловушка задаёт `hidden`, `ability`, `difficulty`, `success`, `failure`,
`repeatable`, `trigger: "enter"`. Срабатывание не расходует дополнительный ход.
POI задаёт `challenge` — ссылку на текстовое испытание. У испытания `text`,
`choices`, `repeatable`; вариант имеет id/text, ability/difficulty/check_tag,
required_tags/advantage_tags/automatic_tags, success/failure и minutes.
Недостающий обязательный инструмент запрещает выбор без затрат времени.
Состоявшийся выбор завершает одноразовое испытание, включая провал проверки.

## Миграция и совместимость

`packs/base` создан неперезаписывающей миграцией текущего контента и фиксированной
карты. Исходники в `tuidungeon/content/data` и `tuidungeon/assets/art` сохранены.
`python -m tuidungeon.content.migrate` проверяет временный пакет до публикации
и отказывается перезаписывать существующий `base`.

`ContentCatalog.load(root)` и `--content-dir` читают прежний формат с короткими
ссылками; старые `docs/templates` оставлены для него. Для нового формата создавайте
объекты в студии, дублируйте файлы из `packs/base` или используйте шаблоны API.
`PackStore.runtime_catalog()` переводит проверенные документы в совместимые
доменные определения; короткие ключи base сохранены для старых Python-примеров.
Для новых клиентов используйте `SessionFactory` и полные ссылки пакетов.
