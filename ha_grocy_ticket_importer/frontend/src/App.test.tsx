import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { App } from "./App";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";
import type { ShoppingResponse } from "./types";

vi.mock("./api", async (original) => ({
  ...(await original<typeof api>()),
  getAuthStatus: vi.fn(),
  getShopping: vi.fn(),
  toggleShopping: vi.fn(),
  removeShopping: vi.fn(),
  chooseAlexaMatch: vi.fn(),
  logoutStandalone: vi.fn(),
  getInventory: vi.fn(),
  getArchivedProducts: vi.fn(),
}));
const shopping: ShoppingResponse = {
  items: [
    {
      id: 12,
      name: "Leche",
      amount: 1,
      unit: "ud.",
      done: false,
      product_id: null,
      image_url: null,
    },
  ],
  pending_matches: [],
  shopping_error: false,
  pending_matches_error: false,
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getAuthStatus).mockResolvedValue({
    authenticated: true,
    ingress: false,
    csrf_token: "fixture",
  });
  vi.mocked(api.getShopping).mockResolvedValue(shopping);
  vi.mocked(api.getInventory).mockResolvedValue({ items: [] });
  vi.mocked(api.getArchivedProducts).mockResolvedValue({ items: [] });
});

it("keeps creation only in the pantry and loads archives only through Actions", async () => {
  renderWithClient(<App />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Mi despensa" }),
  );
  expect(screen.getByRole("button", { name: "Nuevo producto" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Ver archivados" })).toBeNull();
  expect(api.getArchivedProducts).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Acciones" }));
  expect(
    screen.queryByRole("button", {
      name: /Nuevo producto|Añadir.*producto|Gestionar productos/,
    }),
  ).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Productos archivados" }),
  );
  await screen.findByRole("heading", { name: "Productos archivados" });
  await waitFor(() => expect(api.getArchivedProducts).toHaveBeenCalledOnce());
  expect(screen.queryByRole("button", { name: "Nuevo producto" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Mi despensa" }));
  await screen.findByRole("heading", { name: "Mi despensa" });
  expect(screen.getByRole("button", { name: "Nuevo producto" })).toBeTruthy();
});

it("blocks conflicting row actions until a write settles and preserves the row on failure", async () => {
  const pending = deferred<unknown>();
  vi.mocked(api.toggleShopping).mockReturnValue(pending.promise);
  renderWithClient(<App />);
  await userEvent.dblClick(
    await screen.findByRole("button", { name: "✓ Comprado" }),
  );
  expect(api.toggleShopping).toHaveBeenCalledExactlyOnceWith(12, true);
  expect(screen.getByRole("button", { name: "Quitar Leche" })).toHaveProperty(
    "disabled",
    true,
  );
  await act(async () => pending.reject(new Error("Comprueba la lista")));
  await screen.findByRole("alert");
  expect(screen.getByText("Leche")).toBeTruthy();
  expect(api.removeShopping).not.toHaveBeenCalled();
});

it("retries a failed shopping read without issuing a mutation", async () => {
  vi.mocked(api.getShopping).mockRejectedValueOnce(new Error("Sin conexión"));
  renderWithClient(<App />);
  const alert = await screen.findByRole("alert");
  await userEvent.click(
    within(alert).getByRole("button", { name: "Reintentar" }),
  );
  await screen.findByText("Leche");
  expect(api.getShopping).toHaveBeenCalledTimes(2);
  expect(api.toggleShopping).not.toHaveBeenCalled();
});

it("clears private cached data on session expiry and never restores a late shopping response", async () => {
  const pending = deferred<ShoppingResponse>();
  vi.mocked(api.getShopping).mockReturnValue(pending.promise);
  const { client } = renderWithClient(<App />);
  await waitFor(() => expect(api.getShopping).toHaveBeenCalledOnce());
  client.setQueryData(["inventory"], { items: [{ name: "Private fixture" }] });
  vi.mocked(api.getAuthStatus).mockResolvedValue({
    authenticated: false,
    ingress: false,
    csrf_token: "anonymous",
  });
  act(() => window.dispatchEvent(new Event("despensa:session-expired")));
  await screen.findByRole("heading", { name: "Iniciar sesión" });
  await act(async () => pending.resolve(shopping));
  expect(screen.queryByText("Leche")).toBeNull();
  expect(client.getQueryData(["inventory"])).toBeUndefined();
  expect(client.getQueryData(["shopping"])).toBeUndefined();
});

it("keeps an ambiguous Alexa suggestion visible after a stale choice is rejected", async () => {
  vi.mocked(api.getShopping).mockResolvedValue({
    ...shopping,
    pending_matches: [
      {
        key: "leche",
        name: "Leche",
        candidates: [{ id: 7, name: "Leche entera" }],
      },
    ],
  });
  vi.mocked(api.chooseAlexaMatch).mockRejectedValue(
    new Error("La sugerencia ha cambiado"),
  );
  renderWithClient(<App />);
  await userEvent.click(
    await screen.findByText("Elegir producto para «Leche»"),
  );
  await userEvent.selectOptions(
    screen.getByLabelText("Producto sugerido"),
    "7",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Guardar elección" }),
  );
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Producto sugerido")).toHaveProperty(
    "value",
    "7",
  );
  expect(api.chooseAlexaMatch).toHaveBeenCalledExactlyOnceWith("leche", 7);
});

it("shows login and clears private queries immediately after logout", async () => {
  vi.mocked(api.logoutStandalone).mockResolvedValue(undefined);
  const { client } = renderWithClient(<App />);
  await screen.findByText("Leche");
  client.setQueryData(["product", 7], { name: "Private fixture" });
  await userEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));
  await screen.findByRole("heading", { name: "Iniciar sesión" });
  expect(screen.queryByText("Leche")).toBeNull();
  expect(client.getQueryData(["product", 7])).toBeUndefined();
});
