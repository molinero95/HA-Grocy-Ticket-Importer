import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  getCatalogAudit,
  getDuplicateCandidates,
  getMergePreview,
  getDuplicateDifferences, markProductsDifferent, undoProductDifference, mergeCatalogProducts,
  type DuplicateCandidate,
} from "./api";

export function Duplicates() {
  const client = useQueryClient();
  const [message, setMessage] = useState("");
  const differences = useQuery({ queryKey: ["duplicate-differences"], queryFn: getDuplicateDifferences });
  const refresh = () => Promise.all(["duplicates", "duplicate-differences", "inventory", "archived", "shopping", "catalog-audit", "alexa-aliases", "product", "variants", "catalog-barcodes"].map(key => client.invalidateQueries({ queryKey: [key] })));
  const different = useMutation({ mutationFn: ([left, right]: DuplicateCandidate[]) => markProductsDifferent(left, right), retry: false, onSuccess: async () => { setMessage("Marcados como diferentes. Esta pareja no volverá a sugerirse hasta que deshagas la decisión."); setPair(null); await refresh(); } });
  const undo = useMutation({ mutationFn: ({left_id, right_id}: {left_id: number; right_id: number}) => undoProductDifference(left_id, right_id), retry: false, onSuccess: async () => { setMessage("Diferencia deshecha. Se volverán a comprobar las coincidencias."); await refresh(); } });
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["duplicates"],
    queryFn: getDuplicateCandidates,
  });
  const audit = useQuery({
    queryKey: ["catalog-audit"],
    queryFn: getCatalogAudit,
    enabled: false,
  });
  const [pair, setPair] = useState<[number, number] | null>(null);
  return (
    <main>
      <div className="heading">
        <div>
          <span className="eyebrow">REVISIÓN DEL CATÁLOGO</span>
          <h2>Posibles duplicados</h2>
          <p>
            Coincidencias por nombre o código. No se fusiona ni elimina ningún
            producto automáticamente.
          </p>
        </div>
        <button className="secondary-button" onClick={() => void refetch()}>
          Volver a analizar
        </button>
      </div>
      {message && <p role="status" className="notice">{message}</p>}
      {(different.isError || undo.isError) && <p role="alert">{different.error?.message || undo.error?.message}</p>}
      <details className="item difference-history">
        <summary>Productos marcados como diferentes ({differences.data?.differences?.length ?? 0})</summary>
        <p>Se guardan por pareja e ID de producto, también después de renombrar. Puedes deshacer cualquier decisión.</p>
        {differences.isError && <p role="alert">No se pudieron cargar las decisiones. <button className="secondary-button" onClick={() => void differences.refetch()}>Reintentar decisiones</button></p>}
        {differences.data?.differences?.map(row => <div className="difference-row" key={row.left_id + ":" + row.right_id}><span>{row.left_name} (ID {row.left_id}) · {row.right_name} (ID {row.right_id})</span><button className="secondary-button" disabled={undo.isPending} onClick={() => undo.mutate(row)}>Deshacer diferencia</button></div>)}
      </details>
      <section className="item audit-panel">
        <h3>Auditoría completa (solo lectura)</h3>
        <p>
          Revisa referencias y conflictos antes de consolidar productos. No se
          modifican existencias.
        </p>
        <button
          className="primary-button"
          type="button"
          disabled={audit.isFetching}
          onClick={() => void audit.refetch()}
        >
          Analizar catálogo
        </button>
        {audit.isError && <p role="alert">{audit.error.message}</p>}
        {audit.data && (
          <>
            <p>
              {audit.data.products.length} productos ·{" "}
              {audit.data.barcode_conflicts.length} conflictos de códigos ·{" "}
              {audit.data.unlinked_shopping_entries.length} referencias de
              compra sin producto
            </p>
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                const blob = new Blob([JSON.stringify(audit.data, null, 2)], {
                  type: "application/json",
                });
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = "despensa-catalog-audit.json";
                anchor.click();
                URL.revokeObjectURL(url);
              }}
            >
              Exportar auditoría JSON
            </button>
          </>
        )}
      </section>
      {isLoading && <p>Cargando candidatos…</p>}
      {isError && (
        <p role="alert" className="notice">
          No se pudo analizar el catálogo.{" "}
          <button className="secondary-button" onClick={() => void refetch()}>
            Reintentar
          </button>
        </p>
      )}
      {data?.length === 0 && <p>No se han detectado posibles duplicados.</p>}
      {pair && <MergeReview key={pair.join(":")} pair={pair} onSwap={() => setPair([pair[1], pair[0]])} onClose={() => setPair(null)} onMerged={() => { setPair(null); setMessage("Productos combinados. Se ha conservado el producto elegido."); void refresh(); }} />}
      <div className="items">
        {data?.map((group, index) => (
          <article className="item duplicate-group" key={index}>
            <div>
              <strong>{group.reason}</strong>
              <ul>
                {group.items.map((item) => (
                  <li key={item.id}>
                    {item.name} (ID {item.id})
                    {item.barcodes.length > 0 && (
                      <small> · {item.barcodes.join(", ")}</small>
                    )}
                  </li>
                ))}
              </ul>
              {group.items.length >= 2 && (
                <button
                  className="secondary-button"
                  onClick={() =>
                    setPair([group.items[0].id, group.items[1].id])
                  }
                >
                  Revisar combinación
                </button>
              )}
              <button className="secondary-button" disabled={different.isPending || undo.isPending} onClick={() => different.mutate(group.items.slice(0, 2))}>Son diferentes</button>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}


function MergeReview({ pair, onSwap, onClose, onMerged }: { pair: [number, number]; onSwap: () => void; onClose: () => void; onMerged: () => void }) {
  const preview = useQuery({ queryKey: ["merge-preview", pair], queryFn: () => getMergePreview(...pair), retry: false, staleTime: 0 });
  const [confirmation, setConfirmation] = useState("");
  const [attempted, setAttempted] = useState(false);
  const merge = useMutation({ mutationFn: () => mergeCatalogProducts(preview.data!, confirmation, crypto.randomUUID()), retry: false, onMutate: () => setAttempted(true), onSuccess: onMerged });
  return <section className="item audit-panel merge-review" aria-label="Revisar combinación">
    <h3>Combinar productos</h3>
    <button className="secondary-button" disabled={merge.isPending} onClick={onClose}>Cerrar revisión</button>
    {preview.isFetching && <p role="status">Comprobando productos y referencias…</p>}
    {preview.isError && <p role="alert">{preview.error.message} <button className="secondary-button" onClick={() => void preview.refetch()}>Reintentar revisión</button></p>}
    {preview.data && !preview.isFetching && !preview.isError && <>
      <label className="variant-field">Producto que conservarás
        <select value={preview.data.target.id} disabled={attempted} onChange={() => onSwap()}>
          {[preview.data.target, preview.data.source].map(product => <option key={product.id} value={product.id}>{product.name} (ID {product.id})</option>)}
        </select>
      </label>
      <p><strong>Se conserva:</strong> {preview.data.target.name} (ID {preview.data.target.id}) · {preview.data.target.stock_amount} unidades.</p>
      <p><strong>Se integra y desaparece:</strong> {preview.data.source.name} (ID {preview.data.source.id}) · {preview.data.source.stock_amount} unidades.</p>
      <p>Se conservan el nombre, descripción, foto y configuración del producto elegido. Sus lotes, movimientos, códigos y referencias de Grocy se reúnen sin consumir stock. Esta combinación no se puede deshacer.</p>
      {preview.data.audit && <ul>{preview.data.audit.collections.map(row => <li key={row.collection}>{row.label}: {row.status === "ok" ? row.count + " registro(s)" : "No disponible"}</li>)}</ul>}
      {preview.data.blockers.length > 0 && <div role="alert"><strong>No se pueden combinar:</strong><ul>{preview.data.blockers.map(reason => <li key={reason}>{reason}</li>)}</ul><p>Puedes cambiar el producto que conservarás o marcar esta pareja como diferente.</p></div>}
      {preview.data.can_merge && <form className="variant-form" onSubmit={event => { event.preventDefault(); if (!attempted && confirmation === preview.data!.target.name) merge.mutate(); }}>
        <label className="variant-field">Escribe «{preview.data.target.name}» para conservarlo<input autoComplete="off" disabled={attempted} value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
        <button className="primary-button danger-button" disabled={attempted || confirmation !== preview.data.target.name}>{merge.isPending ? "Combinando…" : "Combinar definitivamente"}</button>
      </form>}
    </>}
    {merge.isError && <p role="alert">{merge.error.message} Cierra la revisión y comprueba Grocy antes de intentarlo de nuevo.</p>}
  </section>;
}
