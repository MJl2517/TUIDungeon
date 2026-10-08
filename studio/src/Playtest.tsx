import { useEffect, useState } from "react";
import { api } from "./api";
import { Grid } from "./Grid";
import { Doc, Entry } from "./model";
export function Playtest({
  map,
  entries,
  onClose,
  notify,
}: {
  map: string;
  entries: Entry[];
  onClose: () => void;
  notify: (s: string) => void;
}) {
  const [background, setBackground] = useState("");
  const [seed, setSeed] = useState(42),
    [race, setRace] = useState(
      entries.find((e) => e.category === "races")?.ref ?? "",
    ),
    [cls, setCls] = useState(
      entries.find((e) => e.category === "classes")?.ref ?? "",
    ),
    [session, setSession] = useState<Doc | null>(null),
    [busy, setBusy] = useState(false),
    [scores, setScores] = useState([14, 12, 13, 10, 10, 8]);
  async function start() {
    setBusy(true);
    try {
      if (session) await api("/sessions/" + session.id, undefined, "DELETE");
      setSession(
        await api("/sessions", {
          map_ref: map,
          race,
          character_class: cls,
          seed,
          scores,
          background: background || null,
          viewport_width: 48,
          viewport_height: 24,
        }),
      );
    } catch (e) {
      notify(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function command(command: string, placement?: string, choice?: string) {
    if (!session || busy) return;
    setBusy(true);
    try {
      setSession(
        await api("/sessions/" + session.id + "/commands", {
          command,
          placement,
          choice,
        }),
      );
    } catch (e) {
      notify(String(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).matches("input,textarea,select")) return;
      const key = e.key.toLowerCase();
      if (key === "g") {
        e.preventDefault();
        void command("pickup");
        return;
      }
      if ("wasd".includes(key) && key.length === 1) {
        e.preventDefault();
        void command(key);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });
  useEffect(
    () => () => {
      if (session)
        void api("/sessions/" + session.id, undefined, "DELETE").catch(
          () => {},
        );
    },
    [session?.id],
  );
  return (
    <div className="modal-backdrop">
      <div className="playtest modal">
        <div className="dialog-heading">
          <div>
            <span className="eyebrow">PYTHON ENGINE / PLAYTEST</span>
            <h2>{map}</h2>
          </div>
          <button onClick={onClose}>Закрыть</button>
        </div>
        <div className="toolbar">
          <select
            aria-label="Тестовая раса"
            value={race}
            onChange={(e) => setRace(e.target.value)}
          >
            {entries
              .filter((e) => e.category === "races")
              .map((e) => (
                <option key={e.ref} value={e.ref}>
                  {e.name}
                </option>
              ))}
          </select>
          <select
            aria-label="Тестовый класс"
            value={cls}
            onChange={(e) => {
              const next = e.target.value;
              setCls(next);
              const selected = entries.find(
                (entry) =>
                  entry.ref === background && entry.category === "backgrounds",
              );
              if (selected?.classes?.length && !selected.classes.includes(next))
                setBackground("");
            }}
          >
            {entries
              .filter((e) => e.category === "classes")
              .map((e) => (
                <option key={e.ref} value={e.ref}>
                  {e.name}
                </option>
              ))}
          </select>
          <select
            aria-label="Тестовая предыстория"
            value={background}
            onChange={(e) => setBackground(e.target.value)}
          >
            <option value="">Без предыстории</option>
            {entries
              .filter(
                (e) =>
                  e.category === "backgrounds" &&
                  (!e.classes?.length || e.classes.includes(cls)),
              )
              .map((e) => (
                <option key={e.ref} value={e.ref}>
                  {e.name}
                </option>
              ))}
          </select>
          <label>
            Seed{" "}
            <input
              className="short"
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
            />
          </label>
          <button
            className="primary"
            disabled={busy}
            onClick={() => void start()}
          >
            {session ? "Новая сессия" : "Начать тест"}
          </button>
          {session && (
            <button
              disabled={busy}
              onClick={async () => {
                try {
                  setSession(
                    await api("/sessions/" + session.id + "/reset", {}),
                  );
                } catch (e) {
                  notify(String(e));
                }
              }}
            >
              Перезапустить
            </button>
          )}
        </div>
        <div className="toolbar">
          {["СИЛ", "ЛОВ", "ТЕЛ", "ИНТ", "МДР", "ХАР"].map((name, i) => (
            <label key={name}>
              {name}
              <input
                className="short"
                type="number"
                min="1"
                value={scores[i]}
                onChange={(e) =>
                  setScores(
                    scores.map((v, j) =>
                      i === j ? Number(e.target.value) : v,
                    ),
                  )
                }
              />
            </label>
          ))}
        </div>
        {session ? (
          <div className="play-layout">
            <div className="workspace">
              <div className="canvas-scroll">
                <Grid cells={session.cells} zoom={1.3} />
              </div>
              <p className="muted">
                Карта {session.width}×{session.height} · камера следует за
                героем
              </p>
              <div className="toolbar">
                <button
                  disabled={
                    busy ||
                    !(session.ground ?? []).some(
                      (p: Doc) =>
                        p.x === session.position.x &&
                        p.y === session.position.y,
                    )
                  }
                  onClick={() => void command("pickup")}
                >
                  G · Подобрать
                </button>
                <button disabled={busy} onClick={() => void command("w")}>
                  W ↑
                </button>
                <button disabled={busy} onClick={() => void command("a")}>
                  A ←
                </button>
                <button disabled={busy} onClick={() => void command("s")}>
                  S ↓
                </button>
                <button disabled={busy} onClick={() => void command("d")}>
                  D →
                </button>
                <button disabled={busy} onClick={() => void command("wait")}>
                  Ждать
                </button>
                <button disabled={busy} onClick={() => void command("rest")}>
                  Отдых 8 часов
                </button>
              </div>
              <div className="event-log">
                {[...session.log].reverse().map((e: Doc, i: number) => (
                  <p key={i} className={e.performed ? "" : "muted"}>
                    {e.message}
                    <small> +{e.minutes} мин.</small>
                  </p>
                ))}
              </div>
            </div>
            <aside className="inspector">
              <h3>{session.hero.name}</h3>
              <div className="stat-grid">
                <span>
                  Хиты
                  <strong>
                    {session.hero.hp} / {session.hero.max_hp}
                  </strong>
                </span>
                <span>
                  КД<strong>{session.hero.armor_class}</strong>
                </span>
                <span>
                  Золото<strong>{session.hero.gold}</strong>
                </span>
                <span>
                  Опыт<strong>{session.hero.experience}</strong>
                </span>
              </div>
              <p>
                День {session.clock.day},{" "}
                {String(session.clock.hour).padStart(2, "0")}:
                {String(session.clock.minute).padStart(2, "0")} ·{" "}
                {session.clock.time_of_day}
              </p>
              <p className="hint">
                Ячейки:{" "}
                {Object.entries(session.hero.spell_slots)
                  .map(([lvl, count]) => `${lvl} ур. — ${count}`)
                  .join(", ") || "нет"}{" "}
                · Расовых применений: {session.hero.racial_uses}
              </p>
              <p className="hint">
                Ход {session.turns} · ({session.position.x},{" "}
                {session.position.y})
              </p>
              {session.nearby.map((p: Doc) => (
                <section key={p.id}>
                  <h3>{p.name}</h3>
                  <p>{p.text}</p>
                  {p.completed && (
                    <p className="hint">Испытание уже завершено.</p>
                  )}
                  {p.choices.map((c: Doc) => (
                    <button
                      className="choice"
                      key={c.id}
                      disabled={busy}
                      onClick={() => void command("interact", p.id, c.id)}
                    >
                      {c.text}
                    </button>
                  ))}
                </section>
              ))}
              <h3>Снаряжение и свет</h3>
              <p className="hint">
                Занято рук: {session.hero.hands_used}/2. Снимите оружие или щит,
                чтобы взять источник света. Одна порция масла — час; отдых
                расходует топливо.
              </p>
              {session.hero.inventory.map((item: Doc) => (
                <div key={item.id}>
                  <span>
                    {item.equipped ? "[*] " : item.slot ? "[ ] " : ""}
                    {item.name}
                    {item.light &&
                      ` · ${item.lit ? "горит" : "погашен"}, ${item.fuel_minutes} мин.`}
                    {item.charges != null && ` · ${item.charges} примен.`}
                  </span>
                  {item.slot && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void command(
                          item.equipped ? "unequip" : "equip",
                          item.id,
                        )
                      }
                    >
                      {item.equipped
                        ? "Снять"
                        : item.light
                          ? "Взять и зажечь"
                          : "Надеть"}
                    </button>
                  )}
                </div>
              ))}
              <h3>Броски и эффекты</h3>
              <div className="event-log">
                {[...session.events].reverse().map((e: Doc, i: number) => (
                  <div key={i}>
                    <p>{e.message}</p>
                    {e.effects?.map((f: Doc, j: number) => (
                      <small key={j}>
                        {f.kind}: {f.condition || f.amount}{" "}
                      </small>
                    ))}
                  </div>
                ))}
              </div>
            </aside>
          </div>
        ) : (
          <div className="empty-state">
            <span>✦</span>
            <h3>Отдельная игровая сессия</h3>
            <p>
              Выберите героя и seed. Ловушки, испытания и ресурсы использует тот
              же движок, что и терминальная игра.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
