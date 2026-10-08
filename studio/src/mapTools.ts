import { Doc, Point, clone, placements } from "./model";

export type PaintOptions = {
  masks: boolean;
  mechanics: boolean;
  target: string;
  erase?: boolean;
};
export function paintTile(
  doc: Doc,
  ref: string,
  tile: Doc | undefined,
  p: Point,
  options: PaintOptions,
) {
  const brush = options.erase ? {} : (tile?.brush ?? {});
  if (options.mechanics && brush.transition && !options.target)
    throw new Error("Выберите карту назначения для перехода в правой панели.");
  const walkable = options.masks
    ? options.erase
      ? true
      : (tile?.walkable ?? true)
    : doc.walkability[p.y][p.x];
  if (!walkable && doc.spawn.x === p.x && doc.spawn.y === p.y)
    throw new Error(
      "Старт героя должен оставаться проходимым. Сначала переместите старт.",
    );
  if (
    options.mechanics &&
    (brush.trap || brush.interaction || brush.item || brush.transition) &&
    !walkable
  )
    throw new Error(
      "Для объекта нужна проходимая клетка. Включите начальные маски или разрешите проход.",
    );
  const previous = doc.tiles[p.y][p.x];
  const generatedObject = [
    "equipment",
    "traps",
    "points_of_interest",
    "lights",
    "transitions",
  ].some((key) =>
    (doc[key] ?? []).some(
      (e: Doc) =>
        e.id.startsWith("tile_" + key + "_") && e.x === p.x && e.y === p.y,
    ),
  );
  const underlying =
    tile?.brush?.underlay ??
    (!generatedObject && doc.walkability[p.y][p.x] && previous
      ? previous
      : ref.startsWith("base:")
        ? "base:floor"
        : null);
  doc.tiles[p.y][p.x] = options.erase
    ? null
    : options.mechanics && brush.item
      ? underlying
      : ref;
  if (options.masks) {
    doc.walkability[p.y][p.x] = walkable;
    doc.blocks_sight[p.y][p.x] = options.erase
      ? false
      : (tile?.blocks_sight ?? false);
  }
  if (!options.mechanics) return;
  // Reserved IDs distinguish the brush's placements from manually authored ones.
  for (const key of [
    "traps",
    "points_of_interest",
    "equipment",
    "lights",
    "transitions",
  ]) {
    const id = `tile_${key}_${p.x}_${p.y}`;
    doc[key] = (doc[key] ?? []).filter(
      (entry: Doc) =>
        !(
          entry.id.startsWith("tile_" + key + "_") &&
          entry.x === p.x &&
          entry.y === p.y
        ),
    );
    const reference =
      key === "traps"
        ? brush.trap
        : key === "points_of_interest"
          ? brush.interaction
          : key === "equipment"
            ? brush.item
            : null;
    if (reference) doc[key].push({ id, ...p, ref: reference });
    if (key === "lights" && brush.light)
      doc[key].push({ id, ...p, ...clone(brush.light), enabled: true });
    if (key === "transitions" && brush.transition)
      doc[key].push({ id, ...p, target: options.target });
  }
}

export function sampleMap(
  doc: Doc,
  p: Point,
  preferredLayer: string,
): { layer: string; ref: string; placement?: Doc } | null {
  if (preferredLayer === "walkability" || preferredLayer === "blocks_sight")
    return { layer: preferredLayer, ref: "" };
  if (placements.includes(preferredLayer)) {
    const placement = (doc[preferredLayer] ?? []).find(
      (entry: Point) => entry.x === p.x && entry.y === p.y,
    );
    if (placement)
      return {
        layer: preferredLayer,
        ref: placement.ref ?? placement.target ?? "",
        placement,
      };
  }
  const ref = doc.tiles[p.y]?.[p.x];
  return ref ? { layer: "tiles", ref } : null;
}
