"use client";
import { useEffect, useRef, useState, useMemo } from "react";
import * as Plotly from "plotly.js-basic-dist-min";
import type { Data, Layout } from "plotly.js";
import type { Strategy } from "@/lib/contract";
import { colors, numberText, strategyNames, yearName } from "@/lib/labels";
import { units } from "@/lib/labels";
import { usePlanner } from "./Store";

function Plot({
  title,
  data,
  unit,
  yearAxis,
}: {
  title: string;
  data: Data[];
  unit: string;
  yearAxis: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { t, lang } = usePlanner();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let active = true;
    const layout: Partial<Layout> = {
      autosize: true,
      height: 270,
      margin: { l: 48, r: 15, t: 14, b: 46 },
      showlegend: false,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: {
        family: "Noto Sans Variable, sans-serif",
        color: "#3b5645",
        size: 12,
      },
      xaxis: {
        type: "category",
        fixedrange: true,
        title: { text: yearAxis },
        showgrid: false,
      },
      yaxis: {
        fixedrange: true,
        rangemode: "tozero",
        gridcolor: "#dbe5db",
        zeroline: false,
        title: { text: unit },
      },
      separators: lang === "en" ? ".," : ", ",
      hovermode: "closest",
    };
    const ready = Plotly.react(el, data, layout, {
      displayModeBar: false,
      displaylogo: false,
      responsive: false,
      scrollZoom: false,
    });
    void ready.catch(() => {
      if (active) setFailed(true);
    });
    return () => {
      active = false;
    };
  }, [data, unit, yearAxis, lang]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let width = el.clientWidth,
      frame = 0;
    const observer = new ResizeObserver(([entry]) => {
      const next = Math.round(entry.contentRect.width);
      if (!next || next === width) return;
      width = next;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        void Promise.resolve(Plotly.Plots.resize(el)).catch(() => {});
      });
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      Plotly.purge(el);
    };
  }, []);
  return (
    <>
      <div className="chart-canvas" role="img" aria-label={title} ref={ref} />
      {failed && (
        <p>
          {t(
            "Значения доступны в таблице ниже.",
            "Мәндерді төмендегі кестеден қарай аласыз.",
            "The values are listed in the table below.",
          )}
        </p>
      )}
    </>
  );
}
export default function Charts({ s }: { s: Strategy }) {
  const { t, lang, saved } = usePlanner();
  const result = saved!.data,
    rain = result.climate_context.nasa_imerg_precipitation_mm;
  const demand = t("Потребность в воде", "Суға сұраныс", "Water demand"),
    history = t(
      "Исторические осадки IMERG",
      "IMERG тарихи жауын-шашыны",
      "Historical precipitation (IMERG)",
    );
  const soilLabel = t("Индекс почвы", "Топырақ индексі", "Soil health index");
  const charts = useMemo(() => {
    const x = s.rotation_years.map((y) => yearName(y.year, lang));
    const trace = (
      name: string,
      y: number[],
      color: string,
      width: number,
      dash: "solid" | "dash" | "dot" = "solid",
    ): Data => ({
      x,
      y,
      type: "scatter",
      mode: "lines+markers",
      name,
      line: { color, width, dash },
      marker: { size: 7 },
      hovertemplate: "%{x}<br>" + name + " · %{y}<extra></extra>",
    });
    return {
      water: [
        {
          x,
          y: s.rotation_years.map((y) => y.water_demand_mm),
          type: "bar",
          name: demand,
          marker: { color: "#609378" },
          width: 0.45,
          hovertemplate:
            "%{x}<br>" + demand + ` · %{y} ${units(lang).mm}<extra></extra>`,
        } as Data,
        trace(
          history,
          x.map(() => rain),
          "#376b96",
          2,
          "dash",
        ),
      ],
      soil: result.strategies.map((st) =>
        trace(
          strategyNames[st.strategy_id][lang],
          st.rotation_years.map((y) => y.soil_health_score),
          colors[st.strategy_id],
          st.strategy_id === s.strategy_id ? 4 : 2,
          st.strategy_id === "traditional_risk"
            ? "dash"
            : st.strategy_id === "soil_resilience"
              ? "dot"
              : "solid",
        ),
      ),
    };
  }, [s, lang, result, rain, demand, history]);
  return (
    <>
      <div className="chart-grid">
        {[
          {
            title: t(
              "Потребность в воде и осадки",
              "Суға сұраныс пен жауын-шашын",
              "Water demand and precipitation",
            ),
            unit: units(lang).mm,
            data: charts.water,
            legend: [
              [demand, "#609378"],
              [history, "#376b96"],
            ],
          },
          {
            title: t(
              "Состояние почвы по годам",
              "Топырақтың жылдар бойынша күйі",
              "Soil health by year",
            ),
            unit: t("Индекс", "Индекс", "Index"),
            data: charts.soil,
            legend: result.strategies.map((st) => [
              strategyNames[st.strategy_id][lang],
              colors[st.strategy_id],
            ]),
          },
        ].map((chart) => (
          <section key={chart.title} className="chart-panel">
            <h3>{chart.title}</h3>
            <div className="legend">
              {chart.legend.map(([name, color]) => (
                <span key={name}>
                  <i style={{ background: color }} />
                  {name}
                </span>
              ))}
            </div>
            <Plot
              title={chart.title}
              data={chart.data}
              unit={chart.unit}
              yearAxis={t("Год плана", "Жоспар жылы", "Rotation year")}
            />
          </section>
        ))}
      </div>
      <p className="hint">
        {t(
          "На графике воды показана выбранная стратегия. Линия IMERG обозначает исторический ориентир. График почвы сравнивает все три плана.",
          "Су графигінде таңдалған стратегия көрсетілген. IMERG сызығы тарихи деңгейді білдіреді. Топырақ графигінде үш жоспар салыстырылған.",
          "Bars show water demand for the selected plan. The dashed line marks historical rainfall. The soil chart compares all three rotations.",
        )}
      </p>
      <details className="data-table">
        <summary>
          {t(
            "Открыть таблицу значений",
            "Мәндер кестесін ашу",
            "Show the data table",
          )}
        </summary>
        <div className="table-scroll">
          <table>
            <caption>{strategyNames[s.strategy_id][lang]}</caption>
            <thead>
              <tr>
                {[
                  t("Год", "Жыл", "Year"),
                  demand + " (" + units(lang).mm + ")",
                  t("Объём воды для поля", "Танапқа су көлемі", "Field water volume") + " (" + units(lang).m3 + ")",
                  history + " (" + units(lang).mm + ")",
                  ...result.strategies.map(
                    (st) =>
                      soilLabel + " · " + strategyNames[st.strategy_id][lang],
                  ),
                ].map((v) => (
                  <th key={v} scope="col">
                    {v}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {s.rotation_years.map((y, i) => (
                <tr key={y.year}>
                  <th scope="row">{y.year}</th>
                  <td>{numberText(y.water_demand_mm, lang)}</td>
                  <td>{numberText(y.water_volume_m3, lang)}</td>
                  <td>{numberText(rain, lang)}</td>
                  {result.strategies.map((st) => (
                    <td key={st.strategy_id}>
                      {numberText(st.rotation_years[i].soil_health_score, lang)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
