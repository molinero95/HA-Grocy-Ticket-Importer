import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Inventory } from "./Inventory";
import * as api from "./api";
vi.mock("./api", async (original) => ({
  ...(await original<typeof api>()),
  getInventory: vi.fn(),
  getArchivedProducts: vi.fn(),
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
function mount(archived = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <Inventory archived={archived} />
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


it("marks zero stock even when it is already in the shopping list, and leaves stocked rows neutral", async () => {
  vi.mocked(api.getInventory).mockResolvedValue({ items: [{ ...rows[0], amount: "0.00", shopping_amount: "2" }, rows[1]] });
  mount();
  const empty = (await screen.findByText(rows[0].name)).closest("article")!;
  expect(empty.classList.contains("out-of-stock")).toBe(true);
  expect(empty.textContent).toContain("Sin existencias");
  expect(screen.getByText("Leche").closest("article")!.classList.contains("out-of-stock")).toBe(false);
});
it("keeps archived rows neutral and does not label them as missing stock", async () => {
  vi.mocked(api.getArchivedProducts).mockResolvedValue({ items: [{ ...rows[0], amount: "0" }] });
  mount(true);
  const row = (await screen.findByText(rows[0].name)).closest("article")!;
  expect(row.classList.contains("out-of-stock")).toBe(false);
  expect(screen.queryByText("Sin existencias")).toBeNull();
  expect(screen.queryByRole("combobox", { name: "Filtrar productos" })).toBeNull();
});
it("does not turn unknown stock into a zero-stock warning", async () => {
  vi.mocked(api.getInventory).mockResolvedValue({ items: [{ ...rows[0], amount: "?" }] });
  mount();
  await screen.findByText(rows[0].name);
  expect(screen.queryByText("Sin existencias")).toBeNull();
});

it("marks a positive amount at its per-product threshold as low stock", async () => {
  vi.mocked(api.getInventory).mockResolvedValue({ items: [{ ...rows[0], amount: "2", stock_threshold: "2" }, { ...rows[1], amount: "3", stock_threshold: "2" }] });
  mount();
  const low = (await screen.findByText(rows[0].name)).closest("article")!;
  expect(low.classList.contains("out-of-stock")).toBe(true);
  expect(low.textContent).toContain("Stock bajo");
  expect(screen.queryByText("Sin existencias")).toBeNull();
  expect(screen.getByText("Leche").closest("article")!.classList.contains("out-of-stock")).toBe(false);
});

it("keeps a product with warnings disabled neutral even at zero stock", async () => {
  vi.mocked(api.getInventory).mockResolvedValue({items: [{...rows[0], amount: "0", stock_threshold: "3", stock_warning_enabled: false}]});
  mount();
  const row = (await screen.findByText(rows[0].name)).closest("article")!;
  expect(row.classList.contains("out-of-stock")).toBe(false);
  expect(screen.queryByText("Sin existencias")).toBeNull();
  expect(screen.queryByText("Stock bajo")).toBeNull();
});

it("filters low stock using thresholds, excluding disabled warnings and unknown quantities", async () => {
  vi.mocked(api.getInventory).mockResolvedValue({ items: [
    { ...rows[0], amount: "2", stock_threshold: "2" },
    { ...rows[1], amount: "0" },
    { ...rows[0], id: 3, name: "Sin avisos", amount: "0", stock_warning_enabled: false },
    { ...rows[0], id: 4, name: "Desconocido", amount: "?" },
    { ...rows[0], id: 5, name: "Suficiente", amount: "3", stock_threshold: "2" },
  ] });
  mount();
  await screen.findByText("Suficiente");
  const user = userEvent.setup();
  await user.selectOptions(screen.getByRole("combobox", { name: "Filtrar productos" }), "low-stock");
  expect(screen.getByText("2 artículos")).toBeTruthy();
  expect(screen.getByText(rows[0].name)).toBeTruthy();
  expect(screen.getByText("Leche")).toBeTruthy();
  for (const name of ["Sin avisos", "Desconocido", "Suficiente"]) expect(screen.queryByText(name)).toBeNull();
  await user.click(screen.getByRole("button", { name: "Quitar filtro" }));
  expect(screen.getByText("5 artículos")).toBeTruthy();
  expect(api.getInventory).toHaveBeenCalledTimes(1);
  expect(api.stepShopping).not.toHaveBeenCalled();
});

it("combines shopping status with name and barcode search and clears only the status", async () => {
  vi.mocked(api.lookupBarcode).mockResolvedValue(1);
  mount();
  await screen.findByText("Leche");
  const user = userEvent.setup();
  const filter = screen.getByRole("combobox", { name: "Filtrar productos" });
  const search = screen.getByRole("textbox", { name: "Buscar por nombre o código de barras" });
  await user.selectOptions(filter, "shopping");
  expect(screen.queryByText(rows[0].name)).toBeNull();
  expect(screen.getByText("1 artículos")).toBeTruthy();
  await user.type(search, "tomate");
  expect(screen.getByText("Sin resultados")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Quitar filtro" }));
  expect(search).toHaveProperty("value", "tomate");
  expect(screen.getByText(rows[0].name)).toBeTruthy();
  await user.clear(search);
  await user.type(search, "8412345678901");
  await screen.findByText(rows[0].name);
  await user.selectOptions(filter, "shopping");
  expect(screen.getByText("Sin resultados")).toBeTruthy();
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("refreshes the active shopping filter after removing the last shopping quantity", async () => {
  let removed = false;
  vi.mocked(api.getInventory).mockImplementation(async () => ({ items: [
    { ...rows[1], shopping_amount: removed ? "0" : "1" },
  ] }));
  vi.mocked(api.stepShopping).mockImplementation(async () => { removed = true; });
  mount();
  await screen.findByText("Leche");
  const user = userEvent.setup();
  await user.selectOptions(screen.getByRole("combobox", { name: "Filtrar productos" }), "shopping");
  await user.click(screen.getByRole("button", { name: "Quitar de compra: Leche" }));
  expect(await screen.findByText("Sin resultados")).toBeTruthy();
  expect(screen.getByRole("combobox", { name: "Filtrar productos" })).toHaveProperty("value", "shopping");
  expect(api.stepShopping).toHaveBeenCalledExactlyOnceWith(2, "minus");
});
