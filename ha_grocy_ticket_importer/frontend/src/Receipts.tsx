import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  commitReceipt,
  previewReceipt,
  uploadReceipt,
  getReceiptReviewContext,
} from "./api";
import type { ReceiptUpload, ReceiptReviewItem } from "./api";

type EditableItem = ReceiptReviewItem & { mapping_stale?: boolean };
export function Receipts() {
  const client = useQueryClient();
  const [receipt, setReceipt] = useState<ReceiptUpload | null>(null);
  const [items, setItems] = useState<EditableItem[]>([]);
  const [preview, setPreview] = useState("");
  const [readyToCommit, setReadyToCommit] = useState(false);
  const [committed, setCommitted] = useState(false);
  const [commitStarted, setCommitStarted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const context = useQuery({
    queryKey: ["receipt-review", receipt?.receipt_id],
    queryFn: () => getReceiptReviewContext(receipt!.receipt_id),
    enabled: !!receipt,
    retry: false,
  });
  const [mappedReceipt, setMappedReceipt] = useState<string | null>(null);
  useEffect(() => {
    if (!receipt || !context.data || mappedReceipt === receipt.receipt_id)
      return;
    setItems((previous) =>
      previous.map((item, index) => {
        const original = receipt.receipt.items[index];
        const key = (original.original_name ?? original.name)
          .normalize("NFKC")
          .toLocaleLowerCase()
          .trim()
          .replace(/\s+/g, " ");
        const mapping =
          context.data.line_mappings?.[index] ?? context.data.mappings[key];
        const product =
          mapping &&
          context.data.products.find((p) => p.id === mapping.product_id);
        return mapping?.stale
          ? { ...item, mapping_stale: true }
          : product
            ? {
                ...item,
                product_mode: "existing",
                product_id: product.id,
                stock_unit: product.stock_unit,
                pieces_per_pack: product.pieces_per_pack,
                remember_product: true,
              }
            : item;
      }),
    );
    setMappedReceipt(receipt.receipt_id);
    setPreview("");
    setReadyToCommit(false);
  }, [receipt, context.data, mappedReceipt]);
  const update = (index: number, patch: Partial<EditableItem>) => {
    setItems((previous) =>
      previous.map((item, i) =>
        i === index
          ? {
              ...item,
              ...patch,
              ...(patch.product_mode ? { mapping_stale: false } : {}),
            }
          : item,
      ),
    );
    setPreview("");
    setReadyToCommit(false);
  };
  async function upload(file: File) {
    setBusy(true);
    setError("");
    setPreview("");
    setReadyToCommit(false);
    setReceipt(null);
    setCommitted(false);
    setCommitStarted(false);
    try {
      const result = await uploadReceipt(file);
      setMappedReceipt(null);
      setReceipt(result);
      setItems(
        result.receipt.items.map((item) => ({
          name: item.name,
          stock_unit: Number.isInteger(Number(item.quantity)) ? "piece" : "kg",
          product_mode: "auto",
          product_id: null,
          remember_product: false,
          purchase_units: String(item.quantity),
          pieces_per_pack: item.pieces_per_pack ?? 1,
        })),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function simulate() {
    if (!receipt) return;
    setBusy(true);
    setError("");
    setPreview("");
    setReadyToCommit(false);
    try {
      const result = await previewReceipt(receipt.receipt_id, items);
      setPreview(result.preview);
      setReadyToCommit(result.ready_to_commit === true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (
      !receipt ||
      !preview ||
      !readyToCommit ||
      commitStarted ||
      !window.confirm(
        "¿Confirmas importar este ticket a Grocy? Esta operación modifica el stock y no se puede repetir.",
      )
    )
      return;
    setCommitStarted(true);
    setBusy(true);
    setError("");
    try {
      const result = await commitReceipt(receipt.receipt_id);
      setCommitted(true);
      void client.invalidateQueries({ queryKey: ["inventory"] });
      setPreview(result.output || "Importación completada");
    } catch (e) {
      setError(
        (e as Error).message +
          " No vuelvas a confirmar sin comprobar el stock en Grocy.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main>
      <div className="heading">
        <div>
          <span className="eyebrow">IMPORTACIÓN SEGURA</span>
          <h2>Escanear ticket</h2>
          <p>Revisa los artículos antes de simular su entrada en Grocy.</p>
        </div>
      </div>
      <label className="variant-field">
        Foto o PDF del ticket
        <input
          type="file"
          accept="image/jpeg,image/png,application/pdf"
          capture="environment"
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void upload(file);
          }}
        />
      </label>
      {busy && <p role="status">Procesando…</p>}
      {error && (
        <p role="alert" className="notice">
          {error}
        </p>
      )}
      {receipt && (
        <section>
          <h3>Revisión de artículos</h3>
          <p>
            Corrige las unidades que entrarán en stock y elige su producto. El
            importe original del ticket se conserva. La cantidad final se
            calcula automáticamente.
          </p>
          {context.isPending && <p role="status">Consultando productos…</p>}
          {context.error && (
            <p role="alert">
              {context.error.message}{" "}
              <button onClick={() => void context.refetch()}>
                Reintentar catálogo
              </button>
            </p>
          )}
          {items.map((item, index) => (
            <div className="variant-form receipt-line" key={index}>
              <label className="variant-field">
                Artículo
                <input
                  disabled={busy || commitStarted}
                  value={item.name}
                  onChange={(event) =>
                    update(index, { name: event.target.value })
                  }
                />
              </label>
              <label className="variant-field">
                Cantidad del ticket
                <input
                  disabled={busy || commitStarted || context.isPending}
                  type="number"
                  min="0.001"
                  step={item.stock_unit === "kg" ? "0.001" : "1"}
                  value={item.purchase_units}
                  onChange={(event) =>
                    update(index, { purchase_units: event.target.value })
                  }
                />
              </label>
              <p className="muted">
                Texto del ticket:{" "}
                {receipt.receipt.items[index].original_name ??
                  receipt.receipt.items[index].name}
              </p>
              <label className="variant-field">
                Producto de Despensa
                <select
                  disabled={busy || commitStarted || !context.data}
                  value={
                    item.product_mode === "existing"
                      ? String(item.product_id)
                      : (item.product_mode ?? "auto")
                  }
                  onChange={(event) => {
                    const value = event.target.value;
                    const product = context.data?.products.find(
                      (p) => String(p.id) === value,
                    );
                    update(
                      index,
                      product
                        ? {
                            product_mode: "existing",
                            product_id: product.id,
                            stock_unit: product.stock_unit,
                            pieces_per_pack: product.pieces_per_pack,
                            remember_product: true,
                          }
                        : {
                            product_mode: value as "auto" | "new",
                            product_id: null,
                            remember_product: value === "new",
                          },
                    );
                  }}
                >
                  <option value="auto">Detectar por nombre</option>
                  <option value="new">Crear producto nuevo al importar</option>
                  {context.data?.products.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.name}
                    </option>
                  ))}
                </select>
              </label>
              {item.mapping_stale && (
                <p role="alert">
                  La asociación guardada ha cambiado o su producto ya no está
                  disponible. Elige un producto o crea uno nuevo.
                </p>
              )}
              <label className="variant-field">
                Unidad de stock
                <select
                  disabled={
                    busy || commitStarted || item.product_mode === "existing"
                  }
                  value={item.stock_unit}
                  onChange={(event) =>
                    update(index, {
                      stock_unit: event.target.value as "piece" | "kg",
                      pieces_per_pack: 1,
                      unit_confirmed: true,
                    })
                  }
                >
                  <option value="piece">Piezas</option>
                  <option value="kg">Kilogramos</option>
                </select>
              </label>
              <label className="variant-field">
                Piezas por envase
                <input
                  disabled={
                    busy ||
                    commitStarted ||
                    item.stock_unit === "kg" ||
                    item.product_mode === "existing"
                  }
                  type="number"
                  min="1"
                  max="1000"
                  step="1"
                  value={item.pieces_per_pack}
                  onChange={(event) =>
                    update(index, {
                      pieces_per_pack: Number(event.target.value),
                    })
                  }
                />
              </label>
              <label className="variant-field">
                Cantidad final calculada
                <input
                  aria-label="Cantidad final calculada"
                  readOnly
                  value={
                    Number.isFinite(Number(item.purchase_units)) &&
                    Number(item.purchase_units) > 0
                      ? String(
                          Math.round(
                            Number(item.purchase_units) *
                              (item.stock_unit === "kg"
                                ? 1
                                : item.pieces_per_pack) *
                              1000,
                          ) / 1000,
                        )
                      : ""
                  }
                />
                <span>
                  {item.stock_unit === "kg" ? "kg" : "piezas"} que se añadirán
                  al stock
                </span>
              </label>
              <label className="stock-alert-toggle">
                <input
                  type="checkbox"
                  disabled={
                    busy || commitStarted || item.product_mode === "auto"
                  }
                  checked={item.remember_product ?? false}
                  onChange={(event) =>
                    update(index, { remember_product: event.target.checked })
                  }
                />
                Recordar este artículo para este supermercado
              </label>
            </div>
          ))}
          <button
            disabled={
              busy ||
              commitStarted ||
              !context.data ||
              items.some(
                (item) =>
                  item.mapping_stale ||
                  !item.name.trim() ||
                  !Number.isFinite(Number(item.purchase_units)) ||
                  Number(item.purchase_units) <= 0 ||
                  Number(item.purchase_units) > 1000000 ||
                  Math.abs(
                    Number(item.purchase_units) * 1000 -
                      Math.round(Number(item.purchase_units) * 1000),
                  ) > 0.000001 ||
                  (item.stock_unit === "piece" &&
                    !Number.isInteger(Number(item.purchase_units))) ||
                  !Number.isInteger(item.pieces_per_pack) ||
                  item.pieces_per_pack < 1 ||
                  item.pieces_per_pack > 1000,
              )
            }
            onClick={() => void simulate()}
          >
            Simular importación
          </button>
          {preview && (
            <section>
              <h3>
                {committed
                  ? "Importación completada"
                  : "Resultado de la simulación"}
              </h3>
              <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                {preview}
              </pre>
              {!committed && (
                <>
                  <p>
                    La simulación no modifica el inventario. Confirma solo
                    después de revisar los datos.
                  </p>
                  {readyToCommit && (
                    <button
                      disabled={busy || commitStarted}
                      onClick={() => void confirm()}
                    >
                      Confirmar e importar a Grocy
                    </button>
                  )}
                </>
              )}
              {committed && (
                <p role="status">
                  Ticket importado. No vuelvas a confirmar este ticket.
                </p>
              )}
            </section>
          )}
        </section>
      )}
    </main>
  );
}
