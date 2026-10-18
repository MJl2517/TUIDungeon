"""Standalone atlas with Git-portable marks; uses only the Python standard library."""

from functools import partial
from contextlib import contextmanager
from datetime import datetime, timezone
import argparse
import hashlib
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import os
import webbrowser

ROOT = Path(__file__).resolve().parents[2]
LIMITS = {"mono": 1078, "color": 1078, "input": 816}
SHEET_NAMES = {
    "mono": "Kenney 1-Bit монохромный",
    "color": "Kenney 1-Bit цветной",
    "input": "Kenney Input кнопки",
}


def task_revision(task):
    content = {key: task[key] for key in ("sheet", "tiles", "prompt")}
    return hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()[:16]


def validate_tasks(data):
    if not isinstance(data, list) or len(data) > 5000:
        raise ValueError("Допускается до 5000 заданий, включая архив")
    result, seen, occurrences = [], set(), {}
    fields = {
        "id",
        "sheet",
        "tiles",
        "prompt",
        "status",
        "completed_at",
        "completion_note",
    }
    for task in data:
        if (
            not isinstance(task, dict)
            or set(task) - fields
            or not {"sheet", "tiles", "prompt"} <= set(task)
        ):
            raise ValueError("У задания нужны sheet, tiles и prompt")
        sheet, prompt = task["sheet"], task["prompt"]
        if (
            not isinstance(sheet, str)
            or sheet not in LIMITS
            or not isinstance(prompt, str)
            or not 1 <= len(prompt.strip()) <= 20000
        ):
            raise ValueError(
                "Нужны известный лист и непустое задание до 20000 символов"
            )
        ids = validate_progress(
            {key: task["tiles"] if key == sheet else [] for key in LIMITS}
        )[sheet]
        if not ids:
            raise ValueError("Выберите тайлы для задания")
        item = {"sheet": sheet, "tiles": ids, "prompt": prompt.strip()}
        digest = task_revision(item)
        occurrence = occurrences.get(digest, 0)
        occurrences[digest] = occurrence + 1
        identifier = task.get(
            "id",
            "task_"
            + hashlib.sha256(f"{digest}:{occurrence}".encode()).hexdigest()[:16],
        )
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"task_[a-z0-9]{12,40}", identifier)
            or identifier in seen
        ):
            raise ValueError("Нужен уникальный постоянный ID задания task_…")
        seen.add(identifier)
        state = task.get("status", "pending")
        if state not in ("pending", "completed"):
            raise ValueError("Статус задания: pending или completed")
        item.update(id=identifier, status=state)
        if state == "completed":
            completed_at = task.get("completed_at")
            note = task.get("completion_note", "")
            if (
                not isinstance(completed_at, str)
                or not isinstance(note, str)
                or len(note) > 2000
            ):
                raise ValueError(
                    "Для выполненного задания нужны дата и примечание до 2000 символов"
                )
            if datetime.fromisoformat(completed_at).tzinfo is None:
                raise ValueError("Дата выполнения должна содержать часовой пояс")
            item.update(completed_at=completed_at, completion_note=note)
        elif {"completed_at", "completion_note"} & task.keys():
            raise ValueError("Новое задание не имеет отметки выполнения")
        result.append(item)
    return result


def ranges(ids):
    parts = []
    for value in ids:
        if parts and value == parts[-1][-1] + 1:
            parts[-1].append(value)
        else:
            parts.append([value])
    return ", ".join(
        str(part[0]) if len(part) == 1 else f"{part[0]}–{part[-1]}" for part in parts
    )


def tasks_markdown(tasks):
    lines = [
        "# Новые задания для пакета tiles",
        "",
        "Здесь только незавершённые задания. Архив находится в tasks.json и не требует повторного чтения.",
        "Нумерация ячеек с 1, слева направо, затем следующая строка. Механики копировать, если это указано в задании.",
        "После реализации и проверки завершить только обработанные ID командой, указанной под заданием. Не считать зелёные галочки подтверждением выполнения промпта.",
        "",
    ]
    pending = [task for task in tasks if task.get("status", "pending") == "pending"]
    if not pending:
        lines.extend(
            [
                "Новых заданий нет. Выполненные задания сохранены в архиве просмотрщика.",
                "",
            ]
        )
    for task in pending:
        columns = 34 if task["sheet"] == "input" else 49
        coordinates = ", ".join(
            f"[{(n - 1) // columns + 1}, {(n - 1) % columns + 1}]"
            for n in task["tiles"]
        )
        lines.extend(
            [
                f"## {task['id']} · Тайлы {ranges(task['tiles'])}",
                "",
                f"Лист: {SHEET_NAMES[task['sheet']]}",
                "",
                f"Координаты [строка, столбец]: {coordinates}",
                "",
                task["prompt"],
                "",
                "Завершить после проверки:",
                f"`./tileset-viewer.sh --complete {task['id']}@{task_revision(task)}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_atomic(path, text):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_progress(data):
    if not isinstance(data, dict) or set(data) != set(LIMITS):
        raise ValueError("Нужны списки mono, color и input")
    result = {}
    for sheet, limit in LIMITS.items():
        ids = data[sheet]
        if (
            not isinstance(ids, list)
            or len(ids) > limit
            or any(type(value) is not int or not 1 <= value <= limit for value in ids)
        ):
            raise ValueError(f"Некорректные номера ячеек: {sheet}")
        result[sheet] = sorted(set(ids))
    return result


def implementation_status(root=ROOT):
    """Only visuals assigned to content in packs/tiles count as implemented."""
    root = Path(root)
    if not (root / "packs/tiles").is_dir():
        raise FileNotFoundError("Не найден пакет packs/tiles для сверки атласа")
    usage = {sheet: {} for sheet in LIMITS}
    symbols = {}

    def visual_refs(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                if key == "symbol" and isinstance(nested, str):
                    yield nested
                elif key == "state_symbols" and isinstance(nested, dict):
                    yield from nested.values()
                else:
                    yield from visual_refs(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from visual_refs(nested)

    for path in sorted((root / "packs/tiles").glob("*/*.json")):
        if path.parent.name in {"symbols", "maps", "recipes", "art"}:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        owner = dict(
            ref=f"tiles:{doc['id']}", name=doc["name"], category=path.parent.name
        )
        for ref in sorted(set(visual_refs(doc))):
            if not isinstance(ref, str) or not re.fullmatch(
                r"[a-z][a-z0-9_]*:[a-z][a-z0-9_]*", ref
            ):
                raise ValueError(f"{path}: некорректная ссылка на символ {ref}")
            if ref not in symbols:
                pack, identifier = ref.split(":")
                symbol_path = root / "packs" / pack / "symbols" / (identifier + ".json")
                symbols[ref] = json.loads(symbol_path.read_text(encoding="utf-8"))
            source = symbols[ref].get("source") or {}
            location = source.get("location", "").replace("\\", "/")
            if "assets/1_bit_input/" in location:
                sheet, columns = "input", 34
            elif "assets/1 bit/" in location:
                sheet, columns = ("color" if "colored-" in location else "mono"), 49
            else:
                continue
            xy = source.get("coordinates")
            if (
                not isinstance(xy, list)
                or len(xy) != 2
                or any(type(v) is not int for v in xy)
                or not (0 <= xy[0] < columns and 0 <= xy[1] < LIMITS[sheet] // columns)
            ):
                raise ValueError(f"{ref}: некорректные координаты исходного атласа")
            owners = usage[sheet].setdefault(str(xy[1] * columns + xy[0] + 1), [])
            if owner not in owners:
                owners.append(owner)
    return dict(
        progress={sheet: sorted(map(int, cells)) for sheet, cells in usage.items()},
        usage=usage,
    )


def sync_progress(path, root=ROOT):
    status = implementation_status(root)
    text = json.dumps(status["progress"], ensure_ascii=False, indent=2) + "\n"
    path = Path(path)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        write_atomic(path, text)
    return status


class TaskConflict(ValueError):
    pass


class TaskStore:
    """One portable source of truth; Markdown is a disposable pending-only view."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()

    @contextmanager
    def locked(self):
        # The viewer and the agent CLI may write from different processes.
        with self.lock, self.path.with_name(".tasks.lock").open("a+b") as stream:
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def read(self):
        return validate_tasks(json.loads(self.path.read_text(encoding="utf-8")))

    @staticmethod
    def version(tasks):
        return (
            '"'
            + hashlib.sha256(
                json.dumps(tasks, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest()
            + '"'
        )

    def sync_markdown(self, tasks):
        path = self.path.with_name("tile-requests.md")
        text = tasks_markdown(tasks)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            write_atomic(path, text)

    def snapshot(self):
        with self.locked():
            tasks = self.read()
            self.sync_markdown(tasks)
            return tasks, self.version(tasks)

    def write(self, tasks):
        write_atomic(self.path, json.dumps(tasks, ensure_ascii=False, indent=2) + "\n")
        self.sync_markdown(tasks)
        return tasks, self.version(tasks)

    def check_version(self, tasks, expected):
        if expected != self.version(tasks):
            raise TaskConflict(
                "Задания изменились в другой вкладке или агентом. Обновите список; несохранённый черновик остаётся на странице."
            )

    def save(self, raw, expected):
        with self.locked():
            current = self.read()
            self.check_version(current, expected)
            tasks = validate_tasks(raw)
            archived = {t["id"]: t for t in current if t["status"] == "completed"}
            incoming = {t["id"]: t for t in tasks}
            if any(incoming.get(key) != task for key, task in archived.items()):
                raise TaskConflict(
                    "Выполненные задания защищены от изменения и удаления. Создайте отдельную доработку."
                )
            if any(
                t["status"] == "completed" and t["id"] not in archived for t in tasks
            ):
                raise ValueError(
                    "Используйте действие «Выполнено», чтобы завершить задание"
                )
            return self.write(tasks)

    def complete(self, ids, expected=None, revisions=None, note=""):
        if (
            not isinstance(ids, list)
            or not ids
            or any(not isinstance(x, str) for x in ids)
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("Выберите разные ID заданий для завершения")
        if not isinstance(note, str) or len(note) > 2000:
            raise ValueError("Примечание ограничено 2000 символами")
        with self.locked():
            tasks = self.read()
            if revisions is None:
                self.check_version(tasks, expected)
            by_id = {t["id"]: t for t in tasks}
            for identifier in ids:
                if identifier not in by_id:
                    raise TaskConflict("Неизвестное задание: " + identifier)
                if revisions is not None and revisions.get(identifier) != task_revision(
                    by_id[identifier]
                ):
                    raise TaskConflict(
                        "Формулировка задания изменилась; перечитайте новую версию: "
                        + identifier
                    )
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for identifier in ids:
                task = by_id[identifier]
                if task["status"] != "completed":
                    task.update(
                        status="completed", completed_at=timestamp, completion_note=note
                    )
            return self.write(tasks)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, root, progress, tasks, **kwargs):
        self.root, self.progress, self.tasks = root, progress, tasks
        super().__init__(*args, directory=str(root), **kwargs)

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path in ("/progress.json", "/tile-status.json", "/tasks.json"):
            try:
                tasks = self.path == "/tasks.json"
                if tasks:
                    data, version = self.tasks.snapshot()
                else:
                    data = sync_progress(self.progress, self.root)
                    if self.path == "/progress.json":
                        data = data["progress"]
                    version = None
                self.reply(200, data, version)
            except (OSError, ValueError) as error:
                self.reply(500, {"error": str(error)})
            return
        if self.path == "/":
            self.path = "/tools/tileset-viewer/index.html"
        target = Path(self.translate_path(self.path)).resolve()
        if not target.is_relative_to(self.root) or not (
            target == self.root / "tools/tileset-viewer/index.html"
            or target.is_relative_to(self.root / "assets")
            and target.suffix == ".png"
        ):
            self.send_error(404)
            return
        super().do_GET()

    def reply(self, code, data, version=None):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        if version:
            self.send_header("ETag", version)
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if (
            self.path not in ("/progress.json", "/tasks.json", "/tasks/complete")
            or self.headers.get("Origin") != origin
        ):
            self.reply(403, {"error": "Сохранение разрешено только из просмотрщика"})
            return
        if self.headers.get("Content-Type") != "application/json":
            self.reply(400, {"error": "Нужен JSON"})
            return
        if self.path == "/progress.json":
            self.reply(
                405,
                {
                    "error": "Отметки определяются автоматически по пакету tiles. Обновите страницу просмотрщика."
                },
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 20000000:
                raise ValueError("Некорректный размер данных")
            raw = json.loads(self.rfile.read(length))
            if self.path == "/tasks.json":
                data, version = self.tasks.save(raw, self.headers.get("If-Match"))
            elif self.path == "/tasks/complete":
                if not isinstance(raw, dict) or set(raw) - {"ids", "note"}:
                    raise ValueError("Нужны ids и необязательное note")
                data, version = self.tasks.complete(
                    raw.get("ids"),
                    self.headers.get("If-Match"),
                    note=raw.get("note", ""),
                )
            self.reply(200, data, version)
        except TaskConflict as error:
            self.reply(409, {"error": str(error)})
        except (ValueError, OSError) as error:
            self.reply(400, {"error": str(error)})


def create_server(progress=ROOT / "tools/tileset-viewer/progress.json", *, root=ROOT):
    progress = Path(progress)
    tasks = TaskStore(progress.with_name("tasks.json"))
    tasks.snapshot()
    return ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(Handler, root=Path(root), progress=progress, tasks=tasks),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list-pending",
        action="store_true",
        help="Показать только ID, номера тайлов и версии новых заданий",
    )
    parser.add_argument(
        "--complete",
        nargs="+",
        metavar="ID@REVISION",
        help="Завершить проверенные задания из рабочего MD",
    )
    parser.add_argument("--note", default="", help="Краткий результат выполнения")
    parser.add_argument(
        "--sync-progress",
        action="store_true",
        help="Сверить отметки атласа с назначениями в packs/tiles",
    )
    args = parser.parse_args()
    store = TaskStore(ROOT / "tools/tileset-viewer/tasks.json")
    try:
        if args.sync_progress:
            status = sync_progress(ROOT / "tools/tileset-viewer/progress.json")
            print(
                "Пакет tiles: "
                + ", ".join(
                    f"{sheet}: {len(ids)}" for sheet, ids in status["progress"].items()
                )
            )
            return
        if args.complete:
            tokens = [token.rsplit("@", 1) for token in args.complete]
            if any(len(token) != 2 for token in tokens):
                raise ValueError("Скопируйте ID@версию из tile-requests.md")
            revisions = dict(tokens)
            store.complete(
                [token[0] for token in tokens], revisions=revisions, note=args.note
            )
            sync_progress(ROOT / "tools/tileset-viewer/progress.json")
            print("В архив перенесены: " + ", ".join(revisions))
            return
        if args.list_pending:
            tasks, _ = store.snapshot()
            print(
                json.dumps(
                    [
                        dict(
                            id=t["id"],
                            sheet=t["sheet"],
                            tiles=t["tiles"],
                            revision=task_revision(t),
                        )
                        for t in tasks
                        if t["status"] == "pending"
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        with create_server() as server:
            url = f"http://127.0.0.1:{server.server_port}/"
            print(f"Tileset viewer: {url}\nCtrl+C to stop.", flush=True)
            webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
