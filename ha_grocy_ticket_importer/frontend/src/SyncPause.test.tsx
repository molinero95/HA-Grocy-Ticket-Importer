import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SyncPause } from "./SyncPause";
import type { ShoppingResponse } from "./types";

const health: NonNullable<ShoppingResponse["sync"]> = {
  state: "error", paused: true, reason: "unavailable",
  // A server one day behind the phone must not put yesterday in the notice.
  next_retry_at: Date.parse("2026-11-09T11:02:39+01:00") / 1000,
  retry_after_seconds: 120,
};
beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date("2026-11-10T11:00:39+01:00")); });
afterEach(() => vi.useRealTimers());

it("shows a relative wait with a server one day behind and expires without another read", () => {
  render(<SyncPause sync={health} receivedAt={Date.now()} />);
  expect(screen.getByText(/Reintentará en 2 min/)).toBeTruthy();
  expect(screen.queryByText(/9\/11|Próximo intento/)).toBeNull();
  act(() => vi.advanceTimersByTime(61_000));
  expect(screen.getByText(/Reintentará en 1 min/)).toBeTruthy();
  act(() => vi.advanceTimersByTime(60_000));
  expect(screen.getByText(/El plazo de pausa de Alexa ha terminado/)).toBeTruthy();
  expect(screen.queryByText(/en pausa automática/)).toBeNull();
});

it("does not restart an old cached pause when the user returns the following day", () => {
  render(<SyncPause sync={health} receivedAt={Date.now() - 86_400_000} />);
  expect(screen.getByText(/El plazo de pausa de Alexa ha terminado/)).toBeTruthy();
});

it("rebases only on a fresh response and cleans up its timer", () => {
  const start = Date.now();
  const view = render(<SyncPause sync={health} receivedAt={start} />);
  act(() => vi.advanceTimersByTime(61_000));
  view.rerender(<SyncPause sync={{ ...health, retry_after_seconds: 59 }} receivedAt={Date.now()} />);
  expect(screen.getByText(/Reintentará en 1 min/)).toBeTruthy();
  act(() => vi.advanceTimersByTime(59_000));
  expect(screen.getByText(/El plazo de pausa de Alexa ha terminado/)).toBeTruthy();
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
});

it.each([undefined, NaN, Infinity, -1, 86400])("handles missing or invalid duration %s without trusting a server date", duration => {
  render(<SyncPause sync={{ ...health, retry_after_seconds: duration }} receivedAt={Date.now()} />);
  expect(screen.getByText(/Tiempo restante sin confirmar/)).toBeTruthy();
  expect(screen.queryByText(/9\/11|Próximo intento/)).toBeNull();
});
