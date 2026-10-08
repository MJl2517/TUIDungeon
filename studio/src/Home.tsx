import { Doc, Entry } from "./model";
import { sections } from "./catalog";

export function Home({
  entries,
  categories,
  onCategory,
  onResume,
  draft,
}: {
  entries: Entry[];
  categories: Doc;
  onCategory: (category: string) => void;
  onResume: () => void;
  draft?: Doc;
}) {
  return (
    <div className="studio-home">
      <div className="home-intro">
        <span className="eyebrow">МАСТЕРСКАЯ ПОДЗЕМЕЛИЙ</span>
        <h1>Создайте своё приключение</h1>
        <p>
          Начните с карты. Выберите кисть справа: рисунок, стены, свет, ловушки
          и взаимодействия размещаются на одном холсте.
        </p>
        <div className="toolbar">
          <button className="primary" onClick={() => onCategory("maps")}>
            Открыть карты →
          </button>
          {draft && (
            <button onClick={onResume}>Продолжить: {draft.name}</button>
          )}
        </div>
      </div>
      {["Мир", "Объекты", "Правила", "Персонаж"].map((family) => (
        <section className="home-section" key={family}>
          <h2>{family}</h2>
          <div className="home-cards">
            {Object.entries(sections)
              .filter(([c, s]) => s.family === family && c in categories)
              .map(([c, section]) => (
                <button
                  className="home-card"
                  key={c}
                  onClick={() => onCategory(c)}
                >
                  <span className="home-icon">{section.icon}</span>
                  <span className="home-count">
                    {entries.filter((e) => e.category === c).length}
                  </span>
                  <h3>{section.name}</h3>
                  <p>{section.description}</p>
                  <span className="home-link">Открыть раздел →</span>
                </button>
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}
