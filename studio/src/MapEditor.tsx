import { useEffect, useRef, useState } from "react";
import { Grid } from "./Grid";
import {
  Doc,
  Entry,
  Point,
  clone,
  mapGrid,
  placements,
  flood,
  line,
  rectangle,
  resizeMap,
  inBounds,
} from "./model";
type Props = {
  doc: Doc;
  onChange: (d: Doc) => void;
  entries: Entry[];
  assets: Record<string, Doc>;
  notify: (s: string) => void;
  warnings: Doc[];
};
const names: Record<string, string> = {
  tiles: "Тайлы",
  decorations: "Рисунки",
  walkability: "Проходимость",
  blocks_sight: "Преграды обзору",
  traps: "Ловушки",
  points_of_interest: "Точки интереса",
  monsters: "Существа",
  equipment: "Предметы",
  spawn: "Старт героя",
  transitions: "Переходы",
};
export function MapEditor({
  doc,
  onChange,
  entries,
  assets,
  notify,
  warnings,
}: Props) {
  const [layer, setLayer] = useState("tiles"),
    [tool, setTool] = useState("brush"),
    [ref, setRef] = useState(""),
    [maskValue, setMaskValue] = useState(true),
    [initTile, setInitTile] = useState(true),
    [zoom, setZoom] = useState(1.3),
    [grid, setGrid] = useState(true),
    [width, setWidth] = useState(doc.width),
    [height, setHeight] = useState(doc.height),
    [hover, setHover] = useState<Point>(doc.spawn),
    [selection, setSelection] = useState<Point[]>([]),
    [selected, setSelected] = useState<{ category: string; id: string } | null>(
      null,
    ),
    [clipboard, setClipboard] = useState<Doc | null>(null),
    [visibility, setVisibility] = useState<Record<string, boolean>>({
      walkability: true,
      blocks_sight: false,
    }),
    [preview, setPreview] = useState<Doc | null>(null);
  useEffect(() => {
    setWidth(doc.width);
    setHeight(doc.height);
  }, [doc.width, doc.height]);
  const stroke = useRef<{
      base: Doc;
      start: Point;
      last: Point;
      next: Doc;
    } | null>(null),
    category =
      layer === "decorations"
        ? "art"
        : layer === "transitions"
          ? "maps"
          : layer;
  const options = entries.filter((e) => e.category === category),
    chosen = options.some((e) => e.ref === ref) ? ref : (options[0]?.ref ?? "");
  const shown = preview ?? doc;
  function paint(base: Doc, points: Point[], erase = false) {
    const n = clone(base);
    for (const p of points) {
      if (!inBounds(n, p)) continue;
      if (layer === "tiles") {
        n.tiles[p.y][p.x] = erase ? null : chosen;
        const t = assets["tiles/" + chosen];
        if (initTile && t && !erase) {
          n.walkability[p.y][p.x] = t.walkable;
          n.blocks_sight[p.y][p.x] = t.blocks_sight;
        }
      } else if (layer === "walkability" || layer === "blocks_sight")
        n[layer][p.y][p.x] = erase ? !maskValue : maskValue;
      else if (layer === "spawn") n.spawn = p;
      else {
        n[layer] = n[layer].filter(
          (entry: Point) => entry.x !== p.x || entry.y !== p.y,
        );
        if (!erase && chosen) {
          const entry = {
            id: layer + "_" + Date.now() + "_" + p.x + "_" + p.y,
            ...p,
            [layer === "transitions" ? "target" : "ref"]: chosen,
          };
          n[layer].push(entry);
        }
      }
    }
    return n;
  }
  function copyArea() {
    if (!selection.length) return null;
    const x = Math.min(...selection.map((p) => p.x)),
      y = Math.min(...selection.map((p) => p.y)),
      w = Math.max(...selection.map((p) => p.x)) - x + 1,
      h = Math.max(...selection.map((p) => p.y)) - y + 1;
    const clip: Doc = { x, y, width: w, height: h };
    for (const key of ["tiles", "walkability", "blocks_sight"])
      clip[key] = doc[key]
        .slice(y, y + h)
        .map((r: any[]) => clone(r.slice(x, x + w)));
    for (const key of placements)
      clip[key] = doc[key]
        .filter(
          (p: Point) => p.x >= x && p.x < x + w && p.y >= y && p.y < y + h,
        )
        .map((p: Doc) => ({ ...clone(p), x: p.x - x, y: p.y - y }));
    return clip;
  }
  function paste(p: Point, moving = false) {
    if (moving && selected) {
      const n = clone(doc),
        entry = n[selected.category].find((a: Doc) => a.id === selected.id);
      entry.x = p.x;
      entry.y = p.y;
      onChange(n);
      return;
    }
    const clip = moving ? copyArea() : clipboard;
    if (!clip) {
      notify("Выделите область или выберите объект");
      return;
    }
    const n = clone(doc);
    if (moving) {
      for (const pt of selection) {
        n.tiles[pt.y][pt.x] = null;
        n.walkability[pt.y][pt.x] = true;
        n.blocks_sight[pt.y][pt.x] = false;
      }
      for (const key of placements)
        n[key] = n[key].filter(
          (e: Point) => !selection.some((pt) => pt.x === e.x && pt.y === e.y),
        );
    }
    for (const key of ["tiles", "walkability", "blocks_sight"])
      clip[key].forEach((r: any[], y: number) =>
        r.forEach((v: any, x: number) => {
          if (inBounds(n, { x: p.x + x, y: p.y + y }))
            n[key][p.y + y][p.x + x] = clone(v);
        }),
      );
    for (const key of placements)
      for (const e of clip[key])
        if (inBounds(n, { x: p.x + e.x, y: p.y + e.y }))
          n[key].push({
            ...clone(e),
            id: moving ? e.id : e.id + "_copy_" + Date.now(),
            x: p.x + e.x,
            y: p.y + e.y,
          });
    onChange(n);
  }
  function down(p: Point) {
    setHover(p);
    if (tool === "move" || tool === "paste") {
      paste(p, tool === "move");
      return;
    }
    if (tool === "fill") {
      if (!["tiles", "walkability", "blocks_sight"].includes(layer)) {
        notify("Заливка доступна для тайлов и масок");
        return;
      }
      onChange(
        paint(
          doc,
          flood(doc[layer], p, (a, b) => a === b),
        ),
      );
      return;
    }
    if (tool === "select") {
      const found = placements.flatMap((c) =>
        doc[c]
          .filter((e: Point) => e.x === p.x && e.y === p.y)
          .map((e: Doc) => ({ category: c, id: e.id })),
      );
      setSelected(found[0] ?? null);
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
    if (tool === "rect") s.next = paint(s.base, rectangle(s.start, p, true));
    else if (["tiles", "walkability", "blocks_sight"].includes(layer))
      s.next = paint(s.next, line(s.last, p), tool === "erase");
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
  const overlays = [];
  if (visibility.walkability)
    overlays.push({
      cells: shown.walkability.map((r: boolean[]) => r.map((v) => !v)),
      color: "#f071784d",
    });
  if (visibility.blocks_sight)
    overlays.push({ cells: shown.blocks_sight, color: "#8bb7ee55" });
  const isolated = warnings.flatMap((w) => w.cells ?? []);
  const isolatedSet = new Set(isolated.map((p: Point) => `${p.x},${p.y}`));
  if (isolated.length)
    overlays.push({
      cells: Array.from({ length: doc.height }, (_, y) =>
        Array.from({ length: doc.width }, (_, x) =>
          isolatedSet.has(`${x},${y}`),
        ),
      ),
      color: "#edc87555",
    });
  return (
    <div className="editor-layout">
      <div className="workspace">
        <div className="toolbar">
          {[
            ["brush", "Кисть"],
            ["erase", "Удалить"],
            ["rect", "Область"],
            ["fill", "Заливка"],
            ["select", "Выбрать"],
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
          <button
            onClick={() => {
              const c = copyArea();
              if (c) {
                setClipboard(c);
                notify("Скопированы графика, маски и объекты области");
              }
            }}
          >
            Копировать область
          </button>
        </div>
        <div className="toolbar">
          <select
            aria-label="Слой карты"
            value={layer}
            onChange={(e) => {
              setLayer(e.target.value);
              setRef("");
            }}
          >
            {Object.entries(names).map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
          {["walkability", "blocks_sight"].includes(layer) ? (
            <label>
              <input
                type="checkbox"
                checked={maskValue}
                onChange={(e) => setMaskValue(e.target.checked)}
              />
              {layer === "walkability"
                ? "Разрешить проход"
                : "Преграждать обзор"}
            </label>
          ) : (
            layer !== "spawn" && (
              <select
                aria-label="Шаблон размещения"
                value={chosen}
                onChange={(e) => setRef(e.target.value)}
              >
                {options.map((e) => (
                  <option key={e.ref} value={e.ref}>
                    {e.name} · {e.ref}
                  </option>
                ))}
              </select>
            )
          )}
          {layer === "tiles" && (
            <label>
              <input
                type="checkbox"
                checked={initTile}
                onChange={(e) => setInitTile(e.target.checked)}
              />{" "}
              Начальные маски тайла
            </label>
          )}
          <span className="coordinate">
            {hover.x}, {hover.y}
          </span>
        </div>
        <div className="canvas-scroll">
          <Grid
            cells={mapGrid(shown, assets, visibility)}
            overlays={overlays}
            selection={selection}
            zoom={zoom}
            grid={grid}
            onDown={down}
            onDrag={drag}
            onUp={up}
            onHover={setHover}
          />
        </div>
        <div className="toolbar">
          <label>
            Масштаб{" "}
            <input
              type="range"
              min="0.5"
              max="3"
              step="0.1"
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
          <label>
            Размер{" "}
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
                onChange(resizeMap(doc, width, height));
            }}
          >
            Изменить
          </button>
        </div>
      </div>
      <aside className="inspector">
        <h3>Оверлеи</h3>
        {Object.entries(names)
          .filter(([k]) => k !== "tiles" && k !== "spawn")
          .map(([key, name]) => (
            <label className="toggle" key={key}>
              <input
                type="checkbox"
                checked={visibility[key] ?? key !== "blocks_sight"}
                onChange={(e) =>
                  setVisibility({ ...visibility, [key]: e.target.checked })
                }
              />
              {name}
            </label>
          ))}
        <p className="hint">
          Красный — нет прохода. Синий — преграда обзору. Жёлтый — недостижимые
          участки. Графика не определяет эти маски.
        </p>
        <h3>
          Клетка {hover.x}, {hover.y}
        </h3>
        <dl>
          <dt>Тайл</dt>
          <dd>{doc.tiles[hover.y]?.[hover.x] ?? "Нет"}</dd>
          <dt>Проход</dt>
          <dd>{doc.walkability[hover.y]?.[hover.x] ? "Да" : "Нет"}</dd>
          <dt>Обзор</dt>
          <dd>{doc.blocks_sight[hover.y]?.[hover.x] ? "Закрыт" : "Открыт"}</dd>
        </dl>
        {placements.map((key) =>
          doc[key]
            .filter((p: Point) => p.x === hover.x && p.y === hover.y)
            .map((p: Doc) => (
              <button
                key={p.id}
                className={
                  "object-card " + (selected?.id === p.id ? "selected" : "")
                }
                onClick={() => {
                  setSelected({ category: key, id: p.id });
                  setTool("select");
                }}
              >
                <strong>{names[key]}</strong>
                <span>{p.ref ?? p.target}</span>
                <small>{p.id}</small>
              </button>
            )),
        )}
        {selected && (
          <div className="toolbar">
            <button onClick={() => setTool("move")}>Переместить объект</button>
            <button
              onClick={() => {
                const n = clone(doc);
                n[selected.category] = n[selected.category].filter(
                  (p: Doc) => p.id !== selected.id,
                );
                onChange(n);
                setSelected(null);
              }}
            >
              Удалить объект
            </button>
          </div>
        )}
        <h3>Проверка карты</h3>
        {warnings.length ? (
          warnings.map((w, i) => (
            <p className="warning" key={i}>
              {w.message}
            </p>
          ))
        ) : (
          <p className="hint">
            Проверка связности обновляется после сохранения. Изолированные
            комнаты разрешены.
          </p>
        )}
      </aside>
    </div>
  );
}
