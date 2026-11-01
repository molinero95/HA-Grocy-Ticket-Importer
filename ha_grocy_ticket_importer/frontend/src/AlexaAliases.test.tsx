import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { AlexaAliases } from "./AlexaAliases";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";

vi.mock("./api", () => ({
  getInventory: vi.fn(), getAlexaAliases: vi.fn(), saveAlexaAlias: vi.fn(), deleteAlexaAlias: vi.fn(),
}));
const item = (id: number, name: string) => ({
  id, name, amount: "0", unit: "Piece", image_url: null, shopping_amount: "0",
  shopping_step: "1", shopping_unit: "Piece", shopping_can_subtract: false,
});
const aliases = [
  { key: "leche", name: "Leche", product_id: 7 },
  { key: "bebida blanca", name: "Bebida blanca", product_id: 7 },
  { key: "rojo", name: "Rojo", product_id: 8 },
];
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getInventory).mockResolvedValue({ items: [item(7, "Leche entera"), item(8, "Tomate")] });
  vi.mocked(api.getAlexaAliases).mockResolvedValue({ aliases });
});

it("lists every alias for the selected product and guards deletion with its product ID", async () => {
  vi.mocked(api.deleteAlexaAlias).mockResolvedValue({});
  renderWithClient(<AlexaAliases />);
  await screen.findByRole("option", { name: "Leche entera" });
  await userEvent.selectOptions(screen.getByLabelText("Producto de Despensa"), "7");
  expect(await screen.findByRole("button", { name: "Eliminar alias Leche" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Eliminar alias Bebida blanca" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Eliminar alias Rojo" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Eliminar alias Leche" }));
  expect(api.deleteAlexaAlias).toHaveBeenCalledExactlyOnceWith("leche", 7);
});

it("locks the product and editor during save, then preserves errors without losing the name", async () => {
  const save = deferred<unknown>();
  vi.mocked(api.saveAlexaAlias).mockReturnValue(save.promise);
  renderWithClient(<AlexaAliases />);
  await screen.findByRole("option", { name: "Leche entera" });
  await userEvent.selectOptions(screen.getByLabelText("Producto de Despensa"), "7");
  await userEvent.click(screen.getByRole("button", { name: "Añadir nuevo alias" }));
  await userEvent.type(screen.getByLabelText("Nuevo nombre en Alexa"), "Leche normal");
  await userEvent.click(screen.getByRole("button", { name: "Guardar alias" }));
  expect(screen.getByLabelText("Producto de Despensa")).toHaveProperty("disabled", true);
  expect(screen.getByRole("button", { name: "Cancelar" })).toHaveProperty("disabled", true);
  await act(async () => save.reject(new Error("El alias pertenece a otro producto")));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Nuevo nombre en Alexa")).toHaveProperty("value", "Leche normal");
  await userEvent.selectOptions(screen.getByLabelText("Producto de Despensa"), "8");
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
});

it("allows removing stale aliases even when their product is absent from the selector", async () => {
  vi.mocked(api.getAlexaAliases).mockResolvedValue({ aliases: [{ key: "antiguo", name: "Antiguo", product_id: 99 }] });
  vi.mocked(api.deleteAlexaAlias).mockResolvedValue({});
  renderWithClient(<AlexaAliases />);
  await userEvent.click(await screen.findByRole("button", { name: "Eliminar alias Antiguo" }));
  expect(api.deleteAlexaAlias).toHaveBeenCalledExactlyOnceWith("antiguo", 99);
});
