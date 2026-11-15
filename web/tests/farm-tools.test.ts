import { describe, expect, it } from "vitest";
import { meanDeficit, places } from "../lib/tools";
import {
  assumptionsSchema,
  examples,
  free,
  nearestWithSpace,
  scoreDistrict,
} from "../lib/farm-scenarios";
import { cropName, rationale } from "../lib/english";
import { checkResult } from "../lib/contract";
import { catalog } from "../lib/catalog.server";
import fixture from "../../docs/features/fieldshift/fixtures/contract_response.json";
import archive from "../data/observations.json";

describe("farm tools", () => {
  it("compares only paired observations, retaining shortages and surpluses", () => {
    const series = [
      { date: "2021-06-01", normal: 0.25, value: 0.2 },
      { date: "2021-06-02", normal: null, value: 0.1 },
    ];
    expect(meanDeficit(series)).toBeCloseTo(20);
    expect(meanDeficit([{ ...series[0], value: 0.3 }])).toBeCloseTo(-20);
    expect(meanDeficit([{ ...series[0], normal: 0 }])).toBeNull();
  });
  it("ships a whole load only to a facility with sufficient capacity", () => {
    const plan = examples();
    expect(assumptionsSchema.safeParse(plan).success).toBe(true);
    expect(free(plan.esil[0])).toBe(900);
    expect(nearestWithSpace(plan, "esil", 900)).toBe(42);
    expect(nearestWithSpace(plan, "esil", 901)).toBe(75);
    expect(
      scoreDistrict(10, -5, nearestWithSpace(plan, "esil", 5000)),
    ).toBeCloseTo(110 / 3);
    expect(scoreDistrict(null, 1, 42)).toBeNull();
    plan.esil[0].occupied = plan.esil[0].capacity + 1;
    expect(assumptionsSchema.safeParse(plan).success).toBe(false);
  });
  it("keeps one ordered seasonal series per district", () => {
    for (const place of places)
      for (const key of ["ndvi", "moisture"] as const) {
        const rows = archive[place][key],
          dates = rows.map((row) => row.date);
        expect(dates).toHaveLength(key === "ndvi" ? 7 : 113);
        expect(dates).toEqual([...new Set(dates)].sort());
      }
  });
  it("has English crop names and original explanations across all fixture years", () => {
    const data = checkResult(fixture, 4, catalog);
    for (const y of data.strategies.flatMap((s) => s.rotation_years)) {
      expect(cropName(y, "en")).not.toBe(y.crop_id);
      expect(rationale(y, "en")).not.toMatch(/Switch language|[А-Яа-я]/);
    }
    const first = data.strategies[0].rotation_years[0];
    expect(
      rationale(
        {
          ...first,
          rationale_ru: "Новое обоснование",
          rationale_en: "A new seasonal explanation.",
        },
        "en",
      ),
    ).toEqual("A new seasonal explanation.");
  });
});
