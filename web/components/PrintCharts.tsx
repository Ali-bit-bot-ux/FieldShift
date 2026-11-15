import type { Strategy } from "@/lib/contract";
import { numberText, yearName } from "@/lib/labels";
import { units } from "@/lib/labels";
import { usePlanner } from "./Store";

// Fixed paper layout also works with native Cmd/Ctrl+P before the chart tab is opened.
export function PrintCharts({ s }: { s: Strategy }) {
  const { saved, t, lang } = usePlanner();
  const rain = saved!.data.climate_context.nasa_imerg_precipitation_mm;
  const groups = [
    {
      title: t(
        "Потребность в воде и осадки, мм",
        "Суға сұраныс пен жауын-шашын, мм",
        "Water demand and precipitation, mm",
      ),
      water: true,
      values: s.rotation_years.map((y) => y.water_demand_mm),
    },
    {
      title: t(
        "Индекс состояния почвы",
        "Топырақ күйінің индексі",
        "Soil health index",
      ),
      water: false,
      values: s.rotation_years.map((y) => y.soil_health_score),
    },
  ];
  return (
    <div className="print-charts">
      {groups.map((g) => {
        const min = Math.min(0, ...g.values),
          max = Math.max(1, ...g.values, g.water ? rain : 0);
        const position = (v: number) => ((v - min) / (max - min)) * 100;
        return (
          <section key={g.title}>
            <h3>{g.title}</h3>
            {g.water && (
              <p>
                {t(
                  "Пунктир — исторические осадки IMERG",
                  "Үзік сызық — IMERG тарихи жауын-шашыны",
                  "Dashed line: historical precipitation (IMERG)",
                )}{" "}
                · {numberText(rain, lang)} {units(lang).mm}
              </p>
            )}
            {g.values.map((v, i) => (
              <div className="paper-bar-row" key={i}>
                <span>{yearName(i + 1, lang)}</span>
                <div className="paper-track">
                  <i
                    style={{
                      left: Math.min(position(0), position(v)) + "%",
                      width: Math.abs(position(v) - position(0)) + "%",
                    }}
                  />
                  {g.water && <b style={{ left: position(rain) + "%" }} />}
                </div>
                <strong>{numberText(v, lang)}</strong>
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
