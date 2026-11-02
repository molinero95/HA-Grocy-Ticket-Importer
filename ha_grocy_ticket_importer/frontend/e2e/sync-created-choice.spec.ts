import { expect, test } from "@playwright/test";

test("a worker-rejected association identifies a purchased row instead of claiming no affected article", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 360, height: 850 });
  const item = { amount: "1", unit: "Piece", image_url: null };
  await page.route("**/api/v1/shopping", route => route.fulfill({ json: {
    items: [{ ...item, id: 1, name: "Producto normal", product_id: 8, done: false }, { ...item, id: 2, name: "Producto comprado asociado", product_id: 7, done: true }],
    pending_matches: [], shopping_error: false, pending_matches_error: false,
    sync: { state: "error", reason: "identity_conflict", detail_code: "stale_selection", affected_product_ids: [7] },
  } }));
  await page.goto("http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/");
  await page.getByText("Ver detalles de sincronización", { exact: true }).click();
  const rows = page.locator(".items > article");
  await expect(rows.first()).toContainText("Producto comprado asociado");
  await expect(rows.first()).toHaveClass(/sync-review-item/);
  await expect(page.getByText(/No hay filas concretas identificadas/)).toHaveCount(0);
  await expect(page.getByText("Artículos que necesitan revisión", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("sync-rejected-choice-mobile.png"), fullPage: true });
});
