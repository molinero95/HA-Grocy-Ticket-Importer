import { expect, test } from "@playwright/test";
const base = "http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/";
test("receipt aliases show merchant memory, edit and delete with mobile confirmation", async ({ page }, info) => {
  let aliases = [
    { merchant: "supermercado uno", source_name: "LECHE ENT", product_id: 7, stock_unit: "piece", pieces_per_pack: 1, stale: false },
    { merchant: "supermercado dos", source_name: "LECHE ENT", product_id: 999, stock_unit: "piece", pieces_per_pack: 6, stale: true },
  ];
  let writes = 0;
  await page.route("**/api/v1/receipt-aliases", async route => {
    const method = route.request().method();
    if (method !== "GET") {
      writes++; const body = route.request().postDataJSON();
      expect(body.expected.merchant).toBe("supermercado uno");
      if (method === "PUT") aliases[0] = { ...aliases[0], ...body, product_id: body.product_id, stock_unit: "kg", pieces_per_pack: 1 };
      else aliases = aliases.filter(row => row.merchant !== body.expected.merchant);
      return route.fulfill({ json: { saved: true } });
    }
    return route.fulfill({ json: { aliases, products: [{ id: 7, name: "Leche entera", stock_unit: "piece", pieces_per_pack: 1 }, { id: 8, name: "Tomate con nombre largo para revisar correctamente en móvil", stock_unit: "kg", pieces_per_pack: 1 }] } });
  });
  await page.goto(base);
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page.getByRole("button", { name: "Administrar alias de tickets" }).click();
  await expect(page.getByText("2 de 2 asociaciones")).toBeVisible();
  await expect(page.getByText("Revisar: producto ausente o unidades modificadas")).toBeVisible();
  for (const width of [320, 390, 1024]) {
    await page.setViewportSize({ width, height: 850 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.getByLabel("Producto para LECHE ENT (supermercado uno)")).toBeVisible();
  }
  await page.setViewportSize({ width: 390, height: 850 });
  await page.screenshot({ path: info.outputPath("receipt-aliases-mobile.png"), fullPage: true });
  await page.getByRole("searchbox").fill("leche entera");
  await expect(page.getByText("1 de 2 asociaciones")).toBeVisible();expect(writes).toBe(0);
  await page.getByRole("searchbox").fill("");
  await page.getByLabel("Producto para LECHE ENT (supermercado uno)").selectOption("8");
  await page.getByRole("button", { name: "Guardar LECHE ENT (supermercado uno)" }).click();
  await expect(page.getByText("Asociación de ticket actualizada")).toBeVisible();
  await page.getByRole("button", { name: "Eliminar LECHE ENT (supermercado uno)" }).click();
  expect(writes).toBe(1);
  await page.getByRole("button", { name: "Sí, eliminar" }).click();
  await expect(page.getByText("1 de 1 asociaciones")).toBeVisible();expect(writes).toBe(2);
});

test("receipt suggestions keep a manual choice, show direct addition and allow empty pack edits", async ({ page }, info) => {
  let previews = 0, commits = 0;
  const products = [{ id: 41, name: "Yogur natural", stock_unit: "piece", pieces_per_pack: 6, current_stock: "5" }, { id: 42, name: "Arroz", stock_unit: "piece", pieces_per_pack: 1, current_stock: "0" }];
  await page.route("**/api/v1/receipts", route => route.fulfill({ status: 201, json: { receipt_id: "ticket-review", receipt: { items: [{ name: "YOG NAT", quantity: 2, pieces_per_pack: 5 }] } } }));
  await page.route("**/api/v1/receipts/ticket-review/review-context", route => route.fulfill({ json: { products, mappings: {}, line_suggestions: [[41]] } }));
  await page.route("**/api/v1/receipts/ticket-review/preview", route => {
    previews++;const row = route.request().postDataJSON().items[0];
    expect(row.stock_to_add).toBe("3");expect(row.expected_stock).toBe("5");expect(row.pieces_per_pack).toBe(6);
    return route.fulfill({ json: { ready_to_commit: true, preview: "3 Piece; final 8 Piece" } });
  });
  await page.route("**/api/v1/receipts/ticket-review/commit", route => { commits++;return route.fulfill({ json: { status: "ok" } }); });
  await page.goto(base);
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page.getByRole("button", { name: "Escanear ticket", exact: true }).click();
  await page.getByLabel("Foto o PDF del ticket").setInputFiles({ name: "review.pdf", mimeType: "application/pdf", buffer: Buffer.from("disposable receipt UI") });
  const selector = page.getByLabel("Producto de Despensa");
  await expect(selector).toHaveValue("");
  await expect(page.locator('optgroup[label="Sugeridos por parecido"] option')).toHaveText("Yogur natural");
  await selector.selectOption("41");
  await expect(page.getByLabel("Piezas por envase")).toHaveCount(0);
  await page.getByLabel("Cantidad a añadir", { exact: true }).fill("3");
  await expect(page.getByLabel("Cantidad final calculada")).toHaveValue("8");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("receipt-direct-addition-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Simular importación" }).click();
  await expect(page.getByRole("button", { name: "Confirmar e importar a Grocy" })).toBeVisible();
  expect(previews).toBe(1);expect(commits).toBe(0);
  await selector.selectOption("new");
  const pack = page.getByLabel("Piezas por envase");
  await pack.fill("");await expect(pack).toHaveValue("");
  await pack.fill("05");await expect(pack).toHaveValue("5");
  await expect(page.getByLabel("Cantidad final calculada")).toHaveValue("10");
  await expect(page.getByRole("button", { name: "Confirmar e importar a Grocy" })).toHaveCount(0);
});

test("ticket rows explain disabled simulation, allow omission and highlight server review separately", async ({ page }, info) => {
  let previews = 0;
  await page.route("**/api/v1/receipts", route => route.fulfill({ status: 201, json: { receipt_id: "skip-ticket", receipt: { items: [{ name: "Bolsa", quantity: 1, pieces_per_pack: 0 }, { name: "Yogur", quantity: 2, pieces_per_pack: 5 }] } } }));
  await page.route("**/api/v1/receipts/skip-ticket/review-context", route => route.fulfill({ json: { products: [], mappings: {}, line_suggestions: [[], []] } }));
  await page.route("**/api/v1/receipts/skip-ticket/preview", route => {
    previews++;
    const items = route.request().postDataJSON().items;
    expect(items[0]).toMatchObject({ product_mode: "skip", remember_product: false, product_id: null, pieces_per_pack: 1, purchase_units: "1" });
    return route.fulfill({ json: previews === 1 ? { ready_to_commit: false, preview: "[2] REVIEW Yogur: Multiple catalog matches", line_issues: [{ index: 1, message: "Hay varios productos con ese nombre. Elige uno concreto." }] } : { ready_to_commit: true, preview: "[1] WOULD OMIT Bolsa\n[2] WOULD IMPORT Yogur", line_issues: [] } });
  });
  await page.goto(base);await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page.getByRole("button", { name: "Escanear ticket", exact: true }).click();
  await page.getByLabel("Foto o PDF del ticket").setInputFiles({ name: "skip.pdf", mimeType: "application/pdf", buffer: Buffer.from("disposable skip UI") });
  const first = page.getByRole("group", { name: "Línea 1: Bolsa" }), second = page.getByRole("group", { name: "Línea 2: Yogur" });
  await expect(first).toHaveClass(/receipt-line-invalid/);
  await expect(first).toContainText("Indica entre 1 y 1.000 piezas por envase");
  await expect(page.getByRole("button", { name: "Simular importación" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Revisar primer artículo pendiente" })).toBeVisible();
  await first.getByLabel("Producto de Despensa").selectOption("skip");
  await second.getByLabel("Producto de Despensa").selectOption("new");
  await expect(first).toHaveClass(/receipt-line-skipped/);
  await page.getByRole("button", { name: "Simular importación" }).click();
  await expect(second).toHaveClass(/receipt-line-invalid/);
  await expect(second).toContainText("Hay varios productos con ese nombre");
  await expect(page.getByRole("button", { name: "Confirmar e importar a Grocy" })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("receipt-omitted-and-review-mobile.png"), fullPage: true });
  await second.getByLabel("Producto de Despensa").selectOption("new");
  await page.getByRole("button", { name: "Simular importación" }).click();
  await expect(page.getByRole("button", { name: "Confirmar e importar a Grocy" })).toBeVisible();
  expect(previews).toBe(2);
});

test("price mismatch stays advisory, carry bag is omitted and every stock product requires a choice", async ({ page }, info) => {
  const warning = "Los importes no coinciden (calculado 7.55 €, ticket 7.04 €). La diferencia de precio no bloquea la importación; revisa productos y cantidades.";
  let previews = 0;
  await page.route("**/api/v1/receipts", route => route.fulfill({ status: 201, json: { receipt_id: "advisory-ticket", receipt: { total_warning: warning, items: [{ name: "Producto de prueba", quantity: 1 }, { name: "BOLSA 50% RECICLADA", quantity: 1, product_mode: "skip" }] } } }));
  await page.route("**/api/v1/receipts/advisory-ticket/review-context", route => route.fulfill({ json: { products: [], mappings: {}, line_suggestions: [[], []] } }));
  await page.route("**/api/v1/receipts/advisory-ticket/preview", route => {
    previews++;
    expect(route.request().postDataJSON().items).toMatchObject([{ product_mode: "new" }, { product_mode: "skip" }]);
    return route.fulfill({ json: { ready_to_commit: true, preview: "AVISO: " + warning + "\n[1] WOULD IMPORT Producto de prueba: 1 Piece\n[2] WOULD OMIT BOLSA 50% RECICLADA", line_issues: [] } });
  });
  await page.goto(base);await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page.getByRole("button", { name: "Escanear ticket", exact: true }).click();
  await page.getByLabel("Foto o PDF del ticket").setInputFiles({ name: "advisory.pdf", mimeType: "application/pdf", buffer: Buffer.from("synthetic advisory UI") });
  await expect(page.getByText(warning, { exact: true })).toBeVisible();
  const first = page.getByRole("group", { name: "Línea 1: Producto de prueba" });
  const bag = page.getByRole("group", { name: "Línea 2: BOLSA 50% RECICLADA" });
  await expect(bag).toHaveClass(/receipt-line-skipped/);
  await expect(first.getByLabel("Producto de Despensa")).toHaveValue("");
  await expect(page.getByRole("option", { name: "Detectar por nombre" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Simular importación" })).toBeDisabled();
  await first.getByLabel("Producto de Despensa").selectOption("new");
  await expect(page.getByRole("button", { name: "Simular importación" })).toBeEnabled();
  await page.getByRole("button", { name: "Simular importación" }).click();
  await expect(page.getByRole("button", { name: "Confirmar e importar a Grocy" })).toBeVisible();
  expect(previews).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("receipt-advisory-bag-mobile.png"), fullPage: true });
});
