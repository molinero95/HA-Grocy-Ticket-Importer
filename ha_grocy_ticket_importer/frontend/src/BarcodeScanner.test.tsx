import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { BarcodeScanner } from "./BarcodeScanner";
const originalMediaDevices = Object.getOwnPropertyDescriptor(
  navigator,
  "mediaDevices",
);
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  if (originalMediaDevices)
    Object.defineProperty(navigator, "mediaDevices", originalMediaDevices);
  else Reflect.deleteProperty(navigator, "mediaDevices");
});

it("offers manual input after camera permission is denied without retrying permission", async () => {
  vi.stubGlobal(
    "BarcodeDetector",
    class {
      detect = vi.fn();
    },
  );
  const getUserMedia = vi
    .fn()
    .mockRejectedValue(new DOMException("Denied", "NotAllowedError"));
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
  });
  const detect = vi.fn();
  render(<BarcodeScanner onDetect={detect} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Abrir cámara para escanear" }),
  );
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("Revisa los permisos"),
  );
  expect(getUserMedia).toHaveBeenCalledOnce();
  expect(detect).not.toHaveBeenCalled();
});

it("ignores invalid detections then returns one valid code and stops camera tracks", async () => {
  const stop = vi.fn();
  const detect = vi
    .fn()
    .mockResolvedValueOnce([{ rawValue: "not-a-barcode" }])
    .mockResolvedValue([{ rawValue: "8412345678901" }]);
  vi.stubGlobal(
    "BarcodeDetector",
    class {
      detect = detect;
    },
  );
  const getUserMedia = vi
    .fn()
    .mockResolvedValue({ getTracks: () => [{ stop }] });
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
  });
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  vi.spyOn(HTMLMediaElement.prototype, "readyState", "get").mockReturnValue(4);
  const onDetect = vi.fn();
  render(<BarcodeScanner onDetect={onDetect} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Abrir cámara para escanear" }),
  );
  await waitFor(() =>
    expect(onDetect).toHaveBeenCalledExactlyOnceWith("8412345678901"),
  );
  expect(detect).toHaveBeenCalledTimes(2);
  expect(stop).toHaveBeenCalledOnce();
  expect(screen.queryByRole("dialog")).toBeNull();
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
