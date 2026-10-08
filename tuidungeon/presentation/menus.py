"""Navigation state and reusable action panel descriptions."""

from enum import Enum, auto


class ActionMenu(Enum):
    ROOT = auto()
    ACTIONS = auto()
    REST = auto()
    MAGIC = auto()
    TARGET = auto()
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
    menu = menu or controller.action_menu
    if menu is ActionMenu.META:
        return [
            "1) Сохранить | 2) Загрузить",
            "3) Справка | 4) Выход",
            "5) Настройки",
            "M/Esc: закрыть меню",
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
            f"1) Красться: {mode}",
            "2) Магия",
            "3) Ждать минуту",
            "Backspace: действия | M: меню",
            controller.message,
        ]
    if menu is ActionMenu.REST:
        return [
            "1) Короткий отдых: 1 час",
            "2) Долгий отдых: 8 часов",
            "Короткий: до 1/2 HP; долгий: HP и магия.",
            "Backspace: действия | M: меню",
            controller.message,
        ]
    if menu in (ActionMenu.MAGIC, ActionMenu.TARGET):
        return [
            "1-6) Заклинание" if menu is ActionMenu.MAGIC else "1-6) Живая цель",
            "PgUp/PgDn: страницы",
            "Backspace: назад | M: меню",
            "Успешное применение расходует ход и минуту.",
            controller.message,
        ]
    hint = (
        " | Enter: взаимодействие"
        if controller.engine.nearby_points() and not controller.inventory_focus
        else ""
    )
    return [
        "1) Осмотр" + hint,
        "2) Персонаж",
        "3) Действия | 4) Отдых",
        "WASD: шаг | ↑↓/Enter/F: вещи | M: меню",
        controller.message,
    ]
