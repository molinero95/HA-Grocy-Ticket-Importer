import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { deferred, renderWithClient } from "./test/helpers";
import { ForceSync } from "./ForceSync";
import * as api from "./api";
vi.mock("./api", () => ({ forceShoppingSync: vi.fn() }));
beforeEach(() => vi.resetAllMocks());

it("dispatches one explicit attempt during a double click and refreshes health", async () => {
  const pending = deferred<{ok: boolean}>();
  vi.mocked(api.forceShoppingSync).mockReturnValue(pending.promise);
  const { client } = renderWithClient(<ForceSync />);
  const refresh = vi.spyOn(client, "invalidateQueries");
  await userEvent.dblClick(screen.getByRole("button", { name: "Forzar sincronización" }));
  expect(api.forceShoppingSync).toHaveBeenCalledExactlyOnceWith(expect.any(String));
  expect(screen.getByRole("button", { name: "Sincronizando…" })).toHaveProperty("disabled", true);
  await act(async () => pending.resolve({ ok: true }));
  await screen.findByText("Sincronización completada.");
  expect(refresh).toHaveBeenCalledWith({ queryKey: ["shopping"] });
});

it("does not retry a lost response and allows only a new explicit attempt after refresh", async () => {
  vi.mocked(api.forceShoppingSync).mockRejectedValue(new Error("Failed to fetch"));
  renderWithClient(<ForceSync />);
  await userEvent.click(screen.getByRole("button", { name: "Forzar sincronización" }));
  await screen.findByText(/No se ha confirmado la sincronización/);
  await waitFor(() => expect(api.forceShoppingSync).toHaveBeenCalledTimes(1));
  const firstId = vi.mocked(api.forceShoppingSync).mock.calls[0][0];
  await userEvent.click(screen.getByRole("button", { name: "Forzar sincronización" }));
  await waitFor(() => expect(api.forceShoppingSync).toHaveBeenCalledTimes(2));
  expect(vi.mocked(api.forceShoppingSync).mock.calls[1][0]).not.toBe(firstId);
});

it("cannot force a disabled sync", async () => {
  renderWithClient(<ForceSync disabled />);
  const button = screen.getByRole("button", { name: "Forzar sincronización" });
  expect(button).toHaveProperty("disabled", true);
  await userEvent.click(button);
  expect(api.forceShoppingSync).not.toHaveBeenCalled();
});
