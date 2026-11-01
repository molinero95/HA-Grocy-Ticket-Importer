import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { FullscreenAction } from "./FullscreenAction";
afterEach(() => vi.restoreAllMocks());
it("reports when an embedded host denies fullscreen", async () => {
  Object.defineProperty(document, "fullscreenEnabled", { configurable: true, get: () => false });
  render(<FullscreenAction />);
  await userEvent.click(screen.getByRole("button", { name: "Pantalla completa" }));
  expect((await screen.findByRole("status")).textContent).toContain("no permite pantalla completa");
});
it("requests fullscreen from a click and follows the browser's exit event", async () => {
  Object.defineProperty(document, "fullscreenEnabled", { configurable: true, get: () => true });
  const request = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(document.documentElement, "requestFullscreen", { configurable: true, value: request });
  render(<FullscreenAction />);
  await userEvent.click(screen.getByRole("button", { name: "Pantalla completa" }));
  expect(request).toHaveBeenCalledOnce();
  Object.defineProperty(document, "fullscreenElement", { configurable: true, value: document.documentElement });
  act(() => document.dispatchEvent(new Event("fullscreenchange")));
  expect(screen.getByRole("button", { name: "Salir de pantalla completa" })).toBeTruthy();
  Object.defineProperty(document, "fullscreenElement", { configurable: true, value: null });
  act(() => document.dispatchEvent(new Event("fullscreenchange")));
  expect(screen.getByRole("button", { name: "Pantalla completa" })).toBeTruthy();
});
