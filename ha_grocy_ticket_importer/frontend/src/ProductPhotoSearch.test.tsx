import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ProductPhotoSearch } from "./ProductPhotoSearch";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";
vi.mock("./api", () => ({ discoverWebPhotos: vi.fn(), discoverProduct: vi.fn(), saveNameDiscoveredPhoto: vi.fn() }));
const candidate: api.ProductDiscoveryCandidate = { name: "Leche entera", barcode: "3017620422003", image_url: "https://images.openfoodfacts.org/example.jpg", source_url: "https://world.openfoodfacts.org/product/3017620422003", search_source_url: "https://world.openfoodfacts.org/product/3017620422003", attribution: "Open Food Facts", discovery_token: "signed-choice" };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.discoverWebPhotos).mockResolvedValue({ candidates: [candidate], advisory: true });
  vi.mocked(api.saveNameDiscoveredPhoto).mockResolvedValue({ saved: true, image_url: candidate.image_url! });
});
it("searches the saved name without a barcode and saves an explicit choice only once", async () => {
  const pending = deferred<Awaited<ReturnType<typeof api.saveNameDiscoveredPhoto>>>();
  vi.mocked(api.saveNameDiscoveredPhoto).mockReturnValue(pending.promise);
  const onSaved = vi.fn().mockResolvedValue(undefined);
  renderWithClient(<ProductPhotoSearch id={7} name="Leche entera" imageUrl={null} disabled={false} onSaved={onSaved} />);
  expect(api.discoverWebPhotos).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Buscar foto con IA" }));
  expect(api.discoverWebPhotos).toHaveBeenCalledExactlyOnceWith("Leche entera", "Leche entera", 7);
  const use = await screen.findByRole("button", { name: "Usar esta foto" });
  expect(api.saveNameDiscoveredPhoto).not.toHaveBeenCalled();
  await userEvent.dblClick(use);
  expect(api.saveNameDiscoveredPhoto).toHaveBeenCalledExactlyOnceWith(7, "signed-choice", false);
  expect(screen.getByRole("button", { name: "Buscar foto con IA" })).toHaveProperty("disabled", true);
  await act(async () => pending.resolve({ saved: true }));
  expect(onSaved).toHaveBeenCalledOnce();
});

it("lets OpenAI search a more specific name without renaming the product or requiring a barcode", async () => {
  const web = { ...candidate, kind: "web" as const, barcode: "", name: "Choco Flakes Cuétara", image_url: "api/v1/photos/web/preview", discovery_token: "web-photo-choice" };
  vi.mocked(api.discoverWebPhotos).mockResolvedValue({ candidates: [web], advisory: true });
  renderWithClient(<ProductPhotoSearch id={7} name="Chocoflakes" imageUrl={null} disabled={false} onSaved={vi.fn()} />);
  const query = screen.getByLabelText("Nombre para buscar la foto");
  await userEvent.clear(query);await userEvent.type(query, "Choco Flakes Cuétara");
  await userEvent.click(screen.getByRole("button", { name: "Buscar foto con IA" }));
  expect(api.discoverWebPhotos).toHaveBeenCalledExactlyOnceWith("Chocoflakes", "Choco Flakes Cuétara", 7);
  expect(screen.getByText("Fotografía sugerida · Sin código de barras")).toBeTruthy();
  expect(api.discoverProduct).not.toHaveBeenCalled();
  expect(api.saveNameDiscoveredPhoto).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Usar esta foto" }));
  expect(api.saveNameDiscoveredPhoto).toHaveBeenCalledExactlyOnceWith(7, "web-photo-choice", false);
  await userEvent.clear(query);await userEvent.type(query, "otra búsqueda");
  expect(screen.queryByRole("button", { name: "Usar esta foto" })).toBeNull();
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
  const pending = deferred<Awaited<ReturnType<typeof api.discoverWebPhotos>>>();
  vi.mocked(api.discoverWebPhotos).mockReturnValue(pending.promise);
  const props = { id: 7, name: "Leche entera", disabled: false, onSaved: vi.fn() };
  const { rerender } = renderWithClient(<ProductPhotoSearch {...props} imageUrl={null} />);
  await userEvent.click(screen.getByRole("button", { name: "Buscar foto con IA" }));
  rerender(<ProductPhotoSearch {...props} imageUrl="product/7/photo/local?v=2" />);
  await act(async () => pending.resolve({ candidates: [candidate], advisory: true }));
  expect(screen.queryByRole("button", { name: "Usar esta foto" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Sustituir foto por esta imagen" })).toBeNull();
  expect(api.saveNameDiscoveredPhoto).not.toHaveBeenCalled();
});

it("offers only one OpenAI photo button for generic products too", async () => {
  renderWithClient(<ProductPhotoSearch id={7} name="ajo" imageUrl={null} disabled={false} onSaved={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Buscar foto genérica" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Buscar foto con IA" }));
  expect(api.discoverWebPhotos).toHaveBeenCalledExactlyOnceWith("ajo", "ajo", 7);
});
