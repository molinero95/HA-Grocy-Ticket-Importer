import { expect, test } from "@playwright/test";
const base = "http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/";

test("alias selectors search both columns, save atomically and delete only an alias", async ({ page }, testInfo) => {
  let aliases = [{ key: "leche", name: "Leche", product_id: 7 }, { key: "rojo", name: "Rojo", product_id: 8 }];
  let edits = 0, deletes = 0;
  await page.route("**/api/v1/inventory", route => route.fulfill({ json: { items: [{ id: 7, name: "Leche entera" }, { id: 8, name: "Tomáte triturado de nombre largo" }] } }));
  await page.route("**/api/v1/alexa/aliases", route => route.fulfill({ json: { aliases, suggestions: ["Leche normal", "Pan"] } }));
  await page.route("**/api/v1/alexa/aliases/leche*", async route => {
    const body = route.request().postDataJSON();
    if (route.request().method() === "DELETE") {
      deletes++; expect(body.product_id).toBe(8); aliases = aliases.filter(alias => alias.key !== "leche normal");
      await route.fulfill({ json: { ok: true } });
    } else {
      edits++; expect(body).toEqual({ name: "Leche normal", product_id: 8, expected_name: "Leche", expected_product_id: 7 });
      aliases = aliases.map(alias => alias.key === "leche" ? { key: "leche normal", name: body.name, product_id: body.product_id } : alias);
      await route.fulfill({ json: { alias: aliases[0] } });
    }
  });
  await page.goto(base);
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page.getByRole("button", { name: /Administrar alias de Alexa/ }).click();
  await expect(page.getByRole("table")).toBeVisible();
  for (const width of [320, 390, 900]) {
    await page.setViewportSize({ width, height: 850 });
    const alias = await page.getByLabel("Alias: Leche", { exact: true }).boundingBox();
    const product = await page.getByLabel("Producto para Leche", { exact: true }).boundingBox();
    expect(alias!.x + alias!.width).toBeLessThan(product!.x);
    expect(Math.abs(alias!.y - product!.y)).toBeLessThan(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.setViewportSize({ width: 390, height: 850 });
  const search = page.getByRole("searchbox", { name: "Buscar alias o producto" });
  await search.fill("TOMATE");
  await expect(page.getByLabel("Alias: Leche", { exact: true })).toBeHidden();
  await expect(page.getByLabel("Alias: Rojo", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Borrar búsqueda de alias" }).click();
  await page.getByLabel("Alias: Leche", { exact: true }).selectOption({ label: "Leche normal" });
  await page.getByLabel("Producto para Leche", { exact: true }).selectOption("8");
  await page.screenshot({ path: testInfo.outputPath("alias-selectors-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Guardar alias Leche", exact: true }).click();
  await expect(page.getByLabel("Alias: Leche normal", { exact: true })).toBeVisible();
  expect(edits).toBe(1);
  await page.getByRole("button", { name: "Eliminar alias Leche normal", exact: true }).click();
  await expect(page.getByLabel("Alias: Leche normal", { exact: true })).toHaveCount(0);
  expect(deletes).toBe(1);
  await expect(page.getByLabel("Producto del nuevo alias").getByRole("option", { name: "Leche entera" })).toHaveCount(1);
});

test("product detail searches a name, previews and explicitly replaces a photo without a code/stock write", async ({ page }, testInfo) => {
  let photo = "https://images.openfoodfacts.org/old.jpg", saves = 0, searches = 0;
  const image = "https://images.openfoodfacts.org/new.jpg";
  await page.route("https://images.openfoodfacts.org/*", route => route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="green"/></svg>' }));
  await page.route("**/api/v1/catalog/products/1", route => {
    expect(route.request().method()).toBe("GET");
    return route.fulfill({ json: { id: 1, name: "Tomate", stock_amount: "2", unit_id: 2, purchase_unit_id: 2, image_url: photo, is_pack: false, pack_size: 1, active: true, barcodes: [], units: [{ id: 2, name: "Piece" }] } });
  });
  await page.route("**/api/v1/catalog/products/1/barcodes", route => { expect(route.request().method()).toBe("GET"); return route.fulfill({ json: { barcodes: [] } }); });
  await page.route("**/api/v1/products/1/variants", route => route.fulfill({ json: { product: { id: 1, name: "Tomate" }, variants: [] } }));
  await page.route("**/api/v1/photos/discover", route => {
    searches++; expect(route.request().postDataJSON()).toEqual({ name: "Tomate", barcode: "", product_id: 1, consent: true });
    return route.fulfill({ json: { advisory: true, candidates: [{ name: "Tomate de prueba", barcode: "3017620422003", image_url: image, source_url: "https://world.openfoodfacts.org/product/3017620422003", search_source_url: "https://world.openfoodfacts.org/product/3017620422003", attribution: "Open Food Facts", discovery_token: "signed" }] } });
  });
  await page.route("**/api/v1/catalog/products/1/photo-discovery", route => {
    saves++; expect(route.request().postDataJSON()).toEqual({ token: "signed", replace: true }); photo = image;
    return route.fulfill({ json: { saved: true, image_url: image } });
  });
  await page.goto(base);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await page.locator(".product-name").first().click();
  await page.getByRole("button", { name: "Buscar foto con IA", exact: true }).click();
  await expect(page.getByRole("img", { name: "Imagen de catálogo: Tomate de prueba" })).toBeVisible();
  expect(saves).toBe(0);
  await page.setViewportSize({ width: 390, height: 850 });
  await page.screenshot({ path: testInfo.outputPath("edit-photo-ai-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Sustituir foto por esta imagen", exact: true }).click();
  await expect(page.getByRole("img", { name: "Fotografía de Tomate" })).toHaveAttribute("src", image);
  expect(searches).toBe(1); expect(saves).toBe(1);
  await expect(page.getByLabel("Cantidad final", { exact: true })).toHaveValue("2");
});

test("receipt button opens a native rear-camera picker and returned photo enters review only", async ({ page }, testInfo) => {
  let uploads = 0;
  await page.route("**/api/v1/receipts", async route => {
    uploads++; await route.fulfill({ json: { receipt_id: "camera-fixture", receipt: { items: [{ name: "Leche", quantity: 1 }] } } });
  });
  await page.route("**/api/v1/receipts/camera-fixture/review-context", route => route.fulfill({ json: { products: [], mappings: {} } }));
  await page.goto(base);
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page.getByRole("button", { name: "Escanear ticket", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 850 });
  await page.screenshot({ path: testInfo.outputPath("native-ticket-camera-mobile.png"), fullPage: true });
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Tomar foto del ticket", exact: true }).click();
  const input = await chooser;
  expect(await input.element().getAttribute("capture")).toBe("environment");
  expect(await input.element().getAttribute("accept")).not.toContain("pdf");
  expect(uploads).toBe(0);
  await input.setFiles({ name: "capture.jpg", mimeType: "image/jpeg", buffer: Buffer.from("disposable camera fixture") });
  await expect(page.getByLabel("Artículo", { exact: true })).toHaveValue("Leche");
  await expect(page.getByRole("button", { name: "Confirmar e importar a Grocy" })).toHaveCount(0);
  expect(uploads).toBe(1);
});
