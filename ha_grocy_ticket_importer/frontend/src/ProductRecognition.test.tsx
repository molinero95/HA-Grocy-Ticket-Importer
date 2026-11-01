import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { ProductRecognition } from "./ProductRecognition";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";
vi.mock("./api", () => ({ identifyProductPhoto: vi.fn() }));
const suggestion: api.ProductSuggestion = {
  name: "Leche entera",
  brand: "Example",
  size_text: "1 L",
  confidence: "medium",
  visible_barcode: "",
  barcode: "8412345678901",
  advisory: true,
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal(
    "URL",
    class extends URL {
      static createObjectURL = vi.fn(() => "blob:disposable-preview");
      static revokeObjectURL = vi.fn();
    },
  );
  vi.mocked(api.identifyProductPhoto).mockResolvedValue({ suggestion });
});
afterEach(() => vi.unstubAllGlobals());
it("requires a new front photo and sends only that photo once after explicit analysis", async () => {
  const blob = new File(["new front photo"], "front.jpg", {
    type: "image/jpeg",
  });
  const useName = vi.fn();
  renderWithClient(
    <ProductRecognition barcode="8412345678901" onUseName={useName} />,
  );
  expect(api.identifyProductPhoto).not.toHaveBeenCalled();
  expect(screen.queryByRole("img")).toBeNull();
  expect(
    screen.getByRole("button", { name: "Analizar foto con OpenAI" }),
  ).toHaveProperty("disabled", true);
  const camera = screen.getByLabelText(
    "Tomar foto del frontal o etiqueta del producto",
  ) as HTMLInputElement;
  expect(camera.getAttribute("capture")).toBe("environment");
  expect(camera.hidden).toBe(true);
  const open = vi.spyOn(camera, "click");
  await userEvent.click(
    screen.getByRole("button", { name: "Tomar otra foto para buscar con IA" }),
  );
  expect(open).toHaveBeenCalledOnce();
  open.mockRestore();
  await userEvent.upload(camera, blob);
  expect(api.identifyProductPhoto).not.toHaveBeenCalled();
  expect(
    screen.getByAltText("Foto completa que se enviará a OpenAI"),
  ).toBeTruthy();
  await userEvent.dblClick(
    screen.getByRole("button", { name: "Analizar foto con OpenAI" }),
  );
  await screen.findByText("Leche entera");
  expect(api.identifyProductPhoto).toHaveBeenCalledExactlyOnceWith(
    "8412345678901",
    blob,
  );
  expect(useName).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByRole("button", { name: "Usar nombre sugerido" }),
  );
  expect(useName).toHaveBeenCalledExactlyOnceWith("Leche entera");
});
it("ignores a late result after the scanned code changes and releases local previews", async () => {
  const pending =
    deferred<Awaited<ReturnType<typeof api.identifyProductPhoto>>>();
  vi.mocked(api.identifyProductPhoto).mockReturnValue(pending.promise);
  const { rerender, unmount } = renderWithClient(
    <ProductRecognition barcode="8412345678901" onUseName={vi.fn()} />,
  );
  await userEvent.upload(
    screen.getByLabelText("Tomar foto del frontal o etiqueta del producto"),
    new File(["new label photo"], "label.jpg", { type: "image/jpeg" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Analizar foto con OpenAI" }),
  );
  rerender(<ProductRecognition barcode="12345678" onUseName={vi.fn()} />);
  await act(async () => pending.resolve({ suggestion }));
  expect(screen.queryByText("Leche entera")).toBeNull();
  unmount();
  expect(URL.revokeObjectURL).toHaveBeenCalled();
});
it("allows taking another new photo after failure while preserving manual entry", async () => {
  vi.mocked(api.identifyProductPhoto).mockRejectedValue(
    new Error("No se pudo analizar"),
  );
  renderWithClient(
    <ProductRecognition barcode="8412345678901" onUseName={vi.fn()} />,
  );
  expect(
    screen.getByRole("button", { name: "Analizar foto con OpenAI" }),
  ).toHaveProperty("disabled", true);
  await userEvent.upload(
    screen.getByLabelText("Tomar foto del frontal o etiqueta del producto"),
    new File(["full product"], "front.png", { type: "image/png" }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Analizar foto con OpenAI" }),
  );
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("No se pudo analizar"),
  );
  expect(api.identifyProductPhoto).toHaveBeenCalledTimes(1);
});
