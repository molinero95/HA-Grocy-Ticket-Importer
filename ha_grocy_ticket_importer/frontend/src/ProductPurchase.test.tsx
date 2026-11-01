import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ProductPurchase } from "./ProductPurchase";
import * as api from "./api";
import { renderWithClient } from "./test/helpers";

vi.mock("./api", () => ({ savePurchaseConfiguration: vi.fn() }));
const product: api.CatalogProduct = {
  id: 7,
  name: "Leche",
  unit_id: 2,
  purchase_unit_id: 9,
  stock_amount: "3",
  image_url: null,
  is_pack: true,
  pack_size: 5,
  barcodes: [],
  units: [
    { id: 2, name: "Piece" },
    { id: 9, name: "Pack" },
    { id: 12, name: "Kilogram" },
  ],
};
beforeEach(() => vi.resetAllMocks());

it.each(["0", "1.5", "1001", ""])(
  "rejects invalid purchase factor %j",
  async (factor) => {
    renderWithClient(<ProductPurchase product={product} onSaved={vi.fn()} />);
    const input = screen.getByLabelText("Piezas por pack");
    await userEvent.clear(input);
    if (factor) await userEvent.type(input, factor);
    expect(
      screen.getByRole("button", { name: "Guardar unidad de compra" }),
    ).toHaveProperty("disabled", true);
    expect(api.savePurchaseConfiguration).not.toHaveBeenCalled();
  },
);

it("requires a change, limits compatible units and sends the expected original configuration", async () => {
  const onSaved = vi.fn().mockResolvedValue(undefined);
  vi.mocked(api.savePurchaseConfiguration).mockResolvedValue({});
  renderWithClient(<ProductPurchase product={product} onSaved={onSaved} />);
  expect(
    screen.getByRole("button", { name: "Guardar unidad de compra" }),
  ).toHaveProperty("disabled", true);
  expect(screen.queryByRole("option", { name: "Kilogram" })).toBeNull();
  await userEvent.clear(screen.getByLabelText("Piezas por pack"));
  await userEvent.type(screen.getByLabelText("Piezas por pack"), "6");
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar unidad de compra" }),
  );
  expect(api.savePurchaseConfiguration).toHaveBeenCalledExactlyOnceWith(
    7,
    9,
    "6",
    { unit_id: 2, purchase_unit_id: 9, factor: 5 },
    expect.any(String),
  );
  expect(onSaved).toHaveBeenCalledOnce();
});

it("resets the purchase factor to one when switching to the stock unit", async () => {
  vi.mocked(api.savePurchaseConfiguration).mockResolvedValue({});
  renderWithClient(<ProductPurchase product={product} onSaved={vi.fn()} />);
  await userEvent.selectOptions(
    screen.getByLabelText("Unidad para comprar"),
    "2",
  );
  expect(screen.queryByLabelText("Piezas por pack")).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar unidad de compra" }),
  );
  expect(api.savePurchaseConfiguration).toHaveBeenCalledWith(
    7,
    2,
    "1",
    expect.any(Object),
    expect.any(String),
  );
});

it("locks conflicting or uncertain changes and tells the user to verify configuration", async () => {
  vi.mocked(api.savePurchaseConfiguration).mockRejectedValue(
    new Error("La configuración ha cambiado"),
  );
  const onSaved = vi.fn();
  renderWithClient(<ProductPurchase product={product} onSaved={onSaved} />);
  await userEvent.selectOptions(
    screen.getByLabelText("Unidad para comprar"),
    "2",
  );
  await userEvent.dblClick(
    screen.getByRole("button", { name: "Guardar unidad de compra" }),
  );
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("comprobar la configuración"),
  );
  expect(api.savePurchaseConfiguration).toHaveBeenCalledTimes(1);
  expect(onSaved).not.toHaveBeenCalled();
  expect(
    screen.getByRole("button", { name: "Guardar unidad de compra" }),
  ).toHaveProperty("disabled", true);
});
