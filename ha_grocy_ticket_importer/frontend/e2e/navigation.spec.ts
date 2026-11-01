import { expect, test } from "@playwright/test";
const ingress = "http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/";

test("Back closes nested dialogs, returns through sections and leaves the root normally", async ({ page }) => {
  await page.route("**/api/v1/catalog/units", (route) => route.fulfill({ json: { units: [{ id: 2, name: "Piece" }] } }));
  await page.route("**/api/v1/catalog/archived", (route) => route.fulfill({ json: { items: [] } }));
  const host = ingress.replace("/react/", "/basic");
  await page.goto(host);
  await page.goto(ingress);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await page.getByRole("button", { name: "Nuevo producto", exact: true }).click();
  const parent = page.getByRole("dialog", { name: "Crear producto", exact: true });
  await parent.getByRole("button", { name: "Escanear código" }).click();
  await expect(page.getByRole("dialog", { name: "Escáner de códigos de barras" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("dialog", { name: "Escáner de códigos de barras" })).toHaveCount(0);
  await expect(parent).toBeVisible();
  await expect(parent.getByRole("button", { name: "Escanear código" })).toBeFocused();
  await page.goBack();
  await expect(parent).toHaveCount(0);
  await expect(page.locator("body")).not.toHaveCSS("overflow", "hidden");
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page.getByRole("button", { name: "Productos archivados", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Productos archivados" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Acciones", exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Mi despensa", exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Lista de la compra", exact: true })).toBeVisible();
  await expect(page).toHaveURL(ingress);
  await page.goBack();
  await expect(page).toHaveURL(host);
});

test("replacing a create dialog with an existing product adds no empty history step", async ({ page }) => {
  await page.route("**/api/v1/catalog/units", (route) => route.fulfill({ json: { units: [{ id: 2, name: "Piece" }] } }));
  await page.route("**/api/v1/catalog/products", (route) => route.fulfill({ json: { created: false, product_id: 7 } }));
  await page.route("**/api/v1/catalog/products/7", (route) => route.fulfill({ json: { id: 7, name: "Leche", stock_amount: "0", unit_id: 2, purchase_unit_id: 2, image_url: null, is_pack: false, pack_size: 1, barcodes: [], units: [{ id: 2, name: "Piece" }], active: true } }));
  await page.route("**/api/v1/catalog/products/7/barcodes", (route) => route.fulfill({ json: { barcodes: [] } }));
  await page.route("**/api/v1/products/7/variants", (route) => route.fulfill({ json: { product: { id: 7, name: "Leche" }, variants: [] } }));
  await page.goto(ingress);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await page.getByRole("button", { name: "Nuevo producto", exact: true }).click();
  await page.getByLabel("Nombre", { exact: true }).fill("Leche");
  await page.getByLabel("Unidad", { exact: true }).selectOption("2");
  await page.getByRole("button", { name: "Guardar producto", exact: true }).click();
  await page.getByRole("button", { name: "Abrir ficha del producto" }).click();
  await expect(page.getByLabel("Cantidad final", { exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Lista de la compra", exact: true })).toBeVisible();
});

test("manual close removes its Back entry; empty stock has an accessible amber state on mobile", async ({ page }, testInfo) => {
  await page.route("**/api/v1/inventory", (route) => route.fulfill({ json: { items: [
    { id: 1, name: "Crema sin existencias con un nombre largo", amount: "0.00", unit: "Piece", shopping_amount: "2", shopping_step: "1", shopping_unit: "Piece", shopping_can_subtract: true, image_url: null },
    { id: 2, name: "Leche", amount: "3", unit: "Piece", shopping_amount: "0", shopping_step: "1", shopping_unit: "Piece", shopping_can_subtract: false, image_url: null },
  ] } }));
  await page.route("**/api/v1/catalog/units", (route) => route.fulfill({ json: { units: [{ id: 2, name: "Piece" }] } }));
  await page.goto(ingress);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  const empty = page.locator(".inventory-item").filter({ hasText: "Crema sin existencias" });
  await expect(empty.getByText("Sin existencias", { exact: true })).toBeVisible();
  await expect(empty).toHaveCSS("background-color", "rgb(255, 248, 232)");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("pantry-empty-stock.png"), fullPage: true });
  await page.getByRole("button", { name: "Nuevo producto", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  // Wait for the browser's asynchronous traversal caused by manual close.
  await expect.poll(() => page.evaluate(() => history.state?.despensa?.layers.length)).toBe(0);
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Lista de la compra", exact: true })).toBeVisible();
});
