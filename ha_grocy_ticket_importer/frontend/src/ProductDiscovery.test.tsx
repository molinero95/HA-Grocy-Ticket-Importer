import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ProductDiscovery } from "./ProductDiscovery";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";
vi.mock("./api", () => ({ discoverProduct: vi.fn() }));
const candidate: api.ProductDiscoveryCandidate = {
  name: "Crema Example 100 ml", barcode: "4006000082295",
  image_url: "https://images.openbeautyfacts.org/example.jpg",
  source_url: "https://world.openbeautyfacts.org/product/4006000082295",
  search_source_url: "https://es.openbeautyfacts.org/product/4006000082295/example",
  attribution: "Datos: Open Beauty Facts",
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.discoverProduct).mockResolvedValue({ candidates: [candidate], advisory: true });
});
it("searches only on explicit click, once on double click, and applies only after a choice", async () => {
  const pending = deferred<Awaited<ReturnType<typeof api.discoverProduct>>>();
  vi.mocked(api.discoverProduct).mockReturnValue(pending.promise);
  const use = vi.fn();
  renderWithClient(<ProductDiscovery name="Crema Example 100 ml" barcode="" onUse={use} />);
  expect(api.discoverProduct).not.toHaveBeenCalled();
  await userEvent.dblClick(screen.getByRole("button", { name: "Buscar imagen y código con IA" }));
  expect(api.discoverProduct).toHaveBeenCalledExactlyOnceWith("Crema Example 100 ml", "");
  await act(async () => pending.resolve({ candidates: [candidate], advisory: true }));
  expect(screen.getByRole("link", { name: "Ver fuente de la búsqueda" })).toHaveProperty("href", candidate.search_source_url);
  expect(use).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Usar código e imagen" }));
  expect(use).toHaveBeenCalledExactlyOnceWith(candidate);
});
it("discards late results after changing name away and back or closing the form", async () => {
  const pending = deferred<Awaited<ReturnType<typeof api.discoverProduct>>>();
  vi.mocked(api.discoverProduct).mockReturnValue(pending.promise);
  const use = vi.fn();
  const { rerender, unmount } = renderWithClient(<ProductDiscovery name="Crema" barcode="" onUse={use} />);
  await userEvent.click(screen.getByRole("button", { name: "Buscar imagen y código con IA" }));
  rerender(<ProductDiscovery name="Otra" barcode="" onUse={use} />);
  rerender(<ProductDiscovery name="Crema" barcode="" onUse={use} />);
  await act(async () => pending.resolve({ candidates: [candidate], advisory: true }));
  expect(screen.queryByRole("button", { name: "Usar código e imagen" })).toBeNull();
  unmount();
  expect(use).not.toHaveBeenCalled();
});
it("passes an existing code as a search constraint and keeps empty results and failures advisory", async () => {
  vi.mocked(api.discoverProduct).mockResolvedValueOnce({ candidates: [], advisory: true }).mockRejectedValueOnce(new Error("Sin conexión"));
  renderWithClient(<ProductDiscovery name="Crema" barcode="4006000082295" onUse={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Buscar imagen y código con IA" }));
  expect(await screen.findByText(/No se encontraron coincidencias/)).toBeTruthy();
  expect(api.discoverProduct).toHaveBeenCalledExactlyOnceWith("Crema", "4006000082295");
  await userEvent.click(screen.getByRole("button", { name: "Buscar imagen y código con IA" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("Sin conexión"));
  expect(api.discoverProduct).toHaveBeenCalledTimes(2);
});
