import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { deleteProduct, getProductDeletion } from "./api";
import { useModal } from "./useModal";

export function DeleteProduct({ id, onDeleted, disabled = false }: { id: number; onDeleted: () => void; disabled?: boolean }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const sent = useRef(false);
  const preview = useQuery({ queryKey: ["product-deletion", id], queryFn: () => getProductDeletion(id), enabled: open, retry: false, staleTime: 0, refetchOnWindowFocus: false });
  const remove = useMutation({
    mutationFn: () => deleteProduct(id, preview.data!.name, preview.data!.token, crypto.randomUUID()),
    retry: false,
    onSuccess: () => {
      onDeleted();
      void Promise.all(["archived", "inventory", "shopping", "duplicates"].map(key => client.invalidateQueries({ queryKey: [key] })));
      for (const key of ["product", "variants", "catalog-barcodes", "product-deletion"])
        client.removeQueries({ queryKey: [key, id], exact: true });
    },
  });
  const close = () => { if (!remove.isPending) setOpen(false); };
  const dialog = useModal(close, open);
  return <section className="product-deletion">
    <button className="secondary-button danger-outline" type="button" disabled={disabled || submitted} onClick={() => setOpen(true)}>
      <Trash2 size={17} aria-hidden="true" /> Eliminar producto
    </button>
    {open && <div ref={dialog} tabIndex={-1} className="detail-backdrop" role="dialog" aria-modal="true" aria-label="Confirmar eliminación">
      <section className="detail-panel confirmation-panel">
        <h2>¿Eliminar {preview.data?.name ?? "este producto"}?</h2>
        <p>Se borrarán la ficha, sus códigos, existencias e historial de movimientos de Grocy. Esta acción no se puede deshacer.</p>
        {preview.isFetching && <p role="status">Comprobando producto y referencias…</p>}
        {preview.isError && <p role="alert">{preview.error.message} <button className="secondary-button" onClick={() => void preview.refetch()}>Reintentar revisión</button></p>}
        {preview.data && !preview.isFetching && !preview.isError && <>
          <p>Existencias: {preview.data.stock_amount ?? "0"}. Movimientos: {preview.data.history_count}.</p>
          {!preview.data.allowed && <div role="alert"><p>No se puede eliminar mientras conserva estas dependencias:</p><ul>{preview.data.blockers.map(reason => <li key={reason}>{reason}</li>)}</ul></div>}
        </>}
        {remove.isError && <p role="alert">{remove.error.message} Cierra la ficha y comprueba el resultado antes de otra operación.</p>}
        <div className="variant-buttons">
          <button className="secondary-button" type="button" disabled={remove.isPending} onClick={close}>No</button>
          <button className="primary-button danger-button" type="button"
            disabled={submitted || preview.isFetching || preview.isError || !preview.data?.allowed}
            onClick={() => { if (sent.current || !preview.data?.allowed) return; sent.current = true; setSubmitted(true); remove.mutate(); }}>
            {remove.isPending ? "Eliminando…" : "Sí"}
          </button>
        </div>
      </section>
    </div>}
  </section>;
}
