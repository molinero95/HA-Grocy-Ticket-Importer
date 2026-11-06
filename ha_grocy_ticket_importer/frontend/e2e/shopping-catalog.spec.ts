import { expect, test } from "@playwright/test";

for (const width of [320, 360]) test(`full shopping catalog selects two distinct milks at ${width}px`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 900 });
  const item = { amount: "0", unit: "Piece", image_url: null, shopping_amount: "0", shopping_step: "1", shopping_unit: "Piece", shopping_can_subtract: false };
  const products = [{ ...item, id: 7, name: "Leche entera" }, { ...item, id: 8, name: "Leche Clau" }, { ...item, id: 9, name: "Leche Jaime" }];
  const names = ["Bebida de Clau", "Bebida de Jaime"];
  const saved = new Map<string, number>();
  await page.route("**/api/v1/inventory", route => route.fulfill({ json: { items: products } }));
  await page.route("**/api/v1/shopping", route => route.fulfill({ json: {
    items: [...saved].map(([, id]) => ({ id, name: products.find(p => p.id === id)!.name, product_id: id, amount: 2, unit: "Piece", done: false, image_url: null })),
    pending_matches: names.filter(name => !saved.has(name)).map(name => ({ key: name.toLowerCase(), name, generation: 1, candidates: [{ id: 7, name: "Leche entera" }] })),
    shopping_error: false, pending_matches_error: false,
  } }));
  await page.route("**/api/v1/alexa/matches/*/choose", async route => {
    const body = route.request().postDataJSON();
    const name = body.catalog_choice.expected_name;
    expect(body.catalog_choice.generation).toBe(1);
    expect(body.catalog_choice.product_name).toBe(products.find(p => p.id === body.product_id)!.name);
    expect(route.request().headers()["x-csrf-token"]).toBeTruthy();
    expect(saved.has(name)).toBe(false);
    saved.set(name, body.product_id);
    await route.fulfill({ json: { ok: true, item_id: body.product_id } });
  });
  await page.goto("http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/");
  for (const [index, suffix] of ["Clau", "Jaime"].entries()) {
    const name = names[index];
    const section = page.locator("article").filter({ has: page.getByText(`Elegir producto para «${name}»`, { exact: true }) });
    await section.getByText(`Elegir producto para «${name}»`, { exact: true }).click();
    const select = section.getByLabel("Producto", { exact: true });
    await expect(select.locator("optgroup")).toHaveCount(2);
    await expect(select.locator("option").filter({ hasText: "Leche entera" })).toHaveCount(1);
    await section.getByLabel("Buscar en todos los productos").fill(suffix.toUpperCase());
    await select.selectOption(String(index + 8));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (index === 0) await page.screenshot({ path: testInfo.outputPath(`shopping-catalog-${width}.png`), fullPage: true });
    await section.getByRole("button", { name: "Guardar elección" }).click();
    await expect(page.getByRole("button", { name: `Leche ${suffix}`, exact: true })).toBeVisible();
  }
  expect([...saved.values()]).toEqual([8, 9]);
});
