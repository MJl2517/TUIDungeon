"""Run with python3 -m tuidungeon [--seed INTEGER]."""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TUI Dungeon — пошаговое исследование ASCII-подземелья"
    )
    parser.add_argument(
        "--seed", type=int, help="Начальное значение генератора случайных бросков"
    )
    parser.add_argument(
        "--symbols",
        choices=("ascii", "unicode"),
        default="ascii",
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
    parser.add_argument("--map", default="base:dungeon", help="Карта pack_id:local_id")
    parser.add_argument(
        "--test-map",
        nargs="?",
        const="",
        metavar="PACK:MAP",
        help="Сразу открыть карту с готовым героем; без аргумента используется --map",
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
    if args.test_map is not None:
        if args.studio:
            parser.error(
                "--test-map запускает терминальную игру и несовместим с --studio"
            )
        if args.test_map:
            args.map = args.test_map
    if not 1 <= args.port <= 65535:
        parser.error("Порт должен быть от 1 до 65535")
    if args.studio:
        try:
            from .tooling.server import serve

            serve(args.port, not args.no_browser, args.packs_dir)
            return 0
        except (ValueError, OSError, ImportError) as error:
            print(f"Ошибка студии: {error}. Установка: ./setup.sh", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            return 0
    from .content.catalog import ContentCatalog, ContentError

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
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            "Запустите игру в интерактивном терминале: python3 -m tuidungeon",
            file=sys.stderr,
        )
        return 1
    try:
        import curses
    except ImportError:
        print(
            "Не найден curses. Используйте Python с curses в Linux/macOS.",
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
            args.test_map is not None,
            args.save_file,
        )
    except KeyboardInterrupt:
        return 0
    except curses.error as error:
        print(f"Не удалось открыть терминальный интерфейс: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
