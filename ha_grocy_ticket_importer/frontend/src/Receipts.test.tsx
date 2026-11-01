import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Receipts } from "./Receipts";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";

vi.mock("./api", () => ({
  uploadReceipt: vi.fn(),
  previewReceipt: vi.fn(),
  commitReceipt: vi.fn(),
}));
beforeEach(() => {
  vi.resetAllMocks();
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.mocked(api.uploadReceipt).mockResolvedValue({
    receipt_id: "ticket-1",
    receipt: { items: [{ name: "Leche", quantity: 2, pieces_per_pack: 5 }] },
  });
  vi.mocked(api.previewReceipt).mockResolvedValue({
    preview: "2 packs = 10 piezas",
    ready_to_commit: true,
  });
});
afterEach(() => vi.restoreAllMocks());
async function upload() {
  await userEvent.upload(
    screen.getByLabelText("Foto o PDF del ticket"),
    new File(["fixture"], "ticket.png", { type: "image/png" }),
  );
  await screen.findByLabelText("Artículo");
}
async function preview() {
  await upload();
  await userEvent.click(
    screen.getByRole("button", { name: "Simular importación" }),
  );
  await screen.findByRole("button", { name: "Confirmar e importar a Grocy" });
}

it("requires a preview of the current edits and keeps ticket quantities read-only", async () => {
  renderWithClient(<Receipts />);
  await upload();
  expect(
    screen.queryByRole("button", { name: "Confirmar e importar a Grocy" }),
  ).toBeNull();
  expect(screen.getByLabelText("Cantidad del ticket")).toHaveProperty(
    "readOnly",
    true,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Simular importación" }),
  );
  await screen.findByRole("button", { name: "Confirmar e importar a Grocy" });
  await userEvent.clear(screen.getByLabelText("Artículo"));
  await userEvent.type(screen.getByLabelText("Artículo"), "Leche entera");
  expect(
    screen.queryByRole("button", { name: "Confirmar e importar a Grocy" }),
  ).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Simular importación" }),
  );
  expect(api.previewReceipt).toHaveBeenLastCalledWith("ticket-1", [
    { name: "Leche entera", purchase_units: "2", pieces_per_pack: 5 },
  ]);
  expect(api.commitReceipt).not.toHaveBeenCalled();
});

it.each(["0", "1.5", "1001"])(
  "rejects invalid pack factor %s before preview",
  async (factor) => {
    renderWithClient(<Receipts />);
    await upload();
    await userEvent.clear(screen.getByLabelText("Piezas por envase"));
    await userEvent.type(screen.getByLabelText("Piezas por envase"), factor);
    expect(
      screen.getByRole("button", { name: "Simular importación" }),
    ).toHaveProperty("disabled", true);
    expect(api.previewReceipt).not.toHaveBeenCalled();
  },
);

it("keeps edited items after a failed simulation and allows a new simulation", async () => {
  vi.mocked(api.previewReceipt).mockRejectedValueOnce(
    new Error("Sin conexión"),
  );
  renderWithClient(<Receipts />);
  await upload();
  await userEvent.type(screen.getByLabelText("Artículo"), " entera");
  await userEvent.click(
    screen.getByRole("button", { name: "Simular importación" }),
  );
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Sin conexión",
  );
  expect(screen.getByLabelText("Artículo")).toHaveProperty(
    "value",
    "Leche entera",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Simular importación" }),
  );
  await screen.findByRole("button", { name: "Confirmar e importar a Grocy" });
  expect(api.previewReceipt).toHaveBeenCalledTimes(2);
});

it("does not import when the confirmation dialog is cancelled", async () => {
  vi.mocked(window.confirm).mockReturnValue(false);
  renderWithClient(<Receipts />);
  await preview();
  await userEvent.click(
    screen.getByRole("button", { name: "Confirmar e importar a Grocy" }),
  );
  expect(api.commitReceipt).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Artículo")).toHaveProperty("disabled", false);
});

it("submits once on double click and prevents editing while import is in flight", async () => {
  const pending = deferred<Awaited<ReturnType<typeof api.commitReceipt>>>();
  vi.mocked(api.commitReceipt).mockReturnValue(pending.promise);
  const { client } = renderWithClient(<Receipts />);
  const invalidate = vi.spyOn(client, "invalidateQueries");
  await preview();
  await userEvent.dblClick(
    screen.getByRole("button", { name: "Confirmar e importar a Grocy" }),
  );
  expect(api.commitReceipt).toHaveBeenCalledExactlyOnceWith("ticket-1");
  expect(screen.getByLabelText("Artículo")).toHaveProperty("disabled", true);
  expect(
    screen.getByRole("button", { name: "Simular importación" }),
  ).toHaveProperty("disabled", true);
  await act(async () =>
    pending.resolve({ status: "ok", output: "10 piezas importadas" }),
  );
  await screen.findByRole("heading", { name: "Importación completada" });
  expect(
    screen.queryByRole("button", { name: "Confirmar e importar a Grocy" }),
  ).toBeNull();
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["inventory"] });
});

it("never offers resubmission after an uncertain import", async () => {
  vi.mocked(api.commitReceipt).mockRejectedValue(
    new Error("Respuesta perdida"),
  );
  renderWithClient(<Receipts />);
  await preview();
  await userEvent.click(
    screen.getByRole("button", { name: "Confirmar e importar a Grocy" }),
  );
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringContaining("No vuelvas a confirmar"),
  );
  expect(
    screen.getByRole("button", { name: "Confirmar e importar a Grocy" }),
  ).toHaveProperty("disabled", true);
  expect(screen.getByLabelText("Artículo")).toHaveProperty("disabled", true);
  expect(api.commitReceipt).toHaveBeenCalledTimes(1);
});

it("does not expose confirmation when the server says the preview is not ready", async () => {
  vi.mocked(api.previewReceipt).mockResolvedValue({
    preview: "Revisar productos",
    ready_to_commit: false,
  });
  renderWithClient(<Receipts />);
  await upload();
  await userEvent.click(
    screen.getByRole("button", { name: "Simular importación" }),
  );
  await screen.findByText("Revisar productos");
  expect(
    screen.queryByRole("button", { name: "Confirmar e importar a Grocy" }),
  ).toBeNull();
});
