import { expect, test } from "@playwright/test";

const base = "http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/";
test("unknown barcode requires a new camera photo before explicit analysis and an editable name without a catalog write", async ({
  page,
}, testInfo) => {
  let analyses = 0;
  let writes = 0;
  let photoSaves = 0;
  await page.route("**/api/v1/catalog/units", (route) =>
    route.fulfill({ json: { units: [{ id: 2, name: "Piece" }] } }),
  );
  await page.route("**/api/v1/photos/8412345678901", (route) =>
    route.fulfill({ json: { photo: null } }),
  );
  await page.route("**/api/v1/barcodes/8412345678901", (route) =>
    route.fulfill({ json: { product_id: null } }),
  );
  await page.route("**/api/v1/catalog/products", async (route) => {
    writes++;
    await route.fulfill({ json: { created: true, product_id: 71 } });
  });
  await page.route("**/api/v1/catalog/products/71/photo", async (route) => {
    photoSaves++;
    expect(route.request().postDataBuffer()!.toString("latin1")).toContain(
      "image/png",
    );
    await route.fulfill({ json: { saved: true } });
  });
  await page.route("**/api/v1/photos/identify", async (route) => {
    analyses++;
    const body = route.request().postDataBuffer()!.toString("latin1");
    expect(body).toContain('name="photo"');
    expect(body).toContain("image/png");
    expect(body).toContain('name="consent"');
    await route.fulfill({
      json: {
        suggestion: {
          name: "Yogur natural",
          brand: "Example",
          size_text: "6 x 125 g",
          confidence: "medium",
          visible_barcode: "",
          barcode: "8412345678901",
          advisory: true,
        },
      },
    });
  });
  await page.goto(base);
  await page.getByRole("button", { name: "Mi despensa", exact: true }).click();
  await page
    .getByLabel("Buscar por nombre o código de barras")
    .fill("8412345678901");
  await page.getByRole("button", { name: "Dar de alta este código" }).click();
  const dialog = page.getByRole("dialog", { name: "Crear producto" });
  await expect(dialog.getByLabel("Código de barras (opcional)")).toHaveValue(
    "8412345678901",
  );
  await expect(
    dialog.getByRole("heading", { name: "Identificar con una foto" }),
  ).toBeVisible();
  expect(analyses).toBe(0);
  await expect(
    dialog.getByRole("button", { name: "Analizar foto con OpenAI" }),
  ).toBeDisabled();
  const chooserPromise = page.waitForEvent("filechooser");
  await dialog
    .getByRole("button", { name: "Tomar otra foto para buscar con IA" })
    .click();
  const chooser = await chooserPromise;
  await expect(
    dialog.getByLabel("Tomar foto del frontal o etiqueta del producto"),
  ).toHaveAttribute("capture", "environment");
  await chooser.setFiles({
    name: "front.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "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",
      "base64",
    ),
  });
  await expect
    .poll(() =>
      dialog
        .getByAltText("Foto completa que se enviará a OpenAI")
        .evaluate((node: HTMLImageElement) => node.naturalWidth),
    )
    .toBeGreaterThan(0);
  await dialog
    .getByRole("button", { name: "Analizar foto con OpenAI" })
    .click();
  await expect(dialog.getByText("Nombre sugerido:")).toBeVisible();
  expect(analyses).toBe(1);
  expect(writes).toBe(0);
  await expect(dialog.getByLabel("Nombre", { exact: true })).toHaveValue("");
  await dialog.getByRole("button", { name: "Usar nombre sugerido" }).click();
  await expect(dialog.getByLabel("Nombre", { exact: true })).toHaveValue(
    "Yogur natural",
  );
  await expect(dialog.getByLabel("Código de barras (opcional)")).toHaveValue(
    "8412345678901",
  );
  await expect(
    dialog.getByRole("button", { name: "Analizar foto con OpenAI" }),
  ).toBeDisabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("full-photo-recognition-mobile.png"),
    fullPage: true,
  });
  expect(photoSaves).toBe(0);
  await dialog.getByLabel("Unidad", { exact: true }).selectOption("2");
  await dialog.getByRole("button", { name: "Guardar producto" }).click();
  await expect(dialog.getByText("Producto creado correctamente")).toBeVisible();
  expect(writes).toBe(1);
  expect(photoSaves).toBe(1);
});
