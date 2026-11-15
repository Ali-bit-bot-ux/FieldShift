"use client";

import { useState } from "react";
import { ChevronDown, Droplets } from "lucide-react";
import type { Strategy } from "@/lib/contract";
import { numberText, strategyNames, yearName } from "@/lib/labels";
import { cropName, rationale } from "@/lib/english";
import { units } from "@/lib/labels";
import { usePlanner } from "./Store";

export function YearComparison({
  plan,
  strategies,
}: {
  plan: Strategy;
  strategies: Strategy[];
}) {
  const { lang, t, choose } = usePlanner();
  const referenceId =
    plan.strategy_id === "traditional_risk"
      ? "recommended"
      : "traditional_risk";
  const reference = strategies.find((s) => s.strategy_id === referenceId)!;
  // Both rotations have the same contiguous year numbers after contract validation.
  const firstChange = plan.rotation_years.findIndex(
    (y, i) => y.crop_id !== reference.rotation_years[i].crop_id,
  );
  const [pickedYear, setPickedYear] = useState<number | null>(null);
  const index =
    pickedYear && pickedYear <= plan.rotation_years.length
      ? pickedYear - 1
      : Math.max(0, firstChange);
  const current = plan.rotation_years[index];
  const baseline = reference.rotation_years[index];
  const delta = current.water_demand_mm - baseline.water_demand_mm;
  const amount = numberText(Math.abs(delta), lang);
  const difference =
    delta === 0
      ? t(
          "Одинаковая потребность в воде",
          "Суға қажеттілік бірдей",
          "Both crops have the same water demand",
        )
      : delta < 0
        ? t(`На ${amount} мм меньше`, `${amount} мм аз`, `${amount} mm less`)
        : t(`На ${amount} мм больше`, `${amount} мм көп`, `${amount} mm more`);
  const maxDemand = Math.max(current.water_demand_mm, baseline.water_demand_mm);
  const rows = [
    { id: plan.strategy_id, year: current },
    { id: reference.strategy_id, year: baseline },
  ];
  return (
    <section
      className="year-comparison"
      aria-labelledby="year-comparison-title"
    >
      <div className="comparison-heading">
        <h2 id="year-comparison-title">
          {t(
            "Что меняется по годам",
            "Жыл сайын не өзгереді?",
            "What changes each year?",
          )}
        </h2>
        <div
          className="comparison-years"
          role="group"
          aria-label={t("Год сравнения", "Салыстыру жылы", "Comparison year")}
        >
          {plan.rotation_years.map((y) => (
            <button
              key={y.year}
              type="button"
              aria-pressed={current.year === y.year}
              onClick={() => setPickedYear(y.year)}
            >
              {yearName(y.year, lang)}
            </button>
          ))}
        </div>
      </div>
      <div className="comparison-body">
        <div className="crop-decision">
          <div className="comparison-picker">
            <select
              aria-label={t(
                "Стратегия для сравнения",
                "Салыстырылатын стратегия",
                "Strategy to compare",
              )}
              value={plan.strategy_id}
              onChange={(e) =>
                choose(e.target.value as Strategy["strategy_id"])
              }
            >
              {strategies.map((s) => (
                <option key={s.strategy_id} value={s.strategy_id}>
                  {strategyNames[s.strategy_id][lang]}
                </option>
              ))}
            </select>
            <ChevronDown aria-hidden="true" size={15} />
          </div>
          <h3>{cropName(current, lang)}</h3>
          <p>{rationale(current, lang)}</p>
        </div>
        <div className="demand-comparison">
          <h3>
            <Droplets size={17} />
            {t("Потребность в воде", "Суға қажеттілік", "Water demand")}
          </h3>
          <ul>
            {rows.map(({ id, year }) => (
              <li key={id}>
                <div className="demand-label">
                  <span>
                    {strategyNames[id][lang]}
                    {id === referenceId && <> · {cropName(year, lang)}</>}
                  </span>
                  <strong>
                    {numberText(year.water_demand_mm, lang)} {units(lang).mm}
                  </strong>
                </div>
                <div aria-hidden="true" className="demand-track">
                  <i
                    style={{
                      width:
                        (maxDemand
                          ? (year.water_demand_mm / maxDemand) * 100
                          : 0) + "%",
                    }}
                  />
                </div>
              </li>
            ))}
          </ul>
          <p className="demand-difference" aria-live="polite">
            {difference}
          </p>
        </div>
      </div>
    </section>
  );
}
