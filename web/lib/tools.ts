import type { Lang } from "./contract";
export const sections = {
  planner: { ru: "Севооборот", kk: "Ауыспалы егіс", en: "Crop rotation" },
  phenomap: {
    ru: "Состояние растений",
    kk: "Өсімдік күйі",
    en: "Crop condition",
  },
  hydrorisk: { ru: "Запас влаги", kk: "Ылғал қоры", en: "Soil moisture" },
  silogrid: {
    ru: "Хранение и перевозка",
    kk: "Сақтау және тасымалдау",
    en: "Storage and haulage",
  },
  contagion: {
    ru: "Цепочка рисков",
    kk: "Тәуекелдер тізбегі",
    en: "Economic risk chain",
  },
  vulnerability: {
    ru: "Уязвимость районов",
    kk: "Аудандардың осалдығы",
    en: "District vulnerability",
  },
  backtesting: {
    ru: "Засуха 2021 года",
    kk: "2021 жылғы қуаңшылық",
    en: "2021 drought replay",
  },
  agroadvisor: {
    ru: "Советы агроному",
    kk: "Агрономға кеңес",
    en: "Agronomist’s guide",
  },
};
export type Section = keyof typeof sections;
export const toolNames: Record<Section, string> = {
  planner: "FieldShift",
  phenomap: "PhenoMap",
  hydrorisk: "HydroRisk",
  silogrid: "SiloGrid",
  contagion: "Contagion",
  vulnerability: "Vulnerability",
  backtesting: "Backtesting 2021",
  agroadvisor: "AgroAdvisor",
};
export const placeNames = {
  taiynsha: {
    ru: "Тайыншинский район",
    kk: "Тайынша ауданы",
    en: "Taiynsha District",
  },
  fedorov: {
    ru: "Фёдоровский район",
    kk: "Федоров ауданы",
    en: "Fedorov District",
  },
  esil: { ru: "Есильский район", kk: "Есіл ауданы", en: "Esil District" },
  terenkol: {
    ru: "Теренкольский район",
    kk: "Тереңкөл ауданы",
    en: "Terenkol District",
  },
};
export type Place = keyof typeof placeNames;
export const places = Object.keys(placeNames) as Place[];
export const byRegion = {
  sko: "taiynsha",
  kostanay: "fedorov",
  akmola: "esil",
  pavlodar: "terenkol",
} as const;
export type Reading = {
  date: string;
  value: number | null;
  normal: number | null;
};
export const dateLabel = (value: string, lang: Lang) =>
  new Intl.DateTimeFormat(lang, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(value + "T12:00:00Z"));
export function meanDeficit(series: Reading[]) {
  const pairs = series.filter(
    (p): p is { value: number; normal: number; date: string } =>
      p.value !== null && p.normal !== null,
  );
  const baseline = pairs.reduce((sum, p) => sum + p.normal, 0);
  if (!pairs.length || baseline <= 0) return null;
  return (1 - pairs.reduce((sum, p) => sum + p.value, 0) / baseline) * 100;
}
