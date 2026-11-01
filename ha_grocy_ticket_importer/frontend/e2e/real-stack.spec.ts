import { expect, test, type Page } from "@playwright/test";

test.skip(
  !process.env.GROCY_TEST_DIST,
  "Requires verified real Grocy distribution",
);
test.describe.configure({ mode: "serial" });
const base = "http://127.0.0.1:8767/";
async function command(page: Page, path: string, data?: object) {
  await expect(
    page.getByRole("navigation", { name: "Secciones" }),
  ).toBeVisible();
  const session = await (
    await page.request.get(base + "api/v1/auth/status")
  ).json();
  return page.request.post(
    base + (path.startsWith("__test/") ? "api/v1/" : "") + path,
    { headers: { "X-CSRF-Token": session.csrf_token }, data },
  );
}
async function pantry(page: Page) {
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
}
async function tickets(page: Page) {
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page
    .getByRole("button", { name: "Escanear ticket", exact: true })
    .click();
}

test("catalog, variants, barcode ownership, stock and photos survive a Grocy restart", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "BarcodeDetector", {
      configurable: true,
      value: class {
        async detect() {
          return [{ rawValue: "8411111111111" }];
        }
      },
    });
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
      configurable: true,
      value: async () => new MediaStream(),
    });
    Object.defineProperty(HTMLMediaElement.prototype, "readyState", {
      configurable: true,
      get: () => 4,
    });
    HTMLMediaElement.prototype.play = async () => {};
  });
  await page.goto(base + "react/");
  await pantry(page);
  await page
    .getByRole("button", { name: "Nuevo producto", exact: true })
    .click();
  await page.getByLabel("Nombre", { exact: true }).fill("Producto E2E");
  await page
    .getByLabel("Unidad", { exact: true })
    .selectOption({ label: "Piece" });
  await page
    .getByRole("button", { name: "Guardar producto", exact: true })
    .click();
  await page.getByRole("button", { name: "Abrir ficha del producto" }).click();
  await page.getByLabel("Cantidad final", { exact: true }).fill("3");
  await page.getByRole("button", { name: "Actualizar stock" }).click();
  await expect(page.getByText("Stock actualizado correctamente")).toBeVisible();
  await page.getByRole("button", { name: "+ Añadir variante" }).click();
  await page
    .getByLabel("Código de barras", { exact: true })
    .fill("8411111111111");
  await page
    .getByLabel("Nombre de la variante", { exact: true })
    .fill("Variante E2E");
  await page
    .getByLabel("Supermercado", { exact: true })
    .fill("Tienda de prueba");
  await page.getByRole("button", { name: "Guardar variante" }).click();
  await expect(page.getByText("Variante E2E", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Editar", exact: true }).click();
  await expect(
    page.getByLabel("Código de barras", { exact: true }),
  ).toHaveAttribute("readonly", "");
  await page.getByLabel("Marca", { exact: true }).fill("Marca editada");
  await page.getByRole("button", { name: "Guardar variante" }).click();
  const image = await (
    await page.request.get(base + "__test/photo.png")
  ).body();
  await page
    .getByLabel(/Elegir fotografía/)
    .setInputFiles({ name: "test.png", mimeType: "image/png", buffer: image });
  await page.getByRole("button", { name: "Guardar fotografía" }).click();
  await expect(
    page.getByRole("img", { name: "Fotografía de Producto E2E" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cerrar ficha" }).click();
  await page
    .getByRole("button", { name: "Abrir cámara para escanear", exact: true })
    .click();
  await expect(
    page.getByLabel("Buscar por nombre o código de barras"),
  ).toHaveValue("8411111111111");
  await expect(page.locator(".inventory-item")).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Producto E2E", exact: true }),
  ).toBeVisible();
  expect((await command(page, "__test/restart")).ok()).toBe(true);
  await page.reload();
  await pantry(page);
  await page.getByRole("button", { name: "Producto E2E", exact: true }).click();
  await expect(page.getByText("Variante E2E", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Fotografía de Producto E2E" }),
  ).toBeVisible();
  await expect(
    page.getByText("Stock actual: 3 Piece.", { exact: false }),
  ).toBeVisible();
});

test("receipt preview/commit converts packs and re-upload cannot duplicate adjusted stock", async ({
  page,
}) => {
  await page.goto(base + "react/");
  await tickets(page);
  const file = {
    name: "test.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("isolated-browser-ticket"),
  };
  await page.getByLabel("Foto o PDF del ticket").setInputFiles(file);
  await page.getByRole("button", { name: "Simular importación" }).click();
  await expect(
    page.getByRole("heading", { name: "Resultado de la simulación" }),
  ).toBeVisible();
  await expect(page.locator("pre")).toContainText("10 Piece");
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Confirmar e importar a Grocy" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Importación completada" }),
  ).toBeVisible();
  await pantry(page);
  await page
    .getByRole("button", { name: "Yogur de prueba", exact: true })
    .click();
  await expect(
    page.getByText("Stock actual: 10 Piece.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Consumir producto" }),
  ).toHaveCount(0);
  await page.getByLabel("Cantidad final").fill("9");
  await page
    .getByRole("button", { name: "Actualizar stock", exact: true })
    .click();
  await expect(
    page.getByText("Stock actualizado correctamente", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Stock actual: 9 Piece.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cerrar ficha" }).click();
  await tickets(page);
  await page.getByLabel("Foto o PDF del ticket").setInputFiles(file);
  await page.getByRole("button", { name: "Simular importación" }).click();
  await expect(page.locator("pre")).toContainText("SKIP imported");
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Confirmar e importar a Grocy" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Importación completada" }),
  ).toBeVisible();
  await pantry(page);
  await page
    .getByRole("button", { name: "Yogur de prueba", exact: true })
    .click();
  await expect(
    page.getByText("Stock actual: 9 Piece.", { exact: false }),
  ).toBeVisible();
});

test("Alexa choices immediately create usable rows and removals survive sync and restart", async ({
  page,
}) => {
  await page.goto(base + "react/");
  await expect(
    page.getByRole("button", { name: "Quitar Arroz", exact: true }),
  ).toBeVisible();
  await page.getByText("Elegir producto para «Arroz»", { exact: true }).click();
  const details = page
    .locator("details")
    .filter({ hasText: "Elegir producto para «Arroz»" });
  await details.getByRole("combobox").selectOption({ label: "Arroz basmati" });
  await details.getByRole("button", { name: "Guardar elección" }).click();
  const selectedRow = page
    .locator("article")
    .filter({
      has: page.getByRole("button", { name: "Arroz basmati", exact: true }),
    });
  await expect(
    selectedRow.getByRole("button", { name: "Quitar Arroz basmati" }),
  ).toBeVisible();
  await selectedRow
    .getByRole("button", { name: "✓ Comprado", exact: true })
    .click();
  await selectedRow
    .getByRole("button", { name: "↩ Pendiente", exact: true })
    .click();
  await expect(
    page.getByText("Elegir producto para «Arroz»", { exact: true }),
  ).toHaveCount(0);
  const shopping = await (
    await page.request.get(base + "api/v1/shopping")
  ).json();
  expect(
    shopping.items.filter(
      (item: { name: string }) => item.name === "Arroz basmati",
    ),
  ).toHaveLength(1);
  expect(
    shopping.items.filter((item: { name: string }) => item.name === "Arroz"),
  ).toHaveLength(0);
  expect((await command(page, "__test/sync")).ok()).toBe(true);
  await selectedRow
    .getByRole("button", { name: "Quitar Arroz basmati" })
    .click();
  await expect(selectedRow).toHaveCount(0);
  expect((await command(page, "__test/sync")).ok()).toBe(true);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Arroz basmati", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Elegir producto para «Arroz»", { exact: true }),
  ).toHaveCount(0);
  await page.getByText("Elegir producto para «Pasta»", { exact: true }).click();
  await page
    .locator("details")
    .filter({ hasText: "Elegir producto para «Pasta»" })
    .getByRole("button", { name: "Mantener original" })
    .click();
  await expect(
    page.getByRole("button", { name: "Quitar Pasta", exact: true }),
  ).toBeVisible();
  expect((await command(page, "__test/restart")).ok()).toBe(true);
  expect((await command(page, "__test/sync")).ok()).toBe(true);
  await page.reload();
  await expect(
    page.getByText("Elegir producto para «Pasta»", { exact: true }),
  ).toHaveCount(0);
  expect(
    (
      await (await page.request.get(base + "api/v1/shopping")).json()
    ).items.filter((item: { name: string }) => item.name === "Pasta"),
  ).toHaveLength(1);
});

test("purchase configuration, inline shopping and reversible archive preserve history", async ({
  page,
}) => {
  await page.goto(base + "react/");
  await pantry(page);
  await page
    .getByRole("button", { name: "Producto sin uso", exact: true })
    .click();
  await page.getByLabel("Unidad para comprar").selectOption({ label: "Pack" });
  await page.getByLabel("Piezas por pack", { exact: true }).fill("4");
  const savedPurchase = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/catalog/products/4/purchase") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Guardar unidad de compra" }).click();
  expect((await savedPurchase).ok()).toBe(true);
  // The refreshed product remounts the editor after the verified save.
  await expect(page.getByLabel("Piezas por pack", { exact: true })).toBeEnabled();
  await expect(page.getByLabel("Piezas por pack", { exact: true })).toHaveValue(
    "4",
  );
  await expect(page.getByLabel("Cantidad para comprar")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Añadir cantidad", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Stock actual: 0 Piece.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cerrar ficha" }).click();
  const add = page.getByRole("button", {
    name: "Añadir a compra: Producto sin uso",
    exact: true,
  });
  await add.click();
  await expect(
    page.getByRole("button", {
      name: "Quitar de compra: Producto sin uso",
      exact: true,
    }),
  ).toBeVisible();
  await add.click();
  const inventoryRow = page.locator("article").filter({
    has: page.getByRole("button", { name: "Producto sin uso", exact: true }),
  });
  await expect(inventoryRow.locator(".quantity")).toContainText("2 Piece");
  await expect(inventoryRow).toContainText("En casa: 0 Piece");
  await page
    .getByRole("button", { name: "Lista de la compra", exact: true })
    .click();
  const row = page.locator("article").filter({
    has: page.getByRole("button", { name: "Producto sin uso", exact: true }),
  });
  await expect(row).toContainText("2 Piece");
  await row
    .getByRole("button", { name: "Quitar Producto sin uso", exact: true })
    .click();
  await pantry(page);
  await page
    .getByRole("button", { name: "Producto sin uso", exact: true })
    .click();
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Archivar producto", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Producto sin uso", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page
    .getByRole("button", { name: "Productos archivados", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Producto sin uso", exact: true })
    .click();
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Restaurar producto", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Producto sin uso", exact: true }),
  ).toBeVisible();
});

test("a newly created product becomes an Alexa suggestion without another worker cycle", async ({ page }) => {
  const name = "Jabon recien creado";
  await page.goto(base + "react/");
  const added = await page.request.post(base + "api/services/todo/add_item", {
    headers: { Authorization: "Bearer disposable" },
    data: { entity_id: "todo.disposable", item: name },
  });
  expect(added.ok()).toBe(true);
  expect((await command(page, "__test/sync")).ok()).toBe(true);
  await page.getByRole("button", { name: "Actualizar", exact: true }).click();
  await expect(page.getByText(name, { exact: true })).toBeVisible();
  await pantry(page);
  await page.getByRole("button", { name: "Nuevo producto", exact: true }).click();
  await page.getByLabel("Nombre", { exact: true }).fill(name);
  await page.getByLabel("Unidad", { exact: true }).selectOption({ label: "Piece" });
  await page.getByRole("button", { name: "Guardar producto", exact: true }).click();
  await expect(page.getByText("Producto creado correctamente", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar", exact: true }).click();
  await page.getByRole("button", { name: "Lista de la compra", exact: true }).click();
  await page.getByText(`Elegir producto para «${name}»`, { exact: true }).click();
  await expect(page.getByRole("option", { name, exact: true })).toHaveCount(1);
  await page.getByRole("button", { name: "Guardar elección", exact: true }).click();
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  const row = page.locator("article").filter({ has: page.getByRole("button", { name, exact: true }) });
  await expect(row).toContainText("1 Piece");
});


test("an unused archived product can be permanently removed through the reviewed sheet", async ({ page }) => {
  await page.goto(base + "react/");
  await pantry(page);
  await page.getByRole("button", { name: "Nuevo producto", exact: true }).click();
  await page.getByLabel("Nombre", { exact: true }).fill("Archive deletion E2E");
  await page.getByLabel("Unidad", { exact: true }).selectOption({ label: "Piece" });
  await page.getByRole("button", { name: "Guardar producto", exact: true }).click();
  await page.getByRole("button", { name: "Abrir ficha del producto" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Archivar producto", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page.getByRole("button", { name: "Productos archivados", exact: true }).click();
  await page.getByRole("button", { name: "Archive deletion E2E", exact: true }).click();
  await page.getByRole("button", { name: "Revisar eliminación", exact: true }).click();
  const confirm = page.getByRole("button", { name: "Eliminar producto definitivamente", exact: true });
  await expect(confirm).toBeDisabled();
  await page.getByLabel("Escribe «Archive deletion E2E» para confirmar", { exact: true }).fill("Archive deletion E2E");
  await confirm.click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Archive deletion E2E", exact: true })).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: "Acciones", exact: true }).click();
  await page.getByRole("button", { name: "Productos archivados", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Productos archivados", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Archive deletion E2E", exact: true })).toHaveCount(0);
});

test("duplicate review persists differences and combines through the native Grocy transaction", async ({ page }) => {
  await page.goto(base + "react/");
  for (const name of ["Zumo naranja e2e", "Zumo naranjas e2e"]) {
    await pantry(page);
    await page.getByRole("button", {name: "Nuevo producto", exact: true}).click();
    await page.getByLabel("Nombre", {exact: true}).fill(name);
    await page.getByLabel("Unidad", {exact: true}).selectOption({label: "Piece"});
    await page.getByLabel("Stock inicial").fill("2");
    await page.getByRole("button", {name: "Guardar producto", exact: true}).click();
    await page.getByRole("button", {name: "Abrir ficha del producto"}).click();
    await page.getByRole("button", {name: "Cerrar ficha"}).click();
  }
  const open = async () => {
    await page.getByRole("button", {name: "Acciones", exact: true}).click();
    await page.getByRole("button", {name: "Revisar duplicados y auditoría", exact: true}).click();
  };
  await open();
  const pair = page.locator(".duplicate-group").filter({hasText: "Zumo naranja e2e"});
  await pair.getByRole("button", {name: "Son diferentes", exact: true}).click();
  await expect(pair).toHaveCount(0);
  await page.reload(); await open();
  await expect(pair).toHaveCount(0);
  await page.getByText(/Productos marcados como diferentes/).click();
  await page.locator(".difference-row").filter({hasText: "Zumo naranja e2e"}).getByRole("button", {name: "Deshacer diferencia"}).click();
  await pair.getByRole("button", {name: "Revisar combinación", exact: true}).click();
  const keep = await page.getByLabel("Producto que conservarás").inputValue();
  const target = await page.getByLabel("Producto que conservarás").locator("option:checked").textContent();
  const name = target!.replace(/ \(ID \d+\)$/, "");
  await page.getByLabel(`Escribe «${name}» para conservarlo`, {exact: true}).fill(name);
  await page.getByRole("button", {name: "Combinar definitivamente", exact: true}).click();
  await expect(page.getByText("Productos combinados. Se ha conservado el producto elegido.")).toBeVisible();
  await expect(pair).toHaveCount(0);
  await pantry(page);
  await page.getByRole("button", {name, exact: true}).click();
  await expect(page.getByLabel("Cantidad final", {exact: true})).toHaveValue("4");
  expect(Number(keep)).toBeGreaterThan(0);
});
