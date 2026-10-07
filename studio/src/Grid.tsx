import { useEffect, useRef } from "react";
import { Cell, Point, color } from "./model";
type Props = {
  cells: Cell[][];
  zoom?: number;
  grid?: boolean;
  overlays?: { cells: boolean[][]; color: string }[];
  selection?: Point[];
  onDown?: (p: Point) => void;
  onDrag?: (p: Point) => void;
  onUp?: (p: Point) => void;
  onHover?: (p: Point) => void;
};
export function Grid({
  cells,
  zoom = 1,
  grid = true,
  overlays = [],
  selection = [],
  onDown,
  onDrag,
  onUp,
  onHover,
}: Props) {
  const ref = useRef<HTMLCanvasElement>(null),
    drag = useRef(false);
  const cw = 12 * zoom,
    ch = 20 * zoom,
    w = cells[0]?.length ?? 1,
    h = cells.length;
  useEffect(() => {
    const canvas = ref.current!,
      ctx = canvas.getContext("2d")!;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = w * cw * dpr;
    canvas.height = h * ch * dpr;
    ctx.scale(dpr, dpr);
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
          ctx.fillText(c.char, (x + 0.5) * cw, (y + 0.5) * ch);
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
  }, [cells, cw, ch, w, h, grid, overlays, selection, zoom]);
  const point = (e: React.PointerEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    return {
      x: Math.min(w - 1, Math.max(0, Math.floor((e.clientX - r.left) / cw))),
      y: Math.min(h - 1, Math.max(0, Math.floor((e.clientY - r.top) / ch))),
    };
  };
  return (
    <canvas
      aria-label="Символьный холст"
      ref={ref}
      style={{ width: w * cw, height: h * ch, touchAction: "none" }}
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId);
        drag.current = true;
        onDown?.(point(e));
      }}
      onPointerMove={(e) => {
        onHover?.(point(e));
        if (drag.current) onDrag?.(point(e));
      }}
      onPointerUp={(e) => {
        drag.current = false;
        onUp?.(point(e));
      }}
      onPointerCancel={(e) => {
        drag.current = false;
        onUp?.(point(e));
      }}
    />
  );
}
