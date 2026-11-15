import { test, expect } from "@playwright/test";
import fixture from "../../../docs/features/fieldshift/fixtures/contract_response.json";
import { mkdir } from "node:fs/promises";

for (const width of [390, 768, 1440]) {
  test(`farmer flow at ${width}px, offline assets, languages and print`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 950 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const external: string[] = [],
      errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    page.on("console", (message) => {
      if (message.type() === "error" && /hydrat/i.test(message.text()))
        errors.push(message.text());
    });
    await page.route("**/*", (route) => {
      if (new URL(route.request().url()).hostname !== "127.0.0.1") {
        external.push(route.request().url());
        return route.abort();
      }
      return route.continue();
    });
    await page.goto("/");
    const area = page.getByRole("spinbutton");
    await expect(area).toHaveValue("400");
    await expect(page.locator("#soil option")).toHaveCount(7);
    await expect(page.getByRole("button", { name: "3 года" })).toBeDisabled();
    await page.evaluate(() => document.fonts.ready);
    const screenshots = process.env.FIELDSHIFT_QA_DIR;
    if (screenshots) {
      await mkdir(screenshots, { recursive: true });
      await page.screenshot({
        path: screenshots + `/field-${width}.png`,
        fullPage: true,
      });
    }
    await page.getByRole("button", { name: "Как выбрать" }).click();
    await expect(page.locator("#soil-help")).toBeVisible();
    await page.getByRole("button", { name: "Помощь", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await area.fill("50001");
    await expect(page.getByRole("button", { name: /Далее/ })).toBeDisabled();
    await area.fill("120");
    await page.getByRole("button", { name: /Далее/ }).click();
    await page
      .getByRole("button", { name: "Сохранить влагу", exact: true })
      .click();
    await expect(page.locator("#water_saving")).toHaveValue("50");
    for (const slider of await page.getByRole("slider").all()) {
      await slider.focus();
      await slider.press("Home");
    }
    await expect(page.getByText(/Каждому приоритету/)).toBeVisible();
    await page.getByRole("button", { name: "Посмотреть пример" }).click();
    await expect(page.locator(".strategy")).toHaveCount(3);
    const comparison = page.getByRole("region", {
      name: "Что меняется по годам",
    });
    await expect(
      comparison.getByRole("button", { name: "Год 2" }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(comparison).toContainText("На 140 мм меньше");
    await comparison.getByRole("button", { name: "Год 1" }).click();
    await expect(comparison).toContainText("Одинаковая потребность в воде");
    await comparison.getByRole("combobox").selectOption("traditional_risk");
    await comparison.getByRole("button", { name: "Год 2" }).click();
    await expect(comparison).toContainText("На 140 мм больше");
    await page
      .locator(".strategy")
      .nth(1)
      .getByRole("button", { name: "Выбрать план" })
      .click();
    await page.getByRole("tab", { name: "Сравнение" }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.locator("#result-panel .timeline li")).toHaveCount(4);
    await page.getByRole("button", { name: "ҚАЗ", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "kk");
    await page.getByRole("tab", { name: "Су мен топырақ" }).click();
    await expect(page.locator(".js-plotly-plot")).toHaveCount(2);
    await page.getByText("Мәндер кестесін ашу").click();
    await expect(page.locator("tbody tr")).toHaveCount(4);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    if (screenshots)
      await page.screenshot({
        path: screenshots + `/charts-${width}.png`,
        fullPage: true,
      });
    await page.getByRole("tab", { name: "Жоспардың негізі" }).click();
    await expect(page.locator(".explanation")).toContainText("SMAP");
    await expect(page.locator(".explanation")).toContainText("25%");
    await page.reload();
    await expect(page.getByRole("tab", { selected: true })).toHaveText(
      "Жоспардың негізі",
    );
    await page
      .getByRole("button", { name: "Параметрлер", exact: true })
      .click();
    await expect(area).toHaveValue("120");
    await area.fill("250");
    await page.getByRole("button", { name: /Нәтижелер/ }).click();
    await expect(page.locator(".notice").last()).toContainText(
      "Параметрлер өзгерді",
    );
    await expect(page.locator(".strategy-picker select")).toHaveValue(
      "soil_resilience",
    );
    await page.evaluate(() => {
      window.print = () => {
        document.body.dataset.printInvoked = "yes";
      };
    });
    await page.getByRole("button", { name: "Жоспарды басып шығару" }).click();
    await expect(page.locator("body")).toHaveAttribute(
      "data-print-invoked",
      "yes",
    );
    await page.emulateMedia({ media: "print" });
    await expect(page.locator(".screen")).toBeHidden();
    await expect(page.locator(".print-plan")).toBeVisible();
    await expect(page.locator(".print-plan")).toContainText(
      "Демонстрациялық мысал",
    );
    await expect(page.locator(".print-charts section")).toHaveCount(2);
    await expect(page.locator(".print-plan .timeline li")).toHaveCount(4);
    const pdf = await page.pdf({
      format: "A4",
      printBackground: true,
      path: screenshots ? screenshots + `/print-${width}.pdf` : undefined,
    });
    expect(pdf.length).toBeGreaterThan(10_000);
    expect(external).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test("API mode debounces field edits, keeps the previous plan on failure, retries and supports three years", async ({
  page,
}) => {
  const requests: number[] = [];
  let fail = false;
  await page.route("**/api/fieldshift/recommendation", async (route) => {
    const p = route.request().postDataJSON();
    requests.push(p.field_area_ha);
    if (fail)
      return route.fulfill({
        status: 502,
        json: { error: "service_unavailable" },
      });
    const data = structuredClone(fixture);
    for (const s of data.strategies)
      s.rotation_years = s.rotation_years.slice(0, p.duration_years);
    data.strategies[0].summary_score = p.field_area_ha / 10;
    await route.fulfill({
      headers: { "X-FieldShift-Mode": "api" },
      json: data,
    });
  });
  await page.goto("http://127.0.0.1:3102");
  await page.getByRole("button", { name: "3 года" }).click();
  await page.getByRole("button", { name: /Далее/ }).click();
  expect(requests).toEqual([]);
  await page.getByRole("button", { name: "Получить план" }).click();
  await expect(page.locator(".strategy").first()).toContainText("40");
  await expect(
    page.locator(".crop-sequence").first().locator("li"),
  ).toHaveCount(3);
  await expect(
    page.getByRole("group", { name: "Год сравнения" }).getByRole("button"),
  ).toHaveCount(3);
  await page.getByRole("button", { name: "Параметры", exact: true }).click();
  fail = true;
  await page.getByRole("spinbutton").fill("50");
  await page.getByRole("spinbutton").fill("550");
  await page.getByRole("button", { name: /Результаты/ }).click();
  await expect(page.locator(".results").getByRole("alert")).toBeVisible();
  expect(requests).toEqual([400, 550]);
  await expect(page.locator(".strategy").first()).toContainText("40");
  fail = false;
  await page.getByRole("button", { name: "Повторить" }).click();
  await expect(
    page.locator(".strategy").first().locator(".stats dd").first(),
  ).toHaveText("55");
  await expect(page.locator(".results").getByRole("alert")).toHaveCount(0);
});
