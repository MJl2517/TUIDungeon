"""Run with python3 -m tuidungeon [--seed INTEGER]."""

import argparse
import sys


def main() -> int:
    setup_command = ".\\setup.bat" if sys.platform == "win32" else "./setup.sh"
    run_command = ".\\run.bat" if sys.platform == "win32" else "./run.sh"
    if sys.version_info < (3, 11):
        print("Нужен Python 3.11 или новее.", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(
        description="TUI Dungeon — пошаговое исследование ASCII-подземелья"
    )
    parser.add_argument(
        "--seed", type=int, help="Начальное значение генератора случайных бросков"
    )
    parser.add_argument(
        "--symbols",
        choices=("ascii", "unicode"),
        default=None,
        help="Набор символов карты и рамок",
    )
    parser.add_argument(
        "--content-dir", help="Папка полного каталога JSON-контента вместо встроенного"
    )
    parser.add_argument(
        "--validate-content",
        action="store_true",
        help="Проверить контент и выйти без открытия TUI",
    )
    parser.add_argument(
        "--studio", action="store_true", help="Запустить локальную студию"
    )
    parser.add_argument(
        "--terminal", action="store_true", help="Запустить curses вместо окна tcod"
    )
    parser.add_argument("--map", default="base:dungeon", help="Карта pack_id:local_id")
    test_modes = parser.add_mutually_exclusive_group()
    test_modes.add_argument(
        "--test-map",
        nargs="?",
        const="",
        metavar="PACK:MAP",
        help="Сразу открыть карту с готовым героем; без аргумента используется --map",
    )
    test_modes.add_argument(
        "--test-wizard",
        nargs="?",
        const="",
        metavar="PACK:MAP",
        help="Сразу открыть карту с волшебником, знающим все заклинания; без аргумента используется --map",
    )
    parser.add_argument(
        "--test-class",
        metavar="PACK:CLASS",
        help="Класс готового героя для --test-map (например, base:rogue)",
    )
    parser.add_argument("--packs-dir", help="Папка подключаемых пакетов")
    parser.add_argument(
        "--save-file", help="Файл быстрого сохранения вместо saves/quicksave.json"
    )
    parser.add_argument("--port", type=int, default=8765, help="Порт студии")
    parser.add_argument(
        "--no-browser", action="store_true", help="Не открывать браузер автоматически"
    )
    args = parser.parse_args()
    args.symbols = args.symbols or ("ascii" if args.terminal else "unicode")
    if args.test_class is not None and args.test_map is None:
        parser.error("--test-class используется вместе с --test-map")
    test_map = args.test_map is not None or args.test_wizard is not None
    test_profile = "wizard" if args.test_wizard is not None else None
    if test_map:
        if args.studio:
            parser.error("Тестовый запуск карты несовместим с --studio")
        args.map = args.test_wizard or args.test_map or args.map
    if not 1 <= args.port <= 65535:
        parser.error("Порт должен быть от 1 до 65535")
    if args.studio:
        try:
            from .tooling.server import serve

            serve(args.port, not args.no_browser, args.packs_dir)
            return 0
        except (ValueError, OSError, ImportError) as error:
            print(
                f"Ошибка студии: {error}. Установка: {setup_command}",
                file=sys.stderr,
            )
            return 1
        except KeyboardInterrupt:
            return 0
    try:
        from .content.catalog import ContentCatalog, ContentError
    except ImportError as error:
        print(
            f"Не найдены зависимости: {error}. Выполните {setup_command}",
            file=sys.stderr,
        )
        return 1

    try:
        store = None
        if args.content_dir:
            catalog = ContentCatalog.load(args.content_dir)
        else:
            from .content.packs import PackStore

            store = PackStore(args.packs_dir) if args.packs_dir else PackStore()
            if not args.validate_content:
                store.get("maps", args.map)
            catalog = store.runtime_catalog()
        if args.test_class is not None:
            from .content.packs import runtime_key

            if store and ":" in args.test_class:
                store.get("classes", args.test_class)
            args.test_class = runtime_key(args.test_class)
            if args.test_class not in catalog.classes:
                raise ValueError(f"Неизвестный тестовый класс: {args.test_class}")
        from .presentation.symbols import ArtLibrary

        for monster in catalog.monsters.values():
            if monster.art:
                ArtLibrary().load(monster.art)
    except (ContentError, OSError, ValueError, ImportError) as error:
        print(f"Ошибка контента: {error}", file=sys.stderr)
        return 1
    if args.validate_content:
        if store:
            from .content.schemas import MODELS as models

            print(
                "Пакеты проверены: "
                + ", ".join(f"{m.id} {m.version}" for m in store.manifests.values())
            )
            print(
                "Документы: "
                + ", ".join(
                    f"{category}: {sum(c == category for c, _ in store.documents)}"
                    for category in models
                )
            )
            return 0
        print(
            "Контент проверен: "
            + ", ".join(
                f"{name}: {len(getattr(catalog, name))}"
                for name in catalog.__dataclass_fields__
            )
        )
        return 0
    if not catalog.races or not catalog.classes:
        print(
            "Ошибка контента: для игры нужны хотя бы одна раса и один класс.",
            file=sys.stderr,
        )
        return 1
    if test_profile == "wizard" and "wizard" not in catalog.classes:
        print("Ошибка контента: для --test-wizard нужен класс wizard.", file=sys.stderr)
        return 1
    if not args.terminal:
        try:
            from .presentation.window import run as run_window

            run_window(
                args.seed,
                args.symbols,
                catalog,
                args.map if store else None,
                store,
                test_map,
                args.save_file,
                test_profile=test_profile,
                test_class=args.test_class,
            )
            return 0
        except (ImportError, OSError, RuntimeError) as error:
            print(
                f"Не удалось открыть игровое окно: {error}. "
                f"Установка: {setup_command}; терминальный режим: {run_command} --terminal",
                file=sys.stderr,
            )
            return 1
        except KeyboardInterrupt:
            return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            f"Запустите игру в интерактивном терминале: {run_command} --terminal",
            file=sys.stderr,
        )
        return 1
    try:
        import curses
    except ImportError:
        print(
            f"Не найден curses. Выполните {setup_command}; "
            + (
                "на Windows он установит windows-curses."
                if sys.platform == "win32"
                else "нужен Python с поддержкой curses."
            ),
            file=sys.stderr,
        )
        return 1
    from .presentation.tui import run

    try:
        curses.wrapper(
            run,
            args.seed,
            args.symbols,
            catalog,
            args.map if store else None,
            store,
            test_map,
            args.save_file,
            test_profile=test_profile,
            test_class=args.test_class,
        )
    except KeyboardInterrupt:
        return 0
    except curses.error as error:
        print(f"Не удалось открыть терминальный интерфейс: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
