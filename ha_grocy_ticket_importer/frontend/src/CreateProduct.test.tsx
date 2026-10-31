import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { CreateProduct } from "./CreateProduct";
import * as api from "./api";
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
