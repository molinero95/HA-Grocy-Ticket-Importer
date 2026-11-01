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
  removeAlexaMatch: vi.fn(),
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
  expect(api.chooseAlexaMatch).toHaveBeenCalledExactlyOnceWith(
    "leche",
    7,
    expect.any(String),
  );
});

it.each([7, 0])(
  "saving suggestion %i immediately yields a row with bought/remove controls",
  async (productId) => {
    let saved = false;
    vi.mocked(api.getShopping).mockImplementation(async () =>
      saved
        ? {
            ...shopping,
            items: [
              {
                ...shopping.items[0],
                name: productId ? "Leche entera" : "Leche",
              },
            ],
            pending_matches: [],
          }
        : {
            ...shopping,
            items: [],
            pending_matches: [
              {
                key: "leche",
                name: "Leche",
                candidates: [{ id: 7, name: "Leche entera" }],
              },
            ],
          },
    );
    vi.mocked(api.chooseAlexaMatch).mockImplementation(async () => {
      saved = true;
      return { ok: true, item_id: 12 };
    });
    renderWithClient(<App />);
    expect(
      await screen.findByRole("button", { name: "Quitar Leche" }),
    ).toBeTruthy();
    await userEvent.click(screen.getByText("Elegir producto para «Leche»"));
    if (productId)
      await userEvent.selectOptions(
        screen.getByLabelText("Producto sugerido"),
        "7",
      );
    await userEvent.dblClick(
      screen.getByRole("button", {
        name: productId ? "Guardar elección" : "Mantener original",
      }),
    );
    await screen.findByRole("button", { name: "✓ Comprado" });
    await screen.findByRole("button", {
      name: productId ? "Quitar Leche entera" : "Quitar Leche",
    });
    expect(await screen.findByRole("status")).toHaveProperty(
      "textContent",
      expect.stringContaining("Artículo guardado en la lista"),
    );
    expect(api.chooseAlexaMatch).toHaveBeenCalledExactlyOnceWith(
      "leche",
      productId,
      expect.any(String),
    );
  },
);

it("can remove an unresolved suggestion without opening it or choosing a product", async () => {
  let removed = false;
  vi.mocked(api.getShopping).mockImplementation(async () => ({
    ...shopping,
    items: [],
    pending_matches: removed
      ? []
      : [
          {
            key: "leche",
            name: "Leche",
            candidates: [{ id: 7, name: "Leche entera" }],
          },
        ],
  }));
  vi.mocked(api.removeAlexaMatch).mockImplementation(async () => {
    removed = true;
    return { ok: true };
  });
  renderWithClient(<App />);
  await userEvent.dblClick(
    await screen.findByRole("button", { name: "Quitar Leche" }),
  );
  await screen.findByText("Tu lista de la compra está vacía.");
  expect(api.removeAlexaMatch).toHaveBeenCalledExactlyOnceWith("leche");
  expect(api.chooseAlexaMatch).not.toHaveBeenCalled();
});

it("retains unresolved items and their remove action when saving or removal fails", async () => {
  vi.mocked(api.getShopping).mockResolvedValue({
    ...shopping,
    items: [],
    pending_matches: [
      {
        key: "leche",
        name: "Leche",
        candidates: [{ id: 7, name: "Leche entera" }],
      },
    ],
  });
  vi.mocked(api.removeAlexaMatch).mockRejectedValue(
    new Error("No se pudo confirmar la eliminación"),
  );
  renderWithClient(<App />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Quitar Leche" }),
  );
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Quitar Leche" })).toHaveProperty(
    "disabled",
    false,
  );
  expect(screen.getByText("Elegir producto para «Leche»")).toBeTruthy();
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

it("explains a blocked Alexa cycle and offers explicit exact-note association", async () => {
  vi.mocked(api.getShopping).mockResolvedValue({
    ...shopping,
    items: [{ ...shopping.items[0], name: "Leche entera", amount: 2.5 }],
    pending_matches: [{ key: "leche entera", name: "Leche entera", candidates: [{ id: 7, name: "Leche entera" }], requires_product: true }],
    sync: { state: "error", reason: "note_conflict" },
  });
  vi.mocked(api.chooseAlexaMatch).mockResolvedValue({});
  renderWithClient(<App />);
  expect(await screen.findByText(/Alexa no se ha sincronizado: hay artículos de texto/)).toBeTruthy();
  await userEvent.click(screen.getByText("Elegir producto para «Leche entera»"));
  expect(screen.queryByRole("option", { name: "Mantener artículo original" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Guardar elección" }));
  expect(api.chooseAlexaMatch).toHaveBeenCalledExactlyOnceWith("leche entera", 7, expect.any(String));
});
