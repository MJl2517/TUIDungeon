import { SymbolContext, SymbolSelect } from "./Symbols";
import { glyphRef, visual } from "./symbolModel";
import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { Grid } from "./Grid";
import {
  Cell,
  Doc,
  Point,
  clone,
  compose,
  color,
  flood,
  line,
  rectangle,
  resizeArt,
  inBounds,
} from "./model";
import { api } from "./api";
type Props = {
  viewState?: Doc;
  onViewState?: (state: Doc) => void;
  doc: Doc;
  onChange: (d: Doc) => void;
  notify: (s: string) => void;
  packId?: string;
};
export function ArtEditor({
  doc,
  onChange,
  notify,
  packId = "base",
  viewState = {},
  onViewState,
}: Props) {
  const context = useContext(SymbolContext);
  const [symbol, setSymbol] = useState<string>(
    viewState.symbol ?? glyphRef("█"),
  );
  const [layerIndex, setLayerIndex] = useState(viewState.layerIndex ?? 0),
    [tool, setTool] = useState<string>(viewState.tool ?? "brush"),
    [glyph, setGlyph] = useState<string>(viewState.glyph ?? "█"),
    [fg, setFg] = useState(viewState.fg ?? 7),
    [bg, setBg] = useState<number | null>(viewState.bg ?? null),
    [zoom, setZoom] = useState(viewState.zoom ?? 1.5),
    [grid, setGrid] = useState(viewState.grid ?? true),
    [text, setText] = useState<string>(viewState.text ?? "DUNGEON"),
    [selection, setSelection] = useState<Point[]>(viewState.selection ?? []),
    [hover, setHover] = useState<Point>(viewState.hover ?? { x: 0, y: 0 });
  const [width, setWidth] = useState(doc.width),
    [height, setHeight] = useState(doc.height),
    [clipboard, setClipboard] = useState<Cell[][] | null>(
      viewState.clipboard ?? null,
    ),
    [preview, setPreview] = useState<Doc | null>(null);
  useEffect(() => {
    onViewState?.({
      symbol,
      layerIndex,
      tool,
      glyph,
      fg,
      bg,
      zoom,
      grid,
      text,
      selection,
      hover,
      clipboard,
    });
  }, [
    symbol,
    layerIndex,
    tool,
    glyph,
    fg,
    bg,
    zoom,
    grid,
    text,
    selection,
    clipboard,
  ]);
  const [issues, setIssues] = useState<Doc[]>([]);
  useEffect(() => {
    setWidth(doc.width);
    setHeight(doc.height);
  }, [doc.width, doc.height]);
  useEffect(() => {
    let cancelled = false;
    const id = setTimeout(() => {
      api("/art/check", { document: doc })
        .then((result) => {
          if (!cancelled) setIssues(result.issues);
        })
        .catch(() => {});
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [doc]);
  const stroke = useRef<{
    base: Doc;
    start: Point;
    last: Point;
    next: Doc;
  } | null>(null);
  const index = Math.min(layerIndex, doc.layers.length - 1);
  const shown = preview ?? doc;
  const cells = useMemo(
    () =>
      compose(shown).map((row) =>
        row.map((c) => (c ? visual(c, context.assets) : null)),
      ),
    [shown, context.assets],
  );
  const currentCell: Cell = {
    char: context.assets["symbols/" + symbol]?.glyph ?? glyph,
    symbol,
    foreground: fg,
    background: bg,
  };
  function paint(base: Doc, points: Point[], erase = false) {
    const next = clone(base);
    if (next.layers[index].locked) {
      notify("Слой заблокирован");
      return next;
    }
    for (const p of points)
      if (inBounds(next, p))
        next.layers[index].cells[p.y][p.x] = erase ? null : clone(currentCell);
    return next;
  }
  function copyArea() {
    if (!selection.length) return null;
    const minX = Math.min(...selection.map((p) => p.x)),
      minY = Math.min(...selection.map((p) => p.y)),
      maxX = Math.max(...selection.map((p) => p.x)),
      maxY = Math.max(...selection.map((p) => p.y));
    return doc.layers[index].cells
      .slice(minY, maxY + 1)
      .map((r: Cell[]) => clone(r.slice(minX, maxX + 1)));
  }
  async function down(p: Point) {
    if (doc.layers[index].locked && tool !== "select") {
      notify("Слой заблокирован");
      return;
    }
    if (tool === "fill") {
      onChange(
        paint(
          doc,
          flood(
            doc.layers[index].cells,
            p,
            (a, b) => JSON.stringify(a) === JSON.stringify(b),
          ),
        ),
      );
      return;
    }
    if (tool === "text") {
      let refs: Record<string, string>;
      try {
        refs = (await api("/symbols/resolve-text", { text, pack: packId }))
          .symbols;
        await context.refresh();
      } catch (e) {
        notify(String(e));
        return;
      }
      const n = clone(doc);
      text.split("\n").forEach((row, y) =>
        Array.from(row).forEach((c, x) => {
          if (inBounds(n, { x: p.x + x, y: p.y + y }))
            n.layers[index].cells[p.y + y][p.x + x] = {
              ...currentCell!,
              char: c,
              symbol: refs[c],
            };
        }),
      );
      onChange(n);
      return;
    }
    if (tool === "paste" || tool === "move") {
      const clip = tool === "move" ? copyArea() : clipboard;
      if (!clip) {
        notify("Сначала выделите и скопируйте область");
        return;
      }
      let n = clone(doc);
      if (tool === "move")
        for (const point of selection)
          n.layers[index].cells[point.y][point.x] = null;
      clip.forEach((row: Cell[], y: number) =>
        row.forEach((c: Cell, x: number) => {
          if (inBounds(n, { x: p.x + x, y: p.y + y }))
            n.layers[index].cells[p.y + y][p.x + x] = clone(c);
        }),
      );
      onChange(n);
      return;
    }
    const next = ["brush", "erase"].includes(tool)
      ? paint(doc, [p], tool === "erase")
      : clone(doc);
    stroke.current = { base: clone(doc), start: p, last: p, next };
    setPreview(next);
  }
  function drag(p: Point) {
    const s = stroke.current;
    if (!s) return;
    if (tool === "select") {
      setSelection(rectangle(s.start, p, true));
      return;
    }
    if (["line", "rect"].includes(tool))
      s.next = paint(
        s.base,
        tool === "line" ? line(s.start, p) : rectangle(s.start, p),
      );
    else s.next = paint(s.next, line(s.last, p), tool === "erase");
    s.last = p;
    setPreview(s.next);
  }
  function up(p: Point) {
    const s = stroke.current;
    if (!s) return;
    if (tool === "select") setSelection(rectangle(s.start, p, true));
    else {
      drag(p);
      onChange(s.next);
    }
    stroke.current = null;
    setPreview(null);
  }
  async function importFile(file: File) {
    try {
      if (file.name.endsWith(".json")) {
        const next = {
          ...JSON.parse(await file.text()),
          id: doc.id,
          name: doc.name,
        };
        await api("/validate/art/base:" + doc.id, { document: next });
        onChange(next);
      } else {
        const n = await api("/art/import", {
          id: doc.id,
          name: doc.name,
          text: await file.text(),
          pack: packId,
        });
        onChange(n);
      }
      await context.refresh();
      notify("Импортировано в текущий холст");
    } catch (e) {
      notify(String(e));
    }
  }
  function download() {
    const txt =
      compose(doc)
        .map((r) =>
          r.map((c) => (c ? visual(c, context.assets).char : " ")).join(""),
        )
        .join("\n") + "\n";
    const url = URL.createObjectURL(
      new Blob([txt], { type: "text/plain;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = doc.id + ".txt";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="editor-layout">
      <div className="workspace">
        <div className="toolbar">
          {[
            ["brush", "Кисть"],
            ["erase", "Ластик"],
            ["fill", "Заливка"],
            ["line", "Линия"],
            ["rect", "Рамка"],
            ["text", "Текст"],
            ["select", "Выделить"],
            ["move", "Перенести"],
            ["paste", "Вставить"],
          ].map(([id, name]) => (
            <button
              key={id}
              className={tool === id ? "active" : ""}
              onClick={() => setTool(id)}
            >
              {name}
            </button>
          ))}
        </div>
        <div className="toolbar">
          <label>
            Масштаб{" "}
            <input
              type="range"
              min="0.5"
              max="3"
              step="0.25"
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
            />
          </label>
          <label>
            <input
              type="checkbox"
              checked={grid}
              onChange={(e) => setGrid(e.target.checked)}
            />{" "}
            Сетка
          </label>
          <button
            onClick={() => {
              const c = copyArea();
              if (c) {
                setClipboard(c);
                notify("Область скопирована");
              }
            }}
          >
            Копировать
          </button>
          <span className="coordinate">
            {hover.x}, {hover.y}
          </span>
          <span className="hint">
            Прозрачные клетки показаны шахматной сеткой
          </span>
        </div>
        <div className="canvas-scroll">
          <Grid
            cells={cells}
            overlays={[
              {
                cells: Array.from({ length: doc.height }, (_, y) =>
                  Array.from({ length: doc.width }, (_, x) =>
                    issues.some((p) => p.x === x && p.y === y),
                  ),
                ),
                color: "#f0717888",
              },
            ]}
            zoom={zoom}
            grid={grid}
            selection={selection}
            onDown={down}
            onDrag={drag}
            onUp={up}
            onHover={setHover}
          />
        </div>
        <div className="toolbar">
          <label className="file-button">
            Импорт TXT / JSON
            <input
              type="file"
              accept=".txt,.json"
              onChange={(e) => {
                if (e.target.files?.[0]) void importFile(e.target.files[0]);
                e.target.value = "";
              }}
            />
          </label>
          <button onClick={download}>Экспорт TXT</button>
          <label>
            Холст{" "}
            <input
              className="short"
              type="number"
              min="1"
              max="256"
              value={width}
              onChange={(e) => setWidth(Number(e.target.value))}
            />{" "}
            ×{" "}
            <input
              className="short"
              type="number"
              min="1"
              max="256"
              value={height}
              onChange={(e) => setHeight(Number(e.target.value))}
            />
          </label>
          <button
            onClick={() => {
              if (width >= 1 && width <= 256 && height >= 1 && height <= 256)
                onChange(resizeArt(doc, width, height));
            }}
          >
            Изменить размер
          </button>
        </div>
      </div>
      <aside className="inspector">
        <h3>Кисть</h3>
        {issues.length > 0 && (
          <div className="error">
            <p>Неподдерживаемые символы:</p>
            {issues.slice(0, 10).map((p, i) => (
              <p key={i}>
                Слой {p.layer + 1}, ({p.x}, {p.y})
              </p>
            ))}
          </div>
        )}
        <SymbolSelect
          value={symbol}
          onChange={(ref) => {
            setSymbol(ref);
            setGlyph(context.assets["symbols/" + ref]?.glyph ?? "?");
          }}
          label="Кисть из библиотеки"
        />
        {tool === "text" && (
          <textarea
            aria-label="Текст кисти"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        )}
        <div className="color-options">
          <label>
            Символ{" "}
            <input
              type="number"
              min="0"
              max="255"
              value={fg}
              onChange={(e) =>
                setFg(Math.max(0, Math.min(255, Number(e.target.value))))
              }
            />
          </label>
          <label>
            Фон{" "}
            <select
              value={bg ?? ""}
              onChange={(e) =>
                setBg(e.target.value === "" ? null : Number(e.target.value))
              }
            >
              <option value="">Прозрачный</option>
              {Array.from({ length: 256 }, (_, i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="color-palette">
          {Array.from({ length: 256 }, (_, i) => (
            <button
              key={i}
              title={`Цвет ${i}; Shift — фон`}
              className={fg === i ? "selected" : ""}
              style={{ background: color(i) }}
              onClick={(e) => (e.shiftKey ? setBg(i) : setFg(i))}
            />
          ))}
        </div>
        <p className="hint">Клик — цвет символа. Shift + клик — фон.</p>
        <h3>
          Слои{" "}
          <button
            className="mini"
            onClick={() => {
              const n = clone(doc);
              n.layers.push({
                id: "layer_" + Date.now(),
                name: "Новый слой",
                visible: true,
                locked: false,
                cells: Array.from({ length: doc.height }, () =>
                  Array(doc.width).fill(null),
                ),
              });
              onChange(n);
              setLayerIndex(n.layers.length - 1);
            }}
          >
            +
          </button>
        </h3>
        {[...doc.layers].map((layer: Doc, i: number) => (
          <div
            key={layer.id}
            className={"layer-row " + (i === index ? "selected" : "")}
          >
            <button className="mini" onClick={() => setLayerIndex(i)}>
              ▸
            </button>
            <input
              aria-label="Имя слоя"
              value={layer.name}
              onFocus={() => setLayerIndex(i)}
              onChange={(e) => {
                const n = clone(doc);
                n.layers[i].name = e.target.value;
                onChange(n);
              }}
            />
            <label title="Видимость">
              <input
                type="checkbox"
                checked={layer.visible}
                onChange={(e) => {
                  const n = clone(doc);
                  n.layers[i].visible = e.target.checked;
                  onChange(n);
                }}
              />
              ◉
            </label>
            <label title="Блокировка">
              <input
                type="checkbox"
                checked={layer.locked}
                onChange={(e) => {
                  const n = clone(doc);
                  n.layers[i].locked = e.target.checked;
                  onChange(n);
                }}
              />
              ▣
            </label>
          </div>
        ))}
        <div className="toolbar">
          {[-1, 1].map((delta) => (
            <button
              key={delta}
              disabled={index + delta < 0 || index + delta >= doc.layers.length}
              onClick={() => {
                const n = clone(doc);
                [n.layers[index], n.layers[index + delta]] = [
                  n.layers[index + delta],
                  n.layers[index],
                ];
                onChange(n);
                setLayerIndex(index + delta);
              }}
            >
              {delta < 0 ? "Ниже" : "Выше"}
            </button>
          ))}
          <button
            disabled={doc.layers.length === 1}
            onClick={() => {
              const n = clone(doc);
              n.layers.splice(index, 1);
              onChange(n);
              setLayerIndex(Math.max(0, index - 1));
            }}
          >
            Удалить слой
          </button>
        </div>
        <p className="hint">
          Слои выше в списке рисуются раньше. Полностью прозрачная клетка не
          перекрывает нижние слои.
        </p>
      </aside>
    </div>
  );
}
