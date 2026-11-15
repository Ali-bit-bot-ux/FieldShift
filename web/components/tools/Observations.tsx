import { useState } from "react";
import archive from "@/data/observations.json";
import { DistrictMap, SeriesChart } from "./Visuals";
import {
  meanDeficit,
  placeNames,
  places,
  dateLabel,
  type Place,
} from "@/lib/tools";
import { numberText, units } from "@/lib/labels";
import { usePlanner } from "../Store";
export function Observations({
  kind,
  place,
  setPlace,
}: {
  kind: "phenomap" | "hydrorisk" | "backtesting";
  place: Place;
  setPlace: (p: Place) => void;
}) {
  const { t, lang } = usePlanner(),
    [threshold, setThreshold] = useState(0.15);
  const vegetation = kind === "phenomap",
    backtest = kind === "backtesting",
    metric = vegetation ? "ndvi" : "moisture",
    data = archive[place],
    rows = data[metric];
  const values = Object.fromEntries(
    places.map((p) => [p, meanDeficit(archive[p][metric])]),
  );
  const first = rows.find((p) => p.value !== null && p.value < threshold);
  const unit = vegetation ? "NDVI" : units(lang).moisture;
  return (
    <>
      <p className="tool-intro">
        {t(
          "Архив сезона 2021. В каждом районе показана одна точка. Ориентир — среднее за те же дни 2018–2020 годов.",
          "2021 жылғы маусым мұрағаты. Әр ауданда бір нүкте көрсетілген. Бағдар — 2018–2020 жылдардағы сол күндердің орташа мәні.",
          "2021 season archive. Each district is represented by one sample point. The reference is the mean for the same days of year in 2018–2020.",
        )}
      </p>
      <div className="atlas-grid">
        <section className="tool-sheet">
          <h2>{placeNames[place][lang]}</h2>
          <p className="hint">
            {data.lat}°, {data.lon}° ·{" "}
            {vegetation
              ? "MODIS MOD13Q1 · NDVI"
              : "NASA POWER · SMAP L4 · SFMC"}
          </p>
          {backtest ? (
            <>
              <label className="tool-range">
                {t("Порог сигнала", "Сигнал шегі", "Alert threshold")} ·{" "}
                {numberText(threshold, lang)} {unit}
                <input
                  type="range"
                  min=".01"
                  max=".5"
                  step=".01"
                  value={threshold}
                  onChange={(e) => setThreshold(+e.target.value)}
                />
              </label>
              <p className="tool-reading">
                {first
                  ? t(
                      "Первое наблюдение ниже порога",
                      "Шектен төмен алғашқы бақылау",
                      "First observation below threshold",
                    ) +
                    " · " +
                    dateLabel(first.date, lang)
                  : t(
                      "За этот период сигналов нет",
                      "Осы кезеңде сигнал болған жоқ",
                      "No threshold crossing in this period",
                    )}
              </p>
            </>
          ) : (
            <p className="tool-reading">
              {values[place] === null
                ? "—"
                : numberText(
                    Math.round(Math.abs(values[place]!) * 10) / 10,
                    lang,
                  ) + "%"}{" "}
              <small>
                {(values[place] ?? 0) >= 0
                  ? t(
                      "ниже ориентира за период",
                      "кезеңдік бағдардан төмен",
                      "below the period reference",
                    )
                  : t(
                      "выше ориентира за период",
                      "кезеңдік бағдардан жоғары",
                      "above the period reference",
                    )}
              </small>
            </p>
          )}
          <SeriesChart
            series={rows}
            unit={unit}
            threshold={backtest ? threshold : undefined}
          />
        </section>
        <section className="tool-sheet">
          <h2>
            {t(
              "Отклонение по районам",
              "Аудандар бойынша ауытқу",
              "District departures",
            )}
          </h2>
          <p className="hint">
            {t(
              "Положительный процент означает дефицит относительно ориентира в точке.",
              "Оң пайыз нүктедегі мәннің бағдардан төмен екенін көрсетеді.",
              "A positive percentage means the sample is below its reference.",
            )}
          </p>
          <DistrictMap selected={place} onSelect={setPlace} values={values} />
        </section>
      </div>
      <p className="source-note">
        {vegetation
          ? t(
              "MODIS, 250 м. Сохранены качественные 16-дневные композиты; пропуски видны в таблице.",
              "MODIS, 250 м. Сапалы 16 күндік композиттер алынды. Бос мәндер кестеде көрсетілген.",
              "MODIS, 250 m. Only good-quality 16-day composites are included. Gaps remain in the table.",
            )
          : t(
              "SMAP L4, оценка влажности верхних 5 см. Порог задаёт пользователь.",
              "SMAP L4, үстіңгі 5 см топырақ ылғалының бағасы. Шекті пайдаланушы таңдайды.",
              "SMAP L4 estimates moisture in the top 5 cm. The alert threshold is user-defined.",
            )}{" "}
        <a
          href={
            vegetation
              ? "https://modis.ornl.gov/data/modis_webservice.html"
              : "https://power.larc.nasa.gov/docs/methodology/data/sources_hydrology/"
          }
          target="_blank"
          rel="noreferrer"
        >
          {t("Источник NASA", "NASA дереккөзі", "NASA source")} ↗
        </a>
      </p>
    </>
  );
}
