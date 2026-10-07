export type Doc = Record<string, any>;
export type Cell = {
  char: string;
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
};
export const clone = <T>(value: T): T => structuredClone(value);
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
  for (const key of ["tiles", "walkability", "blocks_sight"])
    next[key] = Array.from({ length: height }, (_, y) =>
      Array.from(
        { length: width },
        (_, x) =>
          doc[key][y]?.[x] ?? (key === "tiles" ? null : key === "walkability"),
      ),
    );
  for (const key of placements)
    next[key] = next[key].filter((p: Point) => p.x < width && p.y < height);
  next.spawn = {
    x: Math.min(doc.spawn.x, width - 1),
    y: Math.min(doc.spawn.y, height - 1),
  };
  return next;
}
export const placements = [
  "decorations",
  "traps",
  "points_of_interest",
  "monsters",
  "equipment",
  "transitions",
];
export function mapGrid(
  doc: Doc,
  assets: Record<string, Doc>,
  visible: Record<string, boolean> = {},
): Cell[][] {
  const grid: Cell[][] = doc.tiles.map((row: (string | null)[]) =>
    row.map((ref) => {
      const t = ref ? assets["tiles/" + ref] : null;
      return t
        ? { char: t.glyph, foreground: t.foreground, background: t.background }
        : null;
    }),
  );
  for (const key of placements) {
    if (visible[key] === false) continue;
    for (const p of doc[key] ?? []) {
      if (key === "decorations") {
        const art = assets["art/" + p.ref];
        if (art)
          compose(art).forEach((row, y) =>
            row.forEach((c, x) => {
              if (grid[p.y + y] && p.x + x < doc.width)
                grid[p.y + y][p.x + x] = overlay(grid[p.y + y][p.x + x], c);
            }),
          );
      } else if (key === "transitions")
        grid[p.y][p.x] = { char: ">", foreground: 14, background: null };
      else {
        const d = assets[key + "/" + p.ref];
        if (d)
          grid[p.y][p.x] = {
            char: d.glyph,
            foreground: d.foreground,
            background: d.background,
          };
      }
    }
  }
  grid[doc.spawn.y][doc.spawn.x] = {
    char: "@",
    foreground: 15,
    background: null,
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
