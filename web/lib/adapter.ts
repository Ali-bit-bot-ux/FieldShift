import { checkResult, payloadSchema, validSoil } from "./contract";
import { catalog, dataMode } from "./catalog.server";

export async function recommend(request: Request): Promise<Response> {
  const input = payloadSchema.safeParse(await request.json().catch(() => null));
  if (!input.success || !validSoil(input.data.soil_type, catalog)) {
    return Response.json({ error: "invalid_field" }, { status: 400 });
  }
  const payload = input.data;
  const mode = dataMode();
  let raw: unknown;
  if (mode === "fixture") {
    if (payload.duration_years !== 4)
      return Response.json({ error: "fixture_horizon" }, { status: 422 });
    raw = (
      await import("../../docs/features/fieldshift/fixtures/contract_response.json")
    ).default;
  } else {
    const url = process.env.FIELDSHIFT_API_URL;
    if (!url)
      return Response.json({ error: "api_unconfigured" }, { status: 503 });
    try {
      const upstream = await fetch(url, {
        method: "POST",
        body: JSON.stringify(payload),
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(20_000)]),
      });
      if (!upstream.ok) throw Error("upstream");
      raw = await upstream.json();
    } catch {
      return Response.json({ error: "service_unavailable" }, { status: 502 });
    }
  }
  try {
    return Response.json(checkResult(raw, payload.duration_years, catalog), {
      headers: { "Cache-Control": "no-store", "X-FieldShift-Mode": mode },
    });
  } catch {
    return Response.json({ error: "invalid_response" }, { status: 502 });
  }
}
