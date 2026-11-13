import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { deferred, renderWithClient } from "./test/helpers";
import { ClearCompletedAlexa } from "./ClearCompletedAlexa";
import * as api from "./api";
vi.mock("./api", () => ({ clearCompletedAlexa: vi.fn() }));
beforeEach(() => { vi.resetAllMocks(); vi.spyOn(window, "confirm").mockReturnValue(true); });

it("cleans only after confirmation and suppresses double clicks", async () => {
  const pending = deferred<{ok: boolean}>();
  vi.mocked(api.clearCompletedAlexa).mockReturnValue(pending.promise);
  renderWithClient(<ClearCompletedAlexa />);
  await userEvent.dblClick(screen.getByRole("button", { name: "Limpiar completados de Alexa" }));
  expect(api.clearCompletedAlexa).toHaveBeenCalledExactlyOnceWith(expect.any(String), expect.anything());
  expect(window.confirm).toHaveBeenCalledOnce();
  expect(screen.getByRole("button", { name: "Limpiando Alexa…" })).toHaveProperty("disabled", true);
  await act(async () => pending.resolve({ ok: true }));
  await screen.findByText("Completados de Alexa eliminados.");
});

it("keeps everything when the confirmation is cancelled", async () => {
  vi.mocked(window.confirm).mockReturnValue(false);
  renderWithClient(<ClearCompletedAlexa />);
  await userEvent.click(screen.getByRole("button", { name: "Limpiar completados de Alexa" }));
  expect(api.clearCompletedAlexa).not.toHaveBeenCalled();
});

it("does not retry an uncertain cleanup", async () => {
  vi.mocked(api.clearCompletedAlexa).mockRejectedValue(new Error("Failed to fetch"));
  renderWithClient(<ClearCompletedAlexa />);
  await userEvent.click(screen.getByRole("button", { name: "Limpiar completados de Alexa" }));
  await screen.findByText(/Limpieza sin confirmar/);
  await waitFor(() => expect(api.clearCompletedAlexa).toHaveBeenCalledTimes(1));
});
