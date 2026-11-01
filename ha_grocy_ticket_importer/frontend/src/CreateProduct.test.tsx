import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { CreateProduct } from "./CreateProduct";
import * as api from "./api";
import { deferred } from "./test/helpers";
vi.mock("./api", async (original) => ({
  ...(await original<typeof api>()),
  getCatalogUnits: vi.fn(),
  createCatalogProduct: vi.fn(),
  saveDiscoveredPhoto: vi.fn(),
  lookupPhoto: vi.fn(),
}));
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getCatalogUnits).mockResolvedValue([
    { id: 2, name: "Piece" },
    { id: 3, name: "Pack" },
  ]);
  vi.mocked(api.lookupPhoto).mockResolvedValue({ photo: null });
});

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
