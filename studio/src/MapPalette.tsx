import { useEffect, useState } from "react";
import { Doc, Entry, color, matchesEntry } from "./model";
import { brushDescription, paletteEntry, tileFamily } from "./catalog";

export const layerNames: Record<string, string> = {
  tiles: "Тайлы",
  decorations: "Рисунки",
  traps: "Ловушки",
  points_of_interest: "Взаимодействия",
  monsters: "Существа",
  equipment: "Предметы",
  lights: "Источники света",
  spawn: "Старт героя",
  transitions: "Переходы",
  walkability: "Проходимость",
  blocks_sight: "Преграды обзору",
};
type Props = {
  entries: Entry[];
  assets: Record<string, Doc>;
  layer: string;
  onLayer: (layer: string) => void;
  chosen: string;
  onChoose: (ref: string) => void;
  target: string;
  onTarget: (target: string) => void;
  documentRef: string;
  onEmpty: (empty: boolean) => void;
};

export function MapPalette({
  entries,
  assets,
  layer,
  onLayer,
  chosen,
  onChoose,
  target,
  onTarget,
  documentRef,
  onEmpty,
}: Props) {
  const [query, setQuery] = useState(""),
    [family, setFamily] = useState(""),
    [group, setGroup] = useState(""),
    [pack, setPack] = useState(""),
    [filter, setFilter] = useState("all"),
    [sort, setSort] = useState("group"),
    [hovered, setHovered] = useState<Entry | null>(null);
  const category =
    layer === "decorations" ? "art" : layer === "transitions" ? "maps" : layer;
  const all = entries.filter((e) => e.category === category);
  const groups = [...new Set(all.map((e) => e.group ?? "Прочее"))].sort(
    (a, b) => a.localeCompare(b, "ru"),
  );
  const families = [
    ...new Set(all.map((e) => tileFamily(paletteEntry(e, assets)))),
  ].sort((a, b) => a.localeCompare(b, "ru"));
  const hasMechanics = (tile: Doc) =>
    Object.values(tile.brush ?? {}).some(Boolean);
  const options = all
    .filter((e) => {
      const tile = paletteEntry(e, assets);
      return (
        matchesEntry(e, query) &&
        (!pack || e.ref.startsWith(pack + ":")) &&
        (layer !== "tiles" ||
          ((!family || tileFamily(tile) === family) &&
            (!group || (e.group ?? "Прочее") === group) &&
            (filter === "all" ||
              (filter === "mechanics" && hasMechanics(tile)) ||
              (filter === "blocking" && !tile.walkable) ||
              (filter === "opaque" && tile.blocks_sight) ||
              (filter === "walkable" && tile.walkable))))
      );
    })
    .sort((a, b) => {
      if (sort === "id") return a.ref.localeCompare(b.ref);
      if (sort === "mechanics") {
        const priority =
          Number(hasMechanics(paletteEntry(b, assets))) -
          Number(hasMechanics(paletteEntry(a, assets)));
        if (priority) return priority;
      }
      if (sort === "group") {
        const comparison = (a.group ?? "").localeCompare(b.group ?? "", "ru");
        if (comparison) return comparison;
      }
      return a.name.localeCompare(b.name, "ru");
    });
  const selected = all.find((e) => e.ref === chosen);
  useEffect(() => {
    onEmpty(options.length === 0);
  }, [options.length, onEmpty]);
  const detail = hovered ?? selected;
  const detailDoc = detail ? paletteEntry(detail, assets) : null;
  const service = [
    "lights",
    "spawn",
    "transitions",
    "walkability",
    "blocks_sight",
  ].includes(layer);
  const changeLayer = (next: string) => {
    setQuery("");
    setGroup("");
    setFamily("");
    setHovered(null);
    onLayer(next);
  };
  return (
    <div className="map-palette">
      <div className="palette-modes" aria-label="Разделы палитры">
        <button
          className={layer === "tiles" ? "selected" : ""}
          onClick={() => changeLayer("tiles")}
        >
          Кисти
        </button>
        <button
          className={!service && layer !== "tiles" ? "selected" : ""}
          onClick={() => changeLayer("monsters")}
        >
          Объекты
        </button>
        <button
          className={service ? "selected" : ""}
          onClick={() => changeLayer("spawn")}
        >
          Служебные
        </button>
      </div>
      <p className="palette-explanation">
        {layer === "tiles"
          ? "Кисть = рисунок клетки + маски + привязанные события. Нажмите на карточку и рисуйте."
          : service
            ? "Свет, старт, переходы и независимые маски карты."
            : "Экземпляры шаблонов поверх рисунка: существа, предметы и взаимодействия."}
      </p>
      <label className="palette-label">
        Слой карты
        <select
          aria-label="Слой карты"
          value={layer}
          onChange={(e) => changeLayer(e.target.value)}
        >
          {Object.entries(layerNames).map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
      </label>
      {!["lights", "spawn", "walkability", "blocks_sight"].includes(layer) && (
        <>
          <input
            aria-label={layer === "tiles" ? "Поиск тайлов" : "Поиск объектов"}
            placeholder="Поиск: имя, символ, ID, тег"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="palette-filters">
            <select
              aria-label="Пакет палитры"
              value={pack}
              onChange={(e) => setPack(e.target.value)}
            >
              <option value="">Все пакеты</option>
              {[...new Set(all.map((e) => e.ref.split(":")[0]))].map((id) => (
                <option key={id}>{id}</option>
              ))}
            </select>
            <select
              aria-label="Сортировка палитры"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              <option value="group">По группе</option>
              <option value="name">По имени</option>
              <option value="id">По ID</option>
              <option value="mechanics">Сначала механика</option>
            </select>
            {layer === "tiles" && (
              <>
                <select
                  aria-label="Категория тайлов"
                  value={family}
                  onChange={(e) => {
                    setFamily(e.target.value);
                    setGroup("");
                  }}
                >
                  <option value="">Все категории</option>
                  {families.map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
                <select
                  aria-label="Группа тайлов"
                  value={group}
                  onChange={(e) => setGroup(e.target.value)}
                >
                  <option value="">Все группы</option>
                  {groups.map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
                <select
                  aria-label="Свойства тайлов"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="all">Любые свойства</option>
                  <option value="mechanics">С событиями / светом</option>
                  <option value="blocking">Блокируют движение</option>
                  <option value="opaque">Блокируют обзор</option>
                  <option value="walkable">Проходимые</option>
                </select>
              </>
            )}
          </div>
          <div className="palette-count">
            Найдено: {options.length}
            <span>● механика &nbsp; ▪ преграда</span>
          </div>
          <div
            className="palette-grid"
            role="group"
            aria-label="Каталог кистей"
          >
            {options.map((e) => {
              const tile = paletteEntry(e, assets),
                mechanics = layer === "tiles" && hasMechanics(tile);
              const info =
                layer === "tiles"
                  ? brushDescription(tile, assets)
                  : [
                      layerNames[layer],
                      tile.description ?? "",
                      layer === "traps"
                        ? `При входе: проверка ${tile.ability}, СЛ ${tile.difficulty}`
                        : layer === "points_of_interest"
                          ? "Взаимодействие по Enter с клетки или рядом"
                          : layer === "equipment"
                            ? "Можно подобрать в инвентарь"
                            : layer === "monsters"
                              ? "Занимает клетку, блокирует движение"
                              : "",
                    ].filter(Boolean);
              return (
                <button
                  data-ref={e.ref}
                  key={e.ref}
                  aria-label={e.name + " · " + e.ref}
                  aria-pressed={chosen === e.ref}
                  className={
                    "palette-tile " + (chosen === e.ref ? "selected" : "")
                  }
                  title={[e.name, ...info].join("\n")}
                  onClick={() => onChoose(e.ref)}
                  onMouseEnter={() => setHovered(e)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(e)}
                  onBlur={() => setHovered(null)}
                >
                  <span
                    className="tile-glyph"
                    style={{
                      color: color(tile.foreground ?? 7),
                      backgroundColor:
                        tile.background != null
                          ? color(tile.background)
                          : undefined,
                    }}
                  >
                    {tile.glyph ?? (layer === "decorations" ? "░" : ">")}
                  </span>
                  <span className="tile-name">{e.name}</span>
                  <span className="tile-sign">
                    {mechanics
                      ? "●"
                      : layer === "tiles" && !tile.walkable
                        ? "▪"
                        : ""}
                  </span>
                </button>
              );
            })}
            {!options.length && (
              <p className="hint palette-empty">
                Нет совпадений. Сбросьте фильтры, чтобы продолжить рисование.
              </p>
            )}
          </div>
        </>
      )}
      {(layer === "transitions" ||
        (layer === "tiles" &&
          assets["tiles/" + chosen]?.brush?.transition)) && (
        <label className="palette-label">
          Карта назначения
          <select
            aria-label="Карта назначения"
            value={target}
            onChange={(e) => onTarget(e.target.value)}
          >
            <option value="">Выберите карту…</option>
            {entries
              .filter((e) => e.category === "maps" && e.ref !== documentRef)
              .map((e) => (
                <option key={e.ref} value={e.ref}>
                  {e.name} · {e.ref}
                </option>
              ))}
          </select>
        </label>
      )}
      {layer === "lights" && (
        <p className="hint">
          Клик добавит свет 6 / 3 клетки. Выберите его инструментом V, чтобы
          изменить радиусы.
        </p>
      )}
      {layer === "spawn" && (
        <p className="hint">
          Клик задаёт старт героя на свободной проходимой клетке.
        </p>
      )}
      {detail && detailDoc && (
        <div className="palette-detail" aria-live="polite">
          <strong>
            {hovered ? "Под курсором: " : "Выбрано: "}
            {detail.name}
          </strong>
          <small>{detail.ref}</small>
          {(layer === "tiles"
            ? brushDescription(detailDoc, assets)
            : [detailDoc.description ?? "", layerNames[layer]]
          )
            .filter(Boolean)
            .map((line, i) => (
              <div key={i}>{line}</div>
            ))}
        </div>
      )}
    </div>
  );
}
