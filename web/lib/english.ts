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
  "Азотфиксация (+35 кг/га) и сохранение глубокой влаги перед коммерческой культурой.":
    "Nitrogen fixation (+35 kg/ha) and conservation of deep soil moisture ahead of a cash crop.",
  "Глубокая корневая система разуплотняет плужную подошву и накапливает гумус (+45 кг/га N).":
    "Deep roots loosen the plough pan and help build organic matter (+45 kg N/ha).",
  "Глубокий стержневой корень (до 2 м) извлекает остаточную влагу и разрушает солонцеватую корку при засухе.":
    "A deep taproot (up to 2 m) reaches residual moisture and breaks the sodic crust during drought.",
  "Истощение азота и резкий рост сорной нагрузки в монокультуре.":
    "Continuous wheat depletes nitrogen and increases weed pressure.",
  "Коммерческий посев пшеницы по No-Till стерне после азотфиксатора без почвоутомления.":
    "No-till wheat follows a nitrogen-fixing crop, reducing the strain of repeated cropping.",
  "Контрольный коммерческий сценарий монокультуры яровой пшеницы.":
    "Continuous spring wheat provides the commercial comparison.",
  "Короткий вегетационный период до наступления суховеев. Высокая стерня No-Till накапливает 50-70 мм талой влаги к новому циклу.":
    "The growing season ends before dry winds arrive. The model assumes tall no-till stubble retains 50–70 mm of meltwater for the next cycle.",
  "Критический риск фузариоза, потеря продуктивной влаги и падение урожайности до 40%.":
    "The model flags high Fusarium risk, loss of available moisture and yield losses of up to 40%.",
  "Повторный посев пшеницы: накопление корневых гнилей и раннее иссушение верхнего горизонта.":
    "Repeated wheat increases root rot and dries the topsoil earlier.",
  "Раннеспелый ячмень оставляет высокую стерню для снегозадержания перед новым циклом.":
    "Early barley leaves tall stubble to trap snow for the next rotation.",
  "Симбиотическая азотфиксация (+35 кг/га) и разрыв цикла злаковых корневых гнилей. Экономия влаги 35%.":
    "Nitrogen fixation (+35 kg/ha) interrupts cereal root rot cycles. Modelled water saving: 35%.",
  "Стартовая высокодоходная культура с надежным сбытом зерна.":
    "The rotation opens with a high-return crop with an established market.",
  "Стержневая корневая система структурирует пахотный слой почвы и разрушает подплужную подошву.":
    "The taproot improves topsoil structure and breaks up the plough pan.",

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
