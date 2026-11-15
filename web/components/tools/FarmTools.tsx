"use client";
import { useState } from "react";
import { usePlanner } from "../Store";
import {
  sections,
  toolNames,
  byRegion,
  placeNames,
  places,
  type Place,
  type Section,
} from "@/lib/tools";
import {
  assumptionsSchema,
  examples,
  type Facility,
} from "@/lib/farm-scenarios";
import { Observations } from "./Observations";
import { Advisor } from "./Advisor";
import { Logistics, RiskChain, Vulnerability } from "./Scenarios";
const storageKey = "fieldshift.facilities.v1";
function readFacilities() {
  try {
    const raw = localStorage.getItem(storageKey);
    if (raw) {
      const parsed = assumptionsSchema.safeParse(JSON.parse(raw));
      if (parsed.success) return parsed.data;
    }
  } catch {
    /* Private browsing can disable storage. */
  }
  return examples();
}
export default function FarmTools({
  section,
}: {
  section: Exclude<Section, "planner">;
}) {
  const { lang, t, settings } = usePlanner(),
    [place, setPlace] = useState<Place>(byRegion[settings.region]),
    [facilities, setFacilities] = useState(readFacilities);

  function update(p: Place, index: number, f: Facility) {
    const next = {
      ...facilities,
      [p]: facilities[p].map((v, i) => (i === index ? f : v)),
    };
    if (!assumptionsSchema.safeParse(next).success) return;
    setFacilities(next);
    try {
      localStorage.setItem(storageKey, JSON.stringify(next));
    } catch {}
  }
  const props = { place, setPlace, facilities, update };
  return (
    <article className="tool-page">
      <div className="tool-page-heading">
        <div>
          <p>{toolNames[section]}</p>
          <h1>{sections[section][lang]}</h1>
        </div>
        {section !== "agroadvisor" && (
          <label className="tool-input">
            {t("Район наблюдения", "Бақылау ауданы", "Sample district")}
            <select
              value={place}
              onChange={(e) => setPlace(e.target.value as Place)}
            >
              {places.map((p) => (
                <option value={p} key={p}>
                  {placeNames[p][lang]}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {section === "agroadvisor" ? (
        <Advisor />
      ) : section === "silogrid" ? (
        <Logistics {...props} />
      ) : section === "contagion" ? (
        <RiskChain place={place} />
      ) : section === "vulnerability" ? (
        <Vulnerability {...props} />
      ) : (
        <Observations kind={section} place={place} setPlace={setPlace} />
      )}
    </article>
  );
}
