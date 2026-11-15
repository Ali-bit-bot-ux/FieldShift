import { useEffect, useState } from "react";
import { z } from "zod";
import type { Section } from "@/lib/tools";
import { usePlanner } from "../Store";
import { numberText, regionNames } from "@/lib/labels";
import type { Settings } from "@/lib/contract";

const labels = {
  phenomap: [
    "Последний NDVI в архиве",
    "Мұрағаттағы соңғы NDVI",
    "Last archived NDVI",
  ],
  hydrorisk: [
    "Последняя влажность, м³/м³",
    "Соңғы ылғалдылық, м³/м³",
    "Last soil moisture, m³/m³",
  ],
  backtesting: [
    "Первый сигнал при SMAI < −1,5",
    "SMAI < −1,5 кезіндегі алғашқы белгі",
    "First signal at SMAI < −1.5",
  ],
  silogrid: [
    "Свободная ёмкость в учебном сценарии пшеницы, т",
    "Бидайдың үлгі сценарийіндегі бос сыйымдылық, т",
    "Available capacity in the example wheat scenario, t",
  ],
  vulnerability: [
    "Средняя оценка районов в модели, из 100",
    "Модельдегі аудандардың орташа бағасы, 100-ден",
    "Mean modelled district score out of 100",
  ],
  contagion: [
    "Лет с сопоставимыми индексами растений и ценами",
    "Өсімдік индексі мен бағасы бар жылдар",
    "Years with paired vegetation and price records",
  ],
  agroadvisor: [
    "Мер в первые 48 часов по справочнику",
    "Анықтамалық бойынша алғашқы 48 сағаттағы шаралар",
    "Catalogue actions in the first 48 hours",
  ],
} as const;
type Tool = Exclude<Section, "planner">;
function readMetric(tool: Tool, data: unknown): number | string | null {
  switch (tool) {
    case "phenomap":
      return z
        .object({ series: z.array(z.object({ ndvi: z.number() })).nonempty() })
        .parse(data)
        .series.at(-1)!.ndvi;
    case "hydrorisk":
      return z
        .object({ latest: z.object({ soil_moisture: z.number() }) })
        .parse(data).latest.soil_moisture;
    case "backtesting":
      return z.object({ trigger_date: z.string().nullable() }).parse(data)
        .trigger_date;
    case "silogrid":
      return z
        .object({ summary: z.object({ free_capacity_t: z.number() }) })
        .parse(data).summary.free_capacity_t;
    case "vulnerability":
      return z
        .object({ summary: z.object({ average_score: z.number() }) })
        .parse(data).summary.average_score;
    case "contagion":
      return z.object({ scatter: z.array(z.unknown()) }).parse(data).scatter
        .length;
    case "agroadvisor":
      return z
        .object({
          action_roadmap: z.object({ emergency_0_48h: z.array(z.unknown()) }),
        })
        .parse(data).action_roadmap.emergency_0_48h.length;
  }
}
export function RegionalData({
  tool,
  region,
  crop,
  soil,
  stage,
}: {
  tool: Tool;
  region: Settings["region"];
  crop?: string;
  soil?: string;
  stage?: string;
}) {
  const { lang, t, mode } = usePlanner(),
    [attempt, retry] = useState(0);
  const year = tool === "backtesting" ? 2021 : 2026;
  const params = JSON.stringify(
    tool === "agroadvisor"
      ? {
          crop_id: crop,
          soil_id: soil,
          growth_stage: stage,
          lang: lang === "kk" ? "kk" : "ru",
        }
      : tool === "silogrid"
        ? { region, crop_id: "spring_wheat" }
        : ["phenomap", "hydrorisk", "vulnerability"].includes(tool)
          ? { region, year }
          : { region },
  );
  const key = JSON.stringify([tool, params, attempt]);
  const [reply, save] = useState<{
    key: string;
    metric?: number | string | null;
    error?: boolean;
  }>();
  useEffect(() => {
    if (mode !== "api") return;
    const ctrl = new AbortController();
    async function load() {
      try {
        const res = await fetch("/api/fieldshift/tools/" + tool, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: params,
          signal: ctrl.signal,
        });
        if (!res.ok) throw Error("upstream");
        const metric = readMetric(tool, (await res.json()).data);
        if (!ctrl.signal.aborted) save({ key, metric });
      } catch {
        if (!ctrl.signal.aborted) save({ key, error: true });
      }
    }
    void load();
    return () => ctrl.abort();
  }, [mode, key, params, tool]);
  if (mode !== "api") return null;
  const observation =
    tool === "phenomap" ||
    tool === "hydrorisk" ||
    tool === "backtesting" ||
    tool === "vulnerability";
  return (
    <section className="tool-sheet regional-data" aria-live="polite">
      <h2>
        {tool === "agroadvisor"
          ? t(
              "Подбор по справочнику",
              "Анықтамалық бойынша таңдау",
              "Catalogue match",
            )
          : regionNames[region][lang]}
        {observation ? " · " + year : ""}
      </h2>
      <p>{t(labels[tool][0], labels[tool][1], labels[tool][2])}</p>
      {reply?.key !== key ? (
        <small>{t("Загрузка…", "Жүктелуде…", "Loading…")}</small>
      ) : reply.error ? (
        <button onClick={() => retry((a) => a + 1)}>
          {t(
            "Данные недоступны. Повторить",
            "Дерек қолжетімсіз. Қайталау",
            "Data unavailable. Retry",
          )}
        </button>
      ) : (
        <strong>
          {typeof reply.metric === "number"
            ? numberText(reply.metric, lang)
            : (reply.metric ??
              t("Сигнала не было", "Белгі болған жоқ", "No signal"))}
        </strong>
      )}
    </section>
  );
}
