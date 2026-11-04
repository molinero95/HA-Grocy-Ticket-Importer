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
    attribution: "Datos: Open Beauty Facts", discovery_token: "signed-candidate",
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
  await page.route("**/api/v1/catalog/products/74/photo-discovery", async route => {
    photos++;
    expect(route.request().postDataJSON()).toEqual({ token: "signed-candidate" });
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

test("provider quota failure explains the cause and preserves the session and manual product form", async ({ page }, info) => {
  let searches = 0, writes = 0;
  await page.route("**/api/v1/catalog/units", route => route.fulfill({ json: { units: [{ id: 2, name: "Piece" }] } }));
  await page.route("**/api/v1/photos/discover", async route => {
    searches++;
    await route.fulfill({ status: 503, json: { code: "ai_quota_exceeded", error: "OpenAI indica que no queda cuota o saldo disponible. Revisa la facturación y los límites del proyecto de la API." } });
  });
  await page.route("**/api/v1/catalog/products", async route => { writes++;await route.fulfill({ status: 500, json: { error: "Unexpected mutation" } }); });
  await page.goto(base);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await page.getByRole("button", { name: "Nuevo producto", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Crear producto" });
  await dialog.getByLabel("Nombre", { exact: true }).fill("Crema Example 100 ml");
  await dialog.getByRole("button", { name: "Buscar imagen y código con IA" }).dblclick();
  await expect(dialog.getByRole("alert")).toContainText("no queda cuota o saldo");
  await expect(dialog.getByRole("alert")).toContainText("Puedes continuar sin imagen");
  await expect(dialog.getByLabel("Nombre", { exact: true })).toHaveValue("Crema Example 100 ml");
  await expect(page.getByRole("navigation", { name: "Secciones" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Guardar producto", exact: true })).toBeEnabled();
  expect(searches).toBe(1);expect(writes).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("ai-search-quota-mobile.png"), fullPage: true });
});

test("generic garlic photo uses no AI or barcode and retains source/license after selection", async ({ page }, info) => {
  let image: string | null = null, searches = 0, saves = 0;
  const url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Garlic.jpg/480px-Garlic.jpg";
  const source = "https://commons.wikimedia.org/?curid=123";
  const credit = { image_url: url, artist: "Example photographer", license: "CC BY-SA 4.0", license_url: "https://creativecommons.org/licenses/by-sa/4.0/", source_url: source };
  await page.route(url, route => route.fulfill({ contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j0fYAAAAASUVORK5CYII=", "base64") }));
  await page.route("**/api/v1/catalog/products/1", route => {
    expect(route.request().method()).toBe("GET");
    return route.fulfill({ json: { id: 1, name: "ajo", stock_amount: "2", unit_id: 2, purchase_unit_id: 2, image_url: image, photo_credit: image ? credit : null, is_pack: false, pack_size: 1, active: true, barcodes: [], units: [{ id: 2, name: "Piece" }] } });
  });
  await page.route("**/api/v1/catalog/products/1/barcodes", route => { expect(route.request().method()).toBe("GET"); return route.fulfill({ json: { barcodes: [] } }); });
  await page.route("**/api/v1/products/1/variants", route => route.fulfill({ json: { product: { id: 1, name: "ajo" }, variants: [] } }));
  await page.route("**/api/v1/photos/discover", () => { throw new Error("Generic search must never call AI"); });
  await page.route("**/api/v1/photos/generic", route => {
    searches++; expect(route.request().postDataJSON()).toEqual({ name: "ajo", product_id: 1 });
    return route.fulfill({ json: { advisory: true, candidates: [{ kind: "generic", file_id: 123, name: "Garlic bulbs", barcode: "", image_url: url, source_url: source, search_source_url: source, attribution: "Wikimedia Commons · CC BY-SA 4.0 · Example photographer", discovery_token: "generic-signed" }] } });
  });
  await page.route("**/api/v1/catalog/products/1/photo-discovery", route => {
    saves++; expect(route.request().postDataJSON()).toEqual({ token: "generic-signed", replace: false }); image = url;
    return route.fulfill({ json: { saved: true, image_url: image } });
  });
  await page.goto(base);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await page.locator(".product-name").first().click();
  await page.getByRole("button", { name: "Buscar foto genérica", exact: true }).click();
  await expect(page.getByText("Foto genérica · Sin código de barras", { exact: true })).toBeVisible();
  expect(saves).toBe(0);
  await page.getByRole("button", { name: "Usar esta foto", exact: true }).click();
  await expect(page.getByRole("img", { name: "Fotografía de ajo" })).toHaveAttribute("src", url);
  await expect(page.getByRole("link", { name: "Fuente de la fotografía" })).toHaveAttribute("href", source);
  await expect(page.getByRole("link", { name: "CC BY-SA 4.0", exact: true })).toBeVisible();
  await expect(page.getByLabel("Cantidad final", { exact: true })).toHaveValue("2");
  expect(searches).toBe(1); expect(saves).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("generic-garlic-photo-mobile.png"), fullPage: true });
});
