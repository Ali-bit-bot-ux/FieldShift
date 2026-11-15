import { expect, test, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const sections = [
  "phenomap",
  "hydrorisk",
  "backtesting",
  "silogrid",
  "contagion",
  "vulnerability",
  "agroadvisor",
];
async function openTool(page: Page, key: string) {
  await page.locator(".tool-nav summary").click();
  await page.locator('.tool-menu a[href="#' + key + '"]').click();
  await expect(page.locator(".tool-page h1")).toBeVisible();
  await expect(
    page.locator('.tool-nav a[aria-current="page"]'),
  ).toHaveAttribute("href", "#" + key);
}
async function english(page: Page, selector = "main") {
  const text = await page.locator(selector).innerText();
  expect(text.match(/.{0,25}[\u0400-\u052f].{0,25}/g)).toBeNull();
}
async function fits(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    ),
  ).toBeLessThanOrEqual(1);
}
test("English wizard, help, every strategy, chart and print", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await english(page);
  await page.getByRole("button", { name: "Help", exact: true }).click();
  await english(page, "dialog");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /Next.*priorities/ }).click();
  await english(page);
  await page.getByRole("button", { name: "View example" }).click();
  await expect(page.locator(".strategy")).toHaveCount(3);
  await english(page);
  for (const strategy of [
    "recommended",
    "soil_resilience",
    "traditional_risk",
  ]) {
    for (const [i, tab] of (await page.getByRole("tab").all()).entries()) {
      await tab.click();
      if (i !== 0)
        await page.locator(".strategy-picker select").selectOption(strategy);
      if (i === 2)
        await expect(
          page.locator(".chart-canvas .main-svg").first(),
        ).toBeVisible();
      await english(page);
    }
    await page.emulateMedia({ media: "print" });
    await english(page, ".print-plan");
    await page.emulateMedia({ media: "screen" });
  }
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator(".strategy-picker select")).toHaveValue(
    "traditional_risk",
  );
});
for (const width of [390, 768, 1440]) {
  test("Archive, risk and farm tools at " + width + "px", async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.route("**/*", (r) =>
      new URL(r.request().url()).hostname === "127.0.0.1"
        ? r.continue()
        : r.abort(),
    );
    await page.goto("/");
    await page.getByRole("button", { name: "EN", exact: true }).click();
    for (const key of sections) {
      await openTool(page, key);
      await fits(page);
      await english(page);
      if (["phenomap", "hydrorisk", "backtesting"].includes(key)) {
        await page.getByLabel("Sample district").selectOption("esil");
        await page.locator(".field-series summary").click();
        await expect(page.locator(".reading-scroll tbody tr")).toHaveCount(
          key === "phenomap" ? 7 : 113,
        );
        await page.locator(".field-series summary").click();
        if (key === "backtesting") {
          await page.getByRole("slider").press("Home");
          await expect(page.locator(".tool-reading")).toHaveText(
            "No threshold crossing in this period",
          );
          await page.getByRole("slider").press("End");
          await expect(page.locator(".tool-reading")).toContainText("May 25");
        }
      }
      if (key === "silogrid") {
        await page.getByLabel("Shipment weight, t").fill("50000");
        await expect(page.getByText("Insufficient capacity")).toHaveCount(2);
        await page.getByLabel("Name", { exact: true }).fill("North store");
        await page.reload();
        await expect(page.getByLabel("Sample district")).toBeVisible();
        await page.getByLabel("Sample district").selectOption("esil");
        await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
          "North store",
        );
      }
      if (key === "contagion") {
        const chart = page.locator(".sensitivity");
        await expect(chart.getByRole("meter")).toHaveCount(5);
        await page.getByLabel("Sale price, ₸/t").fill("0");
        await expect(chart.locator("strong").first()).toHaveText("0 ₸");
      }
      if (key === "vulnerability") {
        await expect(page.locator(".district-rank li")).toHaveCount(4);
      }
      if (key === "agroadvisor") {
        await page
          .getByRole("combobox", { name: "Crop", exact: true })
          .selectOption("chickpea");
        await page.getByLabel("Growth stage").selectOption("0");
        await expect(page.locator(".advice-columns")).toContainText(
          "Water-sensitive stage",
        );
      }
      if (
        process.env.FIELDSHIFT_QA_DIR &&
        ["phenomap", "silogrid", "contagion"].includes(key)
      ) {
        await mkdir(process.env.FIELDSHIFT_QA_DIR, { recursive: true });
        await page.screenshot({
          path:
            process.env.FIELDSHIFT_QA_DIR + "/" + key + "-" + width + ".png",
          fullPage: true,
        });
      }
    }
    await page.goBack();
    await expect(page.locator(".tool-page-heading")).toContainText(
      "Vulnerability",
    );
    await page.getByRole("button", { name: "ҚАЗ", exact: true }).click();
    await expect(page.locator(".tool-page h1")).toHaveText(
      "Аудандардың осалдығы",
    );
    await page.locator('a[href="#planner"]').click();
    await expect(page.locator("#soil")).toBeVisible();
    await fits(page);
    expect(errors).toEqual([]);
  });
}
