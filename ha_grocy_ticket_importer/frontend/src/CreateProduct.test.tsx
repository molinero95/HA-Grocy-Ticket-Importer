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

async function analyzedProductPhoto() {
  vi.mocked(api.identifyProductPhoto).mockResolvedValue({
    suggestion: {
      name: "Yogur natural",
      brand: "Example",
      size_text: "125 g",
      confidence: "medium",
      visible_barcode: "",
      barcode: "8412345678901",
      advisory: true,
    },
  });
  await userEvent.type(
    screen.getByLabelText("Código de barras (opcional)"),
    "8412345678901",
  );
  await screen.findByRole("button", {
    name: "Tomar otra foto para buscar con IA",
  });
  const file = new File(["fresh front-label photograph"], "front.jpg", {
    type: "image/jpeg",
  });
  await userEvent.upload(
    screen.getByLabelText("Tomar foto del frontal o etiqueta del producto"),
    file,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Analizar foto con OpenAI" }),
  );
  await screen.findByRole("button", { name: "Usar nombre sugerido" });
  await userEvent.click(
    screen.getByRole("button", { name: "Usar nombre sugerido" }),
  );
  await userEvent.selectOptions(screen.getByLabelText("Unidad"), "2");
  return file;
}

it("saves the analyzed front photo only after a new product is created", async () => {
  vi.mocked(api.createCatalogProduct).mockResolvedValue({
    created: true,
    product_id: 71,
  });
  vi.mocked(api.uploadCatalogPhoto).mockResolvedValue({ saved: true });
  mount();
  const file = await analyzedProductPhoto();
  expect(api.uploadCatalogPhoto).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar producto" }),
  );
  await screen.findByText("Producto creado correctamente");
  expect(api.uploadCatalogPhoto).toHaveBeenCalledExactlyOnceWith(71, file);
  expect(api.saveDiscoveredPhoto).not.toHaveBeenCalled();
  expect(api.createCatalogProduct).toHaveBeenCalledExactlyOnceWith({
    name: "Yogur natural",
    barcode: "8412345678901",
    unit_id: 2,
    initial_stock: "0",
    pack_size: "1",
  });
});

it("keeps an existing duplicate's photo when recognition finds its name", async () => {
  vi.mocked(api.createCatalogProduct).mockResolvedValue({
    created: false,
    product_id: 7,
  });
  mount();
  await analyzedProductPhoto();
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar producto" }),
  );
  await screen.findByText(/Este producto ya existía/);
  expect(api.uploadCatalogPhoto).not.toHaveBeenCalled();
  expect(api.saveDiscoveredPhoto).not.toHaveBeenCalled();
});

it("keeps the created product and never replays creation after a photo-save failure", async () => {
  vi.mocked(api.createCatalogProduct).mockResolvedValue({
    created: true,
    product_id: 71,
  });
  vi.mocked(api.uploadCatalogPhoto).mockRejectedValue(
    new Error("Lost photo response"),
  );
  mount();
  await analyzedProductPhoto();
  await userEvent.dblClick(
    screen.getByRole("button", { name: "Guardar producto" }),
  );
  await screen.findByText(
    /El producto está creado. No se pudo guardar su foto/,
  );
  expect(api.createCatalogProduct).toHaveBeenCalledTimes(1);
  expect(api.uploadCatalogPhoto).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("button", { name: "Guardar producto" })).toBeNull();
});
