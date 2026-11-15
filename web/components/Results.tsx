"use client";
import dynamic from "next/dynamic";
import { useState } from "react";
import {
  ArrowRight,
  Check,
  CircleAlert,
  Droplets,
  Leaf,
  ListTree,
  Pencil,
  Printer,
  Scale,
  Sprout,
  Wheat,
} from "lucide-react";
import { makePayload, priorityKeys } from "@/lib/contract";
import type { Strategy } from "@/lib/contract";
import {
  colors,
  numberText,
  priorityNames,
  regionNames,
  strategyNames,
  yearName,
} from "@/lib/labels";
import { cropName, rationale } from "@/lib/english";
import { units } from "@/lib/labels";
import { usePlanner } from "./Store";
import { PrintCharts } from "./PrintCharts";
import { Transition } from "./Transition";
import { YearComparison } from "./YearComparison";
function ChartLoading() {
  const { t } = usePlanner();
  return (
    <p role="status">
      {t("Открываем графики…", "Графиктер ашылуда…", "Loading charts\u2026")}
    </p>
  );
}
const Charts = dynamic(() => import("./Charts"), {
  ssr: false,
  loading: ChartLoading,
});
const tabs = ["compare", "years", "charts", "explain"] as const;

function StrategyStats({ s }: { s: Strategy }) {
  const { lang, t } = usePlanner();
  return (
    <dl className="stats">
      <div>
        <dt>{t("Оценка модели", "Модель бағасы", "Model score")}</dt>
        <dd>{numberText(s.summary_score, lang)}</dd>
      </div>
      <div>
        <dt>
          {t(
            "Экономия воды по модели",
            "Модель бойынша су үнемі",
            "Modelled water savings",
          )}
        </dt>
        <dd>{numberText(s.water_saved_percent, lang)}%</dd>
      </div>
      <div>
        <dt>
          {t(
            "Изменение индекса почвы",
            "Топырақ индексінің өзгерісі",
            "Change in soil index",
          )}
        </dt>
        <dd>{s.soil_health_delta}</dd>
      </div>
    </dl>
  );
}
function Comparison() {
  const { saved, lang, t, selected, choose, switchTab } = usePlanner();
  return (
    <div className="compare-grid">
      {saved!.data.strategies.map((s) => {
        const id = s.strategy_id,
          active = selected === id;
        const Icon =
          id === "recommended"
            ? Scale
            : id === "soil_resilience"
              ? Sprout
              : Wheat;
        return (
          <article
            key={id}
            className={active ? "strategy active" : "strategy"}
            style={{ "--tone": colors[id] } as React.CSSProperties}
          >
            <div className="strat-icon">
              <Icon />
            </div>
            <h3>{strategyNames[id][lang]}</h3>
            <StrategyStats s={s} />
            <ol
              className="crop-sequence"
              aria-label={t(
                "Последовательность культур",
                "Дақылдардың кезегі",
                "Crop sequence",
              )}
            >
              {s.rotation_years.map((y) => (
                <li key={y.year}>
                  <span>{y.year}</span>
                  {cropName(y, lang)}
                </li>
              ))}
            </ol>
            <div className="card-actions">
              <button
                className="secondary"
                aria-pressed={active}
                onClick={() => choose(id)}
              >
                {active ? <Check size={16} /> : null}
                {active
                  ? t("Выбран", "Таңдалды", "Selected")
                  : t("Выбрать план", "Жоспарды таңдау", "Select plan")}
              </button>
              <button
                className="link"
                onClick={() => {
                  choose(id);
                  switchTab("years");
                }}
              >
                {t("По годам", "Жылдар бойынша", "Year by year")}
                <ArrowRight size={16} />
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}
function Years({ s }: { s: Strategy }) {
  const { lang, t } = usePlanner();
  return (
    <ol className="timeline">
      {s.rotation_years.map((y) => (
        <li key={y.year}>
          <div className="timeline-bud">
            <Sprout size={18} />
          </div>
          <div className="year-content">
            <div className="year-label">{yearName(y.year, lang)}</div>
            <h3>{cropName(y, lang)}</h3>
            <p>{rationale(y, lang)}</p>
            <div className="year-metrics">
              <span>
                <Droplets />
                {t("Вода", "Су", "Water")}{" "}
                <strong>
                  {numberText(y.water_demand_mm, lang)} {units(lang).mm}
                </strong>
              </span>
              <span>
                <Droplets />
                {t("Объём для поля", "Танапқа су көлемі", "Field water volume")} {" "}
                <strong>
                  {numberText(y.water_volume_m3, lang)} {units(lang).m3}
                </strong>
              </span>
              <span>
                <Leaf />
                {t("Баланс азота", "Азот теңгерімі", "Nitrogen balance")}{" "}
                <strong>
                  {y.nitrogen_balance_kg_ha > 0 ? "+" : ""}
                  {numberText(y.nitrogen_balance_kg_ha, lang)}{" "}
                  {units(lang).nitrogen}
                </strong>
              </span>
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
function Explanation({ s }: { s: Strategy }) {
  const { t, lang, saved, mode } = usePlanner();
  const equalWeights = priorityKeys.every(
    (key) => saved!.settings.priorities[key] === 0,
  );
  const climate = saved!.data.climate_context;
  const stress = {
    NORMAL: t("Обычные условия", "Қалыпты жағдай", "Normal conditions"),
    MILD_STRESS: t(
      "Небольшой дефицит влаги",
      "Аздаған ылғал тапшылығы",
      "Mild moisture stress",
    ),
    MODERATE_DROUGHT: t(
      "Умеренная засуха",
      "Орташа қуаңшылық",
      "Moderate drought",
    ),
    SEVERE_DROUGHT: t("Сильная засуха", "Күшті қуаңшылық", "Severe drought"),
  };
  return (
    <div className="explanation">
      <h3>{s[`title_${lang}`] ?? strategyNames[s.strategy_id][lang]}</h3>
      <p>
        {mode === "fixture"
          ? t(
              "Этот пример иллюстрирует три стратегии. Выбранные вами приоритеты сохраняются для будущего расчёта.",
              "Мысалда үш стратегия көрсетілген. Таңдалған басымдықтар кейінгі есеп үшін сақталады.",
              "This example illustrates three rotations. Your priorities are saved for a field calculation.",
            )
          : t(
              "В запрос на расчёт вошли следующие относительные веса.",
              "Есепке мына салыстырмалы салмақтар берілді.",
              "These weights were sent with the calculation request.",
            )}
      </p>
      {equalWeights && (
        <p className="inset-note">
          {t(
            "При настройке все четыре ползунка стояли на нуле. Поэтому каждому приоритету присвоен вес 25%.",
            "Параметрлерді таңдағанда төрт жүгірткінің де мәні нөл болды. Сондықтан әр басымдыққа 25% салмақ берілді.",
            "All four sliders were set to zero, so each priority received an equal 25% weight.",
          )}
        </p>
      )}
      {mode === "api" && (
        <ul>
          {priorityKeys.map((k) => (
            <li key={k}>
              {priorityNames[k][lang]} ·{" "}
              {numberText(
                100 * makePayload(saved!.settings).priorities[k],
                lang,
              )}
              %
            </li>
          ))}
        </ul>
      )}
      <h4>{t("Выбор культур", "Дақыл таңдау", "Crop choices")}</h4>
      {s.rotation_years.map((y) => (
        <p key={y.year}>
          <strong>
            {yearName(y.year, lang)} · {cropName(y, lang)}.
          </strong>{" "}
          {rationale(y, lang)}
        </p>
      ))}
      <h4>
        {t("Климатические условия", "Климат жағдайлары", "Climate conditions")}
      </h4>
      <p>{stress[climate.climate_stress_level]}</p>
      <dl className="climate-list">
        <div>
          <dt>
            {t(
              "Влажность почвы SMAP",
              "SMAP топырақ ылғалы",
              "Soil moisture (SMAP)",
            )}
          </dt>
          <dd>
            {numberText(climate.nasa_smap_moisture_m3m3, lang)}{" "}
            {units(lang).moisture}
          </dd>
        </div>
        <div>
          <dt>
            {t(
              "Эвапотранспирация GLDAS",
              "GLDAS булану мен транспирация",
              "Evapotranspiration (GLDAS)",
            )}
          </dt>
          <dd>
            {numberText(climate.nasa_gldas_evapotranspiration_mm, lang)}{" "}
            {units(lang).mm}
          </dd>
        </div>
        <div>
          <dt>
            {t(
              "Исторические осадки IMERG",
              "IMERG тарихи жауын-шашыны",
              "Historical precipitation (IMERG)",
            )}
          </dt>
          <dd>
            {numberText(climate.nasa_imerg_precipitation_mm, lang)}{" "}
            {units(lang).mm}
          </dd>
        </div>
      </dl>
      <h4>
        {t(
          "Как читать оценки",
          "Бағаларды қалай түсінуге болады",
          "Reading the scores",
        )}
      </h4>
      <p>
        {t(
          "Оценка модели помогает сопоставить стратегии. Индекс почвы описывает её расчётное состояние. Фактический урожай, осадки и содержание гумуса на поле требуют отдельных наблюдений.",
          "Модель бағасы стратегияларды салыстыруға көмектеседі. Топырақ индексі оның есептік күйін көрсетеді. Танаптағы нақты өнімді, жауын-шашынды және қарашірікті бөлек бақылау қажет.",
          "The score compares plans. The soil index describes modelled soil condition. Local observations are needed to establish yield, rainfall and organic matter in your field.",
        )}
      </p>
    </div>
  );
}
export function Results() {
  const {
    t,
    lang,
    saved,
    mode,
    navigate,
    selected,
    choose,
    tab,
    switchTab,
    status,
    stale,
    generate,
  } = usePlanner();
  const labels = [
    t("Сравнение", "Салыстыру", "Compare"),
    t("План по годам", "Жылдық жоспар", "Year by year"),
    t("Вода и почва", "Су мен топырақ", "Water and soil"),
    t("Почему такой план", "Жоспардың негізі", "Why this plan?"),
  ];
  const s = saved?.data.strategies.find((x) => x.strategy_id === selected);
  const [printing, setPrinting] = useState(false);
  return (
    <section className="sheet results">
      <div className="result-header">
        <div className="sheet-title">
          <span className="icon-box">
            <ListTree />
          </span>
          <h1 data-step-heading tabIndex={-1}>
            {t(
              "План севооборота",
              "Ауыспалы егіс жоспары",
              "Crop rotation plan",
            )}
          </h1>
        </div>
        <div className="result-tools">
          <button className="link" onClick={() => navigate(1)}>
            <Pencil />
            {t("Параметры", "Параметрлер", "Field settings")}
          </button>
          {saved && (
            <button
              className="secondary"
              disabled={printing}
              onClick={async () => {
                setPrinting(true);
                try {
                  await document.fonts.ready;
                  window.print();
                } finally {
                  setPrinting(false);
                }
              }}
            >
              <Printer />
              {t("Распечатать план", "Жоспарды басып шығару", "Print plan")}
            </button>
          )}
        </div>
      </div>
      {mode === "fixture" && (
        <p className="notice">
          {t(
            "Демонстрационный пример на 4 года. Значения одинаковы для всех настроек поля.",
            "Төрт жылдық демонстрациялық мысал. Мәндер танап параметрлеріне қарамастан бірдей.",
            "Four-year demonstration. The figures are the same for all field settings.",
          )}
        </p>
      )}
      {stale && (
        <p className="notice">
          {t(
            "Параметры изменились. Показан предыдущий результат.",
            "Параметрлер өзгерді. Алдыңғы нәтиже көрсетілген.",
            "Field settings have changed. The previous result is shown.",
          )}
        </p>
      )}
      {status === "loading" && (
        <p role="status" className="notice">
          {saved
            ? t(
                "Обновляем план…",
                "Жоспар жаңартылуда…",
                "Updating the plan\u2026",
              )
            : t("Получаем план…", "Жоспар алынуда…", "Fetching the plan\u2026")}
        </p>
      )}
      {status === "error" && (
        <div className="error-box" role="alert">
          <CircleAlert />
          <span>
            {t(
              "Не удалось обновить план. Проверьте соединение и повторите запрос.",
              "Жоспарды жаңарту мүмкін болмады. Байланысты тексеріп, қайта сұратыңыз.",
              "The plan could not be updated. Check your connection and try again.",
            )}
          </span>
          <button className="secondary" onClick={generate}>
            {t("Повторить", "Қайталау", "Try again")}
          </button>
        </div>
      )}
      {s && (
        <>
          <div
            className="result-tabs"
            role="tablist"
            aria-label={t("Разделы плана", "Жоспар бөлімдері", "Plan sections")}
          >
            {tabs.map((key, i) => (
              <button
                key={key}
                role="tab"
                id={"tab-" + key}
                aria-selected={tab === key}
                tabIndex={tab === key ? 0 : -1}
                aria-controls="result-panel"
                onClick={() => switchTab(key)}
                onKeyDown={(e) => {
                  const index =
                    e.key === "ArrowRight"
                      ? (i + 1) % 4
                      : e.key === "ArrowLeft"
                        ? (i + 3) % 4
                        : e.key === "Home"
                          ? 0
                          : e.key === "End"
                            ? 3
                            : -1;
                  if (index !== -1) {
                    e.preventDefault();
                    switchTab(tabs[index]);
                    document.getElementById("tab-" + tabs[index])?.focus();
                  }
                }}
              >
                {labels[i]}
              </button>
            ))}
          </div>
          {tab !== "compare" && (
            <label className="strategy-picker">
              {t("Стратегия", "Стратегия", "Strategy")}
              <select
                value={selected}
                onChange={(e) => choose(e.target.value as typeof selected)}
              >
                {saved!.data.strategies.map((x) => (
                  <option key={x.strategy_id} value={x.strategy_id}>
                    {strategyNames[x.strategy_id][lang]}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div id="result-panel" role="tabpanel" aria-labelledby={"tab-" + tab}>
            <Transition key={tab}>
              {tab === "compare" ? (
                <>
                  <YearComparison
                    plan={s}
                    strategies={saved!.data.strategies}
                  />
                  <h2 className="strategy-list-title">
                    {t(
                      "Три стратегии на весь срок",
                      "Бүкіл мерзімге арналған үш стратегия",
                      "Three rotations over the full period",
                    )}
                  </h2>
                  <Comparison />
                </>
              ) : tab === "years" ? (
                <Years s={s} />
              ) : tab === "charts" ? (
                <Charts s={s} />
              ) : (
                <Explanation s={s} />
              )}
            </Transition>
          </div>
        </>
      )}
    </section>
  );
}
export function PrintPlan() {
  const { saved, lang, t, selected, stale, catalog, settings, mode, status } =
    usePlanner();
  const s = saved!.data.strategies.find((x) => x.strategy_id === selected)!;
  const field = mode === "fixture" ? settings : saved!.settings;
  const soil = catalog.soils.find((x) => x.id === field.soil_type)!;
  return (
    <article className="print-plan">
      <strong>FieldShift</strong>
      <h1>
        {t("План севооборота", "Ауыспалы егіс жоспары", "Crop rotation plan")}
      </h1>
      <p>
        {mode === "fixture"
          ? t(
              "Демонстрационный пример. Значения не рассчитаны для указанных параметров.",
              "Демонстрациялық мысал. Мәндер көрсетілген параметрлер үшін есептелмеген.",
              "Demonstration example. These figures were not calculated for the displayed field settings.",
            )
          : t("Расчёт для поля", "Танапқа арналған есеп", "Field calculation")}
      </p>
      {(stale || status === "loading" || status === "error") && (
        <p>
          {t(
            "Последний сохранённый результат. План не обновлён.",
            "Соңғы сақталған нәтиже. Жоспар жаңартылмаған.",
            "Last saved result. The plan has not been updated.",
          )}
        </p>
      )}
      <p>
        {regionNames[field.region][lang]} · {soil.name[lang]} ·{" "}
        {numberText(field.field_area_ha, lang)} {units(lang).ha} ·{" "}
        {field.duration_years} {t("года", "жыл", "years")}
      </p>
      <p>
        {priorityKeys
          .map(
            (k) =>
              priorityNames[k][lang] +
              " " +
              numberText(makePayload(field).priorities[k] * 100, lang) +
              "%",
          )
          .join(" · ")}
      </p>
      <h2>{strategyNames[selected][lang]}</h2>
      <StrategyStats s={s} />
      <Years s={s} />
      <PrintCharts s={s} />
    </article>
  );
}
