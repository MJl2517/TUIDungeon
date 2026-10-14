import { visual } from "./symbolModel";
export type Doc = Record<string, any>;
export type Cell = {
  char: string;
  symbol?: string;
  mirror_x?: boolean;
  rotation?: number;
  foreground: number;
  background: number | null;
} | null;
export type Point = { x: number; y: number };
export type Entry = {
  category: string;
  ref: string;
  id: string;
  name: string;
  version: string;
  glyph?: string;
  symbol?: string;
  classes?: string[];
  group?: string | null;
  tags?: string[];
  description?: string;
  asset?: boolean;
  details?: Doc;
  features?: Record<string, boolean>;
  search_text?: string;
  usage_count?: number;
  source_name?: string;
};

export const materialTagLabels: Record<string, string> = {
  flammable: "Горючий",
  wooden: "Деревянный",
};

export function matchesEntry(
  entry: Entry,
  query: string,
  assets: Record<string, Doc> = {},
): boolean {
  const text = [
    entry.name,
    entry.ref,
    entry.glyph ?? "",
    entry.group ?? "",
    entry.description ?? "",
    entry.search_text ?? "",
    JSON.stringify(entry.details ?? {}),
    JSON.stringify(assets[entry.category + "/" + entry.ref] ?? {}),
    ...(entry.tags ?? []),
    ...(entry.tags ?? []).map((tag) => materialTagLabels[tag] ?? ""),
  ]
    .join(" ")
    .toLocaleLowerCase("ru");
  return query
    .trim()
    .toLocaleLowerCase("ru")
    .split(/\s+/)
    .every((word) => text.includes(word));
}
export function assetVersionsMatch(
  entries: Entry[],
  versions: Record<string, string>,
): boolean {
  const expected = entries.filter((e) => e.asset);
  return (
    expected.length === Object.keys(versions).length &&
    expected.every((e) => versions[e.category + "/" + e.ref] === e.version)
  );
}
export function libraryResults(
  entries: Entry[],
  query: string,
  category: string,
  pack: string,
  assets: Record<string, Doc> = {},
): Entry[] {
  return entries.filter(
    (e) =>
      (category === "all" || e.category === category) &&
      (pack === "all" || e.ref.startsWith(pack + ":")) &&
      matchesEntry(e, query, assets),
  );
}
export const clone = <T>(value: T): T => structuredClone(value);
// Instance documents inherit objects recursively; arrays and null replace.
export function mergeProperties(base: Doc, patch: Doc = {}): Doc {
  const result = clone(base);
  for (const [key, value] of Object.entries(patch))
    result[key] =
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      result[key] &&
      typeof result[key] === "object" &&
      !Array.isArray(result[key])
        ? mergeProperties(result[key], value)
        : clone(value);
  return result;
}
export function diffProperties(base: Doc, value: Doc): Doc {
  const patch: Doc = {};
  for (const [key, next] of Object.entries(value)) {
    if (JSON.stringify(base[key]) === JSON.stringify(next)) continue;
    const nested =
      next &&
      typeof next === "object" &&
      !Array.isArray(next) &&
      base[key] &&
      typeof base[key] === "object" &&
      !Array.isArray(base[key]);
    const change = nested ? diffProperties(base[key], next) : clone(next);
    if (!nested || Object.keys(change).length) patch[key] = change;
  }
  return patch;
}
export function instanceDocument(base: Doc, placement: Doc): Doc {
  const result = mergeProperties(base, placement.overrides);
  if (
    "glyph" in (placement.overrides ?? {}) &&
    !("symbol" in placement.overrides)
  )
    result.symbol = null;
  const door = result.brush?.door;
  if (door) {
    if (door.material === "stone") {
      door.state = "closed";
      door.locked = false;
    }
    result.glyph =
      door.material === "stone"
        ? "#"
        : door.state === "open"
          ? "/"
          : door.bent
            ? "%"
            : door.locked
              ? "X"
              : "+";
    result.foreground =
      door.foreground ??
      (
        { wood: 130, stone: 244, bars: 250, steel: 117, adamantine: 201 } as Doc
      )[door.material];
    result.walkable = door.state === "open" || !!door.bent;
    result.blocks_sight =
      !result.walkable && door.material !== "bars" && !door.transmits_light;
  }
  return result;
}
export function color(n: number): string {
  const base = [
    "#11151b",
    "#b74445",
    "#70a76a",
    "#c5a15c",
    "#658fcb",
    "#ad77c1",
    "#66b4b4",
    "#c8ccd4",
    "#647180",
    "#f07178",
    "#9bce81",
    "#edc875",
    "#91b8ed",
    "#d6a0ec",
    "#94dddd",
    "#f5f1e6",
  ];
  if (n < 16) return base[n];
  if (n >= 232) {
    const c = 8 + (n - 232) * 10;
    return `rgb(${c},${c},${c})`;
  }
  const v = [0, 95, 135, 175, 215, 255];
  n -= 16;
  return `rgb(${v[Math.floor(n / 36)]},${v[Math.floor(n / 6) % 6]},${v[n % 6]})`;
}
export function overlay(lower: Cell, upper: Cell): Cell {
  return upper
    ? { ...upper, background: upper.background ?? lower?.background ?? null }
    : lower;
}
export function compose(doc: Doc): Cell[][] {
  const grid: Cell[][] = Array.from({ length: doc.height }, () =>
    Array(doc.width).fill(null),
  );
  for (const layer of doc.layers)
    if (layer.visible)
      for (let y = 0; y < doc.height; y++)
        for (let x = 0; x < doc.width; x++)
          grid[y][x] = overlay(grid[y][x], layer.cells[y][x]);
  return grid;
}
export const inBounds = (doc: Doc, p: Point) =>
  p.x >= 0 && p.y >= 0 && p.x < doc.width && p.y < doc.height;
export function line(a: Point, b: Point): Point[] {
  const result: Point[] = [];
  let { x, y } = a;
  const dx = Math.abs(b.x - x),
    sx = x < b.x ? 1 : -1,
    dy = -Math.abs(b.y - y),
    sy = y < b.y ? 1 : -1;
  let err = dx + dy;
  while (true) {
    result.push({ x, y });
    if (x === b.x && y === b.y) break;
    const e = 2 * err;
    if (e >= dy) {
      err += dy;
      x += sx;
    }
    if (e <= dx) {
      err += dx;
      y += sy;
    }
  }
  return result;
}
export function rectangle(a: Point, b: Point, filled = false): Point[] {
  const r: Point[] = [];
  for (let y = Math.min(a.y, b.y); y <= Math.max(a.y, b.y); y++)
    for (let x = Math.min(a.x, b.x); x <= Math.max(a.x, b.x); x++)
      if (filled || x === a.x || x === b.x || y === a.y || y === b.y)
        r.push({ x, y });
  return r;
}
export function flood<T>(
  grid: T[][],
  start: Point,
  equal: (a: T, b: T) => boolean,
): Point[] {
  const target = grid[start.y]?.[start.x];
  if (target === undefined) return [];
  const result: Point[] = [];
  const seen = new Set<string>(),
    pending = [start];
  while (pending.length) {
    const p = pending.pop()!,
      key = `${p.x},${p.y}`;
    if (
      seen.has(key) ||
      !grid[p.y] ||
      p.x < 0 ||
      p.x >= grid[p.y].length ||
      !equal(grid[p.y][p.x], target)
    )
      continue;
    seen.add(key);
    result.push(p);
    pending.push(
      { x: p.x + 1, y: p.y },
      { x: p.x - 1, y: p.y },
      { x: p.x, y: p.y + 1 },
      { x: p.x, y: p.y - 1 },
    );
  }
  return result;
}
export class History<T> {
  past: T[] = [];
  future: T[] = [];
  constructor(public present: T) {}
  commit(value: T) {
    if (JSON.stringify(value) === JSON.stringify(this.present)) return;
    this.past.push(clone(this.present));
    if (this.past.length > 100) this.past.shift();
    this.present = clone(value);
    this.future = [];
  }
  undo() {
    if (!this.past.length) return;
    this.future.push(clone(this.present));
    this.present = this.past.pop()!;
  }
  redo() {
    if (!this.future.length) return;
    this.past.push(clone(this.present));
    this.present = this.future.pop()!;
  }
}
export function resizeArt(doc: Doc, width: number, height: number): Doc {
  const next = clone(doc);
  next.width = width;
  next.height = height;
  for (const layer of next.layers)
    layer.cells = Array.from({ length: height }, (_, y) =>
      Array.from({ length: width }, (_, x) => layer.cells[y]?.[x] ?? null),
    );
  return next;
}
export function resizeMap(doc: Doc, width: number, height: number): Doc {
  const next = clone(doc);
  next.width = width;
  next.height = height;
  for (const key of [
    "tiles",
    "walkability",
    "blocks_sight",
    "roof",
    "tile_mirrors",
    "tile_rotations",
  ])
    next[key] = Array.from({ length: height }, (_, y) =>
      Array.from(
        { length: width },
        (_, x) =>
          doc[key]?.[y]?.[x] ??
          (key === "tiles"
            ? null
            : key === "tile_rotations"
              ? 0
              : key === "walkability"),
      ),
    );
  for (const key of placements)
    next[key] = (next[key] ?? []).filter(
      (p: Point) => p.x < width && p.y < height,
    );
  next.spawn = {
    x: Math.min(doc.spawn.x, width - 1),
    y: Math.min(doc.spawn.y, height - 1),
  };
  return next;
}
export const placements = [
  "objects",
  "decorations",
  "doors",
  "traps",
  "points_of_interest",
  "monsters",
  "equipment",
  "transitions",
  "lights",
];
export function mapMasks(doc: Doc, assets: Record<string, Doc>) {
  const walkability: boolean[][] = clone(doc.walkability);
  const blocks_sight: boolean[][] = clone(doc.blocks_sight);
  for (const p of doc.objects ?? []) {
    const base = assets["objects/" + p.ref];
    if (!base) continue;
    const object = instanceDocument(base, p);
    walkability[p.y][p.x] &&= object.walkable;
    blocks_sight[p.y][p.x] ||= object.blocks_sight;
  }
  for (const p of doc.doors ?? []) {
    const base = assets["objects/" + p.ref];
    if (!base) continue;
    const door = instanceDocument(base, p);
    walkability[p.y][p.x] = door.walkable;
    blocks_sight[p.y][p.x] = door.blocks_sight;
  }
  return { walkability, blocks_sight };
}
export function mapGrid(
  doc: Doc,
  assets: Record<string, Doc>,
  visible: Record<string, boolean> = {},
): Cell[][] {
  const grid: Cell[][] = doc.tiles.map((row: (string | null)[], y: number) =>
    row.map((ref, x) => {
      const t = ref ? assets["tiles/" + ref] : null;
      const cell = t ? visual(t, assets) : null;
      return cell
        ? {
            ...cell,
            mirror_x: !!cell.mirror_x !== !!doc.tile_mirrors?.[y]?.[x],
            rotation:
              (cell.rotation + (doc.tile_rotations?.[y]?.[x] ?? 0)) % 360,
          }
        : null;
    }),
  );
  for (const key of placements) {
    if (visible[key] === false) continue;
    for (const p of doc[key] ?? []) {
      if (key === "decorations") {
        const base = assets["art/" + p.ref];
        const art = base ? instanceDocument(base, p) : null;
        if (art)
          compose(art).forEach((row, y) =>
            row.forEach((c, x) => {
              if (grid[p.y + y] && p.x + x < doc.width)
                grid[p.y + y][p.x + x] = overlay(
                  grid[p.y + y][p.x + x],
                  c ? visual(c, assets) : null,
                );
            }),
          );
      } else if (key === "transitions") {
        if (!(doc.objects ?? []).some((o: Point) => o.x === p.x && o.y === p.y))
          grid[p.y][p.x] = visual({ glyph: ">", foreground: 14 }, assets);
      } else if (key === "lights") {
        if (doc.tiles[p.y]?.[p.x]) continue;
        grid[p.y][p.x] = visual(
          { glyph: "*", foreground: p.enabled ? 11 : 8 },
          assets,
        );
      } else {
        const base = assets[(key === "doors" ? "objects" : key) + "/" + p.ref];
        const d = base ? instanceDocument(base, p) : null;
        if (d) grid[p.y][p.x] = visual(d, assets);
      }
    }
  }
  grid[doc.spawn.y][doc.spawn.x] = {
    ...visual({ symbol: "base:hero", glyph: "@", foreground: 15 }, assets),
  };
  return grid;
}
export function defaultFor(schema: Doc, root: Doc): any {
  if (schema.$ref)
    return defaultFor(root.$defs[schema.$ref.split("/").pop()!], root);
  if ("default" in schema) return clone(schema.default);
  if (schema.anyOf)
    return defaultFor(
      schema.anyOf.find((s: Doc) => s.type !== "null") ?? schema.anyOf[0],
      root,
    );
  if (schema.enum) return schema.enum[0];
  if (schema.type === "array") return [];
  if (schema.type === "object") {
    const obj: Doc = {};
    for (const [k, v] of Object.entries(schema.properties ?? {}))
      obj[k] = defaultFor(v as Doc, root);
    return obj;
  }
  if (schema.type === "integer" || schema.type === "number")
    return schema.minimum ?? 0;
  if (schema.type === "boolean") return false;
  return schema.title === "Id" ? "new_action" : "";
}
