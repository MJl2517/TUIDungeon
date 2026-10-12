import { createContext, useContext, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "./api";
import { Doc, Entry, History, Point, color, line, rectangle } from "./model";
import {
  blankMask,
  drawSymbol,
  fillMask,
  paintMask,
  symbolCanvas,
  transformMask,
  visual,
} from "./symbolModel";
import { ContentBrowser } from "./ContentBrowser";

export const SymbolContext = createContext<{
  assets: Record<string, Doc>;
  entries: Entry[];
  packs: string[];
  refresh: () => Promise<unknown>;
  open: (category: string, ref: string) => void;
}>({
  assets: {},
  entries: [],
  packs: ["base"],
  refresh: async () => {},
  open: () => {},
});

export function SymbolPreview({
  symbol,
  doc,
  size = 32,
  tint = "#edc875",
  background = "transparent",
  text = false,
}: {
  symbol?: string;
  doc?: Doc;
  size?: number;
  tint?: string;
  background?: string;
  text?: boolean;
}) {
  const { assets } = useContext(SymbolContext),
    canvas = useRef<HTMLCanvasElement>(null);
  const image = doc ?? (symbol ? assets["symbols/" + symbol] : undefined);
  useEffect(() => {
    const ctx = canvas.current?.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, 16, 16);
    if (image) drawSymbol(ctx, image, 0, 0, 16, 16, tint);
  }, [image, tint]);
  return text ? (
    <span className="symbol-text" style={{ color: tint }}>
      {image?.glyph ?? "?"}
    </span>
  ) : (
    <canvas
      ref={canvas}
      width={16}
      height={16}
      aria-label={image?.name ?? "Нет символа"}
      className="symbol-preview"
      style={{ width: size, height: size, background }}
    />
  );
}

export function SymbolPicker({
  value,
  onChoose,
  onClose,
}: {
  value?: string;
  onChoose: (ref: string) => void;
  onClose: () => void;
}) {
  const context = useContext(SymbolContext),
    dialog = useRef<HTMLDialogElement>(null);
  const [editing, setEditing] = useState<Doc | null>(null),
    [pack, setPack] = useState(context.packs[0] ?? "base"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const history = useRef<History<Doc> | null>(null);
  function edit(doc: Doc) {
    history.current = new History(structuredClone(doc));
    setEditing(history.current.present);
  }
  function change(doc: Doc) {
    history.current!.commit(doc);
    setEditing(doc);
  }
  const [original, setOriginal] = useState<Entry | null>(null);
  useEffect(() => {
    const prior = document.activeElement as HTMLElement;
    dialog.current?.showModal();
    return () => {
      dialog.current?.close();
      prior?.focus();
    };
  }, []);
  async function save() {
    if (!editing || busy) return;
    setBusy(true);
    setError("");
    try {
      if (!editing.reviewed)
        throw Error(
          "Укажите название, категорию и текстовый знак, затем подтвердите готовность символа.",
        );
      const ref = pack + ":" + editing.id;
      await api(
        "/documents/symbols/" + ref,
        {
          document: editing,
          version: original?.ref === ref ? original.version : null,
        },
        "PUT",
      );
      await context.refresh();
      onChoose(ref);
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return createPortal(
    <dialog
      ref={dialog}
      className="symbol-dialog"
      aria-label="Библиотека символов"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onKeyDown={(e) => e.stopPropagation()}
    >
      <header>
        <h2>{editing ? "Редактор символа" : "Библиотека символов"}</h2>
        <button onClick={onClose}>Esc · Закрыть</button>
      </header>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {editing ? (
        <>
          <div className="toolbar">
            <label>
              Пакет{" "}
              <select
                aria-label="Пакет символа"
                value={pack}
                disabled={!!original}
                onChange={(e) => setPack(e.target.value)}
              >
                {context.packs.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
            <label>
              ID{" "}
              <input
                aria-label="ID символа"
                value={editing.id}
                disabled={!!original}
                onChange={(e) => change({ ...editing, id: e.target.value })}
              />
            </label>
            <button onClick={() => setEditing(null)}>← Библиотека</button>
            <button
              className="primary"
              disabled={busy}
              onClick={() => void save()}
            >
              Сохранить и назначить
            </button>
          </div>
          <SymbolEditor
            doc={editing}
            onChange={change}
            onUndo={() => {
              history.current?.undo();
              setEditing(history.current!.present);
            }}
            onRedo={() => {
              history.current?.redo();
              setEditing(history.current!.present);
            }}
            notify={setError}
          />
        </>
      ) : (
        <>
          <p className="hint">
            Один символ — рисунок 16×16 и знак для терминала. Неразобранные
            изображения нужно согласовать перед назначением.
          </p>
          <div className="toolbar">
            <button
              onClick={() => {
                setOriginal(null);
                edit({
                  id: "symbol_" + Date.now(),
                  name: "Новый символ",
                  glyph: "?",
                  group: "Собственные",
                  tags: [],
                  reviewed: false,
                  pixels: blankMask(),
                });
              }}
            >
              + Нарисовать символ
            </button>
            {value && (
              <>
                <button
                  onClick={() => {
                    const d = context.assets["symbols/" + value];
                    if (!d) return;
                    setOriginal(null);
                    setPack(value.split(":")[0]);
                    edit({
                      ...d,
                      id: d.id + "_copy",
                      name: d.name + " — копия",
                    });
                  }}
                >
                  Дублировать и назначить
                </button>
                <button
                  onClick={() => {
                    context.open("symbols", value);
                    onClose();
                  }}
                >
                  Открыть общий символ
                </button>
              </>
            )}
          </div>
          <ContentBrowser
            entries={context.entries.filter((e) => e.category === "symbols")}
            assets={context.assets}
            category="symbols"
            selected={value}
            onChoose={(e) => {
              const d = context.assets["symbols/" + e.ref];
              if (d?.reviewed) {
                onChoose(e.ref);
                onClose();
              } else if (d) {
                setOriginal(e);
                setPack(e.ref.split(":")[0]);
                edit(d);
              }
            }}
          />
        </>
      )}
    </dialog>,
    document.body,
  );
}

export function SymbolSelect({
  value,
  onChange,
  label = "Символ из библиотеки",
}: {
  value?: string | null;
  onChange: (ref: string) => void;
  label?: string;
}) {
  const { assets } = useContext(SymbolContext),
    [open, setOpen] = useState(false);
  const chosen = value ? assets["symbols/" + value] : null;
  return (
    <>
      <button
        type="button"
        className="symbol-select"
        aria-label={label}
        onClick={() => setOpen(true)}
      >
        <SymbolPreview symbol={value ?? undefined} />
        <span>
          <strong>{chosen?.name ?? "Выбрать символ"}</strong>
          <small>
            {value ?? "Из общей библиотеки"}
            {chosen ? " · " + chosen.glyph : ""}
          </small>
        </span>
        <span>⌕</span>
      </button>
      {open && (
        <SymbolPicker
          value={value ?? undefined}
          onChoose={onChange}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

const tools = [
  ["brush", "B · Кисть"],
  ["erase", "E · Ластик"],
  ["fill", "F · Заливка"],
  ["line", "L · Линия"],
  ["rect", "R · Прямоугольник"],
  ["select", "S · Выделить"],
  ["move", "V · Перенести"],
  ["paste", "Вставить"],
];
export function SymbolEditor({
  doc,
  onChange,
  onUndo,
  onRedo,
  notify,
  usages = [],
}: {
  usages?: Doc[];
  doc: Doc;
  onChange: (d: Doc) => void;
  onUndo: () => void;
  onRedo: () => void;
  notify: (s: string) => void;
}) {
  const { packs, refresh, open } = useContext(SymbolContext);
  const [tool, setTool] = useState("brush"),
    [zoom, setZoom] = useState(20),
    [grid, setGrid] = useState(true),
    [selection, setSelection] = useState<Point[]>([]),
    [clipboard, setClipboard] = useState<{
      rows: string[];
      w: number;
      h: number;
    } | null>(null),
    [preview, setPreview] = useState<string[] | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null),
    stroke = useRef<{
      start: Point;
      last: Point;
      base: string[];
      next: string[];
    } | null>(null);
  const shown = preview ?? doc.pixels;
  const [image, setImage] = useState<{ data: ImageData; url: string } | null>(
      null,
    ),
    [threshold, setThreshold] = useState(127),
    [mode, setMode] = useState("alpha"),
    [confirmed, setConfirmed] = useState(false),
    [picked, setPicked] = useState<number[]>([]),
    [targetPack, setTargetPack] = useState(packs[0] ?? "base"),
    [importing, setImporting] = useState(false);
  useEffect(() => {
    const ctx = canvas.current!.getContext("2d")!;
    ctx.fillStyle = "#11151b";
    ctx.fillRect(0, 0, 16 * zoom, 16 * zoom);
    shown.forEach((row: string, y: number) =>
      Array.from(row).forEach((c, x) => {
        ctx.fillStyle =
          c === "1" ? "#edc875" : (x + y) % 2 ? "#202a36" : "#19212b";
        ctx.fillRect(x * zoom, y * zoom, zoom, zoom);
      }),
    );
    if (grid) {
      ctx.strokeStyle = "#8090a044";
      for (let n = 0; n <= 16; n++) {
        ctx.beginPath();
        ctx.moveTo(n * zoom, 0);
        ctx.lineTo(n * zoom, 16 * zoom);
        ctx.moveTo(0, n * zoom);
        ctx.lineTo(16 * zoom, n * zoom);
        ctx.stroke();
      }
    }
    ctx.fillStyle = "#658fcb88";
    selection.forEach((p) => ctx.fillRect(p.x * zoom, p.y * zoom, zoom, zoom));
  }, [shown, zoom, grid, selection]);
  const commit = (pixels: string[]) => {
    onChange({ ...doc, pixels });
    setPreview(null);
  };
  const point = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(
        0,
        Math.min(15, Math.floor(((e.clientX - r.left) * 16) / r.width)),
      ),
      y: Math.max(
        0,
        Math.min(15, Math.floor(((e.clientY - r.top) * 16) / r.height)),
      ),
    };
  };
  function copy(): { rows: string[]; w: number; h: number } | null {
    if (!selection.length) return null;
    const xs = selection.map((p) => p.x),
      ys = selection.map((p) => p.y),
      x = Math.min(...xs),
      y = Math.min(...ys),
      w = Math.max(...xs) - x + 1,
      h = Math.max(...ys) - y + 1;
    const clip = {
      rows: doc.pixels.slice(y, y + h).map((r: string) => r.slice(x, x + w)),
      w,
      h,
    };
    setClipboard(clip);
    return clip;
  }
  function down(e: React.PointerEvent<HTMLCanvasElement>) {
    if (e.button !== 0) return;
    e.currentTarget.focus();
    e.currentTarget.setPointerCapture(e.pointerId);
    const p = point(e);
    if (tool === "fill") {
      commit(fillMask(doc.pixels, p, "1"));
      return;
    }
    if (tool === "paste" || tool === "move") {
      const clip = tool === "move" ? copy() : clipboard;
      if (!clip) {
        notify("Сначала выделите и скопируйте область");
        return;
      }
      let next =
        tool === "move" ? paintMask(doc.pixels, selection, "0") : doc.pixels;
      clip.rows.forEach((row, y) =>
        Array.from(row).forEach((v, x) => {
          next = paintMask(next, [{ x: p.x + x, y: p.y + y }], v);
        }),
      );
      commit(next);
      return;
    }
    const next =
      tool === "select"
        ? doc.pixels
        : paintMask(doc.pixels, [p], tool === "erase" ? "0" : "1");
    stroke.current = { start: p, last: p, base: doc.pixels, next };
    if (tool === "select") setSelection([p]);
    else setPreview(next);
  }
  function drag(e: React.PointerEvent<HTMLCanvasElement>) {
    const s = stroke.current;
    if (!s) return;
    const p = point(e);
    if (tool === "select") setSelection(rectangle(s.start, p, true));
    else {
      s.next =
        tool === "line"
          ? paintMask(s.base, line(s.start, p), "1")
          : tool === "rect"
            ? paintMask(s.base, rectangle(s.start, p), "1")
            : paintMask(s.next, line(s.last, p), tool === "erase" ? "0" : "1");
      setPreview(s.next);
    }
    s.last = p;
  }
  function up() {
    const s = stroke.current;
    if (!s) return;
    stroke.current = null;
    if (tool !== "select") commit(s.next);
  }
  function exportPNG() {
    symbolCanvas(doc).toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob),
        a = document.createElement("a");
      a.href = url;
      a.download = doc.id + ".png";
      a.click();
      URL.revokeObjectURL(url);
    }, "image/png");
  }
  async function readPNG(file: File) {
    try {
      const header = new Uint8Array(await file.slice(0, 8).arrayBuffer());
      if ([137, 80, 78, 71, 13, 10, 26, 10].some((v, i) => header[i] !== v))
        throw Error(
          "Выберите PNG: другие форматы изображений не поддерживаются.",
        );
      const bitmap = await createImageBitmap(file);
      if (
        bitmap.width % 16 ||
        bitmap.height % 16 ||
        bitmap.width < 16 ||
        bitmap.height < 16 ||
        bitmap.width > 1024 ||
        bitmap.height > 1024
      ) {
        bitmap.close();
        throw Error(
          "PNG должен иметь размеры, кратные 16 (не больше 1024×1024). Масштабирование не выполняется.",
        );
      }
      const c = document.createElement("canvas");
      c.width = bitmap.width;
      c.height = bitmap.height;
      const ctx = c.getContext("2d")!;
      ctx.drawImage(bitmap, 0, 0);
      bitmap.close();
      const data = ctx.getImageData(0, 0, c.width, c.height);
      setImage({ data, url: c.toDataURL() });
      setPicked([0]);
      setConfirmed(false);
      setMode(
        data.data.some((v, i) => i % 4 === 3 && v < 255)
          ? "alpha"
          : "brightness",
      );
    } catch (e) {
      notify(String(e));
    }
  }
  function importedMask(index: number) {
    const { data } = image!,
      cols = data.width / 16;
    return Array.from({ length: 16 }, (_, y) =>
      Array.from({ length: 16 }, (_, x) => {
        const i =
          ((Math.floor(index / cols) * 16 + y) * data.width +
            (index % cols) * 16 +
            x) *
          4;
        return (mode === "alpha"
          ? data.data[i + 3]
          : Math.max(data.data[i], data.data[i + 1], data.data[i + 2])) >
          threshold && data.data[i + 3] > 0
          ? "1"
          : "0";
      }).join(""),
    );
  }
  async function importMany() {
    if (!image || !picked.length || !confirmed || importing) return;
    setImporting(true);
    try {
      const stamp = Date.now();
      for (const n of picked) {
        const id = `import_${stamp}_${n}`;
        await api(
          "/documents/symbols/" + targetPack + ":" + id,
          {
            version: null,
            document: {
              id,
              name: `Импорт [${n % (image.data.width / 16)}, ${Math.floor(n / (image.data.width / 16))}]`,
              glyph: "?",
              group: "Неразобранное",
              reviewed: false,
              tags: [],
              pixels: importedMask(n),
              source: {
                name: "Импорт PNG",
                license: "Указать при согласовании",
              },
            },
          },
          "PUT",
        );
      }
      await refresh();
      setImage(null);
      notify(
        "Изображения добавлены в «Неразобранное»; согласуйте названия и текстовые знаки.",
      );
    } catch (e) {
      notify(String(e));
    } finally {
      setImporting(false);
    }
  }
  return (
    <div className="symbol-editor">
      <div className="symbol-properties">
        <label>
          Название{" "}
          <input
            aria-label="Название символа"
            value={doc.name}
            onChange={(e) => onChange({ ...doc, name: e.target.value })}
          />
        </label>
        <label>
          Категория{" "}
          <input
            aria-label="Категория символа"
            value={doc.group}
            onChange={(e) => onChange({ ...doc, group: e.target.value })}
          />
        </label>
        <label>
          Текстовый знак{" "}
          <input
            aria-label="Текстовый знак символа"
            maxLength={2}
            value={doc.glyph}
            onChange={(e) => onChange({ ...doc, glyph: e.target.value })}
          />
        </label>
        <label>
          Теги (через запятую){" "}
          <input
            aria-label="Теги символа"
            value={(doc.tags ?? []).join(", ")}
            onChange={(e) =>
              onChange({
                ...doc,
                tags: e.target.value
                  .split(",")
                  .map((t) => t.trim())
                  .filter(Boolean),
              })
            }
          />
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={doc.reviewed}
            onChange={(e) => onChange({ ...doc, reviewed: e.target.checked })}
          />
          Название и текстовый знак согласованы
        </label>
      </div>
      <div className="toolbar">
        {tools.map(([id, label]) => (
          <button
            key={id}
            className={tool === id ? "selected" : ""}
            onClick={() => setTool(id)}
          >
            {label}
          </button>
        ))}
        <button onClick={() => copy()}>Копировать</button>
        <button onClick={onUndo}>Отменить</button>
        <button onClick={onRedo}>Повторить</button>
      </div>
      <div className="symbol-workspace">
        <canvas
          ref={canvas}
          width={16 * zoom}
          height={16 * zoom}
          aria-label="Пиксельный холст 16×16"
          tabIndex={0}
          onPointerDown={down}
          onPointerMove={drag}
          onPointerUp={up}
          onPointerCancel={() => {
            stroke.current = null;
            setPreview(null);
          }}
          onKeyDown={(e) => {
            const k = e.key.toLowerCase();
            if ((e.ctrlKey || e.metaKey) && k === "c") {
              e.preventDefault();
              copy();
            } else if ((e.ctrlKey || e.metaKey) && k === "v") {
              e.preventDefault();
              setTool("paste");
            } else if ((e.ctrlKey || e.metaKey) && k === "z") {
              e.preventDefault();
              e.stopPropagation();
              e.shiftKey ? onRedo() : onUndo();
            } else if (!e.ctrlKey && !e.metaKey) {
              const t: Record<string, string> = {
                b: "brush",
                e: "erase",
                f: "fill",
                l: "line",
                r: "rect",
                s: "select",
                v: "move",
              };
              if (t[k]) {
                e.preventDefault();
                setTool(t[k]);
              }
            }
          }}
        />
        <aside>
          <h3>Предпросмотр</h3>
          <div className="symbol-samples">
            {["#11151b", "#eff0eb"].map((bg) =>
              ["#edc875", "#658fcb", "#b74445"].map((tint) => (
                <SymbolPreview
                  key={bg + tint}
                  doc={{ ...doc, pixels: shown }}
                  size={32}
                  background={bg}
                  tint={tint}
                />
              )),
            )}
          </div>
          <p>16×16 исходник · 32×32 в игре</p>
          <SymbolPreview doc={{ ...doc, pixels: shown }} size={16} />
          <p>
            Терминал: <strong>{doc.glyph}</strong>
          </p>
          {doc.source && (
            <p className="hint">
              Источник: {doc.source.name}
              <br />
              {doc.source.license}
              <br />
              {doc.source.location}
            </p>
          )}
          <h3>Где используется ({usages.length})</h3>
          {usages.map((u, n) => (
            <button
              className="usage"
              key={n}
              onClick={() => open(u.category, u.ref)}
            >
              {u.ref}
              <small>{u.field}</small>
            </button>
          ))}
          <details>
            <summary>Сведения об источнике</summary>
            {["name", "license", "location"].map((key) => (
              <label key={key}>
                {
                  (
                    {
                      name: "Название источника",
                      license: "Лицензия",
                      location: "Адрес / путь",
                    } as Doc
                  )[key]
                }
                <input
                  value={doc.source?.[key] ?? ""}
                  onChange={(e) =>
                    onChange({
                      ...doc,
                      source: {
                        name: "Авторский рисунок",
                        license: "Указать лицензию",
                        ...doc.source,
                        [key]: e.target.value,
                      },
                    })
                  }
                />
              </label>
            ))}
          </details>
        </aside>
      </div>
      <div className="toolbar">
        <label>
          Увеличение{" "}
          <input
            aria-label="Масштаб пиксельного холста"
            type="range"
            min={8}
            max={32}
            step={4}
            value={zoom}
            onChange={(e) => setZoom(+e.target.value)}
          />
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={grid}
            onChange={(e) => setGrid(e.target.checked)}
          />
          Сетка
        </label>
        {(
          [
            ["flipX", "Отразить ↔"],
            ["flipY", "Отразить ↕"],
            ["rotate", "Повернуть 90°"],
          ] as const
        ).map(([k, l]) => (
          <button key={k} onClick={() => commit(transformMask(doc.pixels, k))}>
            {l}
          </button>
        ))}
        <button onClick={exportPNG}>Экспорт PNG</button>
        <label className="file-button">
          Импорт PNG / листа
          <input
            type="file"
            accept="image/png"
            aria-label="Импорт PNG символов"
            onChange={(e) => {
              if (e.target.files?.[0]) void readPNG(e.target.files[0]);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <p className="hint">
        B/E/F/L/R/S/V — инструменты · Ctrl+C/Ctrl+V — область · Ctrl+Z — отмена.
        Одна клетка рисунка — один пиксель. Механики объекта здесь не меняются.
      </p>
      {image && (
        <section className="symbol-import">
          <h3>
            Проверка импорта {image.data.width}×{image.data.height}
          </h3>
          <div className="toolbar">
            <label>
              Маска{" "}
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="alpha">По прозрачности</option>
                <option value="brightness">По яркости</option>
              </select>
            </label>
            <label>
              Порог{" "}
              <input
                type="range"
                min={0}
                max={254}
                value={threshold}
                onChange={(e) => setThreshold(+e.target.value)}
              />
            </label>
            <button
              onClick={() =>
                setPicked(
                  Array.from(
                    { length: (image.data.width * image.data.height) / 256 },
                    (_, i) => i,
                  ),
                )
              }
            >
              Выбрать все
            </button>
            <button onClick={() => setImage(null)}>Отмена импорта</button>
          </div>
          <div className="import-cells">
            {Array.from(
              { length: (image.data.width * image.data.height) / 256 },
              (_, n) => (
                <button
                  key={n}
                  aria-label={"Клетка листа " + n}
                  className={picked.includes(n) ? "selected" : ""}
                  onClick={() =>
                    setPicked((p) =>
                      p.includes(n) ? p.filter((i) => i !== n) : [...p, n],
                    )
                  }
                >
                  <SymbolPreview doc={{ pixels: importedMask(n) }} size={32} />
                </button>
              ),
            )}
          </div>
          <label className="toggle">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            Подтверждаю преобразование цветов в одноцветную маску
          </label>
          <div className="toolbar">
            <button
              disabled={picked.length !== 1 || !confirmed}
              onClick={() => {
                commit(importedMask(picked[0]));
                setImage(null);
              }}
            >
              В текущий рисунок
            </button>
            <select
              aria-label="Пакет импортируемых символов"
              value={targetPack}
              onChange={(e) => setTargetPack(e.target.value)}
            >
              {packs.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
            <button
              disabled={!picked.length || !confirmed || importing}
              onClick={() => void importMany()}
            >
              Создать выбранные символы ({picked.length})
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

export function SymbolAssignments({ notify }: { notify: (s: string) => void }) {
  const context = useContext(SymbolContext),
    [query, setQuery] = useState(""),
    [category, setCategory] = useState("all"),
    [pack, setPack] = useState("all"),
    [status, setStatus] = useState("all"),
    [selected, setSelected] = useState<string[]>([]),
    [choosing, setChoosing] = useState(false),
    [pending, setPending] = useState<string | null>(null),
    [busy, setBusy] = useState(false),
    [errors, setErrors] = useState<string[]>([]),
    [page, setPage] = useState(0);
  const rows: {
    key: string;
    entry: Entry;
    doc: Doc;
    path: string;
    label: string;
    symbol?: string;
    state?: string;
  }[] = [];
  context.entries.forEach((entry) => {
    const doc = context.assets[entry.category + "/" + entry.ref];
    if (
      !doc ||
      entry.category === "symbols" ||
      entry.category === "art" ||
      !("glyph" in doc)
    )
      return;
    rows.push({
      key: entry.category + "/" + entry.ref,
      entry,
      doc,
      path: "symbol",
      label: entry.name,
      symbol: doc.symbol,
    });
    (doc.variants ?? []).forEach((v: Doc, n: number) =>
      rows.push({
        key: entry.category + "/" + entry.ref + "/variants/" + n,
        entry,
        doc: v,
        path: "variants." + n + ".symbol",
        label: entry.name + " · " + v.name,
        symbol: v.symbol,
      }),
    );
    const door = doc.brush?.door;
    if (door) {
      const states =
        door.material === "stone"
          ? ["closed"]
          : [
              "closed",
              "locked",
              "open",
              ...(door.material === "bars" ? ["bent"] : []),
            ];
      states.forEach((state) =>
        rows.push({
          key: entry.category + "/" + entry.ref + "/" + state,
          entry,
          doc,
          path: "state_symbols." + state,
          label:
            entry.name +
            " · " +
            (
              {
                closed: "Закрыта",
                locked: "Заперта",
                open: "Открыта",
                bent: "Прутья погнуты",
              } as Doc
            )[state],
          symbol: doc.state_symbols?.[state],
          state,
        }),
      );
    }
  });
  const stateOf = (r: (typeof rows)[number]) =>
    !r.symbol
      ? "missing"
      : context.assets["symbols/" + r.symbol]?.reviewed
        ? "ready"
        : "unreviewed";
  const filtered = rows.filter(
    (r) =>
      (category === "all" || r.entry.category === category) &&
      (pack === "all" || r.entry.ref.startsWith(pack + ":")) &&
      (status === "all" || stateOf(r) === status) &&
      [r.label, r.entry.ref, r.symbol, r.doc.glyph]
        .join(" ")
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  const chosen = rows.filter((r) => selected.includes(r.key)),
    current = Math.min(page, Math.max(0, Math.ceil(filtered.length / 40) - 1));
  async function save() {
    if (!pending || busy) return;
    setBusy(true);
    const failed: string[] = [],
      done: string[] = [];
    const grouped = new Map<string, typeof rows>();
    chosen.forEach((r) => {
      const k = r.entry.category + "/" + r.entry.ref;
      grouped.set(k, [...(grouped.get(k) ?? []), r]);
    });
    for (const [key, items] of grouped) {
      const entry = items[0].entry;
      try {
        const doc = structuredClone(context.assets[key]);
        for (const r of items) {
          const bits = r.path.split(".");
          let target = doc;
          for (const bit of bits.slice(0, -1)) {
            target[bit] ??= {};
            target = target[bit];
          }
          target[bits.at(-1)!] = pending;
        }
        await api(
          "/documents/" + key,
          { document: doc, version: entry.version },
          "PUT",
        );
        done.push(...items.map((r) => r.key));
      } catch (e) {
        failed.push(entry.ref + ": " + String(e));
      }
    }
    try {
      await context.refresh();
    } catch (e) {
      failed.push("Обновление библиотеки: " + String(e));
    }
    setSelected((s) => s.filter((k) => !done.includes(k)));
    setErrors(failed);
    setPending(null);
    setBusy(false);
    notify(`Назначено: ${done.length}; конфликтов/ошибок: ${failed.length}`);
  }
  return (
    <section className="symbol-assignments">
      <h1>Согласование графики</h1>
      <p className="hint">
        Выберите изображения для определений, вариантов и состояний дверей.
        Изменение общего символа влияет на все его использования.
      </p>
      <div className="content-filters">
        <input
          type="search"
          aria-label="Поиск назначений"
          placeholder="Название, ID, символ…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(0);
          }}
        />
        <select
          aria-label="Раздел назначений"
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setPage(0);
          }}
        >
          <option value="all">Все разделы</option>
          {[...new Set(rows.map((r) => r.entry.category))].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select
          aria-label="Пакет назначений"
          value={pack}
          onChange={(e) => {
            setPack(e.target.value);
            setPage(0);
          }}
        >
          <option value="all">Все пакеты</option>
          {context.packs.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <select
          aria-label="Статус назначения"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(0);
          }}
        >
          <option value="all">Все назначения</option>
          <option value="missing">Отсутствующие</option>
          <option value="unreviewed">Непроверенные</option>
          <option value="ready">Согласованные</option>
        </select>
      </div>
      <div className="toolbar">
        <button onClick={() => setSelected(filtered.map((r) => r.key))}>
          Выбрать найденные
        </button>
        <button onClick={() => setSelected([])}>Снять выбор</button>
        <button
          disabled={!chosen.length || busy}
          onClick={() => setChoosing(true)}
        >
          Назначить выбранным ({chosen.length})
        </button>
        <span>{filtered.length} записей</span>
      </div>
      {errors.map((e) => (
        <p className="error" role="alert" key={e}>
          {e}
        </p>
      ))}
      {pending && (
        <div className="assignment-confirm">
          <h3>Предпросмотр назначения</h3>
          <SymbolPreview symbol={pending} />
          <p>
            {chosen.length} записей → {pending}
          </p>
          <div className="assignment-preview-list">
            {chosen.map((r) => (
              <div key={r.key}>
                <SymbolPreview symbol={r.symbol} />
                <span>{r.label} → </span>
                <SymbolPreview symbol={pending} />
              </div>
            ))}
          </div>
          <button
            className="primary"
            disabled={busy}
            onClick={() => void save()}
          >
            Сохранить назначения
          </button>
          <button disabled={busy} onClick={() => setPending(null)}>
            Отмена
          </button>
        </div>
      )}
      <div className="assignment-list">
        {filtered.slice(current * 40, (current + 1) * 40).map((r) => (
          <div key={r.key} className="assignment-row">
            <input
              type="checkbox"
              aria-label={"Выбрать " + r.label}
              checked={selected.includes(r.key)}
              onChange={(e) =>
                setSelected((s) =>
                  e.target.checked
                    ? [...s, r.key]
                    : s.filter((k) => k !== r.key),
                )
              }
            />
            <button
              aria-label={"Назначить " + r.label}
              onClick={() => {
                setSelected([r.key]);
                setChoosing(true);
              }}
            >
              <SymbolPreview
                symbol={
                  r.symbol ?? visual(r.doc, context.assets, r.state).symbol
                }
              />
            </button>
            <span>
              <strong>{r.label}</strong>
              <small>
                {r.entry.ref} · {r.path}
              </small>
            </span>
            <code>{visual(r.doc, context.assets, r.state).char}</code>
            <span>
              {
                (
                  {
                    missing: "Нет назначения",
                    ready: "Согласовано",
                    unreviewed: "Не проверено",
                  } as Doc
                )[stateOf(r)]
              }
            </span>
            <button onClick={() => context.open(r.entry.category, r.entry.ref)}>
              Открыть
            </button>
          </div>
        ))}
      </div>
      <nav className="content-pagination">
        <button disabled={!current} onClick={() => setPage(current - 1)}>
          ← Назад
        </button>
        <span>
          {current + 1} / {Math.max(1, Math.ceil(filtered.length / 40))}
        </span>
        <button
          disabled={(current + 1) * 40 >= filtered.length}
          onClick={() => setPage(current + 1)}
        >
          Далее →
        </button>
      </nav>
      {choosing && (
        <SymbolPicker
          onChoose={(ref) => setPending(ref)}
          onClose={() => setChoosing(false)}
        />
      )}
    </section>
  );
}
