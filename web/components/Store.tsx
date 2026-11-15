"use client";
import {
  createContext,
  useContext,
  useEffect,
  useReducer,
  useRef,
  useState,
  useCallback,
} from "react";
import { z } from "zod";
import {
  checkResult,
  defaults,
  priorityKeys,
  language,
  makePayload,
  settingsSchema,
  strategyIds,
  validSoil,
} from "@/lib/contract";
import type {
  Catalog,
  Settings,
  Result,
  Mode,
  Lang,
  StrategyId,
} from "@/lib/contract";
import { latestRequest } from "@/lib/latest";

type Step = 1 | 2 | 3;
type Tab = "compare" | "years" | "charts" | "explain";
type Saved = { settings: Settings; data: Result; mode: Mode };
type State = {
  hydrated: boolean;
  lang: Lang;
  settings: Settings;
  step: Step;
  tab: Tab;
  selected: StrategyId;
  saved: Saved | null;
  status: "idle" | "scheduled" | "loading" | "error";
  started: boolean;
};
const initial: State = {
  hydrated: false,
  lang: "ru",
  settings: defaults,
  step: 1,
  tab: "compare",
  selected: "recommended",
  saved: null,
  status: "idle",
  started: false,
};
const storageKey = "fieldshift.planner.v1";
const recordSchema = z.object({
  version: z.literal(1),
  lang: language,
  settings: settingsSchema,
  step: z.union([z.literal(1), z.literal(2), z.literal(3)]),
  tab: z.enum(["compare", "years", "charts", "explain"]),
  selected: z.enum(strategyIds),
  saved: z
    .object({
      settings: settingsSchema,
      data: z.unknown(),
      mode: z.enum(["api", "fixture"]),
    })
    .nullable(),
});
function restore(catalog: Catalog, mode: Mode): Partial<State> {
  const raw = localStorage.getItem(storageKey);
  if (!raw) return {};
  const record = recordSchema.parse(JSON.parse(raw));
  const settings = validSoil(record.settings.soil_type, catalog)
    ? { ...record.settings }
    : { ...defaults };
  if (mode === "fixture") settings.duration_years = 4;
  let saved: Saved | null = null;
  if (
    record.saved?.mode === mode &&
    validSoil(record.saved.settings.soil_type, catalog)
  ) {
    try {
      const snapshot = record.saved;
      saved = {
        ...snapshot,
        data: checkResult(
          snapshot.data,
          snapshot.settings.duration_years,
          catalog,
        ),
      };
    } catch {
      /* Restore edits even if an older result no longer validates. */
    }
  }
  return {
    lang: record.lang,
    settings,
    tab: record.tab,
    selected: record.selected,
    saved,
    status:
      mode === "api" && saved && changed(settings, saved.settings)
        ? "scheduled"
        : "idle",
    started: Boolean(saved),
    step: record.step === 3 && !saved ? 2 : record.step,
  };
}
function changed(current: Settings, previous: Settings) {
  return (
    current.region !== previous.region ||
    current.soil_type !== previous.soil_type ||
    current.field_area_ha !== previous.field_area_ha ||
    current.duration_years !== previous.duration_years ||
    priorityKeys.some(
      (key) => current.priorities[key] !== previous.priorities[key],
    )
  );
}
type Action =
  | { type: "patch"; value: Partial<State> }
  | { type: "edit"; value: Partial<Settings>; mode: Mode };
function reducer(state: State, action: Action): State {
  if (action.type === "edit") {
    const settings = { ...state.settings, ...action.value };
    const needsCalculation =
      action.mode === "api" &&
      state.started &&
      (!state.saved || changed(settings, state.saved.settings));
    return {
      ...state,
      settings,
      status: needsCalculation ? "scheduled" : "idle",
    };
  }
  return { ...state, ...action.value };
}
type Context = State & {
  mode: Mode;
  catalog: Catalog;
  stale: boolean;
  t: (ru: string, kk: string, en: string) => string;
  edit: (delta: Partial<Settings>) => void;
  navigate: (step: Step) => void;
  choose: (id: StrategyId) => void;
  switchTab: (tab: Tab) => void;
  switchLang: (lang: Lang) => void;
  generate: () => void;
};
const PlannerContext = createContext<Context | null>(null);
export function usePlanner() {
  const context = useContext(PlannerContext);
  if (!context) throw Error("PlannerProvider missing");
  return context;
}
export function PlannerProvider({
  catalog,
  mode,
  children,
}: {
  catalog: Catalog;
  mode: Mode;
  children: React.ReactNode;
}) {
  const [state, dispatch] = useReducer(reducer, initial);
  const [requests] = useState(latestRequest);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancel = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    requests.cancel();
  }, [requests]);
  useEffect(() => {
    let restored: Partial<State> = {};
    try {
      restored = restore(catalog, mode);
    } catch {
      /* Storage can be unavailable. */
    }
    dispatch({ type: "patch", value: { ...restored, hydrated: true } });
    return cancel;
  }, [catalog, mode, cancel]);
  useEffect(() => {
    document.documentElement.lang = state.lang;
  }, [state.lang]);
  const { hydrated, lang, settings, tab, selected, step, saved } = state;
  useEffect(() => {
    if (!hydrated) return;
    let pending = true;
    function flush() {
      if (!pending) return;
      pending = false;
      if (!settingsSchema.safeParse(settings).success) return;
      try {
        localStorage.setItem(
          storageKey,
          JSON.stringify({
            version: 1,
            lang,
            settings,
            tab,
            selected,
            step,
            saved,
          }),
        );
      } catch {
        /* Private browsing may disable storage. */
      }
    }
    const timeout = setTimeout(flush, 180);
    window.addEventListener("pagehide", flush);
    return () => {
      clearTimeout(timeout);
      window.removeEventListener("pagehide", flush);
    };
  }, [hydrated, lang, settings, tab, selected, step, saved]);

  const run = useCallback(
    async (settings: Settings) => {
      const ticket = requests.begin();
      dispatch({ type: "patch", value: { status: "loading", started: true } });
      try {
        const res = await fetch("/api/fieldshift/recommendation", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(makePayload(settings)),
          signal: ticket.signal,
        });
        if (!res.ok || res.headers.get("X-FieldShift-Mode") !== mode)
          throw Error("recommendation");
        const data = checkResult(
          await res.json(),
          settings.duration_years,
          catalog,
        );
        if (ticket.isCurrent())
          dispatch({
            type: "patch",
            value: { saved: { data, mode, settings }, status: "idle" },
          });
      } catch {
        if (ticket.isCurrent())
          dispatch({ type: "patch", value: { status: "error" } });
      }
    },
    [requests, catalog, mode],
  );
  const stale = Boolean(
    state.saved && changed(state.settings, state.saved.settings),
  );
  useEffect(() => {
    if (
      state.status !== "scheduled" ||
      !settingsSchema.safeParse(state.settings).success
    )
      return;
    const id = setTimeout(() => {
      void run(state.settings);
    }, 600);
    timer.current = id;
    return () => clearTimeout(id);
  }, [state.status, state.settings, run]);
  function edit(delta: Partial<Settings>) {
    cancel();
    dispatch({ type: "edit", value: delta, mode });
  }
  function generate() {
    if (!settingsSchema.safeParse(state.settings).success) return;
    dispatch({ type: "patch", value: { step: 3 } });
    if (state.status === "loading") return;
    if (!state.saved || state.status === "error" || (mode === "api" && stale)) {
      cancel();
      void run(state.settings);
    }
  }
  const value: Context = {
    ...state,
    mode,
    catalog,
    stale,
    edit,
    generate,
    t: (ru, kk, en) =>
      state.lang === "ru" ? ru : state.lang === "kk" ? kk : en,
    navigate: (step) => dispatch({ type: "patch", value: { step } }),
    choose: (selected) => dispatch({ type: "patch", value: { selected } }),
    switchTab: (tab) => dispatch({ type: "patch", value: { tab } }),
    switchLang: (lang) => dispatch({ type: "patch", value: { lang } }),
  };
  return (
    <PlannerContext.Provider value={value}>{children}</PlannerContext.Provider>
  );
}
