import type { Lang, Strategy } from "./contract";

export const soilEnglish: Record<string, [string, string, string]> = {
  chernozem_southern_ordinary: [
    "Ordinary and southern chernozems",
    "Heavy loam to clay",
    "Cracks can drain moisture from deeper layers. Dry spring winds can strip fine topsoil.",
  ],
  chestnut_dark_light: [
    "Dark and light chestnut soils",
    "Medium to heavy silty loam",
    "A dense subsoil restricts roots; the surface can seal and form a hard crust.",
  ],
  sierozem_calcareous: [
    "Light, typical and dark sierozems",
    "Light to medium loess-like loam",
    "High temperatures increase evaporation. Flood irrigation can break down soil structure and cause crusting.",
  ],
  solonchak_solonetz: [
    "Solonetz, solonchak and saline soils",
    "Heavy loam or clay rich in sodium and soluble salts",
    "Salts can stress plants. Water moves slowly through the hardened subsoil.",
  ],
  sandy_arenosol: [
    "Sands and sandy loams",
    "Loose to compact sand",
    "Water drains rapidly and the surface layer can reach 55 °C.",
  ],
  alluvial_meadow: [
    "Alluvial floodplain meadow soils",
    "Layered sandy loam to heavy silt",
    "Moisture depends on river levels and upstream releases. Salts can rise from nearby remnant lakes.",
  ],
  brown_semi_desert: [
    "Brown and grey-brown semi-desert soils",
    "Gravelly loam rich in gypsum and carbonates",
    "Thin topsoil, high gypsum content and low annual precipitation limit water supply.",
  ],
};
export const cropEnglish: Record<string, string> = {
  spring_wheat: "Spring wheat",
  winter_wheat: "Winter wheat",
  spring_barley: "Spring barley",
  oats: "Oats",
  maize_corn: "Maize",
  millet: "Common millet",
  sorghum: "Sorghum",
  sunflower: "Sunflower",
  safflower: "Safflower",
  spring_rapeseed: "Spring rapeseed",
  flax_linseed: "Oilseed flax",
  chickpea: "Chickpea",
  lentil: "Lentil",
  pea: "Field pea",
  alfalfa: "Alfalfa",
  cotton: "Cotton",
};
const variants: Record<string, string> = {
  "Ячмень яровой + No-Till стерня": "Spring barley with no-till stubble",
  "Пшеница яровая по No-Till": "No-till spring wheat",
  "Нут засухоустойчивый": "Drought-tolerant chickpea",
};
const reasons: Record<string, string> = {
  "Стартовая коммерческая культура с высоким сбытом.":
    "The rotation opens with a crop that has strong market demand.",
  "Азотфиксация и разрыв цикла злаковых болезней.":
    "Chickpea fixes nitrogen and breaks the cycle of cereal diseases.",
  "Стержневой корень улучшает структуру пахотного слоя.":
    "The taproot helps improve topsoil structure.",
  "Снегозадержание высокой стерней перед новым циклом.":
    "Tall stubble traps snow before the next rotation.",
  "Азотфиксация и минимальная нагрузка на влагу.":
    "Chickpea fixes nitrogen while keeping water demand low.",
  "Коммерческий год после азотфиксатора.":
    "A cash crop follows the nitrogen-fixing legume.",
  "Глубокая корневая система разуплотняет почву.":
    "Deep roots loosen compacted soil.",
  "Короткий вегетационный период после люцерны.":
    "Barley has a short growing season after alfalfa.",
  "Контрольный коммерческий сценарий.":
    "Continuous wheat provides the comparison for the other rotations.",
  "Повторный посев увеличивает корневые болезни.":
    "Repeated wheat increases the risk of root disease.",
  "Истощение азота и рост сорной нагрузки.":
    "Available nitrogen declines and weed pressure rises.",
  "Высокий риск корневых гнилей и потерь урожая.":
    "Root rot and yield loss become more likely.",
};
type Year = Strategy["rotation_years"][number];
export function cropName(year: Year, lang: Lang) {
  if (lang === "en")
    return (
      year.crop_name_en ??
      variants[year.crop_name_ru] ??
      cropEnglish[year.crop_id] ??
      year.crop_id
    );
  return year[`crop_name_${lang}`];
}
export function rationale(year: Year, lang: Lang) {
  if (lang === "en")
    return (
      year.rationale_en ??
      reasons[year.rationale_ru] ??
      "The service supplied this year's explanation in Russian and Kazakh. Switch language to read the original."
    );
  return year[`rationale_${lang}`];
}
