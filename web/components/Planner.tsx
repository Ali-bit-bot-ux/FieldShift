"use client";
import { useRef, useState, useEffect } from "react";
import { MotionConfig } from "motion/react";
import {
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  FlaskConical,
  MapPin,
  PanelTop,
  Satellite,
  Sprout,
  X,
} from "lucide-react";
import type { Catalog, Mode } from "@/lib/contract";
import { PlannerProvider, usePlanner } from "./Store";
import dynamic from "next/dynamic";
import { ToolNav, useSection } from "./ToolNav";
import { Transition } from "./Transition";
import { FieldCard, Passport, Priorities } from "./Forms";
import { Results, PrintPlan } from "./Results";

const FarmTools = dynamic(() => import("./tools/FarmTools"));
function Help({ onClose }: { onClose: () => void }) {
  const { t } = usePlanner();
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = dialog.current;
    el?.showModal();
    return () => el?.close();
  }, []);
  const sources = [
    [
      "MODIS MOD13Q1",
      t(
        "В PhenoMap сравниваем индекс зелёной растительности NDVI в одной точке за несколько сезонов.",
        "PhenoMap бір нүктедегі өсімдіктің NDVI индексін бірнеше маусым бойынша салыстырады.",
        "PhenoMap compares a sample point’s vegetation index across growing seasons.",
      ),
      "https://modis.ornl.gov/data/modis_webservice.html",
    ],
    [
      "SMAP",
      t(
        "Оценивает влажность верхнего слоя почвы.",
        "Топырақтың үстіңгі қабатындағы ылғалды бағалайды.",
        "Estimates moisture in the surface layer of soil.",
      ),
      "https://smap.jpl.nasa.gov/mission/description/",
    ],
    [
      "GLDAS",
      t(
        "Объединяет наблюдения с моделями суши. В плане используется оценка испарения воды с почвы и через растения.",
        "Бақылауларды жер беті модельдерімен біріктіреді. Жоспарда топырақ пен өсімдіктерден буланатын су бағаланады.",
        "Combines observations with land surface models. The plan uses an estimate of water lost through evaporation and transpiration.",
      ),
      "https://ldas.gsfc.nasa.gov/gldas",
    ],
    [
      "IMERG",
      t(
        "Оценивает осадки. Исторический уровень помогает сравнить потребности культур в воде. Погода в отдельном году может отличаться.",
        "Жауын-шашынды бағалайды. Тарихи деңгей дақылдардың суға сұранысын салыстыруға көмектеседі. Әр жылғы ауа райы әртүрлі болуы мүмкін.",
        "Estimates precipitation. Past rainfall helps put crop water demand in context. Rainfall varies from year to year.",
      ),
      "https://gpm.nasa.gov/data/imerg",
    ],
  ];
  return (
    <dialog
      ref={dialog}
      aria-labelledby="help-title"
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="dialog-content">
        <div className="row-between">
          <span className="icon-box">
            <BookOpen />
          </span>
          <button
            onClick={onClose}
            className="icon-btn"
            aria-label={t("Закрыть", "Жабу", "Close")}
          >
            <X />
          </button>
        </div>
        <h2 id="help-title">
          {t(
            "Помощь и источники",
            "Көмек және дереккөздер",
            "Help and data sources",
          )}
        </h2>
        <h3>
          {t(
            "Зачем чередовать культуры?",
            "Дақылдарды не үшін алмастырады?",
            "Why rotate crops?",
          )}
        </h3>
        <p>
          {t(
            "Разные культуры по-разному расходуют воду и питательные вещества. Чередование также помогает прервать циклы болезней. Сравните варианты и обсудите план с агрономом.",
            "Дақылдардың су мен қоректік заттарға сұранысы әртүрлі. Оларды алмастыру аурулардың таралу циклін үзуге де көмектеседі. Нұсқаларды салыстырып, жоспарды агрономмен талқылаңыз.",
            "Crops use different amounts of water and nutrients. Rotating them can also break disease cycles. Compare the options and discuss your plan with an agronomist.",
          )}
        </p>
        <h3>
          {t(
            "Откуда климатические показатели",
            "Климат көрсеткіштері қайдан алынады",
            "Climate data sources",
          )}
        </h3>
        {sources.map(([label, body, url]) => (
          <section key={label}>
            <a href={url} target="_blank" rel="noreferrer">
              NASA {label}
              <ArrowUpRight size={15} />
            </a>
            <p>{body}</p>
          </section>
        ))}
        <h3>
          {t(
            "Что означает индекс почвы",
            "Топырақ индексінің мәні",
            "What does the soil index measure?",
          )}
        </h3>
        <p>
          {t(
            "FieldShift сравнивает состояние почвы по расчётной шкале. Для оценки фактического содержания гумуса нужен почвенный анализ.",
            "FieldShift топырақ күйін есептік шкала бойынша салыстырады. Қарашіріктің нақты үлесін анықтау үшін топырақ талдауы қажет.",
            "FieldShift uses a modelled index to compare soil condition. A soil test is needed to measure organic matter in the field.",
          )}
        </p>
      </div>
    </dialog>
  );
}
function Workspace() {
  const section = useSection();
  const {
    lang,
    t,
    mode,
    step,
    hydrated,
    navigate,
    switchLang,
    saved,
    settings,
  } = usePlanner();
  const [help, setHelp] = useState(false);
  const previousStep = useRef(step);
  useEffect(() => {
    if (previousStep.current !== step)
      document
        .querySelector<HTMLElement>("[data-step-heading]")
        ?.focus({ preventScroll: true });
    previousStep.current = step;
  }, [step]);
  const steps = [
    t("Моё поле", "Менің танабым", "My field"),
    t("Мои приоритеты", "Басымдықтарым", "My priorities"),
    t("Результаты", "Нәтижелер", "Results"),
  ];
  const helpButton = (
    <button
      className="help-btn"
      aria-label={t("Помощь", "Көмек", "Help")}
      onClick={() => setHelp(true)}
    >
      <CircleHelp size={19} />
      <span>{t("Помощь", "Көмек", "Help")}</span>
    </button>
  );
  return (
    <MotionConfig reducedMotion="user">
      <div className="screen">
        <header>
          <div className="wrap topbar">
            <div className="brand">
              <span className="brand-mark">
                <Sprout size={27} />
              </span>
              FieldShift
            </div>
            <span className="brand-sub">
              {t("Полевой помощник", "Танап көмекшісі", "Field notebook")}
            </span>
            <div className="toolbar">
              {helpButton}
              <div
                className="languages"
                aria-label={t("Язык", "Тіл", "Language")}
              >
                {(["kk", "ru", "en"] as const).map((l) => (
                  <button
                    key={l}
                    lang={l}
                    aria-pressed={lang === l}
                    onClick={() => switchLang(l)}
                  >
                    {{ kk: "ҚАЗ", ru: "РУС", en: "EN" }[l]}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </header>
        <ToolNav section={section} />
        <main className="wrap">
          {section !== "planner" ? (
            hydrated && <FarmTools section={section} />
          ) : (
            <>
              {step !== 3 && (
                <section className="hero">
                  <div className="hero-place">
                    <MapPin size={15} />
                    {t(
                      "Зерновой пояс Казахстана",
                      "Қазақстанның астық белдеуі",
                      "Kazakhstan grain belt",
                    )}
                  </div>
                  <h1>
                    {t(
                      "Планировщик севооборота",
                      "Ауыспалы егіс жоспары",
                      "Crop rotation planner",
                    )}
                  </h1>
                  <p>
                    {t(
                      "Подберите чередование культур для своего поля с учётом почвы, влаги и ваших приоритетов.",
                      "Топыраққа, ылғалға және өз басымдықтарыңызға қарай танапқа дақыл кезегін таңдаңыз.",
                      "Plan a crop sequence around your soil, water supply and priorities.",
                    )}
                  </p>
                </section>
              )}
              <div className="steps-row">
                <nav
                  className="steps"
                  aria-label={t(
                    "Шаги планировщика",
                    "Жоспарлау қадамдары",
                    "Planning steps",
                  )}
                >
                  {steps.map((name, i) => {
                    const n = (i + 1) as 1 | 2 | 3;
                    return (
                      <div key={n}>
                        <button
                          aria-current={n === step ? "step" : undefined}
                          className={n <= step ? "reached" : ""}
                          disabled={
                            (n === 3 && !saved && step !== 3) ||
                            (n !== 1 &&
                              !(
                                settings.field_area_ha >= 0.1 &&
                                settings.field_area_ha <= 50000
                              ))
                          }
                          onClick={() => navigate(n)}
                        >
                          <b>{n < step ? <Check size={14} /> : n}</b>
                          <span>{name}</span>
                        </button>
                        {n < 3 && (
                          <ChevronRight className="connector" size={14} />
                        )}
                      </div>
                    );
                  })}
                </nav>
                {(step !== 3 || mode === "api") && (
                  <div className="data-mode">
                    {mode === "fixture" ? (
                      <FlaskConical size={15} />
                    ) : (
                      <Satellite size={16} />
                    )}{" "}
                    {mode === "fixture"
                      ? t(
                          "Демонстрационный пример",
                          "Демонстрациялық мысал",
                          "Demonstration example",
                        )
                      : t(
                          "Расчёт для поля",
                          "Танапқа арналған есеп",
                          "Field calculation",
                        )}
                  </div>
                )}
              </div>
              <Transition key={step}>
                {step === 3 ? (
                  <Results />
                ) : (
                  <div className="workspace-grid">
                    <div>{step === 1 ? <FieldCard /> : <Priorities />}</div>
                    <Passport />
                  </div>
                )}
              </Transition>
            </>
          )}
        </main>
        <footer className="wrap">
          <span>
            <Sprout size={17} /> FieldShift
          </span>
          <button onClick={() => setHelp(true)}>
            <PanelTop size={15} />
            {t("Источники данных", "Дереккөздер", "Data sources")}
            {section === "planner" && (
              <span className="sources-names">SMAP · GLDAS · IMERG</span>
            )}
          </button>
        </footer>
        {help && <Help onClose={() => setHelp(false)} />}
      </div>
      {section === "planner" && saved && <PrintPlan />}
    </MotionConfig>
  );
}
export function Planner({ catalog, mode }: { catalog: Catalog; mode: Mode }) {
  return (
    <PlannerProvider catalog={catalog} mode={mode}>
      <Workspace />
    </PlannerProvider>
  );
}
