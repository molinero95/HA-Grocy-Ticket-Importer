import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ProductConsumption } from "./ProductConsumption";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";

vi.mock("./api", () => ({ consumeCatalogProduct: vi.fn() }));
beforeEach(() => vi.resetAllMocks());

it.each(["0", "-1", "3.01", ""])(
  "blocks consumption of invalid quantity %j",
  async (value) => {
    renderWithClient(<ProductConsumption id={7} amount="3" unit="kg" />);
    const input = screen.getByLabelText("Cantidad a consumir");
    await userEvent.clear(input);
    if (value) await userEvent.type(input, value);
    expect(screen.getByRole("button", { name: "Consumir" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(api.consumeCatalogProduct).not.toHaveBeenCalled();
  },
);

it("submits the precise amount, expected stock and replenishment once despite double click", async () => {
  const pending =
    deferred<Awaited<ReturnType<typeof api.consumeCatalogProduct>>>();
  vi.mocked(api.consumeCatalogProduct).mockReturnValue(pending.promise);
  const { client } = renderWithClient(
    <ProductConsumption id={7} amount="3" unit="kg" />,
  );
  const invalidate = vi.spyOn(client, "invalidateQueries");
  await userEvent.clear(screen.getByLabelText("Cantidad a consumir"));
  await userEvent.type(screen.getByLabelText("Cantidad a consumir"), "0.25");
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.dblClick(screen.getByRole("button", { name: "Consumir" }));
  expect(api.consumeCatalogProduct).toHaveBeenCalledExactlyOnceWith(
    7,
    "0.25",
    "3",
    true,
    expect.any(String),
  );
  expect(screen.getByLabelText("Cantidad a consumir")).toHaveProperty(
    "disabled",
    true,
  );
  await act(async () =>
    pending.resolve({ shopping_error: false, shopping_added: true }),
  );
  expect(await screen.findByRole("status")).toHaveProperty(
    "textContent",
    "Consumo registrado.",
  );
  for (const key of [["product", 7], ["inventory"], ["shopping"]]) {
    expect(invalidate).toHaveBeenCalledWith({ queryKey: key });
  }
});

it("reports partial replenishment failure without offering another consumption", async () => {
  vi.mocked(api.consumeCatalogProduct).mockResolvedValue({
    shopping_error: true,
    shopping_added: false,
  });
  renderWithClient(<ProductConsumption id={7} amount="3" unit="Piece" />);
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Consumir" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("Stock consumido."),
  );
  expect(screen.getByRole("button", { name: "Consumir" })).toHaveProperty(
    "disabled",
    true,
  );
  expect(api.consumeCatalogProduct).toHaveBeenCalledTimes(1);
});

it("locks an uncertain operation and refreshes stock without automatically retrying", async () => {
  vi.mocked(api.consumeCatalogProduct).mockRejectedValue(
    new Error("Conexión interrumpida"),
  );
  const { client } = renderWithClient(
    <ProductConsumption id={7} amount="3" unit="Piece" />,
  );
  const invalidate = vi.spyOn(client, "invalidateQueries");
  await userEvent.click(screen.getByRole("button", { name: "Consumir" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("Comprueba el stock"),
  );
  await userEvent.click(screen.getByRole("button", { name: "Consumir" }));
  await waitFor(() =>
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["product", 7] }),
  );
  expect(api.consumeCatalogProduct).toHaveBeenCalledTimes(1);
});
