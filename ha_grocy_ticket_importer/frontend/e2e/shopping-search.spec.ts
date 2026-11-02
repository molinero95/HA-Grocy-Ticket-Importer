import { expect, test } from "@playwright/test";
test("shopping search fits mobile, filters pending and purchased items and keeps sync details", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 360, height: 850 });
  const item = { amount: "1", unit: "Piece", image_url: null, product_id: null };
  await page.route("**/api/v1/shopping", route => route.fulfill({ json: {
    items: [{ ...item, id: 1, name: "Tomáte triturado", done: true }, { ...item, id: 2, name: "Arroz", done: false }],
    pending_matches: [{ key: "tomate alexa", name: "Tomate Alexa", candidates: [] }],
    shopping_error: false, pending_matches_error: false, sync: { state: "error", reason: "unavailable" },
  } }));
  await page.goto("http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/");
  const search = page.getByRole("searchbox", { name: "Buscar en la lista de la compra" });
  await search.fill("TOMATE");
  await expect(page.locator(".items > article")).toHaveCount(2);
  await expect(page.getByText("2 de 3 artículos", { exact: true })).toBeVisible();
  await expect(page.getByText("Ver detalles de sincronización", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Eliminar comprados/ })).toHaveCount(0);
  const clear = page.getByRole("button", { name: "Borrar búsqueda de compra" });
  expect((await clear.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("shopping-search-mobile.png"), fullPage: true });
  await search.fill("inexistente");
  await expect(page.getByRole("heading", { name: "Sin resultados", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Mostrar toda la compra" }).click();
  await expect(page.locator(".items > article")).toHaveCount(3);
});
