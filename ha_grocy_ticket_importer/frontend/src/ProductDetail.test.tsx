import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ProductDetail } from "./ProductDetail";
import * as api from "./api";
import { renderWithClient } from "./test/helpers";
vi.mock("./api", async (original) => ({
  ...(await original<typeof api>()),
  getCatalogProduct: vi.fn(),
  getProductVariants: vi.fn(),
  getCatalogBarcodes: vi.fn(),
  adjustCatalogStock: vi.fn(),
  getShoppingOptions: vi.fn(),
  saveProductVariant: vi.fn(),
  setCatalogProductActive: vi.fn(),
  saveCatalogBarcode: vi.fn(),
  saveDiscoveredPhoto: vi.fn(),
  lookupPhoto: vi.fn(),
}));
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getCatalogProduct).mockResolvedValue({
    id: 7,
    name: "Leche",
    stock_amount: "3",
    unit_id: 2,
    purchase_unit_id: 2,
    image_url: null,
    is_pack: false,
    pack_size: 1,
    barcodes: [],
    units: [{ id: 2, name: "Piece" }],
  });
  vi.mocked(api.getProductVariants).mockResolvedValue({
    product: { id: 7, name: "Leche" },
    variants: [],
  });
  vi.mocked(api.getCatalogBarcodes).mockResolvedValue([]);
  vi.mocked(api.adjustCatalogStock).mockResolvedValue({});
  vi.mocked(api.lookupPhoto).mockResolvedValue({ photo: null });
  vi.mocked(api.getShoppingOptions).mockResolvedValue({
    id: 7,
    name: "Leche",
    units: [{ id: 2, name: "Piece", factor: "1" }],
  });
});
it("loads the real stock as the initial target and requires an intentional edit", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ProductDetail id={7} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
  const input = await screen.findByRole("spinbutton", {
    name: "Cantidad final",
  });
  expect(input).toHaveProperty("value", "3");
  expect(
    screen.getByRole("button", { name: "Actualizar stock" }),
  ).toHaveProperty("disabled", true);
  await userEvent.clear(input);
  await userEvent.type(input, "5");
  await userEvent.click(
    screen.getByRole("button", { name: "Actualizar stock" }),
  );
  expect(api.adjustCatalogStock).toHaveBeenCalledOnce();
  expect(api.adjustCatalogStock).toHaveBeenCalledWith(7, "5", "3");
});

it("offers one stock control and sets the remaining total without a separate consumption form", async () => {
  renderWithClient(<ProductDetail id={7} onClose={vi.fn()} />);
  const input = await screen.findByLabelText("Cantidad final");
  expect(
    screen.queryByRole("heading", { name: "Consumir producto" }),
  ).toBeNull();
  expect(screen.queryByRole("button", { name: "Consumir" })).toBeNull();
  expect(screen.queryByLabelText("Cantidad a consumir")).toBeNull();
  await userEvent.clear(input);
  await userEvent.type(input, "2");
  await userEvent.click(
    screen.getByRole("button", { name: "Actualizar stock" }),
  );
  expect(api.adjustCatalogStock).toHaveBeenCalledExactlyOnceWith(7, "2", "3");
});

it("keeps the original expected stock when a background refresh changes the product", async () => {
  const { client } = renderWithClient(
    <ProductDetail id={7} onClose={vi.fn()} />,
  );
  const input = await screen.findByLabelText("Cantidad final");
  await userEvent.clear(input);
  await userEvent.type(input, "5");
  act(() =>
    client.setQueryData(["product", 7], {
      ...client.getQueryData<api.CatalogProduct>(["product", 7])!,
      stock_amount: "4",
    }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Actualizar stock" }),
  );
  expect(api.adjustCatalogStock).toHaveBeenCalledWith(7, "5", "3");
});

it("disables stock writes and archiving when the product cannot be verified", async () => {
  vi.mocked(api.getCatalogProduct).mockRejectedValue(new Error("Sin conexión"));
  renderWithClient(<ProductDetail id={7} onClose={vi.fn()} />);
  await screen.findByText("No se pudo verificar el stock.", { exact: false });
  expect(
    screen.getByRole("button", { name: "Actualizar stock" }),
  ).toHaveProperty("disabled", true);
  expect(
    screen.getByRole("button", { name: "Archivar producto" }),
  ).toHaveProperty("disabled", true);
  expect(api.setCatalogProductActive).not.toHaveBeenCalled();
});

it("rejects invalid variants and retains their details when barcode ownership conflicts", async () => {
  vi.mocked(api.saveProductVariant).mockRejectedValue(
    new Error("Código asociado a otro producto"),
  );
  renderWithClient(<ProductDetail id={7} onClose={vi.fn()} />);
  await userEvent.click(
    await screen.findByRole("button", { name: "+ Añadir variante" }),
  );
  await userEvent.type(
    screen.getByLabelText("Nombre de la variante"),
    "Leche entera",
  );
  await userEvent.type(
    screen.getByLabelText("Supermercado"),
    "Tienda de prueba",
  );
  expect(
    screen.getByRole("button", { name: "Guardar variante" }),
  ).toHaveProperty("disabled", true);
  await userEvent.type(
    screen.getByLabelText("Código de barras", { exact: true }),
    "8412345678901",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar variante" }),
  );
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Código asociado a otro producto",
  );
  expect(screen.getByLabelText("Supermercado")).toHaveProperty(
    "value",
    "Tienda de prueba",
  );
  expect(api.saveProductVariant).toHaveBeenCalledWith(
    7,
    expect.objectContaining({ barcode: "8412345678901", name: "Leche entera" }),
  );
});

it("keeps an existing variant barcode immutable during editing", async () => {
  vi.mocked(api.getProductVariants).mockResolvedValue({
    product: { id: 7, name: "Leche" },
    variants: [
      {
        barcode: "8412345678901",
        name: "Leche entera",
        supermarket: "Tienda",
        brand: "Marca",
        units_per_purchase: 1,
      },
    ],
  });
  renderWithClient(<ProductDetail id={7} onClose={vi.fn()} />);
  await userEvent.click(
    await screen.findByRole("button", { name: /^Editar$/ }),
  );
  expect(
    screen.getByLabelText("Código de barras", { exact: true }),
  ).toHaveProperty("readOnly", true);
});

it("saves a barcode once when advisory photo discovery fails", async () => {
  vi.mocked(api.saveCatalogBarcode).mockResolvedValue({});
  vi.mocked(api.saveDiscoveredPhoto).mockRejectedValue(
    new Error("Proveedor caído"),
  );
  renderWithClient(<ProductDetail id={7} onClose={vi.fn()} />);
  await userEvent.type(
    await screen.findByLabelText("Asociar nuevo código"),
    "8412345678901",
  );
  await userEvent.click(screen.getByRole("button", { name: "Guardar código" }));
  await screen.findByText(/Código guardado. No se pudo buscar la foto/);
  expect(api.saveCatalogBarcode).toHaveBeenCalledExactlyOnceWith(
    7,
    "8412345678901",
    undefined,
  );
  expect(screen.getByLabelText("Asociar nuevo código")).toHaveProperty(
    "value",
    "",
  );
});
