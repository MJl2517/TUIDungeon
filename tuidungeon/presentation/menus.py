"""Navigation state and reusable action panel descriptions."""

from enum import Enum, auto


class ActionMenu(Enum):
    ROOT = auto()
    ACTIONS = auto()
    REST = auto()
    MAGIC = auto()
    TARGET = auto()
    SPELL_ITEM = auto()
    SPELL_OPTION = auto()
    META = auto()
    EXIT = auto()


class SidebarTab(Enum):
    INVENTORY = "Инвентарь"
    SPELLS = "Заклинания"
    CONDITIONS = "Состояния"

    def next(self, direction=1):
        tabs = tuple(type(self))
        return tabs[(tabs.index(self) + direction) % len(tabs)]


SHEET_SECTIONS = ("Лист персонажа", "Снаряжение", "Заклинания")
PAGE_SIZE = 6


def action_lines(controller, menu=None):
    workpiece = (
        controller.engine.workpiece(controller.engine.active_craft)
        if controller.engine and controller.engine.active_craft
        else None
    )
    if workpiece:
        work = workpiece.work
        return [
            f"{work.recipe.name[:25]}: {work.progress}/{work.total}",
            f"[{'#' * min(20, work.progress * 20 // work.total)}{'-' * (20 - min(20, work.progress * 20 // work.total))}]",
            "Space / →: ход | Esc: пауза",
            "Один ход работы = 1 минута.",
            controller.message,
        ]
    attempt = getattr(controller.engine, "lockpick_attempt", None)
    if attempt:
        return [
            f"Взлом замка: {attempt.progress}/{attempt.total}",
            "".join(
                "[#]" if i < attempt.progress else "[ ]" for i in range(attempt.total)
            ),
            "Space: следующий ход | Backspace: отмена",
            "Каждое нажатие Space расходует ход и минуту.",
            controller.message,
        ]
    menu = menu or controller.action_menu
    if menu is ActionMenu.META:
        return [
            "1) Сохранить | 2) Загрузить",
            "3) Справка | 4) Настройки",
            "5) Выход",
            "Esc: закрыть меню",
            controller.message,
        ]
    if menu is ActionMenu.EXIT:
        return [
            "1) В главное меню",
            "2) Выйти из игры",
            "Backspace: отменить",
            "Несохранённые изменения будут потеряны.",
            controller.message,
        ]
    if menu is ActionMenu.ACTIONS:
        mode = "выключить" if controller.engine.state.hero.sneaking else "включить"
        return [
            f"1) Красться [Z]: {mode}",
            "2) Магия",
            "3) Ждать минуту",
            "4) Волшебная рука" if controller.engine.active_hand else "",
            "Esc / Backspace: действия",
            controller.message,
        ]
    if menu is ActionMenu.REST:
        return [
            "1) Короткий отдых: 1 час",
            "2) Долгий отдых: 8 часов",
            "Нужна кровать, лежанка или разложенный спальный мешок."
            if not controller.engine.can_long_rest()
            else "Место для сна доступно.",
            "Короткий: 1/2 HP, заговоры +мод.; долгий: всё.",
            "Esc / Backspace: действия",
            controller.message,
        ]
    if menu in (ActionMenu.MAGIC, ActionMenu.TARGET):
        return [
            "1-6) Заклинание" if menu is ActionMenu.MAGIC else "1-6) Живая цель",
            "PgUp/PgDn: страницы",
            "Esc / Backspace: назад",
            "Применение, включая промах: ход и ресурс.",
            controller.message,
        ]
    nearby = controller.engine.nearby_points() and not controller.inventory_focus
    return [
        "1/E: Осмотр | 2: Герой | J: журнал",
        "3: Действия | 4: Отдых | L: логи",
        ("Enter: окружение" if nearby else "Enter: предмет") + " | Space: дверь",
        "I: вещи | M: магия | B: строить | G: подобрать",
        "Z: Скрытность "
        + ("ВКЛ" if controller.engine.state.hero.sneaking else "ВЫКЛ")
        + " | WASD: шаг",
        controller.message,
    ]
