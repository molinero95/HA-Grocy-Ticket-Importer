import { expect, test } from "@playwright/test";
const base = "http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/";
test("kg stock taps batch into one stock write and shopping quantity is an independent absolute edit", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 360, height: 850 });
  let stock = "0.123", quantity = "0.1", stockWrites = 0, shoppingWrites = 0;
  await page.route("**/api/v1/inventory", route => route.fulfill({ json: { items: [{ id: 7, name: "Tomate pesado", amount: stock, unit: "kg", image_url: null, shopping_amount: quantity, shopping_step: "0.10", shopping_unit: "kg", shopping_can_subtract: true }] } }));
  await page.route("**/api/v1/shopping", route => route.fulfill({ json: { items: [{ id: 4, name: "Tomate pesado", amount: quantity, unit: "kg", done: false, product_id: 7, image_url: null },
    { id: 5, name: "Producto con un nombre mucho más largo", amount: "2", unit: "Piece", done: false, product_id: 8, image_url: "/product-photo.svg" },
    { id: 6, name: "Comprado", amount: "1", unit: "Piece", done: true, product_id: 9, image_url: null }], pending_matches: [], shopping_error: false, pending_matches_error: false } }));
  await page.route("**/product-photo.svg", route => route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40" fill="green"/></svg>' }));
  await page.route("**/api/v1/catalog/products/7/stock", async route => {
    stockWrites++;
    const body = route.request().postDataJSON();
    expect(body.expected_amount).toBe("0.123"); expect(body.step).toBe(true);
    expect(body.operation_id).toMatch(/^[a-f0-9-]{36}$/);
    const before = stock; stock = body.desired_amount;
    await route.fulfill({ json: { before, after: stock } });
  });
  await page.route("**/api/v1/shopping/4/quantity", async route => {
    shoppingWrites++;
    const body = route.request().postDataJSON();
    expect(body.expected_amount).toBe("0.1"); quantity = body.amount;
    await route.fulfill({ json: { id: 4, amount: quantity } });
  });
  await page.goto(base);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  const plus = page.getByRole("button", { name: "Aumentar stock: Tomate pesado" });
  await plus.click(); await plus.click(); await plus.click();
  await expect(page.locator(".quantity")).toContainText("0.423 kg");
  await expect.poll(() => stockWrites).toBe(1);
  await expect(plus).toBeEnabled();
  expect(shoppingWrites).toBe(0);
  await page.screenshot({ path: testInfo.outputPath("pantry-stock-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Lista de la compra", exact: true }).click();
  for (const width of [320, 360, 690]) {
    await page.setViewportSize({ width, height: 850 });
    const actions = page.locator(".items > article .item-actions");
    const boxes = await actions.evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().x));
    expect(Math.max(...boxes) - Math.min(...boxes)).toBeLessThan(1);
    const edit = page.getByRole("button", { name: "Editar cantidad: Tomate pesado" });
    expect((await edit.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    const quantity = page.getByText("0.1 kg", { exact: true });
    expect(Math.abs((await edit.boundingBox())!.x - (await quantity.boundingBox())!.x)).toBeLessThan(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.setViewportSize({ width: 360, height: 850 });
  await page.screenshot({ path: testInfo.outputPath("shopping-edit-link-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Editar cantidad: Tomate pesado" }).click();
  const dialog = page.getByRole("dialog", { name: "Editar cantidad", exact: true });
  await dialog.getByLabel("Cantidad para comprar (kg)").fill("2.75");
  await page.screenshot({ path: testInfo.outputPath("shopping-quantity-mobile.png"), fullPage: true });
  await dialog.getByRole("button", { name: "Guardar cantidad" }).click();
  await expect(page.getByText("2.75 kg", { exact: true })).toBeVisible();
  expect(shoppingWrites).toBe(1); expect(stockWrites).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("active deletion uses a Yes/No modal without typing or an archive action", async ({ page }, testInfo) => {
  let deletes = 0;
  await page.route("**/api/v1/catalog/products/1/deletion", route => route.fulfill({ json: { product_id: 1, name: "Tomate", allowed: true, blockers: [], token: "a".repeat(64), stock_amount: "2", history_count: 4, barcode_count: 1, conversion_count: 0 } }));
  await page.route("**/api/v1/catalog/products/1", async route => {
    if (route.request().method() === "DELETE") { deletes++; expect(route.request().postDataJSON().confirmed).toBe(true); await route.fulfill({ json: { deleted: true } }); }
    else await route.fulfill({ json: { id: 1, name: "Tomate", stock_amount: "2", unit_id: 2, purchase_unit_id: 2, image_url: null, is_pack: false, pack_size: 1, active: true, barcodes: [], units: [{ id: 2, name: "Piece" }] } });
  });
  await page.route("**/api/v1/catalog/products/1/barcodes", route => route.fulfill({ json: { barcodes: [] } }));
  await page.route("**/api/v1/products/1/variants", route => route.fulfill({ json: { product: { id: 1, name: "Tomate" }, variants: [] } }));
  await page.goto(base);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await page.getByRole("button", { name: /Tomate/, exact: false }).filter({ hasNot: page.locator("svg") }).first().click();
  await page.getByRole("button", { name: "Eliminar producto", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Confirmar eliminación", exact: true });
  await expect(dialog.getByText("Existencias: 2. Movimientos: 4.")).toBeVisible();
  await expect(dialog.getByRole("textbox")).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("delete-confirmation-mobile.png"), fullPage: true });
  await dialog.getByRole("button", { name: "No", exact: true }).click(); expect(deletes).toBe(0);
  await page.getByRole("button", { name: "Eliminar producto", exact: true }).click();
  await dialog.getByRole("button", { name: "Sí", exact: true }).click();
  await expect.poll(() => deletes).toBe(1);
});

test("sync details identify review rows and display them first in a different color", async ({ page }, testInfo) => {
  const item = { amount: "1", unit: "Piece", done: false, image_url: null };
  await page.route("**/api/v1/shopping", route => route.fulfill({ json: {
    items: [{ ...item, id: 1, name: "Arroz normal", product_id: 8 }, { ...item, id: 2, name: "Leche entera", product_id: null }],
    pending_matches: [{ key: "leche entera", name: "Leche entera", requires_product: true, candidates: [{ id: 7, name: "Leche entera" }] }],
    shopping_error: false, pending_matches_error: false,
    sync: { state: "error", reason: "note_conflict", detail_code: "note_conflict", checked_at: 1793600000 },
  } }));
  await page.goto(base);
  await page.getByText("Ver detalles de sincronización", { exact: true }).click();
  await expect(page.getByText(/Un artículo guardado como texto coincide/)).toBeVisible();
  const rows = page.locator(".items > article");
  await expect(rows.first()).toContainText("Leche entera");
  await expect(rows.first()).toHaveClass(/sync-review-item/);
  await expect(rows.last()).not.toHaveClass(/sync-review-item/);
  await page.screenshot({ path: testInfo.outputPath("sync-details-mobile.png"), fullPage: true });
});
