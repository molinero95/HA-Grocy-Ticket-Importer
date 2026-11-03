import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Receipts } from "./Receipts";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";

vi.mock("./api", () => ({
  uploadReceipt: vi.fn(),
  getReceiptReviewContext: vi.fn(),
  previewReceipt: vi.fn(),
  commitReceipt: vi.fn(),
}));
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getReceiptReviewContext).mockResolvedValue({
    products: [],
    mappings: {},
  });
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
  await screen.findAllByLabelText("Artículo");
}
async function preview() {
  await upload();
  await userEvent.click(
    screen.getByRole("button", { name: "Simular importación" }),
  );
  await screen.findByRole("button", { name: "Confirmar e importar a Grocy" });
}

it("requires a preview of the current edits and shows calculated stock read-only", async () => {
  renderWithClient(<Receipts />);
  await upload();
  expect(
    screen.queryByRole("button", { name: "Confirmar e importar a Grocy" }),
  ).toBeNull();
  expect(screen.getByLabelText("Cantidad final calculada")).toHaveProperty(
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
    {
      name: "Leche entera",
      purchase_units: "2",
      pieces_per_pack: 5,
      stock_unit: "piece",
      product_mode: "auto",
      product_id: null,
      remember_product: false,
    },
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

it("recalculates the read-only total and invalidates simulation when quantities or pack contents change", async () => {
  renderWithClient(<Receipts />);
  await preview();
  expect(screen.getByLabelText("Cantidad final calculada")).toHaveProperty(
    "value",
    "10",
  );
  await userEvent.clear(screen.getByLabelText("Cantidad del ticket"));
  await userEvent.type(screen.getByLabelText("Cantidad del ticket"), "3");
  expect(screen.getByLabelText("Cantidad final calculada")).toHaveProperty(
    "value",
    "15",
  );
  expect(
    screen.queryByRole("button", { name: "Confirmar e importar a Grocy" }),
  ).toBeNull();
  await userEvent.clear(screen.getByLabelText("Piezas por envase"));
  await userEvent.type(screen.getByLabelText("Piezas por envase"), "6");
  expect(screen.getByLabelText("Cantidad final calculada")).toHaveProperty(
    "value",
    "18",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Simular importación" }),
  );
  expect(api.previewReceipt).toHaveBeenLastCalledWith("ticket-1", [
    expect.objectContaining({ purchase_units: "3", pieces_per_pack: 6 }),
  ]);
});

it("selects a canonical product by ID and applies its current purchase units", async () => {
  vi.mocked(api.getReceiptReviewContext).mockResolvedValue({
    products: [
      {
        id: 41,
        name: "Yogur natural", current_stock: "0",
        stock_unit: "piece",
        pieces_per_pack: 6,
      },
    ],
    mappings: {},
  });
  renderWithClient(<Receipts />);
  await upload();
  await screen.findByRole("option", { name: "Yogur natural" });
  await userEvent.selectOptions(
    screen.getByLabelText("Producto de Despensa"),
    "41",
  );
  expect(screen.getByLabelText("Cantidad final calculada")).toHaveProperty(
    "value",
    "12",
  );
  expect(
    screen.getByLabelText("Recordar este artículo para este supermercado"),
  ).toHaveProperty("checked", true);
  await userEvent.click(
    screen.getByRole("button", { name: "Simular importación" }),
  );
  expect(api.previewReceipt).toHaveBeenCalledWith("ticket-1", [
    expect.objectContaining({
      product_id: 41,
      product_mode: "existing",
      stock_unit: "piece",
      pieces_per_pack: 6,
      remember_product: true,
    }),
  ]);
});

it("loads a remembered merchant mapping while retaining the original receipt text", async () => {
  vi.mocked(api.getReceiptReviewContext).mockResolvedValue({
    products: [
      { id: 41, name: "Leche entera", current_stock: "0", stock_unit: "piece", pieces_per_pack: 1 },
    ],
    mappings: {
      leche: { product_id: 41, stock_unit: "piece", pieces_per_pack: 1 },
    },
  });
  renderWithClient(<Receipts />);
  await upload();
  await screen.findByRole("option", { name: "Leche entera" });
  expect(screen.getByLabelText("Producto de Despensa")).toHaveProperty(
    "value",
    "41",
  );
  expect(screen.getByLabelText("Artículo")).toHaveProperty("value", "Leche");
  await userEvent.selectOptions(
    screen.getByLabelText("Producto de Despensa"),
    "new",
  );
  await userEvent.clear(screen.getByLabelText("Artículo"));
  await userEvent.type(screen.getByLabelText("Artículo"), "Leche sin lactosa");
  await userEvent.click(
    screen.getByRole("button", { name: "Simular importación" }),
  );
  expect(api.previewReceipt).toHaveBeenCalledWith("ticket-1", [
    expect.objectContaining({
      name: "Leche sin lactosa",
      product_mode: "new",
      product_id: null,
      remember_product: true,
    }),
  ]);
});

it("shows fractional kilogram amounts exactly and never multiplies kilograms by a pack", async () => {
  vi.mocked(api.uploadReceipt).mockResolvedValue({
    receipt_id: "kg-ticket",
    receipt: { items: [{ name: "Tomate kg", quantity: 1.095 }] },
  });
  renderWithClient(<Receipts />);
  await upload();
  expect(screen.getByLabelText("Cantidad final calculada")).toHaveProperty(
    "value",
    "1.095",
  );
  expect(screen.getByLabelText("Piezas por envase")).toHaveProperty(
    "disabled",
    true,
  );
});

it("requires an explicit replacement when a remembered product or conversion is stale", async () => {
  vi.mocked(api.getReceiptReviewContext).mockResolvedValue({
    products: [
      { id: 41, name: "Leche entera", current_stock: "0", stock_unit: "piece", pieces_per_pack: 6 },
    ],
    mappings: {
      leche: {
        product_id: 41,
        stock_unit: "piece",
        pieces_per_pack: 1,
        stale: true,
      },
    },
  });
  renderWithClient(<Receipts />);
  await upload();
  await screen.findByText(/La asociación guardada ha cambiado/);
  expect(
    screen.getByRole("button", { name: "Simular importación" }),
  ).toHaveProperty("disabled", true);
  await userEvent.selectOptions(
    screen.getByLabelText("Producto de Despensa"),
    "41",
  );
  expect(
    screen.getByRole("button", { name: "Simular importación" }),
  ).toHaveProperty("disabled", false);
  expect(screen.getByLabelText("Cantidad final calculada")).toHaveProperty(
    "value",
    "12",
  );
});

it("cancelling live camera keeps the current receipt review and never imports stock", async () => {
  renderWithClient(<Receipts />);
  await upload();
  await userEvent.click(screen.getByRole("button", { name: "Tomar foto del ticket" }));
  expect(await screen.findByRole("dialog", { name: "Cámara del ticket" })).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Cerrar cámara del ticket" }));
  expect(api.uploadReceipt).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("Artículo")).toHaveProperty("value", "Leche");
  expect(api.commitReceipt).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Foto o PDF del ticket")).toBeTruthy();
});

it("lets pack input be empty and replaces a leading zero while typing", async () => {
  renderWithClient(<Receipts />);await upload();
  const input = screen.getByLabelText("Piezas por envase");
  await userEvent.clear(input);expect(input).toHaveProperty("value", "");
  await userEvent.type(input, "05");expect(input).toHaveProperty("value", "5");
  expect(screen.getByLabelText("Cantidad final calculada")).toHaveProperty("value", "10");
});
it("selected products accept a direct addition and show current plus final stock instead of pack editing", async () => {
  vi.mocked(api.getReceiptReviewContext).mockResolvedValue({ products: [{ id: 41, name: "Leche entera", current_stock: "5", stock_unit: "piece", pieces_per_pack: 6 }], mappings: {}, line_suggestions: [[41]] });
  renderWithClient(<Receipts />);await upload();
  expect(screen.getByRole("group", { name: "Sugeridos por parecido" })).toBeTruthy();
  expect(screen.getByLabelText("Producto de Despensa")).toHaveProperty("value", "auto");
  await userEvent.selectOptions(screen.getByLabelText("Producto de Despensa"), "41");
  expect(screen.queryByLabelText("Piezas por envase")).toBeNull();
  expect(screen.getByText("Stock actual: 5 Piece")).toBeTruthy();
  const input = screen.getByLabelText("Cantidad a añadir");
  await userEvent.clear(input);await userEvent.type(input, "3");
  expect(screen.getByLabelText("Cantidad final calculada")).toHaveProperty("value", "8");
  await userEvent.click(screen.getByRole("button", { name: "Simular importación" }));
  expect(api.previewReceipt).toHaveBeenLastCalledWith("ticket-1", [expect.objectContaining({ stock_to_add: "3", expected_stock: "5", pieces_per_pack: 6, product_id: 41 })]);
});
it("offers complete catalog and new creation when no similar suggestion exists", async () => {
  vi.mocked(api.getReceiptReviewContext).mockResolvedValue({ products: [{ id: 41, name: "Arroz", current_stock: "0", stock_unit: "piece", pieces_per_pack: 1 }], mappings: {}, line_suggestions: [[]] });
  renderWithClient(<Receipts />);await upload();
  await screen.findByText("Sin sugerencias por parecido. Puedes elegir cualquier producto o crear uno nuevo.");
  expect(screen.getByRole("option", { name: "Arroz" })).toBeTruthy();
  await userEvent.selectOptions(screen.getByLabelText("Producto de Despensa"), "new");
  expect(screen.getByLabelText("Piezas por envase")).toHaveProperty("disabled", false);
});
it("aggregates all explicitly associated lines into the same final product stock", async () => {
  vi.mocked(api.uploadReceipt).mockResolvedValue({ receipt_id: "repeated-lines", receipt: { items: [{ name: "Leche", quantity: 1 }, { name: "Leche", quantity: 1 }] } });
  vi.mocked(api.getReceiptReviewContext).mockResolvedValue({ products: [{ id: 41, name: "Leche entera", current_stock: "5", stock_unit: "piece", pieces_per_pack: 1 }], mappings: { leche: { product_id: 41, stock_unit: "piece", pieces_per_pack: 1 } } });
  renderWithClient(<Receipts />);await upload();
  const inputs = await screen.findAllByLabelText("Cantidad a añadir");
  await userEvent.clear(inputs[0]);await userEvent.type(inputs[0], "3");
  await userEvent.clear(inputs[1]);await userEvent.type(inputs[1], "4");
  for (const total of screen.getAllByLabelText("Cantidad final calculada")) expect(total).toHaveProperty("value", "12");
});
