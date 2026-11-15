import { dataMode } from "@/lib/catalog.server";

const paths = new Map(
  Object.entries({
    phenomap: "phenomap",
    hydrorisk: "hydrorisk",
    backtesting: "backtest/2021",
    contagion: "contagion",
    vulnerability: "vulnerability",
    silogrid: "silogrid",
    agroadvisor: "agroadvisor",
  }),
);
export async function POST(
  req: Request,
  { params }: { params: Promise<{ tool: string }> },
) {
  const path = paths.get((await params).tool);
  if (!path || dataMode() !== "api") return new Response(null, { status: 404 });
  const endpoint = process.env.FIELDSHIFT_API_URL;
  if (!endpoint) return new Response(null, { status: 503 });
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body))
    return new Response(null, { status: 400 });
  try {
    const upstream = await fetch(new URL(path, endpoint), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.any([req.signal, AbortSignal.timeout(20000)]),
    });
    if (!upstream.ok) return new Response(null, { status: upstream.status });
    const result = await upstream.json();
    if (result.status !== "success" || !result.data)
      return new Response(null, { status: 502 });
    return Response.json(result, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return new Response(null, { status: 502 });
  }
}
