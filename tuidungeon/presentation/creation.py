"""Step-by-step creation cards and contextual explanations, without terminal I/O."""

import textwrap

from ..application.creation import CreationStep
from ..domain.rules import Ability
from ..domain.skills import SKILLS


STEP_TITLES = {
    CreationStep.RACE: "Раса",
    CreationStep.CLASS: "Класс",
    CreationStep.BACKGROUND: "Предыстория",
    CreationStep.SKILLS: "Навыки класса",
    CreationStep.BONUS_SKILLS: "Дополнительные навыки",
    CreationStep.EXPERTISE: "Экспертиза",
    CreationStep.ROLL: "Броски",
    CreationStep.DISTRIBUTE: "Характеристики",
    CreationStep.CANTRIPS: "Заговоры",
    CreationStep.CONFIRM: "Подтверждение",
}
ABILITY_HINTS = {
    Ability.STRENGTH: "Сила: ближний бой и переноска вещей. Важна воину.",
    Ability.DEXTERITY: "Ловкость: скрытность, инициатива и лёгкое оружие. Важна плуту.",
    Ability.CONSTITUTION: "Телосложение: запас HP. Полезно каждому классу.",
    Ability.INTELLIGENCE: "Интеллект: знания и магические проверки. Важен волшебнику.",
    Ability.WISDOM: "Мудрость: внимательность и понимание окружающего мира.",
    Ability.CHARISMA: "Харизма: влияние, убеждение и общение с существами.",
}
ROLE_HINTS = {
    "warrior": "Ближний бой и защита. Основная характеристика: Сила.",
    "wizard": "Заклинания и знания. Основная характеристика: Интеллект.",
    "rogue": "Скрытность и лёгкое оружие. Основная характеристика: Ловкость.",
}


def creation_button_entries(layout, creation):
    rect = (
        layout.actions
        if creation.step in (CreationStep.ROLL, CreationStep.CONFIRM)
        else layout.main
    )
    first_row = 0 if rect is layout.actions else 3
    for index, button in enumerate(creation.buttons):
        selected = index == creation.cursor
        label = f"[ {button.label} ]" if selected else button.label
        yield (
            rect.x + 1,
            rect.y + first_row + index + 1,
            f"{button.number}) {label}",
            selected,
            rect.width - 2,
        )


def wrap_lines(lines, width):
    return [part for line in lines for part in (textwrap.wrap(line, width) or [""])]


def background_lines(creation, background):
    if background is None:
        return [
            "Для этого класса пока нет привязанной предыстории.",
            "Можно продолжить без неё.",
        ]
    lines = [background.description, "", "Доп. снаряжение:"]
    lines += [
        "- " + creation.catalog.equipment[item].name
        for item in background.starting_items
    ] or ["Нет."]
    lines += ["", "Владения навыками:"]
    lines += ["- " + SKILLS[skill].name for skill in background.skills] or ["Нет."]
    lines += [
        "Тег: " + (", ".join(sorted(background.tags)) or "нет"),
        "Тег открывает особые варианты в событиях.",
    ]
    return lines


def creation_help(creation):
    step, option = creation.step, creation.focused_option
    if creation.focused_button.number == 0:
        return [
            "Вернуться в главное меню."
            if step is CreationStep.RACE
            else "Отменить последнее назначение."
            if step in (CreationStep.DISTRIBUTE, CreationStep.CONFIRM)
            else "Вернуться на предыдущий шаг.",
            "Навигация не перебрасывает кубики.",
        ]
    if step is CreationStep.RACE:
        return (
            [
                option.description,
                "",
                "Расовые бонусы добавятся после распределения чисел.",
            ]
            if option
            else [
                "Раса даёт бонусы к характеристикам, HP или магии.",
                "Назад: главное меню.",
            ]
        )
    if step is CreationStep.CLASS:
        if option:
            return [
                ROLE_HINTS.get(
                    option.id.rsplit(":", 1)[-1], "Выберите подходящую роль героя."
                ),
                option.description,
                "",
                f"Базовые HP: {option.hit_points}",
                "+ модификатор телосложения и расовый бонус.",
                "",
                "Класс задаёт действия, начальные вещи и магию.",
            ]
        return ["Выберите роль героя.", "Назад: выбор расы."]
    if step is CreationStep.BACKGROUND:
        return background_lines(creation, option)
    if step in creation.skill_steps:
        return [
            f"Выберите {creation.skill_count(step)} разных навыка.",
            "Экспертиза удваивает бонус владения."
            if step is CreationStep.EXPERTISE
            else "Владение добавляет бонус мастерства к проверке навыка.",
            "Бонус на 1 уровне: +2. Без владения используется только модификатор характеристики.",
            f"{option.name}: {option.ability.value}" if option else "",
            "Предыстория и раса уже учтены. Повторные владения не складываются.",
            "1–6: отметить / снять; 7: продолжить; PgUp/PgDn: страницы.",
        ]
    if step is CreationStep.CANTRIPS:
        return (
            [
                option.description,
                "",
                "Режим: "
                + ", ".join(
                    "бой" if m == "combat" else "исследование" for m in option.modes
                ),
                f"Дальность: {option.range} кл.",
                *["План: " + text for text in option.pending_effects],
            ]
            if option
            else []
        ) + [
            "",
            f"Выберите {creation.character_class.cantrips_known} разных заговора.",
            "Каждый расходует один общий заряд.",
            "Запас = значение заклинательской характеристики.",
            "7: продолжить; повторный выбор снимает отметку.",
        ]
    if step is CreationStep.ROLL:
        return [
            "Для каждого числа бросаем четыре шестигранных кубика.",
            "Один наименьший не учитываем (в скобках). Сумма остальных — результат.",
            "",
            "Переброс заменяет все шесть чисел.",
            "",
            "Дальше назначите их характеристикам вручную.",
        ]
    if step is CreationStep.DISTRIBUTE:
        ability = list(Ability)[len(creation.assignments)]
        bonus = creation.race.ability_bonuses[list(Ability).index(ability)]
        if creation.background:
            bonus += creation.background.ability_bonuses[list(Ability).index(ability)]
        lines = [
            ABILITY_HINTS[ability],
            "",
            f"Бонус после выбора: {bonus:+d}",
            "Модиф.: (число - 10) // 2",
            "Каждое число — один раз.",
            "",
            "Уже назначено:",
        ]
        lines += [
            f"{a.value}: {creation.rolls[i].total}"
            for a, i in zip(Ability, creation.assignments)
        ] or ["Пока ничего."]
        return lines
    return ["Бонусы уже учтены в листе героя.", ""] + background_lines(
        creation, creation.background
    )


def render_creation(canvas, layout, controller, hero_lines):
    creation = controller.creation
    step_number = creation.steps.index(creation.step) + 1
    step_count = len(creation.steps)
    canvas.box(
        layout.main,
        f"Создание героя | {step_number}/{step_count} {STEP_TITLES[creation.step]}",
    )
    canvas.box(layout.actions, "Выбор и подсказки")
    canvas.box(layout.sidebar, "Как это работает")
    canvas.box(layout.status, "Новый герой")
    canvas.lines(
        layout.status,
        [
            f"Шаг: {step_number}/{step_count}",
            "Уровень: 1",
            "Начало: день 1, 08:00",
            "Деньги/опыт: 0",
        ],
    )
    help_lines = wrap_lines(creation_help(creation), layout.sidebar.width - 2)
    # Keep the complete explanation reachable when user content is lengthy.
    size = layout.sidebar.height - 3
    last = max(0, (len(help_lines) - 1) // size)
    controller.creation_help_pages = last + 1
    page = min(controller.creation_help_page, last)
    canvas.lines(layout.sidebar, help_lines[page * size : (page + 1) * size])
    if last:
        canvas.line(
            layout.sidebar,
            layout.sidebar.height - 3,
            f"H: подсказка {page + 1}/{last + 1}",
        )

    step = creation.step
    if step in (
        CreationStep.RACE,
        CreationStep.CLASS,
        CreationStep.BACKGROUND,
        CreationStep.CANTRIPS,
        *creation.skill_steps,
    ):
        prompt = {
            CreationStep.RACE: "Выберите происхождение героя.",
            CreationStep.CLASS: "Выберите роль в приключении.",
            CreationStep.BACKGROUND: "Кем герой был до приключения?",
            CreationStep.CANTRIPS: "Выберите заговоры, затем 7: продолжить.",
            CreationStep.SKILLS: "Выберите навыки класса, затем 7: продолжить.",
            CreationStep.BONUS_SKILLS: "Замените повторные владения, затем 7: продолжить.",
            CreationStep.EXPERTISE: "Выберите навыки для экспертизы, затем 7: продолжить.",
        }[step]
        canvas.line(layout.main, 0, prompt)
        if step in creation.skill_steps:
            canvas.line(
                layout.main,
                1,
                f"Выбрано: {len(creation.selected_skills(step))}/{creation.skill_count(step)}",
            )
        if step is CreationStep.CANTRIPS:
            canvas.line(
                layout.main,
                1,
                f"Выбрано: {len(creation.cantrips)}/{creation.character_class.cantrips_known}",
            )
        if creation.character_class and step is CreationStep.BACKGROUND:
            canvas.line(layout.main, 1, "Класс: " + creation.character_class.name)
        if creation.page_count > 1:
            canvas.line(
                layout.main,
                layout.main.height - 3,
                f"Страница {creation.selection_page + 1}/{creation.page_count} | PgUp/PgDn",
            )
    elif step is CreationStep.ROLL:
        lines = ["Шесть результатов: 4d6 без меньшего", ""]
        for number, roll in enumerate(creation.rolls, 1):
            discarded_index = roll.dice.index(roll.discarded)
            dice = " ".join(
                f"({value})" if index == discarded_index else str(value)
                for index, value in enumerate(roll.dice)
            )
            lines.append(f"Бросок {number}: {dice} => {roll.total}")
        lines += [
            "",
            "Это ещё не характеристики героя.",
            "Распределите числа на следующем шаге.",
        ]
        canvas.lines(layout.main, lines)
    elif step is CreationStep.DISTRIBUTE:
        ability = list(Ability)[len(creation.assignments)]
        canvas.line(layout.main, 0, f"Назначьте число: {ability.value}")
        canvas.line(
            layout.main,
            1,
            f"Характеристика {len(creation.assignments) + 1}/6. Выберите свободный результат.",
        )
        canvas.line(
            layout.main,
            layout.main.height - 3,
            "Назначены: "
            + ", ".join(str(creation.rolls[i].total) for i in creation.assignments),
        )
    else:
        canvas.lines(layout.main, hero_lines(creation.preview()))

    for x, y, label, _, limit in creation_button_entries(layout, creation):
        canvas.text(x, y, label, limit)
    if step in (CreationStep.ROLL, CreationStep.CONFIRM):
        canvas.line(layout.actions, 3, "WASD / стрелки: выбор | Enter: подтвердить")
        canvas.line(layout.actions, 4, "Backspace: назад | Цифры: быстрый выбор")
    else:
        canvas.lines(
            layout.actions,
            [
                "WASD / стрелки: выбрать кнопку",
                "Enter: подтвердить выбор",
                "Backspace / 0: назад | Q: выход",
                "Цифры также работают. H: листать подсказку.",
                "Слева — выбор, справа — его объяснение.",
            ],
        )
