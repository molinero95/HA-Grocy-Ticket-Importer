import { expect, test } from "@playwright/test";

const base = "http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/";
test("name-only AI discovery shows sources and requires a choice before creation and photo saving", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 360, height: 850 });
  let searches = 0, creations = 0, photos = 0;
  const code = "4006000082295";
  const candidate = {
    barcode: code, name: "Crema Example 100 ml",
    image_url: "https://images.openbeautyfacts.org/disposable-example.png",
    source_url: "https://world.openbeautyfacts.org/product/" + code,
    search_source_url: "https://es.openbeautyfacts.org/product/" + code + "/example",
    attribution: "Datos: Open Beauty Facts",
  };
  await page.route("https://images.openbeautyfacts.org/disposable-example.png", route => route.fulfill({ contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j0fYAAAAASUVORK5CYII=", "base64") }));
  await page.route("**/api/v1/catalog/units", route => route.fulfill({ json: { units: [{ id: 2, name: "Piece" }] } }));
  await page.route("**/api/v1/photos/discover", async route => {
    searches++;
    expect(route.request().postDataJSON()).toEqual({ name: "Crema Example 100 ml", barcode: "", consent: true });
    await route.fulfill({ json: { candidates: [candidate], advisory: true } });
  });
  await page.route("**/api/v1/photos/" + code, route => route.fulfill({ json: { photo: candidate } }));
  await page.route("**/api/v1/catalog/products", async route => {
    creations++;
    expect(route.request().postDataJSON()).toMatchObject({ name: "Crema Example 100 ml", barcode: code, initial_stock: "0" });
    await route.fulfill({ json: { created: true, product_id: 74 } });
  });
  await page.route("**/api/v1/catalog/products/74/photo-lookup", async route => {
    photos++;
    expect(route.request().postDataJSON()).toEqual({ barcode: code });
    await route.fulfill({ json: { saved: true, image_url: candidate.image_url } });
  });
  await page.goto(base);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await page.getByRole("button", { name: "Nuevo producto", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Crear producto" });
  await dialog.getByLabel("Nombre", { exact: true }).fill("Crema Example 100 ml");
  expect(searches).toBe(0);
  await dialog.getByRole("button", { name: "Buscar imagen y código con IA" }).click();
  await expect(dialog.getByRole("link", { name: "Ver fuente de la búsqueda" })).toHaveAttribute("href", candidate.search_source_url);
  await expect(dialog.getByLabel("Código de barras (opcional)")).toHaveValue("");
  expect(creations).toBe(0);
  expect(photos).toBe(0);
  const choose = dialog.getByRole("button", { name: "Usar código e imagen" });
  expect((await choose.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await choose.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("product-discovery-mobile.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await choose.click();
  await expect(dialog.getByLabel("Código de barras (opcional)")).toHaveValue(code);
  await dialog.getByLabel("Unidad", { exact: true }).selectOption("2");
  await dialog.getByRole("button", { name: "Guardar producto" }).click();
  await expect(dialog.getByText("Producto creado correctamente")).toBeVisible();
  expect(searches).toBe(1);
  expect(creations).toBe(1);
  expect(photos).toBe(1);
});
