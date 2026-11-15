import { z } from "zod";

export const regions = ["sko", "kostanay", "akmola", "pavlodar"] as const;
export const strategyIds = [
  "recommended",
  "soil_resilience",
  "traditional_risk",
] as const;
export const priorityKeys = [
  "yield_profit",
  "water_saving",
  "soil_health",
  "cost_minimization",
] as const;
export const language = z.enum(["ru", "kk", "en"]);
export type Lang = z.infer<typeof language>;
export type Mode = "fixture" | "api";
export type StrategyId = (typeof strategyIds)[number];
export type Soil = {
  id: string;
  name: Record<Lang, string>;
  texture: Record<Lang, string>;
  risk: Record<Lang, string>;
};
export type Catalog = { soils: Soil[]; cropIds: string[] };

const horizon = z.union([z.literal(3), z.literal(4)]);
const weights = (max: number) =>
  z.record(z.enum(priorityKeys), z.number().min(0).max(max));
const base = z.object({
  region: z.enum(regions),
  soil_type: z.string().min(1),
  field_area_ha: z.number().min(0.1).max(50000),
  duration_years: horizon,
});
export const settingsSchema = base.extend({ priorities: weights(100) });
export type Settings = z.infer<typeof settingsSchema>;
export const payloadSchema = base.extend({
  priorities: weights(1).refine(
    (p) => Math.abs(Object.values(p).reduce((a, b) => a + b, 0) - 1) < 1e-8,
  ),
});
export type Payload = z.infer<typeof payloadSchema>;
export const presets = [
  {
    yield_profit: 35,
    water_saving: 35,
    soil_health: 20,
    cost_minimization: 10,
  },
  {
    yield_profit: 20,
    water_saving: 50,
    soil_health: 20,
    cost_minimization: 10,
  },
  {
    yield_profit: 20,
    water_saving: 20,
    soil_health: 50,
    cost_minimization: 10,
  },
];
export const defaults: Settings = {
  region: "sko",
  soil_type: "chernozem_southern_ordinary",
  field_area_ha: 400,
  duration_years: 4,
  priorities: presets[0],
};
export function normalize(p: Settings["priorities"]) {
  const total = priorityKeys.reduce((sum, key) => sum + p[key], 0);
  const result = { ...p };
  for (const key of priorityKeys) result[key] = total ? p[key] / total : 0.25;
  return result;
}
export function makePayload(settings: Settings): Payload {
  return { ...settings, priorities: normalize(settings.priorities) };
}
export function validSoil(id: string, catalog: Catalog) {
  return catalog.soils.some((soil) => soil.id === id);
}
const label = z.string().trim().min(1);
const yearSchema = z.object({
  year: z.number().int(),
  crop_id: label,
  crop_name_ru: label,
  crop_name_kk: label,
  crop_name_en: label.optional(),
  water_demand_mm: z.number().nonnegative(),
water_volume_m3: z.number().nonnegative().optional(),
  soil_health_score: z.number(),
  nitrogen_balance_kg_ha: z.number(),
  rationale_ru: label,
  rationale_kk: label,
  rationale_en: label.optional(),
});
const strategySchema = z.object({
  strategy_id: z.enum(strategyIds),
  title_ru: label,
  title_kk: label,
  title_en: label.optional(),
  summary_score: z.number(),
  water_saved_percent: z.number(),
  soil_health_delta: label,
  rotation_years: z.array(yearSchema),
});
const responseSchema = z.object({
  status: z.literal("success"),
  climate_context: z.strictObject({
    nasa_smap_moisture_m3m3: z.number(),
    nasa_gldas_evapotranspiration_mm: z.number(),
    nasa_imerg_precipitation_mm: z.number().nonnegative(),
    climate_stress_level: z.enum([
      "NORMAL",
      "MILD_STRESS",
      "MODERATE_DROUGHT",
      "SEVERE_DROUGHT",
    ]),
  }),
  strategies: z.array(strategySchema).length(3),
});
export type Result = z.infer<typeof responseSchema>;
export type Strategy = Result["strategies"][number];
export function checkResult(
  raw: unknown,
  years: number,
  catalog: Catalog,
): Result {
  const data = responseSchema.parse(raw);
  const ids = new Set(data.strategies.map((s) => s.strategy_id));
  if (ids.size !== 3) throw Error("strategy_ids");
  for (const s of data.strategies) {
    s.rotation_years.sort((a, b) => a.year - b.year);
    if (
      s.rotation_years.length !== years ||
      s.rotation_years.some(
        (y, i) => y.year !== i + 1 || !catalog.cropIds.includes(y.crop_id),
      )
    ) {
      throw Error("rotation_years");
    }
  }
  data.strategies.sort(
    (a, b) =>
      strategyIds.indexOf(a.strategy_id) - strategyIds.indexOf(b.strategy_id),
  );
  return data;
}


