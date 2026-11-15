import type { Lang, StrategyId } from "./contract";
export const regionNames = {
  sko: {
    en: "North Kazakhstan Region",
    ru: "Северо-Казахстанская область",
    kk: "Солтүстік Қазақстан облысы",
  },
  kostanay: {
    en: "Kostanay Region",
    ru: "Костанайская область",
    kk: "Қостанай облысы",
  },
  akmola: {
    en: "Akmola Region",
    ru: "Акмолинская область",
    kk: "Ақмола облысы",
  },
  pavlodar: {
    en: "Pavlodar Region",
    ru: "Павлодарская область",
    kk: "Павлодар облысы",
  },
};
export const strategyNames: Record<StrategyId, Record<Lang, string>> = {
  recommended: {
    en: "Balanced rotation",
    ru: "Сбалансированный план",
    kk: "Теңгерімді жоспар",
  },
  soil_resilience: {
    en: "Soil recovery",
    ru: "Восстановление почвы",
    kk: "Топырақты қалпына келтіру",
  },
  traditional_risk: { en: "Monoculture", ru: "Монокультура", kk: "Дара дақыл" },
};
export const priorityNames = {
  yield_profit: {
    en: "Crop income",
    ru: "Доход от урожая",
    kk: "Өнімнен түсетін табыс",
  },
  water_saving: {
    en: "Water conservation",
    ru: "Сохранение влаги",
    kk: "Ылғалды сақтау",
  },
  soil_health: { en: "Soil health", ru: "Состояние почвы", kk: "Топырақ күйі" },
  cost_minimization: {
    en: "Lower input costs",
    ru: "Снижение затрат",
    kk: "Шығынды азайту",
  },
};
export const colors = {
  recommended: "#2f6b45",
  soil_resilience: "#376b96",
  traditional_risk: "#a9433f",
};
export const yearName = (year: number, lang: Lang) =>
  lang === "en"
    ? `Year ${year}`
    : lang === "ru"
      ? `Год ${year}`
      : `${year}-жыл`;
const formats = Object.fromEntries(
  ["ru", "kk", "en"].map((lang) => [
    lang,
    new Intl.NumberFormat(lang, { maximumFractionDigits: 3 }),
  ]),
);
export const numberText = (n: number, lang: Lang) => formats[lang].format(n);
export const units = (lang: Lang) =>
  lang === "en"
    ? { mm: "mm", ha: "ha", m3: "m³", nitrogen: "kg/ha", moisture: "m³/m³" }
    : { mm: "мм", ha: "га", m3: "м³", nitrogen: "кг/га", moisture: "м³/м³" };
