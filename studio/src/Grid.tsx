import { useContext, useLayoutEffect, useRef } from "react";
import { SymbolContext } from "./Symbols";
import { drawSymbol } from "./symbolModel";
import { Cell, Point, color } from "./model";
type Props = {
  cells: Cell[][];
  zoom?: number;
  grid?: boolean;
  square?: boolean;
  symbols?: boolean;
  overlays?: { cells: boolean[][]; color: string }[];
  selection?: Point[];
  ghost?: { point: Point; cell: Cell }[];
  onDown?: (p: Point, modifiers?: PointerModifiers) => void;
  onDrag?: (p: Point, modifiers?: PointerModifiers) => void;
  onUp?: (p: Point, modifiers?: PointerModifiers) => void;
  onHover?: (p: Point, modifiers?: PointerModifiers) => void;
  onLeave?: () => void;
};
export type PointerModifiers = { altKey: boolean; shiftKey: boolean };
export function Grid({
  cells,
  zoom = 1,
  grid = true,
  square = false,
  symbols = false,
  overlays = [],
  selection = [],
  ghost = [],
  onDown,
  onDrag,
  onUp,
  onHover,
  onLeave,
}: Props) {
  const { assets } = useContext(SymbolContext);
  const ref = useRef<HTMLCanvasElement>(null),
    ghostRef = useRef<HTMLCanvasElement>(null),
    drag = useRef(false);
  const cw = (square ? 16 : 12) * zoom,
    ch = (square ? 16 : 20) * zoom,
    w = cells[0]?.length ?? 1,
    h = cells.length;
  useLayoutEffect(() => {
    const canvas = ref.current!,
      ctx = canvas.getContext("2d")!;
    const dpr = window.devicePixelRatio || 1;
    const width = Math.round(w * cw * dpr),
      height = Math.round(h * ch * dpr);
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#11151b";
    ctx.fillRect(0, 0, w * cw, h * ch);
    ctx.font = `${16 * zoom}px "DejaVu Sans Mono",Consolas,monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    cells.forEach((row, y) =>
      row.forEach((c, x) => {
        if (c?.background != null) {
          ctx.fillStyle = color(c.background);
          ctx.fillRect(x * cw, y * ch, cw, ch);
        } else if (!c && (x + y) % 2 === 0) {
          ctx.fillStyle = "#191f27";
          ctx.fillRect(x * cw, y * ch, cw, ch);
        }
        if (c) {
          ctx.fillStyle = color(c.foreground);
          const image = c.symbol ? assets["symbols/" + c.symbol] : undefined;
          if (symbols && image)
            drawSymbol(
              ctx,
              image,
              x * cw,
              y * ch,
              cw,
              ch,
              color(c.foreground),
              !!c.mirror_x,
              c.rotation ?? 0,
            );
          else ctx.fillText(c.char, (x + 0.5) * cw, (y + 0.5) * ch);
        }
      }),
    );
    for (const layer of overlays) {
      ctx.fillStyle = layer.color;
      layer.cells.forEach((row, y) =>
        row.forEach((active, x) => {
          if (active) ctx.fillRect(x * cw, y * ch, cw, ch);
        }),
      );
    }
    if (grid) {
      ctx.strokeStyle = "#ffffff0d";
      ctx.lineWidth = 1;
      for (let x = 0; x <= w; x++) {
        ctx.beginPath();
        ctx.moveTo(x * cw, 0);
        ctx.lineTo(x * cw, h * ch);
        ctx.stroke();
      }
      for (let y = 0; y <= h; y++) {
        ctx.beginPath();
        ctx.moveTo(0, y * ch);
        ctx.lineTo(w * cw, y * ch);
        ctx.stroke();
      }
    }
    ctx.fillStyle = "#edc87555";
    for (const p of selection) ctx.fillRect(p.x * cw, p.y * ch, cw, ch);
  }, [cells, cw, ch, w, h, grid, overlays, selection, zoom, symbols, assets]);
  const left = ghost.length ? Math.min(...ghost.map((g) => g.point.x)) : 0;
  const top = ghost.length ? Math.min(...ghost.map((g) => g.point.y)) : 0;
  const ghostWidth = ghost.length
    ? Math.max(...ghost.map((g) => g.point.x)) - left + 1
    : 1;
  const ghostHeight = ghost.length
    ? Math.max(...ghost.map((g) => g.point.y)) - top + 1
    : 1;
  useLayoutEffect(() => {
    const canvas = ghostRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!,
      dpr = window.devicePixelRatio || 1;
    const width = Math.round(ghostWidth * cw * dpr),
      height = Math.round(ghostHeight * ch * dpr);
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, ghostWidth * cw, ghostHeight * ch);
    ctx.font = `${16 * zoom}px "DejaVu Sans Mono",Consolas,monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const { point, cell } of ghost) {
      if (!cell) continue;
      const x = (point.x - left) * cw,
        y = (point.y - top) * ch;
      ctx.globalAlpha = 0.2;
      ctx.fillStyle =
        cell.background == null ? "#edc875" : color(cell.background);
      ctx.fillRect(x, y, cw, ch);
      ctx.globalAlpha = 0.65;
      const image = cell.symbol ? assets["symbols/" + cell.symbol] : undefined;
      if (symbols && image)
        drawSymbol(
          ctx,
          image,
          x,
          y,
          cw,
          ch,
          color(cell.foreground),
          !!cell.mirror_x,
          cell.rotation ?? 0,
        );
      else {
        ctx.fillStyle = color(cell.foreground);
        ctx.fillText(cell.char, x + cw / 2, y + ch / 2);
      }
      ctx.globalAlpha = 0.9;
      ctx.strokeStyle = "#edc875";
      ctx.lineWidth = 1;
      ctx.strokeRect(x + 0.5, y + 0.5, cw - 1, ch - 1);
    }
    ctx.globalAlpha = 1;
  }, [
    ghost,
    ghostWidth,
    ghostHeight,
    cw,
    ch,
    left,
    top,
    zoom,
    symbols,
    assets,
  ]);
  const point = (e: React.PointerEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    return {
      x: Math.min(w - 1, Math.max(0, Math.floor((e.clientX - r.left) / cw))),
      y: Math.min(h - 1, Math.max(0, Math.floor((e.clientY - r.top) / ch))),
    };
  };
  return (
    <div
      style={{
        position: "relative",
        display: "inline-block",
        verticalAlign: "top",
        width: w * cw,
        height: h * ch,
      }}
    >
      <canvas
        aria-label="Символьный холст"
        ref={ref}
        style={{ width: w * cw, height: h * ch, touchAction: "none" }}
        onPointerDown={(e) => {
          if (e.button !== 0) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          drag.current = true;
          onDown?.(point(e), { altKey: e.altKey, shiftKey: e.shiftKey });
        }}
        onPointerMove={(e) => {
          onHover?.(point(e), { altKey: e.altKey, shiftKey: e.shiftKey });
          if (drag.current)
            onDrag?.(point(e), { altKey: e.altKey, shiftKey: e.shiftKey });
        }}
        onPointerUp={(e) => {
          if (!drag.current) return;
          drag.current = false;
          onUp?.(point(e), { altKey: e.altKey, shiftKey: e.shiftKey });
        }}
        onPointerCancel={(e) => {
          if (!drag.current) return;
          drag.current = false;
          onUp?.(point(e), { altKey: e.altKey, shiftKey: e.shiftKey });
        }}
        onPointerLeave={onLeave}
      />
      {ghost.length > 0 && (
        <canvas
          ref={ghostRef}
          aria-label="Предпросмотр кисти"
          style={{
            position: "absolute",
            pointerEvents: "none",
            left: left * cw,
            top: top * ch,
            width: ghostWidth * cw,
            height: ghostHeight * ch,
          }}
        />
      )}
    </div>
  );
}
