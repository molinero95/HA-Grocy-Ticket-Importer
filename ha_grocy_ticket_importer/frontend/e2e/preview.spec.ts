import { expect, test } from "@playwright/test";

test("standalone session, mobile alignment, stock controls and camera fallback", async ({
  page,
}, testInfo) => {
  await page.goto("http://127.0.0.1:8765/react/");
  await page.getByLabel("Contraseña").fill("wrong");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Contraseña incorrecta");
  await page.getByLabel("Contraseña").fill("browser-test");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Lista de la compra" }),
  ).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("mobile-shopping.png"), fullPage: true });
  const actions = page.locator(".item-actions");
  await expect(actions).toHaveCount(2);
  const left = await actions.nth(0).boundingBox();
  const right = await actions.nth(1).boundingBox();
  expect(left?.x).toBe(right?.x);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "✓ Comprado", exact: true })
    .first()
    .click();
  await expect(page.getByRole("button", { name: "↩ Pendiente" })).toHaveCount(
    1,
  );
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  const add = page.getByRole("button", { name: /Añadir a compra: Tomate/ });
  await add.click();
  await expect(
    page.getByRole("button", { name: /Quitar de compra: Tomate/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Quitar de compra: Tomate/ }).click();
  await expect(
    page.getByRole("button", { name: /Quitar de compra: Tomate/ }),
  ).toHaveCount(0);
  await page
    .getByLabel("Buscar por nombre o código de barras")
    .fill("8412345678901");
  await expect(page.locator(".inventory-item")).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Leche", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Abrir cámara para escanear" })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Escáner de códigos de barras" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cerrar cámara" }).click();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(
    page.getByRole("heading", { name: "Iniciar sesión" }),
  ).toBeVisible();
});

test("bundled assets and API requests keep the ingress prefix", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto(
    "http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/",
  );
  await expect(
    page.getByRole("heading", { name: "Lista de la compra" }),
  ).toBeVisible();
  expect(
    requests
      .filter((url) => url.includes("/api/v1/"))
      .every((url) => url.includes("/api/hassio_ingress/browser-test/api/v1/")),
  ).toBe(true);
  await expect(page.getByRole("button", { name: "Cerrar sesión" })).toHaveCount(
    0,
  );
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Mi despensa" }),
  ).toBeVisible();
});
