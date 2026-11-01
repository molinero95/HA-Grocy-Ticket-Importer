import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { ProductDetail } from "./ProductDetail";
import * as api from "./api";
vi.mock("./api", async (original) => ({
  ...(await original<typeof api>()),
  getCatalogProduct: vi.fn(),
  getProductVariants: vi.fn(),
  getCatalogBarcodes: vi.fn(),
  adjustCatalogStock: vi.fn(),
}));
it("loads the real stock as the initial target and requires an intentional edit", async () => {
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
