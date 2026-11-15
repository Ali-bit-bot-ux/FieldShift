import soils from "../../dataset/soils.json";
import crops from "../../dataset/crops.json";
import type { Catalog, Mode } from "./contract";
import { soilEnglish } from "./english";
export const catalog: Catalog = {
  soils: soils.map((s) => ({
    id: s.id,
    name: {
      ru: s.name_ru,
      kk: s.name_kk.replace(" (каштановые)", ""),
      en: soilEnglish[s.id][0],
    },
    texture: { ru: s.texture, kk: s.texture_kk, en: soilEnglish[s.id][1] },
    risk: {
      ru: s.primary_vulnerability,
      kk: s.primary_vulnerability_kk,
      en: soilEnglish[s.id][2],
    },
  })),
  cropIds: crops.map((c) => c.id),
};
export function dataMode(): Mode {
  const mode = process.env.FIELDSHIFT_DATA_MODE ?? "fixture";
  if (mode !== "fixture" && mode !== "api")
    throw Error("Invalid FIELDSHIFT_DATA_MODE");
  return mode;
}
