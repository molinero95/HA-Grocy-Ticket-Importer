import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  commitReceipt,
  previewReceipt,
  uploadReceipt,
  getReceiptReviewContext,
} from "./api";
import type { ReceiptUpload, ReceiptReviewItem, ReceiptReviewProduct } from "./api";

import { ReceiptCamera } from "./ReceiptCamera";

type EditableItem = Omit<ReceiptReviewItem, "pieces_per_pack"> & { pieces_per_pack: number | string; mapping_stale?: boolean };
function lineProblems(item: EditableItem, products: ReceiptReviewProduct[], all: EditableItem[]): string[] {
  if (item.product_mode === "skip") return [];
  const problems: string[] = [];
  if (item.product_mode !== "existing" && item.product_mode !== "new") problems.push("Elige un producto de las sugerencias o del catálogo, crea uno nuevo u omite la línea.");
  const bounded = (value: unknown, integer = false) => {
    const number = Number(value);
    return String(value ?? "").trim() !== "" && Number.isFinite(number) && number > 0 && number <= 1000000 && (integer ? Number.isInteger(number) : Math.abs(number * 1000 - Math.round(number * 1000)) <= .000001);
  };
  if (!item.name.trim()) problems.push("Escribe el nombre del artículo.");
  else if (item.name.trim().length > 200) problems.push("El nombre debe tener como máximo 200 caracteres.");
  if (!bounded(item.purchase_units)) problems.push("La cantidad del ticket debe ser mayor que cero, hasta 1.000.000 y con un máximo de tres decimales.");
  else if (item.stock_unit === "piece" && item.product_mode !== "existing" && !Number.isInteger(Number(item.purchase_units))) problems.push("Las piezas deben ser enteras. Si es un peso, selecciona kilogramos.");
  const pack = Number(item.pieces_per_pack);
  if (!Number.isInteger(pack) || pack < 1 || pack > 1000) problems.push("Indica entre 1 y 1.000 piezas por envase, sin decimales.");
  if (item.stock_unit === "kg" && pack !== 1) problems.push("En kilogramos, la equivalencia del envase debe ser 1.");
  if (!item.stock_unit) problems.push("Selecciona la unidad de stock.");
  if (item.mapping_stale) problems.push("La asociación guardada necesita revisión. Vuelve a elegir el producto.");
  if (item.product_mode === "existing") {
    if (!products.some(product => product.id === item.product_id)) problems.push("El producto elegido no está disponible. Elige otro producto.");
    if (typeof item.expected_stock !== "string" || item.expected_stock.trim() === "" || !Number.isFinite(Number(item.expected_stock)) || Number(item.expected_stock) < 0) problems.push("No se conoce el stock actual. Pulsa Actualizar stock y catálogo.");
    if (!bounded(item.stock_to_add, item.stock_unit === "piece")) problems.push(item.stock_unit === "piece" ? "Indica una cantidad entera a añadir, mayor que cero y hasta 1.000.000." : "Indica los kg a añadir, mayores que cero, hasta 1.000.000 y con un máximo de tres decimales.");
  }
  const key = (name: string) => name.trim().toLocaleLowerCase("es").replace(/\s+/g, " ");
  if (item.product_mode === "new" && products.some(product => key(product.name) === key(item.name))) problems.push("Ya existe un producto con ese nombre. Selecciónalo en la lista.");
  if (item.product_mode === "new" && all.filter(line => line.product_mode !== "skip" && key(line.name) === key(item.name)).length > 1) problems.push("El nombre se repite en otra línea. Revisa los productos o elige cuál omitir.");
  return problems;
}
export function Receipts() {
  const client = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const uploadPending = useRef(false);
  const [receipt, setReceipt] = useState<ReceiptUpload | null>(null);
  const [items, setItems] = useState<EditableItem[]>([]);
  const [preview, setPreview] = useState("");
  const [readyToCommit, setReadyToCommit] = useState(false);
  const [committed, setCommitted] = useState(false);
  const [commitStarted, setCommitStarted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [serverIssues, setServerIssues] = useState<Record<number, string[]>>({});
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
        if (item.product_mode === "skip") return item;
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
                stock_to_add: String(Number(item.purchase_units) * product.pieces_per_pack),
                expected_stock: product.current_stock,
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
    setServerIssues(previous => { const next = { ...previous }; delete next[index]; return next; });
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
    if (uploadPending.current) return;
    uploadPending.current = true;
    setBusy(true);
    setError("");
    setPreview("");
    setReadyToCommit(false);
    setServerIssues({});
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
          product_mode: item.product_mode === "skip" ? "skip" : undefined,
          product_id: null,
          remember_product: false,
          purchase_units: String(item.quantity),
          pieces_per_pack: item.pieces_per_pack ?? 1,
        })),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      uploadPending.current = false;
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
      const result = await previewReceipt(receipt.receipt_id, items.map((item, index) => item.product_mode === "skip" ? { name: (receipt.receipt.items[index].name || "Artículo omitido").slice(0, 200), product_mode: "skip", product_id: null, remember_product: false, purchase_units: String(receipt.receipt.items[index].quantity), pieces_per_pack: 1 } : ({ ...item, pieces_per_pack: Number(item.pieces_per_pack) })));
      const issues: Record<number, string[]> = {};
      for (const issue of result.line_issues ?? []) if (Number.isInteger(issue.index) && issue.index >= 0 && issue.index < items.length) (issues[issue.index] ??= []).push(issue.message);
      setServerIssues(issues);
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
  const localIssues = items.map(item => lineProblems(item, context.data?.products ?? [], items));
  const problems = items.map((_, index) => [...localIssues[index], ...(serverIssues[index] ?? [])]);
  const pendingRows = problems.map((messages, index) => messages.length ? index : -1).filter(index => index >= 0);
  return (
    <main>
      <div className="heading">
        <div>
          <span className="eyebrow">IMPORTACIÓN SEGURA</span>
          <h2>Escanear ticket</h2>
          <p>Revisa los artículos antes de simular su entrada en Grocy.</p>
        </div>
      </div>
      <ReceiptCamera disabled={busy} onCapture={file => void upload(file)} onChooseFile={() => fileInput.current?.click()} />
      <label className="variant-field">
        Foto o PDF del ticket
        <input
          ref={fileInput}
          type="file"
          accept="image/jpeg,image/png,application/pdf"
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
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
          {receipt.receipt.total_warning && <p className="receipt-review-summary" role="status">{receipt.receipt.total_warning}</p>}
          <p>
            Corrige las unidades que entrarán en stock y elige su producto. El
            importe del ticket es informativo y no bloquea la importación. La cantidad final se
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
          {context.data && <button className="secondary-button" disabled={busy || commitStarted || context.isFetching} onClick={async () => {
            const fresh = await context.refetch();
            if (!fresh.isSuccess || !fresh.data) return;
            setItems(previous => previous.map(item => {
              if (item.product_mode !== "existing") return item;
              const product = fresh.data.products.find(product => product.id === item.product_id);
              return !product || product.stock_unit !== item.stock_unit || product.pieces_per_pack !== Number(item.pieces_per_pack) ? { ...item, mapping_stale: true } : { ...item, expected_stock: product.current_stock };
            }));
            setServerIssues({}); setPreview(""); setReadyToCommit(false);
          }}>Actualizar stock y catálogo</button>}
          {items.map((item, index) => (
            <div className={"variant-form receipt-line" + (problems[index].length ? " receipt-line-invalid" : item.product_mode === "skip" ? " receipt-line-skipped" : "")} key={index} id={`receipt-line-${index}`} role="group" aria-label={`Línea ${index + 1}: ${item.name}`} tabIndex={-1}>
              {problems[index].length > 0 && <div className="receipt-line-problems" role="alert"><strong>Pendiente de revisión · Línea {index + 1}</strong><ul>{problems[index].map((message, issue) => <li key={issue}>{message}</li>)}</ul></div>}
              {item.product_mode === "skip" && <p className="receipt-line-omitted">Omitido: no se creará producto ni se añadirá stock de esta línea. Se conserva para reconocer el ticket y evitar importaciones repetidas.</p>}
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
                  disabled={busy || commitStarted || context.isPending || item.product_mode === "skip"}
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
                      : (item.product_mode ?? "")
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
                            stock_to_add: String(Number(item.purchase_units) * product.pieces_per_pack),
                            expected_stock: product.current_stock,
                            remember_product: true,
                          }
                        : {
                            product_mode: value as "new" | "skip",
                            product_id: null,
                            stock_to_add: undefined,
                            expected_stock: undefined,
                            remember_product: value === "new",
                          },
                    );
                  }}
                >
                  <option value="" disabled>Elegir producto o crear uno nuevo</option>
                  <option value="new">Crear producto nuevo al importar</option>
                  <option value="skip">Omitir: no crear producto ni añadir stock</option>
                  {(context.data?.line_suggestions?.[index]?.length ?? 0) > 0 && <optgroup label="Sugeridos por parecido">{context.data!.line_suggestions![index].map(id => context.data!.products.find(product => product.id === id)).filter(product => product !== undefined).map(product => <option key={product.id} value={product.id}>{product.name}</option>)}</optgroup>}
                  <optgroup label="Todos los productos">{context.data?.products.filter(product => !context.data?.line_suggestions?.[index]?.includes(product.id)).map(product => <option key={product.id} value={product.id}>{product.name}</option>)}</optgroup>
                </select>
              </label>
              {context.data && item.product_mode !== "skip" && <p className="muted">{context.data.line_suggestions?.[index]?.length ? 'Las sugerencias se basan en el parecido del texto. Revisa el producto y su formato.' : 'Sin sugerencias por parecido. Puedes elegir cualquier producto o crear uno nuevo.'}</p>}
              {item.mapping_stale && (
                <p role="alert">
                  La asociación guardada ha cambiado o su producto ya no está
                  disponible. Elige un producto o crea uno nuevo.
                </p>
              )}
              {item.product_mode !== "skip" && <>
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
              {item.product_mode === "existing" ? <>
                <p>Stock actual: {item.expected_stock ?? "Desconocido"} {item.stock_unit === "kg" ? "kg" : "Piece"}</p>
                <label className="variant-field">Cantidad a añadir<input aria-label="Cantidad a añadir" type="number" min={item.stock_unit === "kg" ? "0.001" : "1"} max="1000000" step={item.stock_unit === "kg" ? "0.001" : "1"} disabled={busy || commitStarted} value={item.stock_to_add ?? ""} onChange={event => update(index, { stock_to_add: event.target.value.replace(/^0+(?=\d)/, "") })} /><span>{item.stock_unit === "kg" ? "kg" : "Piece"} que se añadirán a este producto</span></label>
              </> : <>
              <label className="variant-field">
                Piezas por envase
                <input
                  disabled={
                    busy ||
                    commitStarted ||
                    item.stock_unit === "kg"
                  }
                  type="number"
                  min="1"
                  max="1000"
                  step="1"
                  value={item.pieces_per_pack}
                  onChange={(event) =>
                    update(index, {
                      pieces_per_pack: event.target.value.replace(/^0+(?=\d)/, ""),
                    })
                  }
                />
              </label>
              </>}
              <label className="variant-field">
                Cantidad final calculada
                <input
                  aria-label="Cantidad final calculada"
                  readOnly
                  value={item.product_mode === "existing"
                    ? item.expected_stock === undefined || !item.stock_to_add ? "" : String(Math.round((Number(item.expected_stock) + items.filter(line => line.product_mode === "existing" && line.product_id === item.product_id).reduce((sum, line) => sum + Number(line.stock_to_add || 0), 0)) * 1000) / 1000)
                    : Number.isFinite(Number(item.purchase_units)) && Number(item.purchase_units) > 0 && item.pieces_per_pack !== "" ? String(Math.round(Number(item.purchase_units) * (item.stock_unit === "kg" ? 1 : Number(item.pieces_per_pack)) * 1000) / 1000) : ""}
                />
                <span>
                  {item.stock_unit === "kg" ? "kg" : "piezas"} {item.product_mode === "existing" ? "de stock final previsto con las líneas asociadas a este producto" : "que se añadirán al stock"}
                </span>
              </label>
              <label className="stock-alert-toggle">
                <input
                  type="checkbox"
                  disabled={
                    busy || commitStarted || !item.product_mode
                  }
                  checked={item.remember_product ?? false}
                  onChange={(event) =>
                    update(index, { remember_product: event.target.checked })
                  }
                />
                Recordar este artículo para este supermercado
              </label>
              </>}
            </div>
          ))}
          {!commitStarted && pendingRows.length > 0 && <div className="receipt-review-summary" role="status">
            <p>Hay {pendingRows.length} artículo(s) pendientes de revisión. Las filas amarillas indican qué falta; puedes corregirlas u omitirlas.</p>
            <button className="secondary-button" onClick={() => { const first = document.getElementById(`receipt-line-${pendingRows[0]}`); first?.scrollIntoView({ behavior: "smooth", block: "start" }); first?.focus({ preventScroll: true }); }}>Revisar primer artículo pendiente</button>
          </div>}
          {!commitStarted && !context.data && <p role="status">{context.isPending ? "Espera a que termine de cargar el catálogo para simular." : "La simulación requiere el catálogo. Pulsa Reintentar catálogo."}</p>}
          <button
            disabled={
              busy ||
              commitStarted ||
              !context.data ||
              localIssues.some(messages => messages.length > 0)
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
