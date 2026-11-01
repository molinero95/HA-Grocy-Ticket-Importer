import { expect, test } from "@playwright/test";

for (const width of [360, 768]) {
  test(`pantry status filter combines with search and fits ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 850 });
    const base = { unit: "ud.", image_url: null, shopping_unit: "ud.", shopping_step: "1", shopping_can_subtract: true };
    await page.route("**/api/v1/inventory", route => route.fulfill({ json: { items: [
      { ...base, id: 1, name: "Leche entera", amount: "2", stock_threshold: "2", shopping_amount: "0" },
      { ...base, id: 2, name: "Arroz", amount: "4", shopping_amount: "1" },
      { ...base, id: 3, name: "Sal", amount: "0", stock_warning_enabled: false, shopping_amount: "0" },
    ] } }));
    await page.goto("http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/");
    await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
    const filter = page.getByRole("combobox", { name: "Filtrar productos" });
    await expect(page.locator("article")).toHaveCount(3);
    const box = await filter.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(box!.width).toBeGreaterThanOrEqual(44);
    await filter.selectOption("low-stock");
    await expect(page.locator("article")).toHaveCount(1);
    await expect(page.locator("article")).toContainText("Leche entera");
    await page.screenshot({ path: testInfo.outputPath(`pantry-filter-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await filter.selectOption("shopping");
    await expect(page.locator("article")).toContainText("Arroz");
    await page.getByRole("textbox", { name: "Buscar por nombre o código de barras" }).fill("leche");
    await expect(page.getByText("Sin resultados", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Quitar filtro" }).click();
    await expect(page.locator("article")).toContainText("Leche entera");
    await expect(filter).toHaveValue("all");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });
}
