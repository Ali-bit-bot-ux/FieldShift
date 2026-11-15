import { useState } from "react";
import archive from "@/data/observations.json";
import {
  type Facility,
  type Facilities,
  free,
  scoreDistrict,
  nearestWithSpace,
} from "@/lib/farm-scenarios";
import { meanDeficit, type Place, places, placeNames } from "@/lib/tools";
import { numberText } from "@/lib/labels";
import { usePlanner } from "../Store";
import { DistrictMap } from "./Visuals";

function Numeric({
  label,
  value,
  change,
  min = 0,
  max = 1e8,
}: {
  label: string;
  value: number;
  change: (n: number) => void;
  min?: number;
  max?: number;
}) {
  const { t } = usePlanner();
  const [draft, setDraft] = useState<string | null>(null);
  const invalid =
    draft !== null &&
    (draft.trim() === "" ||
      !Number.isFinite(Number(draft)) ||
      Number(draft) < min ||
      Number(draft) > max);
  return (
    <label className="tool-input">
      {label}
      <input
        type="number"
        step="any"
        min={min}
        max={max}
        value={draft ?? value}
        aria-invalid={invalid}
        onChange={(e) => {
          setDraft(e.target.value);
          const n = e.target.valueAsNumber;
          if (Number.isFinite(n) && n >= min && n <= max) change(n);
        }}
        onBlur={() => setDraft(null)}
      />
      {invalid && (
        <small>
          {t("Допустимый диапазон", "Рұқсат етілген аралық", "Allowed range")}{" "}
          {min}–{max}
        </small>
      )}
    </label>
  );
}
type Props = {
  place: Place;
  setPlace: (p: Place) => void;
  facilities: Facilities;
  update: (p: Place, index: number, f: Facility) => void;
};
export function Logistics({ place, facilities, update }: Props) {
  const { lang, t } = usePlanner(),
    [index, select] = useState(0),
    [load, setLoad] = useState(500);
  const list = facilities[place],
    f = list[index],
    origin = archive[place],
    fmt = (v: number) => numberText(v, lang),
    ton = t("т", "т", "t");
  function set(key: keyof Facility, v: number | string) {
    update(place, index, { ...f, [key]: v });
  }
  return (
    <>
      <p className="tool-intro">
        {t(
          "Две учебные площадки и тарифы для сравнения. Введите адресные координаты и подтверждённые значения своих элеваторов.",
          "Салыстыру үшін екі үлгі алаң мен тариф берілген. Элеваторларыңыздың координаттары мен расталған деректерін енгізіңіз.",
          "Two example facilities and rates are provided. Enter your elevators’ coordinates and confirmed figures to plan a shipment.",
        )}
      </p>
      <div className="atlas-grid">
        <section className="tool-sheet">
          <h2>{t("Партия зерна", "Астық партиясы", "Grain shipment")}</h2>
          <Numeric
            label={t(
              "Масса партии, т",
              "Партия салмағы, т",
              "Shipment weight, t",
            )}
            value={load}
            min={0.1}
            change={setLoad}
          />
          <table className="scenario-table">
            <thead>
              <tr>
                <th>{t("Элеватор", "Элеватор", "Elevator")}</th>
                <th>{t("Свободно", "Бос орын", "Free capacity")}</th>
                <th>{t("Перевозка", "Тасымал", "Haulage")}</th>
              </tr>
            </thead>
            <tbody>
              {list.map((x, i) => (
                <tr key={i}>
                  <th>
                    <button
                      aria-pressed={index === i}
                      onClick={() => select(i)}
                    >
                      {i + 1}. {x.name}
                    </button>
                  </th>
                  <td>
                    {fmt(free(x))} {ton}
                  </td>
                  <td>
                    {free(x) < load
                      ? t(
                          "Партия не помещается",
                          "Партия сыймайды",
                          "Insufficient capacity",
                        )
                      : fmt(Math.round(x.roadKm * x.rate * load)) + " ₸"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <DistrictMap
            selected={place}
            route={{ origin, facilities: list, index }}
          />
          <p className="hint">
            {t(
              "Линия соединяет районную точку и площадку. В смете используется введённый дорожный километраж.",
              "Сызық аудан нүктесі мен алаңды қосады. Есепке енгізілген жол ұзындығы алынады.",
              "The line connects the sample point and the facility. The estimate uses the road distance you enter.",
            )}
          </p>
          <a
            className="link"
            target="_blank"
            rel="noreferrer"
            href={`https://www.google.com/maps/dir/?api=1&origin=${origin.lat},${origin.lon}&destination=${f.lat},${f.lon}&travelmode=driving`}
          >
            {t(
              "Открыть дорожный маршрут",
              "Автожол бағытын ашу",
              "Open driving directions",
            )}{" "}
            ↗
          </a>
        </section>
        <section className="tool-sheet" key={place + index}>
          <h2>
            {t("Параметры площадки", "Алаң параметрлері", "Facility details")}
          </h2>
          <label className="tool-input">
            {t("Название", "Атауы", "Name")}
            <input
              maxLength={80}
              value={f.name}
              onChange={(e) => set("name", e.target.value)}
            />
          </label>
          <div className="scenario-fields">
            <Numeric
              label={t("Вместимость, т", "Сыйымдылығы, т", "Capacity, t")}
              value={f.capacity}
              min={f.occupied}
              change={(v) => set("capacity", v)}
            />
            <Numeric
              label={t("Занято, т", "Пайдаланылғаны, т", "Occupied, t")}
              value={f.occupied}
              max={f.capacity}
              change={(v) => set("occupied", v)}
            />
            <Numeric
              label={t(
                "Дорога в одну сторону, км",
                "Бір бағыттағы жол, км",
                "One-way road distance, km",
              )}
              value={f.roadKm}
              change={(v) => set("roadKm", v)}
            />
            <Numeric
              label={t("Тариф, ₸/т·км", "Тариф, ₸/т·км", "Rate, ₸/t·km")}
              value={f.rate}
              change={(v) => set("rate", v)}
            />
            <Numeric
              label={t("Широта", "Ендік", "Latitude")}
              min={-90}
              max={90}
              value={f.lat}
              change={(v) => set("lat", v)}
            />
            <Numeric
              label={t("Долгота", "Бойлық", "Longitude")}
              min={-180}
              max={180}
              value={f.lon}
              change={(v) => set("lon", v)}
            />
          </div>
        </section>
      </div>
    </>
  );
}
export function RiskChain({ place }: { place: Place }) {
  const { t, lang } = usePlanner();
  const [sensitivity, S] = useState(0.5),
    [harvest, H] = useState(1000),
    [capacity, C] = useState(600),
    [price, P] = useState(80000),
    [discount, D] = useState(10);
  const deficit = Math.max(0, meanDeficit(archive[place].moisture) ?? 0);
  function estimate(waterDeficit: number) {
    const tonnes =
      harvest * (1 - Math.min(100, waterDeficit * sensitivity) / 100);
    const overflow = Math.max(0, tonnes - capacity);
    return {
      tonnes,
      overflow,
      revenue:
        (tonnes - overflow) * price + overflow * price * (1 - discount / 100),
    };
  }
  const { tonnes, overflow, revenue } = estimate(deficit);
  const fmt = (v: number) => numberText(Math.round(v * 10) / 10, lang);
  return (
    <section className="tool-sheet">
      <p>
        {t(
          "Сценарий хозяйства. Коэффициент задаёт предполагаемую потерю урожая при каждом проценте дефицита влаги. Зерно сверх вместимости продаётся с введённой скидкой.",
          "Шаруашылық сценарийі. Коэффициент ылғал тапшылығының әр пайызына келетін болжамды өнім жоғалуын береді. Сыймаған астық енгізілген жеңілдікпен сатылады.",
          "Farm scenario. Sensitivity sets the assumed yield loss per percentage point of moisture deficit. Grain above storage capacity is sold at the entered discount.",
        )}
      </p>
      <div className="chain-flow">
        {[
          [
            t("Вода", "Су", "Water"),
            fmt(deficit) + "%",
            t("дефицит за период", "кезеңдегі тапшылық", "period deficit"),
          ],
          [
            t("Поле", "Танап", "Field"),
            fmt(tonnes) + " " + t("т", "т", "t"),
            t("после потерь", "шығыннан кейін", "after losses"),
          ],
          [
            t("Хранение", "Сақтау", "Storage"),
            fmt(overflow) + " " + t("т", "т", "t"),
            t("сверх вместимости", "сыймағаны", "above capacity"),
          ],
          [
            t("Продажа", "Сату", "Market"),
            fmt(revenue) + " ₸",
            t("выручка сценария", "сценарий түсімі", "scenario revenue"),
          ],
        ].map(([a, b, c]) => (
          <div key={a}>
            <span>{a}</span>
            <strong>{b}</strong>
            <small>{c}</small>
          </div>
        ))}
      </div>
      <div className="scenario-fields">
        <Numeric
          label={t(
            "Урожай без потерь, т",
            "Шығынсыз өнім, т",
            "Harvest before losses, t",
          )}
          value={harvest}
          change={H}
        />
        <Numeric
          label={t(
            "Чувствительность, % на 1% дефицита",
            "Сезімталдық, 1% тапшылыққа %",
            "Sensitivity, % yield loss per 1% deficit",
          )}
          value={sensitivity}
          max={5}
          change={S}
        />
        <Numeric
          label={t(
            "Доступное хранение, т",
            "Бос сыйымдылық, т",
            "Available storage, t",
          )}
          value={capacity}
          change={C}
        />
        <Numeric
          label={t("Цена продажи, ₸/т", "Сату бағасы, ₸/т", "Sale price, ₸/t")}
          value={price}
          change={P}
        />
        <Numeric
          label={t(
            "Скидка при срочной продаже, %",
            "Жедел сатудағы жеңілдік, %",
            "Immediate-sale discount, %",
          )}
          value={discount}
          max={100}
          change={D}
        />
      </div>
      <figure className="sensitivity">
        <figcaption>
          {t(
            "Как дефицит влаги меняет выручку",
            "Ылғал тапшылығы түсімді қалай өзгертеді",
            "How moisture deficit changes revenue",
          )}
        </figcaption>
        <p className="hint">
          {t(
            "Те же условия хозяйства при пяти уровнях нехватки влаги.",
            "Шаруашылық жағдайы бірдей, ылғал тапшылығы бес түрлі.",
            "The same farm assumptions at five levels of moisture deficit.",
          )}
        </p>
        {[0, 10, 20, 30, 40].map((v) => {
          const amount = estimate(v).revenue;
          return (
            <div key={v}>
              <span>{v}%</span>
              <meter
                min={0}
                max={Math.max(1, estimate(0).revenue)}
                value={amount}
                aria-label={t("Выручка", "Түсім", "Revenue") + " · " + v + "%"}
              />
              <strong>{fmt(amount)} ₸</strong>
            </div>
          );
        })}
      </figure>
    </section>
  );
}
export function Vulnerability({ place, setPlace, facilities }: Props) {
  const { lang, t } = usePlanner(),
    [load, setLoad] = useState(500);
  const scored = places
    .map((p) => {
      const w = meanDeficit(archive[p].moisture),
        n = meanDeficit(archive[p].ndvi),
        km = nearestWithSpace(facilities, p, load);
      return { p, w, n, km, score: scoreDistrict(w, n, km) };
    })
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  const format = (v: number | null) =>
    v === null ? "—" : numberText(Math.round(v * 10) / 10, lang);
  return (
    <>
      <p className="tool-intro">
        {t(
          "Сценарная шкала 0–100. Три равных вклада: дефицит влаги, дефицит NDVI и дорожное расстояние до элеватора со свободным местом. Каждый вклад ограничен диапазоном 0–100; 100 км и отсутствие места дают максимум логистического риска.",
          "0–100 сценарий шкаласы. Ылғал тапшылығы, NDVI тапшылығы және бос орны бар элеваторға дейінгі жол үш бірдей салмақпен есептеледі. Әр үлес 0–100 аралығында. 100 км немесе бос орынның жоқтығы ең жоғары логистикалық тәуекелді береді.",
          "Scenario index from 0 to 100. Moisture deficit (%), NDVI deficit (%) and road distance to available storage (km) each contribute one third. Each is clipped to 0–100. Distances of 100 km or more and no available space receive the maximum logistics score.",
        )}
      </p>
      <div className="atlas-grid">
        <section className="tool-sheet">
          <h2>
            {t(
              "Районы по оценке риска",
              "Аудандардың тәуекел бағасы",
              "District risk ranking",
            )}
          </h2>
          <Numeric
            label={t(
              "Партия для хранения, т",
              "Сақталатын астық, т",
              "Shipment for storage, t",
            )}
            value={load}
            min={0.1}
            change={setLoad}
          />
          <ol className="district-rank">
            {scored.map((row) => (
              <li key={row.p}>
                <button
                  onClick={() => setPlace(row.p)}
                  aria-pressed={place === row.p}
                >
                  <span>{placeNames[row.p][lang]}</span>
                  <b>{format(row.score)}</b>
                </button>
              </li>
            ))}
          </ol>
          <p className="hint">
            {t(
              "Маршруты и мощности взяты из сценариев SiloGrid. Измените их под своё хозяйство.",
              "Жолдар мен сыйымдылық SiloGrid сценарийлерінен алынған. Шаруашылығыңызға сай өзгертіңіз.",
              "Distances and capacities come from the SiloGrid scenarios. Edit them to reflect your farm.",
            )}{" "}
            <a href="#silogrid">SiloGrid ↗</a>
          </p>
        </section>
        <section className="tool-sheet">
          <h2>{placeNames[place][lang]}</h2>
          <DistrictMap
            selected={place}
            values={Object.fromEntries(scored.map((v) => [v.p, v.score]))}
          />
          <p>
            {t(
              "Дефицит влаги / NDVI",
              "Ылғал / NDVI тапшылығы",
              "Moisture / NDVI deficit",
            )}{" "}
            · {format(scored.find((r) => r.p === place)!.w)}% /{" "}
            {format(scored.find((r) => r.p === place)!.n)}%
          </p>
        </section>
      </div>
    </>
  );
}
