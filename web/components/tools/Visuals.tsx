import { useId } from "react";
import paths from "@/data/district-paths.json";
import {
  places,
  placeNames,
  dateLabel,
  type Reading,
  type Place,
} from "@/lib/tools";
import { usePlanner } from "../Store";
import { numberText } from "@/lib/labels";
export function DistrictMap({
  selected,
  values,
  onSelect,
  route,
}: {
  selected: Place;
  values?: Partial<Record<Place, number | null>>;
  onSelect?: (p: Place) => void;
  route?: {
    origin: { lat: number; lon: number };
    facilities: { lat: number; lon: number; name: string }[];
    index: number;
  };
}) {
  const { lang, t } = usePlanner();
  const id = useId();
  const project = (p: { lon: number; lat: number }) => ({
    x: (p.lon - 60) * 35,
    y: (55.5 - p.lat) * 58,
  });
  const origin = route && project(route.origin);
  const pins = (route?.facilities ?? []).map(project);
  const windowPoints = origin ? [origin, ...pins] : [];
  const left = Math.min(...windowPoints.map((p) => p.x)),
    top = Math.min(...windowPoints.map((p) => p.y));
  const width = Math.max(...windowPoints.map((p) => p.x)) - left,
    height = Math.max(...windowPoints.map((p) => p.y)) - top;
  const scale = Math.max(width / 480, height / 175, 0.12);
  const view = origin
    ? [
        left + width / 2 - 332.5 * scale,
        top + height / 2 - 148 * scale,
        665 * scale,
        296 * scale,
      ].join(" ")
    : "0 0 665 296";
  const shade = (v: number | null | undefined) =>
    v == null
      ? "#e7e9dc"
      : v <= 0
        ? "#a6c9a5"
        : v < 15
          ? "#e1c987"
          : v < 30
            ? "#d99c69"
            : "#ad6457";
  return (
    <figure className="district-map">
      <svg viewBox={view} role="img" aria-labelledby={id}>
        <title id={id}>
          {t(
            "Карта районов зернового пояса",
            "Астық белдеуіндегі аудандар картасы",
            "Grain belt district map",
          )}
        </title>
        {paths.map((p, i) => (
          <path
            key={i}
            d={p.d}
            fill={p.district ? shade(values?.[p.district as Place]) : "#e4e9dd"}
            stroke="#fafbf4"
            strokeWidth={route ? scale : 1.2}
          />
        ))}
        {paths
          .filter((p) => p.district === selected)
          .map((p) => (
            <path
              key={p.district}
              d={p.d}
              fill="none"
              stroke="#214e39"
              strokeWidth={route ? 2 * scale : 2.5}
            />
          ))}
        {route && origin && (
          <g>
            <line
              x1={origin.x}
              y1={origin.y}
              x2={pins[route.index].x}
              y2={pins[route.index].y}
              stroke="#234a36"
              strokeWidth={2 * scale}
              strokeDasharray={4 * scale + " " + 3 * scale}
            />
            <circle
              cx={origin.x}
              cy={origin.y}
              r={5 * scale}
              strokeWidth={scale}
              stroke="#fff"
              fill="#28533c"
            />
            <text
              x={origin.x}
              y={origin.y + 22 * scale}
              textAnchor="middle"
              fontSize={16 * scale}
              fill="#234a36"
            >
              {t("Районная точка", "Аудан нүктесі", "District point")}
            </text>
            {pins.map((pt, i) => (
              <g key={i}>
                <title>{route.facilities[i].name}</title>
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={(route.index === i ? 8 : 6) * scale}
                  strokeWidth={2 * scale}
                  stroke="#fff"
                  fill={route.index === i ? "#93482a" : "#586556"}
                />
                <text
                  x={pt.x}
                  y={pt.y - 14 * scale}
                  textAnchor="middle"
                  fontWeight="bold"
                  fontSize={18 * scale}
                  fill="#233d2c"
                >
                  {i + 1}
                </text>
              </g>
            ))}
          </g>
        )}
      </svg>
      {onSelect && (
        <div className="map-index">
          {places.map((p) => (
            <button
              key={p}
              aria-pressed={p === selected}
              onClick={() => onSelect(p)}
            >
              <i style={{ background: shade(values?.[p]) }} />
              {placeNames[p][lang]}
              {values?.[p] != null && (
                <b>{numberText(Math.round(values[p]!), lang)}%</b>
              )}
            </button>
          ))}
        </div>
      )}
      <figcaption>
        {t("Границы 2017 г.", "2017 жылғы шекаралар", "2017 boundaries")} ·{" "}
        <a
          href="https://www.geoboundaries.org/api/current/gbOpen/KAZ/ADM2/"
          target="_blank"
          rel="noreferrer"
        >
          geoBoundaries / © OpenStreetMap, ODbL
        </a>
      </figcaption>
    </figure>
  );
}
export function SeriesChart({
  series,
  unit,
  threshold,
}: {
  series: Reading[];
  unit: string;
  threshold?: number;
}) {
  const { lang, t } = usePlanner(),
    id = useId(),
    format = (v: number) => numberText(v, lang);
  const vals = series
    .flatMap((r) => [r.value, r.normal])
    .filter((n): n is number => n != null);
  const low = Math.min(0, ...vals, threshold ?? 0),
    high = Math.max(...vals, threshold ?? 0, 0.01);
  const x = (i: number) => 48 + (500 * i) / Math.max(1, series.length - 1),
    y = (v: number) => 165 - ((v - low) * 138) / (high - low);
  function path(key: "normal" | "value") {
    let gap = true;
    return series
      .map((r, i) => {
        const n = r[key];
        if (n === null) {
          gap = true;
          return "";
        }
        const c = gap ? "M" : "L";
        gap = false;
        return c + x(i).toFixed(1) + " " + y(n).toFixed(1);
      })
      .join(" ");
  }
  const obs = t("Наблюдения 2021", "2021 жылғы бақылау", "2021 observations"),
    base = t("Среднее 2018–2020", "2018–2020 орташа мәні", "2018–2020 mean");
  return (
    <div className="field-series">
      <p className="axis-unit">{unit}</p>
      <div className="legend">
        <span>
          <i style={{ background: "#29684b" }} />
          {obs}
        </span>
        <span>
          <i style={{ background: "#827251" }} />
          {base}
        </span>
        {threshold !== undefined && (
          <span>
            <i style={{ background: "#a94936" }} />
            {t("Порог", "Шек", "Threshold")}
          </span>
        )}
      </div>
      <svg viewBox="0 0 580 204" role="img" aria-labelledby={id}>
        <title id={id}>
          {obs} · {unit}
        </title>
        {[0, 0.5, 1].map((f) => {
          const v = low + (high - low) * f;
          return (
            <g key={f}>
              <line x1="48" x2="548" y1={y(v)} y2={y(v)} stroke="#d4dfd2" />
              <text x="43" y={y(v) + 4} textAnchor="end">
                {format(Number(v.toFixed(2)))}
              </text>
            </g>
          );
        })}
        {threshold !== undefined && (
          <line
            x1="48"
            x2="548"
            y1={y(threshold)}
            y2={y(threshold)}
            stroke="#a94936"
            strokeDasharray="3 3"
          />
        )}
        <path
          d={path("normal")}
          stroke="#827251"
          fill="none"
          strokeDasharray="6 4"
          strokeWidth="2"
        />
        <path d={path("value")} fill="none" stroke="#29684b" strokeWidth="3" />
        {series.length < 12 &&
          series.map((r, i) =>
            r.value != null ? (
              <circle
                key={r.date}
                cx={x(i)}
                cy={y(r.value)}
                r="3.5"
                fill="#29684b"
              />
            ) : null,
          )}
        {[0, Math.floor(series.length / 2), series.length - 1].map((i) => (
          <text key={i} x={x(i)} y="190" textAnchor="middle">
            {dateLabel(series[i].date, lang)}
          </text>
        ))}
      </svg>
      <details>
        <summary>
          {t(
            "Числа по датам",
            "Күндер бойынша мәндер",
            "View readings by date",
          )}
        </summary>
        <div className="reading-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("Дата", "Күн", "Date")}</th>
                <th>
                  {obs} ({unit})
                </th>
                <th>
                  {base} ({unit})
                </th>
              </tr>
            </thead>
            <tbody>
              {series.map((row) => (
                <tr key={row.date}>
                  <th>{row.date}</th>
                  <td>{row.value === null ? "—" : format(row.value)}</td>
                  <td>{row.normal === null ? "—" : format(row.normal)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
