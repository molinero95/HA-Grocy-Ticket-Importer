import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { StockStepper } from "./StockStepper";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";
vi.mock("./api", () => ({ adjustCatalogStock: vi.fn(), getInventory: vi.fn() }));
beforeEach(() => vi.resetAllMocks());
it("shows a kg burst immediately, preserves thousandths and sends one absolute stock command", async () => {
  vi.mocked(api.adjustCatalogStock).mockResolvedValue({ before: "0.123", after: "0.423" });
  renderWithClient(<StockStepper id={7} name="Tomate" amount="0.123" unit="kg" />);
  const plus = screen.getByRole("button", { name: "Aumentar stock: Tomate" });
  await userEvent.click(plus); await userEvent.click(plus); await userEvent.click(plus);
  expect(screen.getByText("0.423 kg")).toBeTruthy();
  expect(api.adjustCatalogStock).not.toHaveBeenCalled();
  await waitFor(() => expect(api.adjustCatalogStock).toHaveBeenCalledExactlyOnceWith(7, "0.423", "0.123", expect.any(String), true));
});
it("does not replay a lost stock response and requires a read before another edit", async () => {
  const pending = deferred<Awaited<ReturnType<typeof api.adjustCatalogStock>>>();
  vi.mocked(api.adjustCatalogStock).mockReturnValue(pending.promise);
  renderWithClient(<StockStepper id={7} name="Leche" amount="2" unit="Piece" />);
  await userEvent.click(screen.getByRole("button", { name: "Reducir stock: Leche" }));
  await waitFor(() => expect(api.adjustCatalogStock).toHaveBeenCalledOnce());
  await act(async () => pending.reject(new Error("Resultado incierto")));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Aumentar stock: Leche" })).toHaveProperty("disabled", true);
  expect(api.adjustCatalogStock).toHaveBeenCalledOnce();
});
it("commits an already requested burst after navigation without making another shopping call", async () => {
  vi.mocked(api.adjustCatalogStock).mockResolvedValue({ before: "2", after: "3" });
  const { unmount } = renderWithClient(<StockStepper id={7} name="Leche" amount="2" unit="Piece" />);
  await userEvent.click(screen.getByRole("button", { name: "Aumentar stock: Leche" }));
  unmount();
  await waitFor(() => expect(api.adjustCatalogStock).toHaveBeenCalledOnce());
});
it("sends Piece totals as integers without adding decimal zeroes", async () => {
  vi.mocked(api.adjustCatalogStock).mockResolvedValue({ before: "2.000", after: "3" });
  renderWithClient(<StockStepper id={7} name="Leche" amount="2.000" unit="Piece" />);
  await userEvent.click(screen.getByRole("button", { name: "Aumentar stock: Leche" }));
  expect(screen.getByText("3 Piece")).toBeTruthy();
  await waitFor(() => expect(api.adjustCatalogStock).toHaveBeenCalledExactlyOnceWith(7, "3", "2.000", expect.any(String), true));
});
