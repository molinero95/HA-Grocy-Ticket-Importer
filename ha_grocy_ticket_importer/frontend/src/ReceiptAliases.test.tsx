import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ReceiptAliases } from "./ReceiptAliases";
import * as api from "./api";
import { renderWithClient } from "./test/helpers";
vi.mock("./api", () => ({ getReceiptAliases: vi.fn(), updateReceiptAlias: vi.fn(), deleteReceiptAlias: vi.fn() }));
const original: api.ReceiptAlias = { merchant: "mercado uno", source_name: "leche ent", product_id: 1, stock_unit: "piece", pieces_per_pack: 1 };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getReceiptAliases).mockResolvedValue({ aliases: [original, { ...original, merchant: "mercado dos", stale: true, product_id: 999 }], products: [{ id: 1, name: "Leche entera", stock_unit: "piece", pieces_per_pack: 1 }, { id: 2, name: "Tomate", stock_unit: "kg", pieces_per_pack: 1 }] });
});
it("shows every merchant-scoped mapping and missing identities, filters without writes", async () => {
  renderWithClient(<ReceiptAliases />);
  await screen.findByText("2 de 2 asociaciones");
  expect(screen.getByText("Revisar: producto ausente o unidades modificadas")).toBeTruthy();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Supermercado" }), "mercado dos");
  expect(screen.getByText("1 de 2 asociaciones")).toBeTruthy();
  await userEvent.type(screen.getByRole("searchbox"), "no existe");
  expect(screen.getByText("0 de 2 asociaciones")).toBeTruthy();
  expect(api.updateReceiptAlias).not.toHaveBeenCalled(); expect(api.deleteReceiptAlias).not.toHaveBeenCalled();
});
it("saves edited text and product with the full expected row", async () => {
  vi.mocked(api.updateReceiptAlias).mockResolvedValue({});
  renderWithClient(<ReceiptAliases />);
  const text = await screen.findByLabelText("Texto de leche ent (mercado uno)");
  await userEvent.clear(text); await userEvent.type(text, "LECHE NUEVA");
  await userEvent.selectOptions(screen.getByLabelText("Producto para leche ent (mercado uno)"), "2");
  await userEvent.dblClick(screen.getByRole("button", { name: "Guardar leche ent (mercado uno)" }));
  await waitFor(() => expect(api.updateReceiptAlias).toHaveBeenCalledExactlyOnceWith(original, { merchant: "mercado uno", source_name: "LECHE NUEVA", product_id: 2 }));
});
it("deletion needs explicit yes, targets one mapping, and does not replay errors", async () => {
  vi.mocked(api.deleteReceiptAlias).mockRejectedValue(new Error("La asociación ha cambiado"));
  renderWithClient(<ReceiptAliases />);
  await userEvent.click(await screen.findByRole("button", { name: "Eliminar leche ent (mercado uno)" }));
  expect(api.deleteReceiptAlias).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: /^No$/ }));
  await userEvent.click(screen.getByRole("button", { name: "Eliminar leche ent (mercado uno)" }));
  await userEvent.click(screen.getByRole("button", { name: "Sí, eliminar" }));
  await screen.findByRole("alert");
  expect(api.deleteReceiptAlias).toHaveBeenCalledExactlyOnceWith(original);
});
