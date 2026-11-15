import { afterEach, expect, it, vi } from "vitest";
import fixture from "../../docs/features/fieldshift/fixtures/contract_response.json";
import { recommend } from "../lib/adapter";
import { defaults, makePayload } from "../lib/contract";
import { latestRequest } from "../lib/latest";
const payload = makePayload(defaults);
const post = (body: unknown) =>
  new Request("http://localhost/api/fieldshift/recommendation", {
    method: "POST",
    body: JSON.stringify(body),
  });
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

it("serves only a four-year unchanged example and checks incoming soil IDs", async () => {
  vi.stubEnv("FIELDSHIFT_DATA_MODE", "fixture");
  expect(await (await recommend(post(payload))).json()).toEqual(fixture);
  expect(
    (await recommend(post({ ...payload, duration_years: 3 }))).status,
  ).toBe(422);
  expect(
    (await recommend(post({ ...payload, soil_type: "other" }))).status,
  ).toBe(400);
});
it("returns an API failure without serving the example", async () => {
  vi.stubEnv("FIELDSHIFT_DATA_MODE", "api");
  vi.stubEnv("FIELDSHIFT_API_URL", "http://python/plan");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
  const response = await recommend(post(payload));
  expect(response.status).toBe(502);
  expect(await response.json()).toEqual({ error: "service_unavailable" });
});
it("proxies canonical JSON and rejects the wrong horizon from upstream", async () => {
  vi.stubEnv("FIELDSHIFT_DATA_MODE", "api");
  vi.stubEnv("FIELDSHIFT_API_URL", "http://python/plan");
  const upstream = vi.fn(async () => Response.json(fixture));
  vi.stubGlobal("fetch", upstream);
  const response = await recommend(post(payload));
  expect(await response.json()).toEqual(fixture);
  expect(response.headers.get("X-FieldShift-Mode")).toBe("api");
  expect(upstream).toHaveBeenCalledWith(
    "http://python/plan",
    expect.objectContaining({ body: JSON.stringify(payload) }),
  );
  expect(
    (await recommend(post({ ...payload, duration_years: 3 }))).status,
  ).toBe(502);
});
it("ignores out-of-order adapter responses even if transport ignores cancellation", async () => {
  vi.stubEnv("FIELDSHIFT_DATA_MODE", "api");
  vi.stubEnv("FIELDSHIFT_API_URL", "http://python/plan");
  const oldResponse = Promise.withResolvers<Response>();
  const current = structuredClone(fixture);
  current.strategies[0].summary_score = 75;
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockReturnValueOnce(oldResponse.promise)
      .mockResolvedValueOnce(Response.json(current)),
  );
  const requests = latestRequest(),
    accepted: number[] = [];
  async function submit() {
    const ticket = requests.begin();
    const response = await recommend(post(payload));
    const body = await response.json();
    if (ticket.isCurrent()) accepted.push(body.strategies[0].summary_score);
  }
  const first = submit();
  await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  await submit();
  oldResponse.resolve(Response.json(fixture));
  await first;
  expect(accepted).toEqual([75]);
});
