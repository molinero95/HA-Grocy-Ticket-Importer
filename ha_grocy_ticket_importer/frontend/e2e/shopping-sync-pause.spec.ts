import { expect, test } from "@playwright/test";

test("automatic sync pause shows the next attempt while shopping remains usable on mobile", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 360, height: 850 });
  let done = false;
  let writes = 0;
  let forced = false;
  let attempts = 0;
  await page.route("**/api/v1/shopping", route => route.fulfill({ json: {
    items: [{ id: 71, product_id: null, name: "Leche para casa", amount: 2, unit: "Piece", image_url: null, done }],
    pending_matches: [], shopping_error: false, pending_matches_error: false,
    sync: forced ? { state: "ok" } : { state: "error", reason: "unavailable", paused: true,
      next_retry_at: Math.floor(Date.now() / 1000) - 86400, retry_after_seconds: 1800, consecutive_failures: 5 },
  } }));
  await page.route("**/api/v1/shopping/71/toggle", async route => {
    writes++; done = route.request().postDataJSON().done;
    await route.fulfill({ json: { ok: true } });
  });
  await page.route("**/api/v1/shopping/sync", async route => {
    attempts++;
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers()["x-csrf-token"]).toBeTruthy();
    expect(route.request().postDataJSON().operation_id).toMatch(/^[a-f0-9-]{36}$/);
    forced = true;
    await route.fulfill({ json: { ok: true } });
  });
  await page.goto("http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/");
  await expect(page.getByText(/Sincronización con Alexa en pausa automática/)).toBeVisible();
  await expect(page.getByText(/Reintentará en 30 min/)).toBeVisible();
  await expect(page.getByText(/Próximo intento:/)).toHaveCount(0);
  await page.getByText("Ver detalles de sincronización", { exact: true }).click();
  await expect(page.getByText(/Alexa Devices mantiene sus propias actualizaciones/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("shopping-sync-pause-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "✓ Comprado", exact: true }).click();
  await expect(page.getByRole("button", { name: "↩ Pendiente", exact: true })).toBeVisible();
  expect(writes).toBe(1);
  await expect(page.getByText(/Sincronización con Alexa en pausa automática/)).toBeVisible();
  await page.getByRole("button", { name: "Forzar sincronización", exact: true }).click();
  await expect(page.getByText(/Sincronización con Alexa en pausa automática/)).toHaveCount(0);
  expect(attempts).toBe(1);
});
