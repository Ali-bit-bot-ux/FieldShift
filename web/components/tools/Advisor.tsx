import { RegionalData } from "./RegionalData";
import { useState } from "react";
import advice from "@/data/advice.json";
import { cropEnglish } from "@/lib/english";
import { usePlanner } from "../Store";

export function Advisor() {
  const { t, lang, catalog, settings, saved, selected } = usePlanner();
  const [crop, setCrop] = useState(
    saved?.data.strategies.find((s) => s.strategy_id === selected)
      ?.rotation_years[0].crop_id ?? "spring_wheat",
  );
  const [soil, setSoil] = useState(settings.soil_type),
    [stage, setStage] = useState(-1);
  const plant = advice.crops.find((c) => c.id === crop)!;
  const pair = advice.matrix.find((r) => r.crop === crop && r.soil === soil);
  const practices = advice.practices.filter((p) =>
    pair ? pair.ids.includes(p.id) : p.soils.includes(soil),
  );
  return (
    <>
      <section className="tool-sheet">
        <div className="scenario-fields">
          <label className="tool-input">
            {t("Культура", "Дақыл", "Crop")}
            <select
              value={crop}
              onChange={(e) => {
                setCrop(e.target.value);
                setStage(-1);
              }}
            >
              {advice.crops.map((p) => (
                <option key={p.id} value={p.id}>
                  {lang === "en" ? cropEnglish[p.id] : p[lang]}
                </option>
              ))}
            </select>
          </label>
          <label className="tool-input">
            {t("Почва", "Топырақ", "Soil")}
            <select value={soil} onChange={(e) => setSoil(e.target.value)}>
              {catalog.soils.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name[lang]}
                </option>
              ))}
            </select>
          </label>
          <label className="tool-input">
            {t("Фаза роста", "Өсу кезеңі", "Growth stage")}
            <select value={stage} onChange={(e) => setStage(+e.target.value)}>
              <option value={-1}>
                {t(
                  "Другая фаза / уточнить",
                  "Басқа кезең / нақтылау",
                  "Other stage / check in field",
                )}
              </option>
              {plant.phases.map((p, i) => (
                <option key={i} value={i}>
                  {p[lang]}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="source-note">
          {pair
            ? t(
                "Подбор для этой пары культуры и почвы есть в матрице FieldShift.",
                "Бұл дақыл мен топырақ жұбы FieldShift кестесінде бар.",
                "The FieldShift catalogue contains a crop–soil match.",
              )
            : t(
                "Для этой пары отдельного сценария нет. Показаны варианты из справочника для выбранной почвы.",
                "Бұл жұпқа жеке сценарий жоқ. Таңдалған топыраққа арналған анықтамалық нұсқалар көрсетілді.",
                "There is no crop-specific match for this soil. These are soil-level options from the catalogue.",
              )}
        </p>
      </section>
      <div className="advice-columns">
        {[
          [
            "emergency_0_48h",
            t("Ближайшие 48 часов", "Алдағы 48 сағат", "Next 48 hours"),
          ],
          [
            "seasonal_tactical",
            t("В этом сезоне", "Осы маусымда", "This season"),
          ],
          [
            "long_term_strategic",
            t("На следующие сезоны", "Келесі маусымдарға", "Future seasons"),
          ],
        ].map(([period, label]) => (
          <section className="tool-sheet" key={period}>
            <h2>{label}</h2>
            {period === "emergency_0_48h" && (
              <p>
                {stage >= 0
                  ? t(
                      "Влагочувствительная фаза. Измерьте влажность у корней и осмотрите растения в нескольких местах поля.",
                      "Ылғалға сезімтал кезең. Тамыр маңындағы ылғалды өлшеп, танаптың бірнеше жерінде өсімдіктерді тексеріңіз.",
                      "Water-sensitive stage. Check moisture around the roots and inspect plants at several points in the field.",
                    ) +
                    " · " +
                    plant.phases[stage][lang]
                  : t(
                      "Уточните фазу развития и проверьте влажность в корневой зоне.",
                      "Даму кезеңін анықтап, тамыр аймағындағы ылғалды тексеріңіз.",
                      "Identify the growth stage and check moisture in the root zone.",
                    )}
              </p>
            )}
            <ul>
              {practices
                .filter((p) => p.period === period)
                .map((p) => (
                  <li key={p.id}>{p[lang]}</li>
                ))}
            </ul>
            {!practices.some((p) => p.period === period) && (
              <p className="hint">
                {t(
                  "Дополнительных мер для этого срока в справочнике нет.",
                  "Осы мерзімге қосымша шара көрсетілмеген.",
                  "The catalogue lists no additional actions for this time frame.",
                )}
              </p>
            )}
          </section>
        ))}
      </div>
      <RegionalData
        tool="agroadvisor"
        region={settings.region}
        crop={crop}
        soil={soil}
        stage={plant.phases[stage]?.ru}
      />
    </>
  );
}
