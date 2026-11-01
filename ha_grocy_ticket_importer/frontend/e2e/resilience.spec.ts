import { expect, test } from "@playwright/test";

const ingress = "http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/";

test("duplicate-review buttons and native file selection use consistent touch-friendly styles", async ({
  page,
}, testInfo) => {
  await page.route("**/api/v1/catalog/duplicates", (route) =>
    route.fulfill({
      json: {
        groups: [
          {
            reason: "Nombre similar",
            items: [
              { id: 1, name: "Leche", barcodes: [] },
              { id: 2, name: "Leche entera", barcodes: [] },
            ],
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/catalog/audit", (route) =>
    route.fulfill({
      json: {
        schema_version: 1,
        source: "grocy",
        products: [],
        barcode_conflicts: [],
        unlinked_shopping_entries: [],
      },
    }),
  );
  await page.goto(ingress);
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Revisar duplicados y auditoría",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("button", { name: "Comparar los dos primeros" }),
  ).toBeVisible();
  for (const name of [
    "Volver a analizar",
    "Analizar catálogo",
    "Comparar los dos primeros",
  ]) {
    const button = page.getByRole("button", { name, exact: true });
    expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    expect(
      await button.evaluate((node) =>
        parseFloat(getComputedStyle(node).borderRadius),
      ),
    ).toBeGreaterThan(0);
  }
  await page
    .getByRole("button", { name: "Analizar catálogo", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Exportar auditoría JSON" }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("duplicate-review-mobile.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page
    .getByRole("button", { name: "Escanear ticket", exact: true })
    .click();
  const input = page.getByLabel("Foto o PDF del ticket");
  const picker = await input.evaluate((node) => {
    const style = getComputedStyle(node, "::file-selector-button");
    return {
      radius: parseFloat(style.borderRadius),
      height: parseFloat(style.minHeight),
    };
  });
  expect(picker.radius).toBeGreaterThan(0);
  expect(picker.height).toBeGreaterThanOrEqual(44);
  await page.screenshot({
    path: testInfo.outputPath("receipt-file-picker-mobile.png"),
    fullPage: true,
  });
});

test("create form buttons share accessible styling and a catalog name remains optional", async ({
  page,
}, testInfo) => {
  await page.route("**/api/v1/catalog/units", (route) =>
    route.fulfill({ json: { units: [{ id: 2, name: "Piece" }] } }),
  );
  await page.route("**/api/v1/photos/4006000082295", (route) =>
    route.fulfill({
      json: {
        photo: {
          barcode: "4006000082295",
          name: "Nivea",
          image_url: null,
          source_url: "https://world.openbeautyfacts.org/product/4006000082295",
          attribution: "Datos: Open Beauty Facts",
        },
      },
    }),
  );
  await page.route("**/api/v1/catalog/products", (route) =>
    route.fulfill({ json: { created: false, product_id: 7 } }),
  );
  await page.goto(ingress);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await page
    .getByRole("button", { name: "Nuevo producto", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Crear producto" });
  await dialog
    .getByLabel("Nombre", { exact: true })
    .fill("Mi nombre de producto");
  await dialog.getByLabel("Código de barras (opcional)").fill("4006000082295");
  await expect(
    dialog.getByRole("button", { name: "Usar este nombre" }),
  ).toBeVisible();
  await expect(dialog.getByLabel("Nombre", { exact: true })).toHaveValue(
    "Mi nombre de producto",
  );
  await dialog.getByRole("button", { name: "Usar este nombre" }).click();
  await expect(dialog.getByLabel("Nombre", { exact: true })).toHaveValue(
    "Nivea",
  );
  await dialog.getByLabel("Unidad", { exact: true }).selectOption("2");
  for (const name of [
    "Cerrar",
    "Escanear código",
    "Usar este nombre",
    "Guardar producto",
  ]) {
    const button = dialog.getByRole("button", { name, exact: true });
    expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  await page.screenshot({
    path: testInfo.outputPath("create-product-form.png"),
    fullPage: true,
  });
  await dialog.getByRole("button", { name: "Guardar producto" }).click();
  await expect(
    dialog.getByRole("button", { name: "Abrir ficha del producto" }),
  ).toBeVisible();
  expect(
    (await dialog
      .getByRole("button", { name: "Abrir ficha del producto" })
      .boundingBox())!.height,
  ).toBeGreaterThanOrEqual(44);
  await page.screenshot({
    path: testInfo.outputPath("create-product-existing.png"),
    fullPage: true,
  });
});

test("a saved suggestion immediately offers bought/remove controls, including after marking bought", async ({
  page,
}) => {
  let saved = false,
    removed = false,
    done = false;
  const counts = { choose: 0, toggle: 0, remove: 0 };
  await page.route("**/api/v1/shopping", (route) =>
    route.fulfill({
      json: {
        items:
          saved && !removed
            ? [
                {
                  id: 71,
                  product_id: 8,
                  name: "Arroz basmati",
                  amount: 1,
                  unit: "Piece",
                  done,
                  image_url: null,
                },
              ]
            : [],
        pending_matches:
          !saved && !removed
            ? [
                {
                  key: "arroz",
                  name: "Arroz",
                  candidates: [{ id: 8, name: "Arroz basmati" }],
                },
              ]
            : [],
        shopping_error: false,
        pending_matches_error: false,
      },
    }),
  );
  await page.route("**/api/v1/alexa/matches/arroz/choose", (route) => {
    counts.choose++;
    const body = route.request().postDataJSON();
    expect(body.product_id).toBe(8);
    expect(body.operation_id).toMatch(/^[a-f0-9-]{36}$/);
    saved = true;
    return route.fulfill({ json: { ok: true, item_id: 71 } });
  });
  await page.route("**/api/v1/shopping/71/toggle", (route) => {
    counts.toggle++;
    done = route.request().postDataJSON().done;
    return route.fulfill({ json: { ok: true } });
  });
  await page.route("**/api/v1/shopping/71", (route) => {
    expect(route.request().method()).toBe("DELETE");
    counts.remove++;
    removed = true;
    return route.fulfill({ json: { ok: true } });
  });
  await page.goto(ingress);
  await expect(
    page.getByRole("button", { name: "Quitar Arroz", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("1 artículos", { exact: true })).toBeVisible();
  await page.getByText("Elegir producto para «Arroz»", { exact: true }).click();
  await page.getByLabel("Producto sugerido").selectOption("8");
  await page
    .getByRole("button", { name: "Guardar elección", exact: true })
    .click();
  await expect(page.getByText(/Artículo guardado en la lista/)).toBeVisible();
  await page.getByRole("button", { name: "✓ Comprado", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "↩ Pendiente", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Quitar Arroz basmati", exact: true })
    .click();
  await expect(
    page.getByText("Tu lista de la compra está vacía.", { exact: true }),
  ).toBeVisible();
  expect(counts).toEqual({ choose: 1, toggle: 1, remove: 1 });
});

test("archives live in Actions without a duplicate product-creation shortcut", async ({
  page,
}, testInfo) => {
  await page.route("**/api/v1/catalog/archived", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: 99,
            name: "Producto archivado de prueba",
            amount: "0",
            unit: "Piece",
            image_url: null,
            shopping_amount: "0",
            shopping_step: "1",
            shopping_unit: "Piece",
            shopping_can_subtract: false,
          },
        ],
      },
    }),
  );
  await page.goto(ingress);
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await expect(
    page.getByRole("button", {
      name: /Nuevo producto|Añadir.*producto|Gestionar productos/,
    }),
  ).toHaveCount(0);
  await page.screenshot({
    path: testInfo.outputPath("actions-mobile.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Productos archivados", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Productos archivados" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Ver producto" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Nuevo producto" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: /Añadir a compra/ }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Nuevo producto" }),
  ).toBeVisible();
  await expect(
    page.getByText("Producto archivado de prueba", { exact: true }),
  ).toHaveCount(0);
});

for (const width of [360, 768, 1280]) {
  test(`shopping fits ${width}px with long names and stable action columns`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 850 });
    await page.goto(ingress);
    await expect(page.locator(".item-actions")).toHaveCount(2);
    const boxes = await Promise.all(
      [0, 1].map((i) => page.locator(".item-actions").nth(i).boundingBox()),
    );
    expect(boxes[0]!.x).toBeCloseTo(boxes[1]!.x, 0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page
      .getByRole("button", { name: "Mi despensa", exact: true })
      .click();
    const create = page.getByRole("button", {
      name: "Nuevo producto",
      exact: true,
    });
    await expect(create).toBeVisible();
    const createBox = await create.boundingBox();
    expect(createBox!.height).toBeGreaterThanOrEqual(44);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(
      page.getByRole("button", { name: "Ver archivados" }),
    ).toHaveCount(0);
    await page.screenshot({
      path: testInfo.outputPath(`inventory-${width}.png`),
      fullPage: true,
    });
  });
}

test("nested camera dialog traps keyboard focus, Escape restores focus and releases scroll", async ({
  page,
}) => {
  await page.route("**/api/v1/catalog/units", (route) =>
    route.fulfill({ json: { units: [{ id: 2, name: "Piece" }] } }),
  );
  await page.goto(ingress);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  const trigger = page.getByRole("button", {
    name: "Nuevo producto",
    exact: true,
  });
  await trigger.click();
  const parent = page.getByRole("dialog", {
    name: "Crear producto",
    exact: true,
  });
  const close = parent.getByRole("button", { name: "Cerrar", exact: true });
  await expect(close).toBeFocused();
  await expect(page.locator("body")).toHaveCSS("overflow", "hidden");
  // Save is disabled: the last focusable field is stock, which must wrap to close.
  await page.keyboard.press("Shift+Tab");
  await expect(parent.getByLabel("Stock inicial")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  const cameraTrigger = parent.getByRole("button", {
    name: "Escanear código",
  });
  await cameraTrigger.click();
  const camera = page.getByRole("dialog", {
    name: "Escáner de códigos de barras",
    exact: true,
  });
  await expect(
    camera.getByRole("button", { name: "Cerrar cámara" }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    camera.getByRole("button", { name: "Cerrar cámara" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(camera).toHaveCount(0);
  await expect(parent).toBeVisible();
  await expect(cameraTrigger).toBeFocused();
  await expect(page.locator("body")).toHaveCSS("overflow", "hidden");
  await page.keyboard.press("Escape");
  await expect(parent).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await expect(page.locator("body")).not.toHaveCSS("overflow", "hidden");
});

test("a lost purchase response sends one request and leaves an error beside the unchanged cart", async ({
  page,
}) => {
  let writes = 0;
  await page.route("**/api/v1/shopping/products/1/step", async (route) => {
    writes++;
    await route.abort("failed");
  });
  await page.goto(ingress);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  const add = page.getByRole("button", { name: /Añadir a compra: Tomate/ });
  await add.click();
  await expect(page.getByRole("alert")).toContainText(/fetch/i);
  await expect(add).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Quitar de compra: Tomate/ }),
  ).toHaveCount(0);
  expect(writes).toBe(1);
});

test("an expired session removes the private shopping view after an unauthorized write", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:8765/react/");
  await page.getByLabel("Contraseña").fill("browser-test");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Lista de la compra" }),
  ).toBeVisible();
  let writes = 0;
  await page.route("**/api/v1/shopping/*/toggle", (route) => {
    writes++;
    return route.fulfill({
      status: 401,
      json: { error: "authentication_required" },
    });
  });
  await page
    .getByRole("button", { name: "✓ Comprado", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Iniciar sesión" }),
  ).toBeVisible();
  await expect(page.locator(".item")).toHaveCount(0);
  expect(writes).toBe(1);
});

test("Alexa note conflicts expose a preserving association action on mobile", async ({ page }, testInfo) => {
  let selected = false;
  await page.route("**/api/v1/shopping", (route) => route.fulfill({ json: {
    items: [{ id: 71, name: "Leche entera", amount: 2.5, unit: "Piece", done: false, product_id: selected ? 7 : null, image_url: null }],
    pending_matches: selected ? [] : [{ key: "leche entera", name: "Leche entera", candidates: [{ id: 7, name: "Leche entera" }], requires_product: true }],
    shopping_error: false, pending_matches_error: false,
    sync: selected ? { state: "ok" } : { state: "error", reason: "note_conflict" },
  } }));
  await page.route("**/api/v1/alexa/matches/*/choose", async (route) => {
    expect(route.request().postDataJSON().product_id).toBe(7);
    selected = true;
    await route.fulfill({ json: { ok: true, item_id: 71 } });
  });
  await page.goto(ingress);
  await expect(page.getByText(/Alexa no se ha sincronizado: hay artículos de texto/)).toBeVisible();
  await page.getByText("Elegir producto para «Leche entera»").click();
  await expect(page.getByRole("option", { name: "Mantener artículo original" })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("alexa-note-review-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Guardar elección", exact: true }).click();
  await expect(page.getByText(/Alexa no se ha sincronizado: hay artículos de texto/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Leche entera", exact: true })).toBeVisible();
  await expect(page.locator("article")).toContainText("2.5 Piece");
});
