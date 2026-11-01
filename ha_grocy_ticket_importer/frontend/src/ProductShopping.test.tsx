import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ProductShopping } from "./ProductShopping";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";

vi.mock("./api", () => ({
  getShoppingOptions: vi.fn(),
  addShoppingAmount: vi.fn(),
}));
const options = {
  id: 7,
  name: "Leche",
  units: [
    { id: 2, name: "Piece", factor: "1" },
    { id: 9, name: "Pack", factor: "5" },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getShoppingOptions).mockResolvedValue(options);
});

it("requires verified units before permitting a purchase", async () => {
  const pending = deferred<typeof options>();
  vi.mocked(api.getShoppingOptions).mockReturnValue(pending.promise);
  renderWithClient(<ProductShopping id={7} />);
  expect(
    screen.getByRole("button", { name: "Añadir cantidad" }),
  ).toHaveProperty("disabled", true);
  await act(async () => pending.reject(new Error("Sin conexión")));
  await screen.findByRole("alert");
  expect(
    screen.getByRole("button", { name: "Añadir cantidad" }),
  ).toHaveProperty("disabled", true);
  vi.mocked(api.getShoppingOptions).mockResolvedValue(options);
  await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  await screen.findByRole("option", { name: "Pack" });
  expect(
    screen.getByRole("button", { name: "Añadir cantidad" }),
  ).toHaveProperty("disabled", false);
});

it("sends purchase units without converting packs twice and blocks double click", async () => {
  const pending = deferred<unknown>();
  vi.mocked(api.addShoppingAmount).mockReturnValue(pending.promise);
  const { client } = renderWithClient(<ProductShopping id={7} />);
  const invalidate = vi.spyOn(client, "invalidateQueries");
  await screen.findByRole("option", { name: "Pack" });
  await userEvent.selectOptions(
    screen.getByLabelText("Unidad de la cantidad"),
    "9",
  );
  await userEvent.clear(screen.getByLabelText("Cantidad para comprar"));
  await userEvent.type(screen.getByLabelText("Cantidad para comprar"), "2");
  await userEvent.dblClick(
    screen.getByRole("button", { name: "Añadir cantidad" }),
  );
  expect(api.addShoppingAmount).toHaveBeenCalledExactlyOnceWith(
    7,
    "2",
    9,
    expect.any(String),
  );
  await act(async () => pending.resolve({}));
  await screen.findByRole("status");
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["shopping"] });
});

it("keeps the submitted quantity locked after a lost response", async () => {
  vi.mocked(api.addShoppingAmount).mockRejectedValue(
    new Error("Comprueba la lista antes de reintentar"),
  );
  renderWithClient(<ProductShopping id={7} />);
  await screen.findByRole("option", { name: "Piece" });
  await userEvent.click(
    screen.getByRole("button", { name: "Añadir cantidad" }),
  );
  await screen.findByRole("alert");
  expect(
    screen.getByRole("button", { name: "Añadir cantidad" }),
  ).toHaveProperty("disabled", true);
  expect(screen.getByLabelText("Unidad de la cantidad")).toHaveProperty(
    "disabled",
    true,
  );
  expect(api.addShoppingAmount).toHaveBeenCalledTimes(1);
});
