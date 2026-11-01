import { expect, test } from "@playwright/test";

const ingress = "http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/";

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
    page.getByRole("button", { name: "Ver y restaurar" }),
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
    name: "Abrir cámara para escanear",
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
