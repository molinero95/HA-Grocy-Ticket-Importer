import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ResolvedMergeReview } from "./ResolvedMergeReview";
import * as api from "./api";
import { renderWithClient } from "./test/helpers";
vi.mock("./api", () => ({ getMergeResolutionOptions: vi.fn(), previewMergeResolution: vi.fn(), commitResolvedMerge: vi.fn() }));
const product = { barcodes: [], id: 1, name: "Tomate peso", stock_amount: "1.5", unit_id: 3, purchase_unit_id: 3, pack_size: 1 };
const options: api.MergeResolutionOptions = { source: product, target: { ...product, id: 2, name: "Tomates", unit_id: 2, purchase_unit_id: 2, stock_amount: "2" }, source_variants: [], target_variants: [], can_merge: true, blockers: [], token: "a".repeat(64), units: [{ id: 2, name: "Piece" }, { id: 3, name: "Kilogram" }], target_threshold: { amount: "0", warning_enabled: true } };
const render = () => renderWithClient(<ResolvedMergeReview pair={[1, 2]} onSwap={vi.fn()} onClose={vi.fn()} onBack={vi.fn()} onMerged={vi.fn()} />);
beforeEach(() => {
  vi.resetAllMocks();vi.mocked(api.getMergeResolutionOptions).mockResolvedValue(options);
  vi.mocked(api.previewMergeResolution).mockImplementation(async (_, __, resolution) => ({ ...options, resolution, combined_stock: "5", stock_correction: "-1", unit_name: "Piece" }));
});
async function prepare() {
  await userEvent.type(await screen.findByLabelText("Equivalencia de Tomate peso"), "2");
  await userEvent.type(screen.getByLabelText("Stock final que debe quedar"), "4");
  await userEvent.click(screen.getByRole("button", { name: "Revisar resultado final" }));
  return screen.findByLabelText("Resultado final revisado");
}
it("requires explicit equivalence and final stock, previews without a write and clears stale results after editing", async () => {
  render();await screen.findByLabelText("Nombre final");
  expect(screen.getByRole("button", { name: "Revisar resultado final" })).toHaveProperty("disabled", true);
  await prepare(); expect(api.commitResolvedMerge).not.toHaveBeenCalled();
  await userEvent.type(screen.getByLabelText("Nombre final"), " nuevo");
  expect(screen.queryByLabelText("Resultado final revisado")).toBeNull();
});
it("requires exact final name and locks after a single uncertain commit", async () => {
  vi.mocked(api.commitResolvedMerge).mockRejectedValue(new Error("Comprueba ambos productos"));
  render(); await prepare();
  const button = screen.getByRole("button", { name: "Combinar con estos datos finales" });
  expect(button).toHaveProperty("disabled", true);
  await userEvent.type(screen.getByLabelText("Escribe «Tomates» para confirmar combinación"), "Tomates");
  await userEvent.dblClick(button);await screen.findByRole("alert");
  expect(api.commitResolvedMerge).toHaveBeenCalledOnce();expect(button).toHaveProperty("disabled", true);
  expect(screen.getByLabelText("Stock final que debe quedar")).toHaveProperty("disabled", true);
});
it("keeps dependency blockers visible even when units and stock are supplied", async () => {
  vi.mocked(api.previewMergeResolution).mockImplementation(async (_, __, resolution) => ({ ...options, resolution, can_merge: false, blockers: ["Hay vínculos de tickets"], combined_stock: "5", stock_correction: "-1", unit_name: "Piece" }));
  render();await prepare();await screen.findByText("Hay vínculos de tickets");
  expect(screen.queryByRole("button", { name: "Combinar con estos datos finales" })).toBeNull();
});
