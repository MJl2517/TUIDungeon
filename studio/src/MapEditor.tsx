import { useEffect, useMemo, useRef, useState } from "react";
import { Grid } from "./Grid";
import type { PointerModifiers } from "./Grid";
import { visual } from "./symbolModel";
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
  mapMasks,
} from "./model";
import { MapPalette, layerNames } from "./MapPalette";
import { paletteCategory, paletteLayer } from "./catalog";
import { paintTile, paintObject, sampleMap } from "./mapTools";
import { InstanceInspector } from "./InstanceInspector";
import { instanceDocument } from "./model";
type Props = {
  doc: Doc;
  onChange: (d: Doc) => void;
  entries: Entry[];
  assets: Record<string, Doc>;
  notify: (s: string) => void;
  warnings: Doc[];
  shortcutsEnabled?: boolean;
  documentRef: string;
  schemas: Record<string, Doc>;
  mechanics: Doc[];
};
const names = layerNames;
export function MapEditor({
  doc,
  onChange,
  entries,
  assets,
  notify,
  warnings,
  shortcutsEnabled = true,
  documentRef,
  schemas,
  mechanics,
}: Props) {
  const [section, setSection] = useState("floor"),
    [layer, setLayer] = useState("tiles"),
    [tool, setTool] = useState("brush"),
    [ref, setRef] = useState("base:floor"),
    [transitionTarget, setTransitionTarget] = useState(""),
    [applyMechanics, setApplyMechanics] = useState(true),
    [panel, setPanel] = useState("palette"),
    [spaceHeld, setSpaceHeld] = useState(false),
    [shiftHeld, setShiftHeld] = useState(false),
    [pointerInside, setPointerInside] = useState(false),
    [panning, setPanning] = useState(false),
    [brushSize, setBrushSize] = useState(1),
    [paletteEmpty, setPaletteEmpty] = useState(false),
    [maskValue, setMaskValue] = useState(true),
    [initTile, setInitTile] = useState(true),
    [zoom, setZoom] = useState(2),
    [symbolMode, setSymbolMode] = useState(
      () => localStorage.getItem("map-render-mode") !== "text",
    ),
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
      roof: false,
    }),
    [preview, setPreview] = useState<Doc | null>(null);
  useEffect(() => {
    localStorage.setItem("map-render-mode", symbolMode ? "symbols" : "text");
  }, [symbolMode]);
  useEffect(() => {
    setWidth(doc.width);
    setHeight(doc.height);
  }, [doc.width, doc.height]);
  const stroke = useRef<{
      base: Doc;
      start: Point;
      last: Point;
      next: Doc;
      mirrored: boolean;
    } | null>(null),
    category =
      layer === "decorations"
        ? "art"
        : layer === "transitions"
          ? "maps"
          : layer === "doors"
            ? "objects"
            : layer;
  const options = entries.filter(
    (e) =>
      e.category === category &&
      (layer === "transitions" ||
        (paletteLayer(e, assets) === layer &&
          paletteCategory(e, assets) === section)),
  );
  const chosen =
    layer === "transitions"
      ? transitionTarget
      : options.some((e) => e.ref === ref)
        ? ref
        : (options.find((e) => e.ref === "base:floor")?.ref ??
          options[0]?.ref ??
          "");
  const viewport = useRef<HTMLDivElement>(null);
  const pan = useRef<{
    x: number;
    y: number;
    left: number;
    top: number;
    pointer: number;
  } | null>(null);
  const shown = preview ?? doc;
  function paint(
    base: Doc,
    points: Point[],
    erase = false,
    mirrored = shiftHeld,
  ) {
    if (
      [
        "tiles",
        "objects",
        "doors",
        "equipment",
        "points_of_interest",
        "traps",
      ].includes(layer) &&
      !erase &&
      (!chosen || paletteEmpty)
    ) {
      notify("Нет объектов для рисования. Измените поиск или группу.");
      return clone(base);
    }
    const n = clone(base);
    try {
      for (const p of points) {
        if (!inBounds(n, p)) continue;
        if (layer === "tiles") {
          paintTile(n, chosen, assets["tiles/" + chosen], p, {
            masks: initTile,
            mechanics: applyMechanics,
            target: transitionTarget,
            erase,
            mirror: mirrored,
          });
        } else if (
          [
            "objects",
            "doors",
            "equipment",
            "points_of_interest",
            "traps",
          ].includes(layer)
        ) {
          paintObject(
            n,
            layer,
            chosen,
            assets[category + "/" + chosen],
            p,
            transitionTarget,
            erase,
            mirrored,
          );
        } else if (["walkability", "blocks_sight", "roof"].includes(layer))
          n[layer][p.y][p.x] = erase ? !maskValue : maskValue;
        else if (layer === "spawn") {
          if (
            !mapMasks(n, assets).walkability[p.y][p.x] ||
            (n.monsters ?? []).some((m: Point) => m.x === p.x && m.y === p.y)
          )
            throw new Error("Выберите свободную проходимую клетку для старта.");
          n.spawn = p;
        } else {
          n[layer] = (n[layer] ?? []).filter(
            (entry: Point) => entry.x !== p.x || entry.y !== p.y,
          );
          if (!erase && (chosen || layer === "lights")) {
            if (layer === "doors") {
              if (
                assets["objects/" + chosen]?.brush?.door?.state !== "open" &&
                !assets["objects/" + chosen]?.brush?.door?.bent &&
                p.x === n.spawn.x &&
                p.y === n.spawn.y
              )
                throw new Error(
                  "Закрытая дверь не может занимать старт героя.",
                );
              n.walkability[p.y][p.x] = true;
              n.blocks_sight[p.y][p.x] = false;
            }
            if (
              layer !== "lights" &&
              layer !== "decorations" &&
              !n.walkability[p.y][p.x]
            )
              throw new Error(
                "Объект можно разместить только на проходимой клетке.",
              );
            if (layer === "monsters" && p.x === n.spawn.x && p.y === n.spawn.y)
              throw new Error("Существо не может занимать старт героя.");
            const entry = {
              id: layer + "_" + Date.now() + "_" + p.x + "_" + p.y,
              ...p,
              ...(mirrored && layer === "monsters"
                ? {
                    overrides: {
                      mirror_x: !assets[category + "/" + chosen]?.mirror_x,
                    },
                  }
                : {}),
              ...(layer === "lights"
                ? { radius: 6, bright_radius: 3, enabled: true }
                : { [layer === "transitions" ? "target" : "ref"]: chosen }),
            };
            n[layer].push(entry);
          }
        }
      }
    } catch (error) {
      notify(String(error).replace(/^Error: /, ""));
      return clone(base);
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
    for (const key of [
      "tiles",
      "walkability",
      "blocks_sight",
      "roof",
      "tile_mirrors",
    ])
      clip[key] = (
        doc[key] ??
        Array.from({ length: doc.height }, () => Array(doc.width).fill(false))
      )
        .slice(y, y + h)
        .map((r: any[]) => clone(r.slice(x, x + w)));
    for (const key of placements)
      clip[key] = (doc[key] ?? [])
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
      for (const transition of n.transitions ?? [])
        if (transition.id === entry.id + "_transition") {
          transition.x = p.x;
          transition.y = p.y;
        }
      onChange(n);
      return;
    }
    const clip = moving ? copyArea() : clipboard;
    if (!clip) {
      notify("Выделите область или выберите объект");
      return;
    }
    const n = clone(doc);
    n.tile_mirrors ??= Array.from({ length: doc.height }, () =>
      Array(doc.width).fill(false),
    );
    if (moving) {
      for (const pt of selection) {
        n.tiles[pt.y][pt.x] = null;
        n.tile_mirrors[pt.y][pt.x] = false;
        n.walkability[pt.y][pt.x] = true;
        n.blocks_sight[pt.y][pt.x] = false;
        n.roof[pt.y][pt.x] = false;
      }
      for (const key of placements)
        n[key] = (n[key] ?? []).filter(
          (e: Point) => !selection.some((pt) => pt.x === e.x && pt.y === e.y),
        );
    }
    for (const key of [
      "tiles",
      "walkability",
      "blocks_sight",
      "roof",
      "tile_mirrors",
    ])
      clip[key].forEach((r: any[], y: number) =>
        r.forEach((v: any, x: number) => {
          if (inBounds(n, { x: p.x + x, y: p.y + y }))
            n[key][p.y + y][p.x + x] = clone(v);
        }),
      );
    const copyPrefix = "copy_" + Date.now() + "_";
    for (const key of placements)
      for (const e of clip[key])
        if (inBounds(n, { x: p.x + e.x, y: p.y + e.y }))
          (n[key] ??= []).push({
            ...clone(e),
            id: moving ? e.id : copyPrefix + e.id,
            x: p.x + e.x,
            y: p.y + e.y,
          });
    onChange(n);
  }
  function pick(p: Point, temporary = false) {
    const sample = sampleMap(doc, p, layer);
    if (!sample) {
      notify("В клетке нет тайла или объекта для пипетки.");
      return;
    }
    setLayer(sample.layer);
    const sampled = entries.find(
      (e) => e.ref === sample.ref && paletteLayer(e, assets) === sample.layer,
    );
    setSection(
      sampled ? (paletteCategory(sampled, assets) ?? "service") : "service",
    );
    setRef(sample.ref);
    if (sample.layer === "transitions") setTransitionTarget(sample.ref);
    if (["walkability", "blocks_sight", "roof"].includes(sample.layer))
      setMaskValue(doc[sample.layer][p.y][p.x]);
    if (sample.placement?.id && sample.layer === "lights") {
      setSelected({ category: "lights", id: sample.placement.id });
      setPanel("cell");
    }
    if (!temporary) setTool("brush");
    notify("Пипетка: " + (sample.ref || names[sample.layer]));
  }
  function brushPoints(points: Point[]) {
    const expanded: Point[] = [];
    const offset = Math.floor((brushSize - 1) / 2);
    for (const p of points)
      for (let y = 0; y < brushSize; y++)
        for (let x = 0; x < brushSize; x++)
          expanded.push({ x: p.x + x - offset, y: p.y + y - offset });
    return expanded;
  }
  function down(p: Point, modifiers?: PointerModifiers) {
    const mirrored = modifiers?.shiftKey ?? shiftHeld;
    setShiftHeld(mirrored);
    setHover(p);
    if (tool === "picker") {
      pick(p);
      return;
    }

    if (tool === "move" || tool === "paste") {
      paste(p, tool === "move");
      return;
    }
    if (tool === "fill") {
      if (!["tiles", "walkability", "blocks_sight", "roof"].includes(layer)) {
        notify("Заливка доступна для тайлов и масок");
        return;
      }
      onChange(
        paint(
          doc,
          flood(doc[layer], p, (a, b) => a === b),
          false,
          mirrored,
        ),
      );
      return;
    }
    if (tool === "select") {
      const found = placements.flatMap((c) =>
        (doc[c] ?? [])
          .filter((e: Point) => e.x === p.x && e.y === p.y)
          .map((e: Doc) => ({ category: c, id: e.id })),
      );
      found.sort(
        (a, b) =>
          Number(b.category === layer) - Number(a.category === layer) ||
          Number(a.category === "decorations") -
            Number(b.category === "decorations"),
      );
      setSelected(found[0] ?? null);
      setPanel("cell");
    }
    const next = ["brush", "erase"].includes(tool)
      ? paint(doc, brushPoints([p]), tool === "erase", mirrored)
      : clone(doc);
    stroke.current = { base: clone(doc), start: p, last: p, next, mirrored };
    setPreview(next);
  }
  function drag(p: Point, modifiers?: PointerModifiers) {
    const s = stroke.current;
    if (!s) return;
    s.mirrored = modifiers?.shiftKey ?? s.mirrored;
    if (tool === "select") {
      setSelection(rectangle(s.start, p, true));
      return;
    }
    if (tool === "rect")
      s.next = paint(s.base, rectangle(s.start, p, true), false, s.mirrored);
    else if (tool === "line")
      s.next = paint(s.base, line(s.start, p), false, s.mirrored);
    else if (["brush", "erase"].includes(tool))
      s.next = paint(
        s.next,
        brushPoints(line(s.last, p)),
        tool === "erase",
        s.mirrored,
      );
    s.last = p;
    setPreview(s.next);
  }
  function up(p: Point, modifiers?: PointerModifiers) {
    const s = stroke.current;
    if (!s) return;
    if (tool === "select") setSelection(rectangle(s.start, p, true));
    else {
      drag(p, modifiers);
      onChange(s.next);
    }
    stroke.current = null;
    setPreview(null);
  }
  function finishPan(e: React.PointerEvent<HTMLDivElement>) {
    if (!pan.current) return;
    e.preventDefault();
    e.stopPropagation();
    if (e.currentTarget.hasPointerCapture(e.pointerId))
      e.currentTarget.releasePointerCapture(e.pointerId);
    pan.current = null;
    setPanning(false);
  }
  function fit() {
    const view = viewport.current;
    if (!view) return;
    setZoom(
      Math.max(
        1,
        Math.min(
          6,
          Math.floor(
            Math.min(
              (view.clientWidth - 56) / (16 * doc.width),
              (view.clientHeight - 56) / (16 * doc.height),
            ),
          ),
        ),
      ),
    );
    view.scrollTo(0, 0);
  }
  function deleteSelection() {
    const n = clone(doc);
    if (selected) {
      n.transitions = (n.transitions ?? []).filter(
        (entry: Doc) => entry.id !== selected.id + "_transition",
      );
      n[selected.category] = n[selected.category].filter(
        (entry: Doc) => entry.id !== selected.id,
      );
      setSelected(null);
    } else if (selection.length) {
      for (const p of selection) {
        n.tiles[p.y][p.x] = null;
        if (n.tile_mirrors) n.tile_mirrors[p.y][p.x] = false;
        n.walkability[p.y][p.x] = true;
        n.blocks_sight[p.y][p.x] = false;
        n.roof[p.y][p.x] = false;
      }
      for (const key of placements)
        n[key] = (n[key] ?? []).filter(
          (entry: Point) =>
            !selection.some((p) => p.x === entry.x && p.y === entry.y),
        );
    }
    onChange(n);
  }
  useEffect(() => {
    const keydown = (e: KeyboardEvent) => {
      if (
        !shortcutsEnabled ||
        document.querySelector(".modal-backdrop, dialog[open]") ||
        ((e.target as HTMLElement).closest(
          "input,textarea,select,[contenteditable=true]",
        ) &&
          !(e.key === "Shift" && pointerInside))
      )
        return;
      if (e.key === "Shift") {
        setShiftHeld(true);
        return;
      }
      if (e.code === "Space") {
        e.preventDefault();
        setSpaceHeld(true);
        return;
      }
      if (e.altKey) return;
      if (e.ctrlKey || e.metaKey) {
        if (e.code === "KeyC") {
          const copied = copyArea();
          if (copied) {
            e.preventDefault();
            setClipboard(copied);
            notify("Область скопирована. Ctrl+V — вставить.");
          }
        }
        if (e.code === "KeyV" && clipboard) {
          e.preventDefault();
          setTool("paste");
        }
        return;
      }
      const bindings: Record<string, string> = {
        KeyB: "brush",
        KeyI: "picker",
        KeyH: "pan",
        KeyE: "erase",
        KeyR: "rect",
        KeyL: "line",
        KeyG: "fill",
        KeyV: "select",
        KeyM: "move",
      };
      if (bindings[e.code]) {
        e.preventDefault();
        setTool(bindings[e.code]);
      } else if (e.code === "Digit0" || e.code === "Numpad0") {
        e.preventDefault();
        fit();
      } else if (
        ["Equal", "NumpadAdd", "Minus", "NumpadSubtract"].includes(e.code)
      ) {
        e.preventDefault();
        setZoom((z) =>
          Math.max(
            0.2,
            Math.min(
              3,
              z + (["Equal", "NumpadAdd"].includes(e.code) ? 0.1 : -0.1),
            ),
          ),
        );
      } else if (e.code === "Escape") {
        stroke.current = null;
        setPreview(null);
        setSelection([]);
        setSelected(null);
        setTool("brush");
      } else if (e.code === "Delete" && (selected || selection.length)) {
        e.preventDefault();
        deleteSelection();
      }
    };
    const reset = () => {
      setSpaceHeld(false);
      setShiftHeld(false);
      setPointerInside(false);
      setPanning(false);
      pan.current = null;
    };
    const keyup = (e: KeyboardEvent) => {
      if (e.code === "Space") setSpaceHeld(false);
      if (e.key === "Shift") setShiftHeld(false);
    };
    window.addEventListener("keydown", keydown);
    window.addEventListener("keyup", keyup);
    window.addEventListener("blur", reset);
    return () => {
      window.removeEventListener("keydown", keydown);
      window.removeEventListener("keyup", keyup);
      window.removeEventListener("blur", reset);
    };
  });
  useEffect(() => {
    const view = viewport.current;
    if (!view) return;
    const wheel = (e: WheelEvent) => {
      if (!e.ctrlKey || !shortcutsEnabled) return;
      e.preventDefault();
      const next = Math.max(1, Math.min(6, zoom + (e.deltaY < 0 ? 1 : -1)));
      const rect = view.getBoundingClientRect(),
        x = e.clientX - rect.left,
        y = e.clientY - rect.top;
      const left = ((view.scrollLeft + x) * next) / zoom - x,
        top = ((view.scrollTop + y) * next) / zoom - y;
      setZoom(next);
      requestAnimationFrame(() => view.scrollTo(left, top));
    };
    view.addEventListener("wheel", wheel, { passive: false });
    return () => view.removeEventListener("wheel", wheel);
  }, [zoom, shortcutsEnabled]);
  const masks = useMemo(() => mapMasks(shown, assets), [shown, assets]);
  const cells = useMemo(
    () => mapGrid(shown, assets, visibility),
    [shown, assets, visibility],
  );
  const overlays = useMemo(() => {
    const result = [];
    if (visibility.walkability)
      result.push({
        cells: masks.walkability.map((r: boolean[]) => r.map((v) => !v)),
        color: "#f071784d",
      });
    if (visibility.blocks_sight)
      result.push({ cells: masks.blocks_sight, color: "#8bb7ee55" });
    if (visibility.roof || layer === "roof")
      result.push({ cells: shown.roof, color: "#a890d980" });
    const isolated = warnings.flatMap((w) => w.cells ?? []);
    const isolatedSet = new Set(isolated.map((p: Point) => `${p.x},${p.y}`));
    if (isolated.length)
      result.push({
        cells: Array.from({ length: doc.height }, (_, y) =>
          Array.from({ length: doc.width }, (_, x) =>
            isolatedSet.has(`${x},${y}`),
          ),
        ),
        color: "#edc87555",
      });
    return result;
  }, [masks, visibility, warnings, doc.height, doc.width, shown.roof, layer]);
  const ghost = useMemo(() => {
    if (
      !pointerInside ||
      panning ||
      spaceHeld ||
      paletteEmpty ||
      !shortcutsEnabled ||
      !["brush", "rect", "line", "fill"].includes(tool) ||
      ![
        "tiles",
        "objects",
        "doors",
        "equipment",
        "points_of_interest",
        "traps",
        "monsters",
      ].includes(layer)
    )
      return [];
    const definition = assets[category + "/" + chosen];
    if (!definition) return [];
    const cell = visual(definition, assets);
    cell.mirror_x = !!definition.mirror_x !== shiftHeld;
    return (tool === "brush" ? brushPoints([hover]) : [hover])
      .filter((p) => inBounds(doc, p))
      .map((point) => ({ point, cell }));
  }, [
    pointerInside,
    panning,
    spaceHeld,
    paletteEmpty,
    shortcutsEnabled,
    tool,
    layer,
    category,
    chosen,
    assets,
    shiftHeld,
    hover.x,
    hover.y,
    brushSize,
    doc.width,
    doc.height,
  ]);
  return (
    <div className="editor-layout map-editor">
      <div className="workspace">
        <div className="toolbar">
          {[
            ["brush", "Кисть", "B"],
            ["picker", "Пипетка", "I"],
            ["pan", "Рука", "H / ПКМ"],
            ["erase", "Удалить", "E"],
            ["rect", "Прямоугольник", "R"],
            ["line", "Линия", "L"],
            ["fill", "Заливка", "G"],
            ["select", "Выбрать", "V"],
            ["move", "Перенести", "M"],
            ["paste", "Вставить", "Ctrl+V"],
          ].map(([id, name, shortcut]) => (
            <button
              key={id}
              title={name + " · " + shortcut}
              className={tool === id ? "active" : ""}
              onClick={() => setTool(id)}
            >
              {name}
              <kbd>{shortcut}</kbd>
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
            Копировать<kbd>Ctrl+C</kbd>
          </button>
        </div>
        <div className="toolbar map-options">
          <span className="layer-badge">{names[layer]}</span>
          {["walkability", "blocks_sight", "roof"].includes(layer) && (
            <label>
              <input
                type="checkbox"
                checked={maskValue}
                onChange={(e) => setMaskValue(e.target.checked)}
              />
              {layer === "walkability"
                ? "Разрешить проход"
                : layer === "roof"
                  ? "Крыша над клеткой"
                  : "Преграждать обзор"}
            </label>
          )}
          {layer === "tiles" && (
            <>
              <label>
                <input
                  type="checkbox"
                  checked={initTile}
                  onChange={(e) => setInitTile(e.target.checked)}
                />
                Начальные маски тайла
              </label>
              <label title="Добавлять привязанные ловушки, свет, взаимодействия и предметы">
                <input
                  aria-label="Механика кисти"
                  type="checkbox"
                  checked={applyMechanics}
                  onChange={(e) => setApplyMechanics(e.target.checked)}
                />
                Механика кисти
              </label>
            </>
          )}
          <label>
            Кисть{" "}
            <select
              aria-label="Размер кисти"
              value={brushSize}
              onChange={(e) => setBrushSize(Number(e.target.value))}
            >
              {[1, 2, 3, 5, 8].map((size) => (
                <option key={size} value={size}>
                  {size} × {size}
                </option>
              ))}
            </select>
          </label>
          <span className="coordinate">
            {hover.x}, {hover.y}
          </span>
        </div>
        <div
          className={
            "canvas-scroll map-viewport " +
            (panning || spaceHeld || tool === "pan" ? "is-panning" : "")
          }
          ref={viewport}
          onContextMenu={(e) => e.preventDefault()}
          onPointerDownCapture={(e) => {
            if (
              e.button !== 2 &&
              e.button !== 1 &&
              !(e.button === 0 && (spaceHeld || tool === "pan"))
            )
              return;
            e.preventDefault();
            e.stopPropagation();
            const view = e.currentTarget;
            setPointerInside(false);
            view.setPointerCapture(e.pointerId);
            pan.current = {
              x: e.clientX,
              y: e.clientY,
              left: view.scrollLeft,
              top: view.scrollTop,
              pointer: e.pointerId,
            };
            setPanning(true);
          }}
          onPointerMoveCapture={(e) => {
            const start = pan.current;
            if (!start) return;
            e.preventDefault();
            e.stopPropagation();
            e.currentTarget.scrollLeft = start.left - (e.clientX - start.x);
            e.currentTarget.scrollTop = start.top - (e.clientY - start.y);
          }}
          onPointerUpCapture={finishPan}
          onPointerCancelCapture={finishPan}
        >
          <Grid
            cells={cells}
            square={true}
            symbols={symbolMode}
            overlays={overlays}
            selection={selection}
            zoom={zoom}
            grid={grid}
            ghost={ghost}
            onDown={(p, modifiers) =>
              modifiers?.altKey ? pick(p, true) : down(p, modifiers)
            }
            onDrag={drag}
            onUp={up}
            onHover={(p, modifiers) => {
              setHover(p);
              setPointerInside(true);
              setShiftHeld(!!modifiers?.shiftKey);
            }}
            onLeave={() => setPointerInside(false)}
          />
        </div>
        <div className="map-shortcuts">
          ПКМ / Space + перетаскивание — двигать карту · Alt + клик — пипетка ·
          Ctrl + колесо — масштаб · Shift при рисовании — зеркально по
          горизонтали
          {shiftHeld && <strong> · Отражение включено</strong>}
        </div>
        <div className="toolbar">
          <label>
            Клетка {zoom * 16}×{zoom * 16}{" "}
            <input
              type="range"
              aria-label="Масштаб карты"
              min="1"
              max="6"
              step="1"
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
            />
          </label>
          <button onClick={() => setSymbolMode((v) => !v)}>
            {symbolMode ? "Символы" : "Текст"}
          </button>
          <button title="Вписать карту (0)" onClick={fit}>
            Вписать
          </button>
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
              aria-label="Ширина карты"
              min="1"
              max="256"
              value={width}
              onChange={(e) => setWidth(Number(e.target.value))}
            />{" "}
            ×{" "}
            <input
              className="short"
              type="number"
              aria-label="Высота карты"
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
      <aside className="inspector map-sidebar">
        <div className="map-side-tabs">
          <button
            className={panel === "palette" ? "selected" : ""}
            onClick={() => setPanel("palette")}
          >
            Палитра
          </button>
          <button
            className={panel === "cell" ? "selected" : ""}
            onClick={() => setPanel("cell")}
          >
            Клетка
          </button>
          <button
            className={panel === "settings" ? "selected" : ""}
            onClick={() => setPanel("settings")}
          >
            Карта
          </button>
        </div>
        {panel === "palette" ? (
          <MapPalette
            entries={entries}
            assets={assets}
            layer={layer}
            section={section}
            onSection={(next) => {
              setSection(next);
              const candidates = entries.filter(
                (e) => paletteCategory(e, assets) === next,
              );
              const first =
                candidates.find(
                  (e) =>
                    e.ref ===
                    (
                      { floor: "base:floor", wall: "base:wall" } as Record<
                        string,
                        string
                      >
                    )[next],
                ) ?? candidates[0];
              setLayer(
                next === "service"
                  ? "spawn"
                  : first
                    ? paletteLayer(first, assets)!
                    : "objects",
              );
              setRef(first?.ref ?? "");
              setTool("brush");
            }}
            onLayer={(next) => {
              setLayer(next);
              setRef("");
              setTool("brush");
              if (next === "roof") setMaskValue(true);
            }}
            chosen={chosen}
            onChoose={(next, nextLayer) => {
              if (nextLayer) setLayer(nextLayer);
              const selectedEntry = entries.find(
                (e) =>
                  e.ref === next &&
                  paletteLayer(e, assets) === (nextLayer ?? layer),
              );
              if (selectedEntry)
                setSection(paletteCategory(selectedEntry, assets) ?? "service");
              if ((nextLayer ?? layer) === "transitions")
                setTransitionTarget(next);
              else setRef(next);
              setTool("brush");
            }}
            target={transitionTarget}
            onTarget={setTransitionTarget}
            documentRef={documentRef}
            onEmpty={setPaletteEmpty}
          />
        ) : (
          <div className="map-inspector-content">
            {panel === "settings" && (
              <>
                <h3>Освещение</h3>
                <select
                  aria-label="Освещение карты"
                  value={doc.ambient_light ?? "bright"}
                  onChange={(e) =>
                    onChange({ ...doc, ambient_light: e.target.value })
                  }
                >
                  <option value="dark">Темнота</option>
                  <option value="dim">Полумрак</option>
                  <option value="bright">Яркий свет</option>
                </select>
                <p className="hint">
                  Слой «Источники света»: рисуйте стационарные огни. Маска
                  преград обзору перекрывает свет; в тесте свет также дают
                  факелы и лампы в руках. Слой «Крыша» убирает общий свет на
                  закрытых клетках, не перекрывая свет от источников.
                </p>
                <h3>Оверлеи</h3>
                {Object.entries(names)
                  .filter(([k]) => k !== "tiles" && k !== "spawn")
                  .map(([key, name]) => (
                    <label className="toggle" key={key}>
                      <input
                        type="checkbox"
                        checked={visibility[key] ?? key !== "blocks_sight"}
                        onChange={(e) =>
                          setVisibility({
                            ...visibility,
                            [key]: e.target.checked,
                          })
                        }
                      />
                      {name}
                    </label>
                  ))}
                <p className="hint">
                  Красный — нет прохода. Синий — преграда обзору. Жёлтый —
                  недостижимые участки. Фиолетовый — крыша (при рисовании крыши
                  виден всегда). Графика не определяет эти маски.
                </p>
              </>
            )}
            {panel === "cell" && (
              <>
                {selected &&
                  (() => {
                    const placement = (doc[selected.category] ?? []).find(
                      (p: Doc) => p.id === selected.id,
                    );
                    if (!placement || !placement.ref) return null;
                    return (
                      <InstanceInspector
                        placement={placement}
                        layer={selected.category}
                        schemas={schemas}
                        mechanics={mechanics}
                        assets={assets}
                        entries={entries}
                        onChange={(changes) => {
                          const category =
                            selected.category === "doors"
                              ? "objects"
                              : selected.category;
                          const base = assets[category + "/" + placement.ref];
                          if (
                            selected.category === "doors" &&
                            placement.x === doc.spawn.x &&
                            placement.y === doc.spawn.y &&
                            instanceDocument(base, { ...placement, ...changes })
                              .brush.door.state !== "open"
                          ) {
                            notify(
                              "Закрытая дверь не может занимать старт героя.",
                            );
                            return;
                          }
                          onChange({
                            ...doc,
                            [selected.category]: doc[selected.category].map(
                              (p: Doc) =>
                                p.id === placement.id
                                  ? { ...p, ...changes }
                                  : p,
                            ),
                          });
                        }}
                      />
                    );
                  })()}
                {selected?.category === "lights" &&
                  (() => {
                    const source = (doc.lights ?? []).find(
                      (p: Doc) => p.id === selected.id,
                    );
                    if (!source) return null;
                    const update = (changes: Doc) =>
                      onChange({
                        ...doc,
                        lights: doc.lights.map((p: Doc) =>
                          p.id === source.id ? { ...p, ...changes } : p,
                        ),
                      });
                    return (
                      <section>
                        <label>
                          Радиус света{" "}
                          <input
                            className="short"
                            type="number"
                            min="1"
                            max="32"
                            value={source.radius}
                            onChange={(e) => {
                              const radius = Math.max(
                                1,
                                Math.min(32, Number(e.target.value)),
                              );
                              update({
                                radius,
                                bright_radius: Math.min(
                                  source.bright_radius,
                                  radius,
                                ),
                              });
                            }}
                          />
                        </label>
                        <label>
                          Яркий радиус{" "}
                          <input
                            className="short"
                            type="number"
                            min="0"
                            max={source.radius}
                            value={source.bright_radius}
                            onChange={(e) =>
                              update({
                                bright_radius: Math.max(
                                  0,
                                  Math.min(
                                    source.radius,
                                    Number(e.target.value),
                                  ),
                                ),
                              })
                            }
                          />
                        </label>
                        <label>
                          <input
                            type="checkbox"
                            checked={source.enabled}
                            onChange={(e) =>
                              update({ enabled: e.target.checked })
                            }
                          />{" "}
                          Включён
                        </label>
                      </section>
                    );
                  })()}
                <h3>
                  Клетка {hover.x}, {hover.y}
                </h3>
                <label>
                  <input
                    type="checkbox"
                    aria-label="Отразить тайл в клетке"
                    checked={!!doc.tile_mirrors?.[hover.y]?.[hover.x]}
                    onChange={(e) => {
                      const n = clone(doc);
                      n.tile_mirrors ??= Array.from(
                        { length: doc.height },
                        () => Array(doc.width).fill(false),
                      );
                      n.tile_mirrors[hover.y][hover.x] = e.target.checked;
                      onChange(n);
                    }}
                  />{" "}
                  Отразить тайл по горизонтали
                </label>
                <dl>
                  <dt>Тайл</dt>
                  <dd>{doc.tiles[hover.y]?.[hover.x] ?? "Нет"}</dd>
                  <dt>Крыша</dt>
                  <dd>{doc.roof[hover.y]?.[hover.x] ? "Да" : "Нет"}</dd>
                  <dt>Проход</dt>
                  <dd>
                    {masks.walkability[hover.y]?.[hover.x] ? "Да" : "Нет"}
                  </dd>
                  <dt>Обзор</dt>
                  <dd>
                    {masks.blocks_sight[hover.y]?.[hover.x]
                      ? "Закрыт"
                      : "Открыт"}
                  </dd>
                </dl>
                {placements.map((key) =>
                  (doc[key] ?? [])
                    .filter((p: Point) => p.x === hover.x && p.y === hover.y)
                    .map((p: Doc) => (
                      <button
                        key={p.id}
                        className={
                          "object-card " +
                          (selected?.id === p.id ? "selected" : "")
                        }
                        onClick={() => {
                          setSelected({ category: key, id: p.id });
                          setTool("select");
                        }}
                      >
                        <strong>{names[key]}</strong>
                        <span>
                          {p.ref ?? p.target ?? `${p.radius} кл. света`}
                        </span>
                        <small>{p.id}</small>
                      </button>
                    )),
                )}
                {selected && (
                  <div className="toolbar">
                    <button onClick={() => setTool("move")}>
                      Переместить объект
                    </button>
                    <button
                      onClick={() => {
                        deleteSelection();
                      }}
                    >
                      Удалить объект
                    </button>
                  </div>
                )}
              </>
            )}
            {panel === "settings" && (
              <>
                <h3>Проверка карты</h3>
                {warnings.length ? (
                  warnings.map((w, i) => (
                    <p className="warning" key={i}>
                      {w.message}
                    </p>
                  ))
                ) : (
                  <p className="hint">
                    Проверка связности обновляется после сохранения.
                    Изолированные комнаты разрешены.
                  </p>
                )}
              </>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
