import { useEffect, useState } from "react";
import { Doc } from "./model";

export function StorageDialog({
  container,
  hero,
  busy,
  message,
  onClose,
  transfer,
}: {
  container: Doc;
  hero: Doc;
  busy: boolean;
  message: string;
  onClose: () => void;
  transfer: (
    item: string,
    quantity: number,
    deposit: boolean,
  ) => Promise<boolean>;
}) {
  const [side, setSide] = useState(1);
  const [selected, setSelected] = useState([0, 0]);
  const [pending, setPending] = useState<{
    item: string;
    maximum: number;
    deposit: boolean;
  } | null>(null);
  const [quantity, setQuantity] = useState(1);
  const lists: Doc[][] = [hero.stacks, container.items];
  const options = lists[side];
  const index = Math.max(0, Math.min(selected[side], options.length - 1));
  const close = () => (pending ? setPending(null) : onClose());
  async function confirm() {
    if (!pending || busy) return;
    if (await transfer(pending.item, quantity, pending.deposit))
      setPending(null);
  }
  async function move() {
    if (busy || (side === 0 && !container.personal)) return;
    const item = options[index];
    if (!item) return;
    if (item.quantity > 1) {
      setPending({
        item: item.id,
        maximum: item.quantity,
        deposit: side === 0,
      });
      setQuantity(1);
    } else await transfer(item.id, 1, side === 0);
  }
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const key = event.key;
      if (
        ![
          "Tab",
          "ArrowLeft",
          "ArrowRight",
          "ArrowUp",
          "ArrowDown",
          "Enter",
          "F5",
          "Backspace",
          "Escape",
          "Home",
          "End",
          "PageUp",
          "PageDown",
        ].includes(key)
      )
        return;
      event.preventDefault();
      event.stopPropagation();
      if (key === "Backspace" || key === "Escape") {
        close();
        return;
      }
      if (busy || (event.repeat && (key === "Enter" || key === "F5"))) return;
      if (pending) {
        if (key === "Enter" || key === "F5") void confirm();
        else if (key === "Home" || key === "PageUp") setQuantity(1);
        else if (key === "End" || key === "PageDown")
          setQuantity(pending.maximum);
        else if (key.startsWith("Arrow"))
          setQuantity((v) =>
            Math.max(
              1,
              Math.min(
                pending.maximum,
                v + (["ArrowRight", "ArrowUp"].includes(key) ? 1 : -1),
              ),
            ),
          );
      } else if (["Tab", "ArrowLeft", "ArrowRight"].includes(key))
        setSide(key === "Tab" ? 1 - side : Number(key === "ArrowRight"));
      else if (key === "Enter" || key === "F5") void move();
      else
        setSelected((v) =>
          v.map((value, i) =>
            i !== side
              ? value
              : Math.max(
                  0,
                  Math.min(
                    options.length - 1,
                    key === "Home"
                      ? 0
                      : key === "End"
                        ? options.length - 1
                        : value +
                          (key === "ArrowUp"
                            ? -1
                            : key === "PageUp"
                              ? -8
                              : key === "PageDown"
                                ? 8
                                : 1),
                  ),
                ),
          ),
        );
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });
  useEffect(() => {
    document
      .querySelector(".storage-pane.active .storage-row.selected")
      ?.scrollIntoView({ block: "nearest" });
  }, [side, index]);
  return (
    <div className="modal-backdrop storage-backdrop">
      <section
        className="storage-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Обмен с контейнером"
      >
        <header>
          <h2>{container.name}</h2>
          <button onClick={close}>Закрыть</button>
        </header>
        <p>
          {container.personal
            ? "Личный контейнер: можно класть и забирать. Содержимое не обновляется."
            : "Лутовый контейнер: можно только забирать."}
        </p>
        <div className="storage-panes">
          {lists.map((items, pane) => (
            <section
              key={pane}
              className={"storage-pane" + (side === pane ? " active" : "")}
              aria-label={
                pane === 0 ? "Инвентарь героя" : "Содержимое контейнера"
              }
            >
              <button className="storage-heading" onClick={() => setSide(pane)}>
                {pane === 0 ? "Инвентарь" : "Контейнер"}
                {pane === 0 && !container.personal ? " · только просмотр" : ""}
              </button>
              <div
                className="storage-list"
                role="listbox"
                aria-label={pane === 0 ? "Вещи героя" : "Вещи контейнера"}
              >
                {!items.length && <p>(пусто)</p>}
                {items.map((item, i) => (
                  <button
                    key={item.id}
                    role="option"
                    aria-selected={
                      side === pane &&
                      i === Math.min(selected[pane], items.length - 1)
                    }
                    className={
                      "storage-row" +
                      (i === Math.min(selected[pane], items.length - 1)
                        ? " selected"
                        : "")
                    }
                    onClick={() => {
                      setSide(pane);
                      setSelected((v) => v.map((n, j) => (j === pane ? i : n)));
                    }}
                  >
                    <span>{item.label}</span>
                    <small>{item.weight.toFixed(2)} кг</small>
                  </button>
                ))}
              </div>
              <footer>
                Вес: {pane === 0 ? hero.carried_weight : container.weight} /{" "}
                {pane === 0 ? hero.max_carry_weight : container.capacity} кг
              </footer>
            </section>
          ))}
        </div>
        {pending ? (
          <div className="storage-quantity">
            <label>
              Количество: {quantity} / {pending.maximum}
              <input
                aria-label="Количество для переноса"
                type="range"
                min="1"
                max={pending.maximum}
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
              />
            </label>
            <button disabled={busy} onClick={() => void confirm()}>
              Перенести {quantity}
            </button>
            <button disabled={busy} onClick={() => setPending(null)}>
              Отменить количество
            </button>
            <small>
              ←/→: количество · Home/End: один/всё · Enter: подтвердить
            </small>
          </div>
        ) : (
          <button
            disabled={
              busy || !options.length || (side === 0 && !container.personal)
            }
            onClick={() => void move()}
          >
            {side === 0 ? "Положить →" : "← Забрать"}
          </button>
        )}
        <p className="storage-message" aria-live="polite">
          {message}
        </p>
        <footer>
          Tab / ←→: колонка · ↑↓: предмет · Enter / F5: перенос · Backspace:
          назад
        </footer>
      </section>
    </div>
  );
}
