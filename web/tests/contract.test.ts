import { describe, expect, it } from "vitest";
import fixture from "../../docs/features/fieldshift/fixtures/contract_response.json";
import {
  checkResult,
  defaults,
  makePayload,
  normalize,
  payloadSchema,
} from "../lib/contract";
import { catalog } from "../lib/catalog.server";

describe("field and priorities", () => {
  it("uses equal weights when all are zero", () => {
    expect(
      Object.values(
        normalize({
          yield_profit: 0,
          water_saving: 0,
          soil_health: 0,
          cost_minimization: 0,
        }),
      ),
    ).toEqual([0.25, 0.25, 0.25, 0.25]);
  });
  it("normalizes relative importance without changing the user's sliders", () => {
    const values = {
      yield_profit: 40,
      water_saving: 20,
      soil_health: 10,
      cost_minimization: 10,
    };
    expect(Object.values(normalize(values))).toEqual([0.5, 0.25, 0.125, 0.125]);
    expect(values.yield_profit).toBe(40);
    expect(payloadSchema.safeParse(makePayload(defaults)).success).toBe(true);
    expect(
      payloadSchema.safeParse({ ...makePayload(defaults), field_area_ha: 0 })
        .success,
    ).toBe(false);
  });
});
describe("canonical response", () => {
  it("preserves the original example, including every year's indices", () => {
    expect(checkResult(fixture, 4, catalog)).toEqual(fixture);
  });
  it("rejects missing and duplicated strategies, unknown crops, malformed climate, missing years, duplicate years and non-finite metrics", () => {
    for (const change of [
      (f: typeof fixture) => f.strategies.pop(),
      (f: typeof fixture) => {
        f.strategies[0] = f.strategies[1];
      },
      (f: typeof fixture) => {
        f.strategies[0].rotation_years[0].crop_id = "unknown";
      },
      (f: typeof fixture) =>
        Reflect.deleteProperty(f.climate_context, "nasa_smap_moisture_m3m3"),
      (f: typeof fixture) => f.strategies[1].rotation_years.pop(),
      (f: typeof fixture) => {
        f.strategies[0].rotation_years[1].year = 1;
      },
      (f: typeof fixture) => {
        f.strategies[0].summary_score = Infinity;
      },
      (f: typeof fixture) => {
        f.strategies[0].rotation_years[0].water_demand_mm = NaN;
      },
    ]) {
      const raw = structuredClone(fixture);
      change(raw);
      expect(() => checkResult(raw, 4, catalog)).toThrow();
    }
    expect(() => checkResult(fixture, 3, catalog)).toThrow();
  });
});
