import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Inventory } from "./Inventory";
import * as api from "./api";
vi.mock("./api", async (original) => ({
  ...(await original<typeof api>()),
  getInventory: vi.fn(),
  lookupBarcode: vi.fn(),
  stepShopping: vi.fn(),
}));
const rows = [
  {
    id: 1,
    name: "Tomáte de nombre muy largo",
    amount: "2",
    unit: "kg",
    image_url: null,
    shopping_amount: "0",
    shopping_unit: "kg",
    shopping_step: "0.1",
    shopping_can_subtract: false,
  },
  {
    id: 2,
    name: "Leche",
    amount: "3",
    unit: "ud.",
    image_url: null,
    shopping_amount: "1",
    shopping_unit: "ud.",
    shopping_step: "1",
    shopping_can_subtract: true,
  },
];
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <Inventory />
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getInventory).mockResolvedValue({ items: rows });
});
describe("inventory interactions", () => {
  it("changes cart to stepper and back in place after successful writes", async () => {
    let added = false;
    vi.mocked(api.getInventory).mockImplementation(async () => ({
      items: [
        {
          ...rows[0],
          shopping_amount: added ? "0.1" : "0",
          shopping_can_subtract: added,
        },
      ],
    }));
    vi.mocked(api.stepShopping).mockImplementation(async (_id, direction) => {
      added = direction === "plus";
    });
    mount();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", {
        name: "Añadir a compra: " + rows[0].name,
      }),
    );
    await user.click(
      await screen.findByRole("button", {
        name: "Quitar de compra: " + rows[0].name,
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", {
          name: "Quitar de compra: " + rows[0].name,
        }),
      ).toBeNull(),
    );
    expect(api.stepShopping).toHaveBeenNthCalledWith(1, 1, "plus");
    expect(api.stepShopping).toHaveBeenNthCalledWith(2, 1, "minus");
  });
  it("filters by typed barcode automatically without opening a product sheet", async () => {
    vi.mocked(api.lookupBarcode).mockResolvedValue(2);
    mount();
    expect(screen.queryByRole("button", { name: "Buscar" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "Abrir cámara para escanear" }),
    ).toBeTruthy();
    const user = userEvent.setup();
    await screen.findByText("Leche");
    await user.type(
      screen.getByRole("textbox", {
        name: "Buscar por nombre o código de barras",
      }),
      "8412345678901",
    );
    await waitFor(() => expect(screen.queryByText(rows[0].name)).toBeNull());
    expect(await screen.findByText("Leche")).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  it("ignores a late barcode response after switching to name search", async () => {
    let resolve!: (id: number) => void;
    vi.mocked(api.lookupBarcode).mockImplementation(
      () =>
        new Promise<number>((done) => {
          resolve = done;
        }),
    );
    mount();
    const user = userEvent.setup();
    const search = screen.getByRole("textbox", {
      name: "Buscar por nombre o código de barras",
    });
    await user.type(search, "8412345678901");
    await waitFor(() =>
      expect(api.lookupBarcode).toHaveBeenCalledWith("8412345678901"),
    );
    await user.clear(search);
    await user.type(search, "tomate");
    await act(async () => resolve(2));
    expect(screen.getByText(rows[0].name)).toBeTruthy();
    expect(screen.queryByText("Leche")).toBeNull();
  });
  it("keeps the cart and exposes an inline error after a failed write", async () => {
    vi.mocked(api.stepShopping).mockRejectedValue(
      new Error("Grocy no disponible"),
    );
    mount();
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", {
        name: "Añadir a compra: " + rows[0].name,
      }),
    );
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Grocy no disponible",
    );
    expect(
      screen.queryByRole("button", {
        name: "Quitar de compra: " + rows[0].name,
      }),
    ).toBeNull();
  });
});
