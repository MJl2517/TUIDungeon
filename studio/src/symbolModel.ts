import type { Doc, Point } from "./model";

export const blankMask = () => Array<string>(16).fill("0".repeat(16));
export const glyphRef = (char: string) =>
  `base:glyph_${(char.codePointAt(0) ?? 32).toString(16).padStart(4, "0")}`;
export function visual(doc: Doc, assets: Record<string, Doc>, state?: string) {
  const door = doc.brush?.door;
  const key =
    state ??
    (door
      ? door.state === "open"
        ? "open"
        : door.locked
          ? "locked"
          : "closed"
      : undefined);
  const ref =
    (key && doc.state_symbols?.[key]) ||
    doc.symbol ||
    glyphRef(doc.glyph ?? doc.char ?? "?");
  const symbol = assets["symbols/" + ref];
  return {
    symbol: symbol ? ref : undefined,
    char: symbol?.glyph ?? doc.glyph ?? doc.char ?? "?",
    foreground: doc.foreground ?? 7,
    background: doc.background ?? null,
  };
}
export function paintMask(mask: string[], points: Point[], value: string) {
  const next = mask.map((row) => row.split(""));
  for (const p of points)
    if (p.x >= 0 && p.y >= 0 && p.x < 16 && p.y < 16) next[p.y][p.x] = value;
  return next.map((row) => row.join(""));
}
export function fillMask(mask: string[], start: Point, value: string) {
  const original = mask[start.y][start.x];
  if (original === value) return mask;
  const todo = [start],
    seen = new Set<string>(),
    points: Point[] = [];
  while (todo.length) {
    const p = todo.pop()!,
      key = `${p.x},${p.y}`;
    if (
      p.x < 0 ||
      p.y < 0 ||
      p.x >= 16 ||
      p.y >= 16 ||
      seen.has(key) ||
      mask[p.y][p.x] !== original
    )
      continue;
    seen.add(key);
    points.push(p);
    todo.push(
      { x: p.x - 1, y: p.y },
      { x: p.x + 1, y: p.y },
      { x: p.x, y: p.y - 1 },
      { x: p.x, y: p.y + 1 },
    );
  }
  return paintMask(mask, points, value);
}
export function transformMask(
  mask: string[],
  kind: "flipX" | "flipY" | "rotate",
) {
  return Array.from({ length: 16 }, (_, y) =>
    Array.from({ length: 16 }, (_, x) =>
      kind === "rotate"
        ? mask[15 - x][y]
        : kind === "flipX"
          ? mask[y][15 - x]
          : mask[15 - y][x],
    ).join(""),
  );
}
const images = new WeakMap<Doc, HTMLCanvasElement>();
export function symbolCanvas(doc: Doc) {
  let canvas = images.get(doc);
  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.width = canvas.height = 16;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "white";
    doc.pixels.forEach((row: string, y: number) =>
      Array.from(row).forEach((c, x) => {
        if (c === "1") ctx.fillRect(x, y, 1, 1);
      }),
    );
    images.set(doc, canvas);
  }
  return canvas;
}
export function drawSymbol(
  ctx: CanvasRenderingContext2D,
  doc: Doc,
  x: number,
  y: number,
  w: number,
  h: number,
  tint: string,
) {
  // Cache tinted images per immutable asset object, not per map cell.
  let variants = tinted.get(doc);
  if (!variants) {
    variants = new Map();
    tinted.set(doc, variants);
  }
  let image = variants.get(tint);
  if (!image) {
    image = document.createElement("canvas");
    image.width = image.height = 16;
    const c = image.getContext("2d")!;
    c.drawImage(symbolCanvas(doc), 0, 0);
    c.globalCompositeOperation = "source-in";
    c.fillStyle = tint;
    c.fillRect(0, 0, 16, 16);
    variants.set(tint, image);
  }
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(image, x, y, w, h);
}
const tinted = new WeakMap<Doc, Map<string, HTMLCanvasElement>>();
