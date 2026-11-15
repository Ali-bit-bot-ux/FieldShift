import { z } from "zod";
import archive from "../data/observations.json";
import { places, type Place } from "./tools";
const store = z
  .object({
    name: z.string().max(80),
    lat: z.number().min(-90).max(90),
    lon: z.number().min(-180).max(180),
    capacity: z.number().nonnegative(),
    occupied: z.number().nonnegative(),
    roadKm: z.number().nonnegative(),
    rate: z.number().nonnegative(),
  })
  .refine((x) => x.occupied <= x.capacity);
export const assumptionsSchema = z.record(
  z.enum(["esil", "fedorov", "taiynsha", "terenkol"]),
  z.array(store).length(2),
);
export type Facility = z.infer<typeof store>;
export type Facilities = z.infer<typeof assumptionsSchema>;
export function examples(): Facilities {
  return Object.fromEntries(
    places.map((p) => [
      p,
      [0, 1].map((i) => ({
        name: i ? "B" : "A",
        lat: +(archive[p].lat + 0.18 + i * 0.15).toFixed(3),
        lon: +(archive[p].lon + 0.28 + i * 0.35).toFixed(3),
        capacity: i ? 8000 : 5000,
        occupied: i ? 4000 : 4100,
        roadKm: i ? 75 : 42,
        rate: i ? 30 : 35,
      })),
    ]),
  ) as Facilities;
}
export const free = (f: Facility) => Math.max(0, f.capacity - f.occupied);
export function scoreDistrict(
  water: number | null,
  plants: number | null,
  km: number,
) {
  if (water === null || plants === null) return null;
  const clamp = (v: number) => Math.max(0, Math.min(100, v));
  return (clamp(water) + clamp(plants) + clamp(km)) / 3;
}
export function nearestWithSpace(
  facilities: Facilities,
  place: Place,
  load: number,
) {
  return Math.min(
    ...facilities[place].filter((f) => free(f) >= load).map((f) => f.roadKm),
  );
}
