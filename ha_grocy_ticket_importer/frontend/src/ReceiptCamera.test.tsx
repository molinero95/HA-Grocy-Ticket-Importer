import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ReceiptCamera } from "./ReceiptCamera";
import { deferred, renderWithClient } from "./test/helpers";
const originalMediaDevices = Object.getOwnPropertyDescriptor(navigator, "mediaDevices");
const stop = vi.fn(), getUserMedia = vi.fn(), drawImage = vi.fn();
beforeEach(() => {
  vi.resetAllMocks();
  getUserMedia.mockResolvedValue({ getTracks: () => [{ stop }] });
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  vi.spyOn(HTMLMediaElement.prototype, "readyState", "get").mockReturnValue(4);
  vi.spyOn(HTMLVideoElement.prototype, "videoWidth", "get").mockReturnValue(4000);
  vi.spyOn(HTMLVideoElement.prototype, "videoHeight", "get").mockReturnValue(2000);
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(callback => callback(new Blob(["camera fixture"], { type: "image/jpeg" })));
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:receipt-camera");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
});
afterEach(() => {
  vi.restoreAllMocks();
  if (originalMediaDevices) Object.defineProperty(navigator, "mediaDevices", originalMediaDevices);
  else Reflect.deleteProperty(navigator, "mediaDevices");
});
async function open() {
  await userEvent.click(screen.getByRole("button", { name: "Tomar foto del ticket" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Capturar foto" })).toHaveProperty("disabled", false));
}
it("opens a live rear-camera stream only after clicking and accepts a full-frame JPEG once", async () => {
  const use = vi.fn(); renderWithClient(<ReceiptCamera disabled={false} onCapture={use} onChooseFile={vi.fn()} />);
  expect(getUserMedia).not.toHaveBeenCalled();
  await open();
  expect(getUserMedia).toHaveBeenCalledExactlyOnceWith({ audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 2560 } } });
  await userEvent.dblClick(screen.getByRole("button", { name: "Capturar foto" }));
  expect(drawImage).toHaveBeenCalledExactlyOnceWith(expect.any(HTMLVideoElement), 0, 0, 2560, 1280);
  expect(HTMLCanvasElement.prototype.toBlob).toHaveBeenCalledOnce();
  expect(stop).toHaveBeenCalledOnce();
  expect(await screen.findByAltText("Foto capturada del ticket")).toBeTruthy();
  expect(use).not.toHaveBeenCalled();
  await userEvent.dblClick(screen.getByRole("button", { name: "Usar esta foto" }));
  expect(use).toHaveBeenCalledExactlyOnceWith(expect.any(File));
  expect((use.mock.calls[0][0] as File).type).toBe("image/jpeg");
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:receipt-camera");
});
it("retakes without uploading, releases both streams and revokes the discarded preview", async () => {
  const use = vi.fn(); renderWithClient(<ReceiptCamera disabled={false} onCapture={use} onChooseFile={vi.fn()} />);
  await open(); await userEvent.click(screen.getByRole("button", { name: "Capturar foto" }));
  await userEvent.click(await screen.findByRole("button", { name: "Repetir foto" }));
  await waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(2));
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:receipt-camera");
  await userEvent.click(screen.getByRole("button", { name: "Cerrar cámara del ticket" }));
  await waitFor(() => expect(stop).toHaveBeenCalledTimes(2));
  expect(use).not.toHaveBeenCalled();
});
it("denied permission offers files without retrying or uploading automatically", async () => {
  getUserMedia.mockRejectedValue(new DOMException("Denied", "NotAllowedError"));
  const choose = vi.fn(), use = vi.fn();
  renderWithClient(<ReceiptCamera disabled={false} onCapture={use} onChooseFile={choose} />);
  await userEvent.click(screen.getByRole("button", { name: "Tomar foto del ticket" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("Permite la cámara"));
  expect(getUserMedia).toHaveBeenCalledOnce();
  await userEvent.click(screen.getByRole("button", { name: "Elegir foto o PDF" }));
  expect(choose).toHaveBeenCalledOnce(); expect(use).not.toHaveBeenCalled();
});
it("stops a stream arriving after close instead of attaching it to another dialog", async () => {
  const pending = deferred<MediaStream>(); getUserMedia.mockReturnValue(pending.promise);
  renderWithClient(<ReceiptCamera disabled={false} onCapture={vi.fn()} onChooseFile={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Tomar foto del ticket" }));
  await userEvent.click(screen.getByRole("button", { name: "Cerrar cámara del ticket" }));
  await act(async () => pending.resolve({ getTracks: () => [{ stop }] } as unknown as MediaStream));
  expect(stop).toHaveBeenCalledOnce(); expect(screen.queryByRole("dialog")).toBeNull();
});
it("ignores encoding completed after close and only retries a failed capture explicitly", async () => {
  let finish!: BlobCallback;
  vi.mocked(HTMLCanvasElement.prototype.toBlob).mockImplementation(callback => { finish = callback; });
  const use = vi.fn(); renderWithClient(<ReceiptCamera disabled={false} onCapture={use} onChooseFile={vi.fn()} />);
  await open(); await userEvent.click(screen.getByRole("button", { name: "Capturar foto" }));
  await act(async () => finish(null));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(getUserMedia).toHaveBeenCalledOnce();
  await userEvent.click(screen.getByRole("button", { name: "Volver a abrir cámara" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Capturar foto" })).toHaveProperty("disabled", false));
  await userEvent.click(screen.getByRole("button", { name: "Capturar foto" }));
  await userEvent.click(screen.getByRole("button", { name: "Cerrar cámara del ticket" }));
  await act(async () => finish(new Blob(["late"], { type: "image/jpeg" })));
  expect(use).not.toHaveBeenCalled(); expect(URL.createObjectURL).not.toHaveBeenCalled();
});
it("has a file fallback when live capture is unavailable and requests no permission", async () => {
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
  renderWithClient(<ReceiptCamera disabled={false} onCapture={vi.fn()} onChooseFile={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Tomar foto del ticket" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("elige una foto o PDF"));
  expect(getUserMedia).not.toHaveBeenCalled();
});
