"""Standalone atlas with Git-portable marks; uses only the Python standard library."""

from functools import partial
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


def validate_tasks(data):
    if not isinstance(data, list) or len(data) > 500:
        raise ValueError("Допускается до 500 заданий")
    result = []
    for task in data:
        if not isinstance(task, dict) or set(task) != {"sheet", "tiles", "prompt"}:
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
        result.append({"sheet": sheet, "tiles": ids, "prompt": prompt.strip()})
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
        "# Задания для пакета tiles",
        "",
        "Создать контент в пакете `tiles` по заданиям ниже. Нумерация ячеек с 1, слева направо, затем следующая строка. Существующие механики копировать, если это указано в задании.",
        "",
    ]
    for index, task in enumerate(tasks, 1):
        columns = 34 if task["sheet"] == "input" else 49
        coordinates = ", ".join(
            f"[{(n - 1) // columns + 1}, {(n - 1) % columns + 1}]"
            for n in task["tiles"]
        )
        lines.extend(
            [
                f"## {index}. Тайлы {ranges(task['tiles'])}",
                "",
                f"Лист: {SHEET_NAMES[task['sheet']]}",
                "",
                f"Координаты [строка, столбец]: {coordinates}",
                "",
                task["prompt"],
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


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, root, progress, **kwargs):
        self.root, self.progress = root, progress
        super().__init__(*args, directory=str(root), **kwargs)

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path in ("/progress.json", "/tasks.json"):
            try:
                tasks = self.path == "/tasks.json"
                path = self.progress.with_name("tasks.json") if tasks else self.progress
                data = (validate_tasks if tasks else validate_progress)(
                    json.loads(path.read_text(encoding="utf-8"))
                )
                self.reply(200, data)
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

    def reply(self, code, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if (
            self.path not in ("/progress.json", "/tasks.json")
            or self.headers.get("Origin") != origin
        ):
            self.reply(403, {"error": "Сохранение разрешено только из просмотрщика"})
            return
        if self.headers.get("Content-Type") != "application/json":
            self.reply(400, {"error": "Нужен JSON"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            tasks = self.path == "/tasks.json"
            if not 0 < length <= (2000000 if tasks else 30000):
                raise ValueError("Некорректный размер данных")
            data = (validate_tasks if tasks else validate_progress)(
                json.loads(self.rfile.read(length))
            )
            path = self.progress.with_name("tasks.json") if tasks else self.progress
            write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            if tasks:
                write_atomic(
                    self.progress.with_name("tile-requests.md"), tasks_markdown(data)
                )
            self.reply(200, data)
        except (ValueError, OSError) as error:
            self.reply(400, {"error": str(error)})


def create_server(progress=ROOT / "tools/tileset-viewer/progress.json"):
    return ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Handler, root=ROOT, progress=Path(progress))
    )


if __name__ == "__main__":
    with create_server() as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Tileset viewer: {url}\nCtrl+C to stop.", flush=True)
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
