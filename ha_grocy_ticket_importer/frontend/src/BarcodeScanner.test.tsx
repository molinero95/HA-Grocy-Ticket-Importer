import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { BarcodeScanner } from "./BarcodeScanner";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
it("offers manual entry when BarcodeDetector is unavailable", async () => {
  vi.stubGlobal("BarcodeDetector", undefined);
  render(<BarcodeScanner onDetect={vi.fn()} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Abrir cámara para escanear" }),
  );
  expect(screen.getByRole("alert").textContent).toContain(
    "Introduce el código manualmente",
  );
});
it("stops a late camera stream after the dialog is closed", async () => {
  const stop = vi.fn();
  let resolve!: (stream: MediaStream) => void;
  const getUserMedia = vi.fn(
    () =>
      new Promise<MediaStream>((done) => {
        resolve = done;
      }),
  );
  vi.stubGlobal(
    "BarcodeDetector",
    class {
      detect = vi.fn();
    },
  );
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
  });
  render(<BarcodeScanner onDetect={vi.fn()} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Abrir cámara para escanear" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Cerrar cámara" }));
  await act(async () =>
    resolve({ getTracks: () => [{ stop }] } as unknown as MediaStream),
  );
  expect(stop).toHaveBeenCalledOnce();
  expect(screen.queryByRole("dialog")).toBeNull();
});
