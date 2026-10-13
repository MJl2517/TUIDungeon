import { SymbolPreview } from "./Symbols";
import { visual } from "./symbolModel";
import { useEffect, useState } from "react";
import { ContentSelect } from "./ContentBrowser";
import { Doc, Entry, color, matchesEntry } from "./model";
import {
  brushDescription,
  paletteEntry,
  paletteLayer,
  tileFamily,
  contentGroup,
  paletteCategory,
  paletteSections,
} from "./catalog";

export const layerNames: Record<string, string> = {
  tiles: "Поверхности",
  objects: "Окружение",
  doors: "Двери",
  decorations: "Рисунки",
  traps: "Ловушки",
  points_of_interest: "Взаимодействия",
  monsters: "Существа",
  equipment: "Предметы",
  roof: "Крыша",
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
  section: string;
  onSection: (section: string) => void;
  onLayer: (layer: string) => void;
  chosen: string;
  onChoose: (ref: string, layer?: string) => void;
  target: string;
  onTarget: (target: string) => void;
  documentRef: string;
  onEmpty: (empty: boolean) => void;
};

export function MapPalette({
  entries,
  assets,
  layer,
  section,
  onSection,
  onLayer,
  chosen,
  onChoose,
  target,
  onTarget,
  documentRef,
  onEmpty,
}: Props) {
  const [searchAcross, setSearchAcross] = useState(true);
  const [query, setQuery] = useState(""),
    [family, setFamily] = useState(""),
    [group, setGroup] = useState(""),
    [pack, setPack] = useState(""),
    [filter, setFilter] = useState("all"),
    [sort, setSort] = useState("group"),
    [hovered, setHovered] = useState<Entry | null>(null);
  const category =
    layer === "decorations"
      ? "art"
      : layer === "transitions"
        ? "maps"
        : layer === "doors"
          ? "objects"
          : layer;
  const searching = searchAcross && !!query.trim() && layer !== "transitions";
  const all = searching
    ? entries.filter((e) => paletteLayer(e, assets))
    : entries.filter((e) =>
        section === "service"
          ? layer === "transitions"
            ? e.category === "maps"
            : paletteCategory(e, assets) === "service" &&
              paletteLayer(e, assets) === layer
          : paletteCategory(e, assets) === section,
      );
  const groupOf = (e: Entry) =>
    e.category === "tiles" ? (e.group ?? "Прочее") : contentGroup(e, assets);
  const groups = [...new Set(all.map(groupOf))].sort((a, b) =>
    a.localeCompare(b, "ru"),
  );
  const families = [
    ...new Set(all.map((e) => tileFamily(paletteEntry(e, assets)))),
  ].sort((a, b) => a.localeCompare(b, "ru"));
  const hasMechanics = (tile: Doc) =>
    Object.values(tile.brush ?? {}).some(Boolean);
  const options = all
    .filter((e) => {
      const tile = paletteEntry(e, assets);
      if (!matchesEntry(e, query, assets)) return false;
      return (
        (!pack || e.ref.startsWith(pack + ":")) &&
        (!group || groupOf(e) === group) &&
        (e.category !== "tiles" ||
          ((!family || tileFamily(tile) === family) &&
            (!group || groupOf(e) === group) &&
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
        const comparison = groupOf(a).localeCompare(groupOf(b), "ru");
        if (comparison) return comparison;
      }
      return a.name.localeCompare(b.name, "ru");
    });
  const selected = all.find(
    (e) => e.ref === chosen && paletteLayer(e, assets) === layer,
  );
  const unavailable = !options.some(
    (e) => e.ref === chosen && (paletteLayer(e, assets) ?? layer) === layer,
  );
  useEffect(() => {
    onEmpty(unavailable);
  }, [unavailable, onEmpty]);
  const detail = hovered ?? selected;
  const detailDoc = detail ? paletteEntry(detail, assets) : null;
  const service = section === "service";
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
        {Object.entries(paletteSections).map(([id, value], index) => (
          <button
            key={id}
            aria-label={value.name}
            aria-pressed={section === id}
            className={section === id ? "selected" : ""}
            onClick={() => {
              setQuery("");
              setGroup("");
              setFamily("");
              setFilter("all");
              setHovered(null);
              onSection(id);
            }}
          >
            <span>
              {index + 1}. {value.name}
            </span>
            {id !== "service" && (
              <small>
                {
                  entries.filter((e) => paletteCategory(e, assets) === id)
                    .length
                }
              </small>
            )}
          </button>
        ))}
      </div>
      <p className="palette-explanation">
        {paletteSections[section].description}
      </p>
      {service && (
        <label className="palette-label">
          Слой карты
          <select
            aria-label="Слой карты"
            value={layer}
            onChange={(e) => changeLayer(e.target.value)}
          >
            {Object.entries(layerNames)
              .filter(([id]) =>
                [
                  "roof",
                  "lights",
                  "spawn",
                  "transitions",
                  "walkability",
                  "blocks_sight",
                  "objects",
                  "tiles",
                ].includes(id),
              )
              .map(([id, name]) => (
                <option key={id} value={id}>
                  {id === "objects" ? "Лестницы и выходы" : name}
                </option>
              ))}
          </select>
        </label>
      )}
      {!["lights", "spawn", "walkability", "blocks_sight", "roof"].includes(
        layer,
      ) && (
        <>
          <input
            aria-label="Поиск кистей"
            placeholder="Поиск: имя, символ, ID, тег"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <label className="toggle">
            <input
              type="checkbox"
              checked={searchAcross}
              onChange={(e) => setSearchAcross(e.target.checked)}
            />{" "}
            Искать во всех слоях
          </label>
          {searching && (
            <p className="hint">
              Поиск по всем слоям. Выбранные фильтры продолжают действовать.
            </p>
          )}
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
            {layer !== "tiles" && groups.length > 1 && (
              <select
                aria-label="Группа объектов"
                value={group}
                onChange={(e) => setGroup(e.target.value)}
              >
                <option value="">Все группы</option>
                {groups.map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            )}
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
          <button
            className="subtle"
            onClick={() => {
              setQuery("");
              setPack("");
              setGroup("");
              setFamily("");
              setFilter("all");
            }}
          >
            Сбросить поиск и фильтры
          </button>
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
              const entryLayer = paletteLayer(e, assets) ?? layer;
              const isSelected = chosen === e.ref && layer === entryLayer;
              const tile = paletteEntry(e, assets),
                mechanics =
                  hasMechanics(tile) ||
                  [
                    "traps",
                    "points_of_interest",
                    "equipment",
                    "monsters",
                  ].includes(entryLayer);
              const info = ["tiles", "objects", "doors"].includes(entryLayer)
                ? brushDescription(tile, assets)
                : [
                    layerNames[entryLayer],
                    tile.description ?? "",
                    entryLayer === "traps"
                      ? `При входе: проверка ${tile.ability}, СЛ ${tile.difficulty}`
                      : entryLayer === "points_of_interest"
                        ? "Взаимодействие по Enter с клетки или рядом"
                        : entryLayer === "equipment"
                          ? "Можно подобрать в инвентарь"
                          : entryLayer === "monsters"
                            ? "Занимает клетку, блокирует движение"
                            : "",
                  ].filter(Boolean);
              return (
                <button
                  data-ref={e.ref}
                  key={e.category + "/" + e.ref}
                  aria-label={e.name + " · " + e.ref}
                  aria-pressed={isSelected}
                  className={"palette-tile " + (isSelected ? "selected" : "")}
                  title={[e.name, ...info].join("\n")}
                  onClick={() => {
                    if (searching) {
                      setGroup("");
                      setFamily("");
                      setPack("");
                      setFilter("all");
                    }
                    onChoose(e.ref, entryLayer);
                  }}
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
                    {tile.symbol ? (
                      <SymbolPreview
                        symbol={visual(tile, assets).symbol}
                        mirror_x={!!tile.mirror_x}
                        tint={color(tile.foreground ?? 7)}
                      />
                    ) : (
                      (tile.glyph ?? (layer === "decorations" ? "░" : ">"))
                    )}
                  </span>
                  <span className="tile-name">
                    {e.name}
                    {searching && (
                      <small>
                        {
                          paletteSections[paletteCategory(e, assets) ?? section]
                            .name
                        }
                      </small>
                    )}
                  </span>
                  <span className="tile-sign">
                    {mechanics
                      ? "●"
                      : ["tiles", "objects"].includes(entryLayer) &&
                          !tile.walkable
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
        (["tiles", "objects"].includes(layer) &&
          assets[category + "/" + chosen]?.brush?.transition)) && (
        <label className="palette-label">
          Карта назначения
          <ContentSelect
            entries={entries.filter(
              (e) => e.category === "maps" && e.ref !== documentRef,
            )}
            label="Карта назначения"
            value={target}
            onChange={onTarget}
          />
        </label>
      )}
      {layer === "roof" && (
        <>
          <button
            className="palette-tile selected"
            aria-label="Крыша"
            aria-pressed="true"
            onClick={() => changeLayer("roof")}
          >
            <span className="tile-glyph">⌂</span>
            <span className="tile-name">Крыша</span>
          </button>
          <p className="hint">
            Рисуйте над пещерой или зданием. Крыша убирает общий свет, сохраняя
            пол и объекты. Факелы и лампы работают. E — убрать крышу.
          </p>
        </>
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
          {(["tiles", "objects", "doors"].includes(
            paletteLayer(detail, assets) ?? layer,
          )
            ? brushDescription(detailDoc, assets)
            : [
                detailDoc.description ?? "",
                layerNames[paletteLayer(detail, assets) ?? layer],
              ]
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
