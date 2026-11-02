import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CreateProduct } from "./CreateProduct";
import * as api from "./api";
import { deferred } from "./test/helpers";
vi.mock("./api", async (original) => ({
  ...(await original<typeof api>()),
  getCatalogUnits: vi.fn(),
  createCatalogProduct: vi.fn(),
  saveDiscoveredPhoto: vi.fn(),
  lookupPhoto: vi.fn(),
  identifyProductPhoto: vi.fn(),
  uploadCatalogPhoto: vi.fn(),
  saveNameDiscoveredPhoto: vi.fn(),
  discoverProduct: vi.fn(),
}));
beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:product-photo-test");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  vi.mocked(api.getCatalogUnits).mockResolvedValue([
    { id: 2, name: "Piece" },
    { id: 3, name: "Pack" },
  ]);
  vi.mocked(api.lookupPhoto).mockResolvedValue({ photo: null });
});

afterEach(() => vi.restoreAllMocks());

it.each([
  { label: "Código de barras (opcional)", value: "123" },
  { label: "Stock inicial", value: "-1" },
  { label: "Piezas por pack", value: "1.5" },
  { label: "Piezas por pack", value: "1001" },
])("blocks invalid creation: $label = $value", async ({ label, value }) => {
  mount();
  await userEvent.type(screen.getByLabelText("Nombre"), "Leche");
  await userEvent.selectOptions(screen.getByLabelText("Unidad"), "3");
  await userEvent.clear(screen.getByLabelText(label));
  await userEvent.type(screen.getByLabelText(label), value);
  expect(
    screen.getByRole("button", { name: "Guardar producto" }),
  ).toHaveProperty("disabled", true);
  expect(api.createCatalogProduct).not.toHaveBeenCalled();
});

it("preserves entered fields after creation is rejected", async () => {
  vi.mocked(api.createCatalogProduct).mockRejectedValue(
    new Error("Código ya asociado"),
  );
  mount();
  await userEvent.type(screen.getByLabelText("Nombre"), "Leche entera");
  await userEvent.selectOptions(screen.getByLabelText("Unidad"), "3");
  await userEvent.clear(screen.getByLabelText("Piezas por pack"));
  await userEvent.type(screen.getByLabelText("Piezas por pack"), "5");
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar producto" }),
  );
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Nombre")).toHaveProperty(
    "value",
    "Leche entera",
  );
  expect(screen.getByLabelText("Piezas por pack")).toHaveProperty("value", "5");
});

it("creates once on double click even when photo persistence fails", async () => {
  const pending =
    deferred<Awaited<ReturnType<typeof api.createCatalogProduct>>>();
  vi.mocked(api.createCatalogProduct).mockReturnValue(pending.promise);
  vi.mocked(api.saveDiscoveredPhoto).mockRejectedValue(
    new Error("Proveedor no disponible"),
  );
  mount();
  await userEvent.type(screen.getByLabelText("Nombre"), "Leche");
  await userEvent.type(
    screen.getByLabelText("Código de barras (opcional)"),
    "8412345678901",
  );
  await userEvent.selectOptions(screen.getByLabelText("Unidad"), "2");
  await userEvent.dblClick(
    screen.getByRole("button", { name: "Guardar producto" }),
  );
  expect(api.createCatalogProduct).toHaveBeenCalledTimes(1);
  await act(async () => pending.resolve({ created: true, product_id: 7 }));
  await screen.findByText(
    /El producto está creado. No se pudo guardar su foto/,
  );
  expect(screen.queryByRole("button", { name: "Guardar producto" })).toBeNull();
});
function mount(onOpenProduct = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <CreateProduct onClose={vi.fn()} onOpenProduct={onOpenProduct} />
    </QueryClientProvider>,
  );
  return client;
}
it("only displays the pack factor for a Pack purchase unit", async () => {
  mount();
  await screen.findByRole("option", { name: "Pack" });
  expect(screen.queryByLabelText("Piezas por pack")).toBeNull();
  await userEvent.selectOptions(screen.getByLabelText("Unidad"), "3");
  expect(screen.getByLabelText("Piezas por pack")).toBeTruthy();
  await userEvent.selectOptions(screen.getByLabelText("Unidad"), "2");
  expect(screen.queryByLabelText("Piezas por pack")).toBeNull();
});
it("links to an existing product without attaching a photo or permitting resubmission", async () => {
  const open = vi.fn();
  mount(open);
  vi.mocked(api.createCatalogProduct).mockResolvedValue({
    created: false,
    product_id: 7,
  });
  await userEvent.type(screen.getByLabelText("Nombre"), "Leche");
  await userEvent.selectOptions(screen.getByLabelText("Unidad"), "2");
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar producto" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Abrir ficha del producto" }),
  );
  expect(open).toHaveBeenCalledWith(7);
  expect(api.saveDiscoveredPhoto).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Guardar producto" })).toBeNull();
});

it("refreshes shopping suggestions immediately after creation before photo lookup completes", async () => {
  const photo = deferred<Awaited<ReturnType<typeof api.saveDiscoveredPhoto>>>();
  vi.mocked(api.createCatalogProduct).mockResolvedValue({
    created: true,
    product_id: 7,
  });
  vi.mocked(api.saveDiscoveredPhoto).mockReturnValue(photo.promise);
  const client = mount();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  await userEvent.type(screen.getByLabelText("Nombre"), "Leche");
  await userEvent.type(
    screen.getByLabelText("Código de barras (opcional)"),
    "8412345678901",
  );
  await userEvent.selectOptions(screen.getByLabelText("Unidad"), "2");
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar producto" }),
  );
  await waitFor(() =>
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["shopping"] }),
  );
  await act(async () => photo.resolve({ saved: true, image_url: null }));
});

it("uses a verified catalog suggestion only on selection and saves its photo after creation", async () => {
  const candidate: api.ProductDiscoveryCandidate = {
    name: "Crema Example 100 ml", barcode: "4006000082295",
    image_url: "https://images.openbeautyfacts.org/example.jpg",
    source_url: "https://world.openbeautyfacts.org/product/4006000082295",
    search_source_url: "https://world.openbeautyfacts.org/product/4006000082295",
    attribution: "Datos: Open Beauty Facts",
  };
  vi.mocked(api.discoverProduct).mockResolvedValue({ candidates: [candidate], advisory: true });
  vi.mocked(api.createCatalogProduct).mockResolvedValue({ created: true, product_id: 72 });
  vi.mocked(api.saveDiscoveredPhoto).mockResolvedValue({ saved: true, image_url: candidate.image_url });
  mount();
  await userEvent.type(screen.getByLabelText("Nombre"), "Crema Example 100 ml");
  await userEvent.click(screen.getByRole("button", { name: "Buscar imagen y código con IA" }));
  await screen.findByRole("button", { name: "Usar código e imagen" });
  expect(screen.getByLabelText("Código de barras (opcional)")).toHaveProperty("value", "");
  expect(api.createCatalogProduct).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Usar código e imagen" }));
  expect(screen.getByLabelText("Código de barras (opcional)")).toHaveProperty("value", candidate.barcode);
  await userEvent.selectOptions(screen.getByLabelText("Unidad"), "2");
  await userEvent.click(screen.getByRole("button", { name: "Guardar producto" }));
  await screen.findByText("Producto creado correctamente");
  expect(api.saveDiscoveredPhoto).toHaveBeenCalledExactlyOnceWith(72, candidate.barcode);
  expect(api.createCatalogProduct).toHaveBeenCalledExactlyOnceWith({ name: "Crema Example 100 ml", barcode: candidate.barcode, unit_id: 2, initial_stock: "0", pack_size: "1" });
});

it("defaults to the actual Piece ID and has no photo upload for AI", async () => {
  mount();
  await screen.findByRole("option", { name: "Piece" });
  await waitFor(() => expect(screen.getByLabelText("Unidad")).toHaveProperty("value", "2"));
  expect(screen.queryByRole("button", { name: /Tomar otra foto|Analizar foto/ })).toBeNull();
});

it("keeps an unknown scanned code while choosing a photo by name", async () => {
  vi.mocked(api.discoverProduct).mockResolvedValue({ candidates: [{ name: "Crema Example", barcode: "4006000082295", image_url: "https://images.openbeautyfacts.org/example.jpg", source_url: "https://world.openbeautyfacts.org/product/4006000082295", search_source_url: "https://world.openbeautyfacts.org/product/4006000082295", attribution: "Datos: Open Beauty Facts", discovery_token: "signed-choice" }], advisory: true });
  vi.mocked(api.createCatalogProduct).mockResolvedValue({ created: true, product_id: 73 });
  vi.mocked(api.saveNameDiscoveredPhoto).mockResolvedValue({ saved: true });
  mount();
  await userEvent.type(screen.getByLabelText("Nombre"), "Crema Example");
  await userEvent.type(screen.getByLabelText("Código de barras (opcional)"), "8412345678901");
  await userEvent.click(screen.getByRole("button", { name: "Buscar imagen y código con IA" }));
  await userEvent.click(await screen.findByRole("button", { name: "Usar imagen y conservar código" }));
  expect(screen.getByLabelText("Código de barras (opcional)")).toHaveProperty("value", "8412345678901");
  await userEvent.click(screen.getByRole("button", { name: "Guardar producto" }));
  await screen.findByText("Producto creado correctamente");
  expect(api.saveNameDiscoveredPhoto).toHaveBeenCalledExactlyOnceWith(73, "signed-choice");
});
