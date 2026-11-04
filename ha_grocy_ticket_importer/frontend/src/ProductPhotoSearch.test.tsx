import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ProductPhotoSearch } from "./ProductPhotoSearch";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";
vi.mock("./api", () => ({ discoverGenericPhotos: vi.fn(), discoverProduct: vi.fn(), saveNameDiscoveredPhoto: vi.fn() }));
const candidate: api.ProductDiscoveryCandidate = { name: "Leche entera", barcode: "3017620422003", image_url: "https://images.openfoodfacts.org/example.jpg", source_url: "https://world.openfoodfacts.org/product/3017620422003", search_source_url: "https://world.openfoodfacts.org/product/3017620422003", attribution: "Open Food Facts", discovery_token: "signed-choice" };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.discoverProduct).mockResolvedValue({ candidates: [candidate], advisory: true });
  vi.mocked(api.saveNameDiscoveredPhoto).mockResolvedValue({ saved: true, image_url: candidate.image_url! });
});
it("searches the saved name without a barcode and saves an explicit choice only once", async () => {
  const pending = deferred<Awaited<ReturnType<typeof api.saveNameDiscoveredPhoto>>>();
  vi.mocked(api.saveNameDiscoveredPhoto).mockReturnValue(pending.promise);
  const onSaved = vi.fn().mockResolvedValue(undefined);
  renderWithClient(<ProductPhotoSearch id={7} name="Leche entera" imageUrl={null} disabled={false} onSaved={onSaved} />);
  expect(api.discoverProduct).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Buscar foto con IA" }));
  expect(api.discoverProduct).toHaveBeenCalledExactlyOnceWith("Leche entera", "", 7);
  const use = await screen.findByRole("button", { name: "Usar esta foto" });
  expect(api.saveNameDiscoveredPhoto).not.toHaveBeenCalled();
  await userEvent.dblClick(use);
  expect(api.saveNameDiscoveredPhoto).toHaveBeenCalledExactlyOnceWith(7, "signed-choice", false);
  expect(screen.getByRole("button", { name: "Buscar foto con IA" })).toHaveProperty("disabled", true);
  await act(async () => pending.resolve({ saved: true }));
  expect(onSaved).toHaveBeenCalledOnce();
});
it("makes replacement explicit and keeps the existing image when saving fails", async () => {
  vi.mocked(api.saveNameDiscoveredPhoto).mockRejectedValue(new Error("La fotografía ha cambiado"));
  const onSaved = vi.fn().mockResolvedValue(undefined);
  renderWithClient(<ProductPhotoSearch id={7} name="Leche entera" imageUrl="product/7/photo/local?v=1" disabled={false} onSaved={onSaved} />);
  await userEvent.click(screen.getByRole("button", { name: "Buscar foto con IA" }));
  await userEvent.click(await screen.findByRole("button", { name: "Sustituir foto por esta imagen" }));
  expect(api.saveNameDiscoveredPhoto).toHaveBeenCalledExactlyOnceWith(7, "signed-choice", true);
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("La fotografía ha cambiado"));
  expect(onSaved).not.toHaveBeenCalled();
});
it("discards results when the saved product/photo context changes", async () => {
  const pending = deferred<Awaited<ReturnType<typeof api.discoverProduct>>>();
  vi.mocked(api.discoverProduct).mockReturnValue(pending.promise);
  const props = { id: 7, name: "Leche entera", disabled: false, onSaved: vi.fn() };
  const { rerender } = renderWithClient(<ProductPhotoSearch {...props} imageUrl={null} />);
  await userEvent.click(screen.getByRole("button", { name: "Buscar foto con IA" }));
  rerender(<ProductPhotoSearch {...props} imageUrl="product/7/photo/local?v=2" />);
  await act(async () => pending.resolve({ candidates: [candidate], advisory: true }));
  expect(screen.queryByRole("button", { name: "Usar esta foto" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Sustituir foto por esta imagen" })).toBeNull();
  expect(api.saveNameDiscoveredPhoto).not.toHaveBeenCalled();
});

it("finds a generic garlic photo without paid AI or a barcode and saves only an explicit selection", async () => {
  const generic = { ...candidate, kind: "generic" as const, file_id: 123, name: "Garlic bulbs", barcode: "", discovery_token: "generic-choice", attribution: "Wikimedia Commons · CC0" };
  const pending = deferred<Awaited<ReturnType<typeof api.discoverGenericPhotos>>>();
  vi.mocked(api.discoverGenericPhotos).mockReturnValue(pending.promise);
  const onSaved = vi.fn().mockResolvedValue(undefined);
  renderWithClient(<ProductPhotoSearch id={7} name="ajo" imageUrl={null} disabled={false} onSaved={onSaved} />);
  await userEvent.dblClick(screen.getByRole("button", { name: "Buscar foto genérica" }));
  expect(api.discoverGenericPhotos).toHaveBeenCalledExactlyOnceWith("ajo", 7);
  expect(api.discoverProduct).not.toHaveBeenCalled();
  await act(async () => pending.resolve({ candidates: [generic], advisory: true }));
  expect(screen.getByText("Foto genérica · Sin código de barras")).toBeTruthy();
  expect(api.saveNameDiscoveredPhoto).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Usar esta foto" }));
  expect(api.saveNameDiscoveredPhoto).toHaveBeenCalledExactlyOnceWith(7, "generic-choice", false);
});

it("keeps generic empty results advisory and discards a late generic search after rename", async () => {
  vi.mocked(api.discoverGenericPhotos).mockResolvedValueOnce({ candidates: [], advisory: true });
  const props = { id: 7, name: "ajo", imageUrl: null, disabled: false, onSaved: vi.fn() };
  const { rerender } = renderWithClient(<ProductPhotoSearch {...props} />);
  await userEvent.click(screen.getByRole("button", { name: "Buscar foto genérica" }));
  expect(await screen.findByText(/No se encontraron fotos genéricas/)).toBeTruthy();
  const pending = deferred<Awaited<ReturnType<typeof api.discoverGenericPhotos>>>();
  vi.mocked(api.discoverGenericPhotos).mockReturnValue(pending.promise);
  await userEvent.click(screen.getByRole("button", { name: "Buscar foto genérica" }));
  rerender(<ProductPhotoSearch {...props} name="cebolla" />);
  await act(async () => pending.resolve({ candidates: [{ ...candidate, kind: "generic", barcode: "" }], advisory: true }));
  expect(screen.queryByRole("button", { name: "Usar esta foto" })).toBeNull();
  expect(api.saveNameDiscoveredPhoto).not.toHaveBeenCalled();
});
