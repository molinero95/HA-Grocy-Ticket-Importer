import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { Duplicates } from "./Duplicates";
import { renderWithClient } from "./test/helpers";

const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status });
afterEach(() => vi.unstubAllGlobals());

it("compares duplicates and shows stock/reference blockers using only read requests", async () => {
  const product = {
    id: 1,
    name: "Leche",
    stock_amount: "3",
    unit_id: 2,
    purchase_unit_id: 2,
    pack_size: 1,
    barcodes: [],
  };
  const fetch = vi.fn(async (url: string) =>
    url.includes("merge-preview")
      ? json({
          source: product,
          target: { ...product, id: 2, name: "Leche entera" },
          source_variants: [],
          target_variants: [],
          can_merge: false,
          blockers: ["Hay existencias: consolidación bloqueada"],
          audit: {
            collections: [
              {
                collection: "recipes",
                label: "Recetas",
                status: "error",
                count: null,
                references: [],
              },
            ],
          },
        })
      : json({
          groups: [
            {
              reason: "Nombre similar",
              items: [
                { id: 1, name: "Leche", barcodes: [] },
                { id: 2, name: "Leche entera", barcodes: [] },
              ],
            },
          ],
        }),
  );
  vi.stubGlobal("fetch", fetch);
  renderWithClient(<Duplicates />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Comparar los dos primeros" }),
  );
  await screen.findByText("Hay existencias: consolidación bloqueada");
  await screen.findByText("Recetas: No disponible");
  expect(screen.queryByRole("button", { name: /^Fusionar/ })).toBeNull();
  expect(fetch.mock.calls).toHaveLength(2);
  for (const call of vi.mocked(globalThis.fetch).mock.calls) {
    expect(call[1]).toMatchObject({ method: "GET" });
  }
});

it("recovers a failed analysis and loads the full audit only on explicit request", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(json({ error: "catalog_unavailable" }, 503))
    .mockResolvedValueOnce(json({ groups: [] }))
    .mockResolvedValueOnce(
      json({
        schema_version: 1,
        source: "Grocy",
        products: [],
        barcode_conflicts: [],
        unlinked_shopping_entries: [],
      }),
    );
  vi.stubGlobal("fetch", fetch);
  renderWithClient(<Duplicates />);
  await screen.findByRole("alert");
  expect(fetch).toHaveBeenCalledTimes(1);
  await userEvent.click(
    screen.getByRole("button", { name: "Volver a analizar" }),
  );
  await screen.findByText("No se han detectado posibles duplicados.");
  expect(fetch).toHaveBeenCalledTimes(2);
  await userEvent.click(
    screen.getByRole("button", { name: "Analizar catálogo" }),
  );
  await screen.findByRole("button", { name: "Exportar auditoría JSON" });
  expect(fetch).toHaveBeenCalledTimes(3);
});
