import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ProductThreshold } from "./ProductThreshold";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";
vi.mock("./api", async original => ({ ...(await original<typeof api>()), saveStockThreshold: vi.fn() }));
beforeEach(() => vi.resetAllMocks());
it("saves a threshold once against its displayed value and leaves stock alone", async () => {
  const pending = deferred<{stock_threshold: string; stock_warning_enabled: boolean}>();
  vi.mocked(api.saveStockThreshold).mockReturnValue(pending.promise);
  renderWithClient(<ProductThreshold id={7} threshold="0" unit="Piece" />);
  const input = screen.getByLabelText("Umbral mínimo (Piece)");
  await userEvent.clear(input); await userEvent.type(input, "2");
  await userEvent.dblClick(screen.getByRole("button", { name: "Guardar umbral" }));
  expect(api.saveStockThreshold).toHaveBeenCalledExactlyOnceWith(7, "2", "0", true, true);
  await act(async () => pending.resolve({stock_threshold: "2", stock_warning_enabled: true}));
  await screen.findByText("Umbral guardado");
});
it("preserves the edited value after a stale save fails and blocks negative values", async () => {
  vi.mocked(api.saveStockThreshold).mockRejectedValue(new Error("El umbral ha cambiado"));
  renderWithClient(<ProductThreshold id={7} threshold="0" unit="kg" />);
  const input = screen.getByLabelText("Umbral mínimo (kg)");
  await userEvent.clear(input); await userEvent.type(input, "-1");
  expect(screen.getByRole("button", { name: "Guardar umbral" })).toHaveProperty("disabled", true);
  await userEvent.clear(input); await userEvent.type(input, "0.5");
  await userEvent.click(screen.getByRole("button", { name: "Guardar umbral" }));
  await screen.findByRole("alert");
  expect(input).toHaveProperty("value", "0.5");
});

it("can disable the warning while preserving the threshold", async () => {
  vi.mocked(api.saveStockThreshold).mockResolvedValue({stock_threshold: "3", stock_warning_enabled: false});
  renderWithClient(<ProductThreshold id={7} threshold="3" unit="Piece" />);
  await userEvent.click(screen.getByRole("checkbox", {name: "No avisar de stock bajo"}));
  await userEvent.click(screen.getByRole("button", {name: "Guardar umbral"}));
  expect(api.saveStockThreshold).toHaveBeenCalledExactlyOnceWith(7, "3", "3", false, true);
});
