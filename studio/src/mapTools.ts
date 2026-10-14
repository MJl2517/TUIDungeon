import { Doc, Point, clone, placements } from "./model";

export type PaintOptions = {
  masks: boolean;
  mechanics: boolean;
  target: string;
  erase?: boolean;
  mirror?: boolean;
  rotation?: number;
};
export function paintTile(
  doc: Doc,
  ref: string,
  tile: Doc | undefined,
  p: Point,
  options: PaintOptions,
) {
  const brush = options.erase ? {} : (tile?.brush ?? {});
  if (
    brush.door &&
    brush.door.state !== "open" &&
    !brush.door.bent &&
    doc.spawn.x === p.x &&
    doc.spawn.y === p.y
  )
    throw new Error("Закрытая дверь не может занимать старт героя.");
  if (options.mechanics && brush.transition && !options.target)
    throw new Error("Выберите карту назначения для перехода в правой панели.");
  const walkable = options.masks
    ? options.erase
      ? true
      : brush.door
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
    "doors",
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
    : (options.mechanics && brush.item) || brush.door
      ? underlying
      : ref;
  doc.tile_mirrors ??= Array.from({ length: doc.height }, () =>
    Array(doc.width).fill(false),
  );
  doc.tile_mirrors[p.y][p.x] =
    !options.erase && !brush.door && !brush.item && !!options.mirror;
  doc.tile_rotations ??= Array.from({ length: doc.height }, () =>
    Array(doc.width).fill(0),
  );
  doc.tile_rotations[p.y][p.x] =
    !options.erase && !brush.door && !brush.item ? (options.rotation ?? 0) : 0;
  if (options.masks) {
    doc.walkability[p.y][p.x] = walkable;
    doc.blocks_sight[p.y][p.x] = options.erase
      ? false
      : (tile?.blocks_sight ?? false);
  }
  // A door is always an instance, including when optional brush events are off.
  if (
    brush.door ||
    (doc.doors ?? []).some(
      (e: Doc) => e.x === p.x && e.y === p.y && e.id.startsWith("tile_doors_"),
    )
  ) {
    doc.doors = (doc.doors ?? []).filter(
      (e: Doc) =>
        !(
          (brush.door || e.id.startsWith("tile_doors_")) &&
          e.x === p.x &&
          e.y === p.y
        ),
    );
    if (brush.door) {
      doc.doors.push({
        id: `tile_doors_${p.x}_${p.y}`,
        ...p,
        ref,
        ...(options.mirror || options.rotation
          ? {
              overrides: {
                ...(options.mirror ? { mirror_x: !tile?.mirror_x } : {}),
                ...(options.rotation
                  ? {
                      rotation:
                        ((tile?.rotation ?? 0) + options.rotation) % 360,
                    }
                  : {}),
              },
            }
          : {}),
      });
      doc.walkability[p.y][p.x] = true;
      doc.blocks_sight[p.y][p.x] = false;
    }
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
    if (reference)
      doc[key].push({
        id,
        ...p,
        ref: reference,
        ...(options.mirror || options.rotation
          ? {
              overrides: {
                ...(options.mirror ? { mirror_x: true } : {}),
                ...(options.rotation ? { rotation: options.rotation } : {}),
              },
            }
          : {}),
      });
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
  if (["walkability", "blocks_sight", "roof"].includes(preferredLayer))
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

// Native objects paint from their own definition; no companion tile document.
export function paintObject(
  doc: Doc,
  layer: string,
  ref: string,
  definition: Doc | undefined,
  p: Point,
  target = "",
  erase = false,
  mirror = false,
  rotation = 0,
) {
  if (!erase && !definition) throw new Error("Сначала выберите объект.");
  if (
    !erase &&
    (definition?.movable || definition?.destruction) &&
    !doc.tiles[p.y][p.x]
  )
    throw new Error("Сначала нарисуйте пол под разбираемым объектом.");
  if (!erase && layer === "objects" && definition?.brush?.door)
    throw new Error("Дверь размещается в слое дверей.");
  if (
    !erase &&
    layer === "objects" &&
    !definition?.walkable &&
    p.x === doc.spawn.x &&
    p.y === doc.spawn.y
  )
    throw new Error("Объект не может перекрывать старт героя.");
  if (!erase && definition?.brush?.transition && !target)
    throw new Error("Выберите карту назначения для перехода.");
  if (
    !erase &&
    layer !== "objects" &&
    layer !== "doors" &&
    !doc.walkability[p.y][p.x]
  )
    throw new Error("Объект можно разместить только на проходимой клетке.");
  if (
    !erase &&
    layer === "doors" &&
    definition?.brush?.door?.state !== "open" &&
    !definition?.brush?.door?.bent &&
    p.x === doc.spawn.x &&
    p.y === doc.spawn.y
  )
    throw new Error("Закрытая дверь не может занимать старт героя.");
  const removed = (doc[layer] ?? []).filter(
    (entry: Point) => entry.x === p.x && entry.y === p.y,
  );
  doc.transitions = (doc.transitions ?? []).filter(
    (t: Doc) => !removed.some((e: Doc) => t.id === e.id + "_transition"),
  );
  doc[layer] = (doc[layer] ?? []).filter(
    (entry: Point) => entry.x !== p.x || entry.y !== p.y,
  );
  if (erase) return;
  let id = `object_${layer}_${p.x}_${p.y}`;
  const used = new Set(
    placements.flatMap((key) => (doc[key] ?? []).map((entry: Doc) => entry.id)),
  );
  while (used.has(id) || used.has(id + "_transition")) id += "_new";
  doc[layer].push({
    id,
    ref,
    ...p,
    ...(mirror || rotation
      ? {
          overrides: {
            ...(mirror ? { mirror_x: !definition?.mirror_x } : {}),
            ...(rotation
              ? { rotation: ((definition?.rotation ?? 0) + rotation) % 360 }
              : {}),
          },
        }
      : {}),
  });
  if (definition?.brush?.transition)
    doc.transitions.push({ id: id + "_transition", target, ...p });
}
