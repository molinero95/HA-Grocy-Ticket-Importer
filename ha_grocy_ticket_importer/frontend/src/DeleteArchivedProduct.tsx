import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { deleteArchivedProduct, getProductDeletion } from "./api";

export function DeleteArchivedProduct({ id, onDeleted }: { id: number; onDeleted: () => void }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const preview = useQuery({ queryKey: ["product-deletion", id], queryFn: () => getProductDeletion(id), enabled: open, retry: false, staleTime: 0 });
  const remove = useMutation({
    mutationFn: () => deleteArchivedProduct(id, preview.data!.name, name, preview.data!.token, crypto.randomUUID()),
    retry: false,
    onMutate: () => setSubmitted(true),
    onSuccess: async () => {
      onDeleted();
      await Promise.all(["archived", "inventory", "shopping"].map((key) => client.invalidateQueries({ queryKey: [key] })));
      for (const key of ["product", "variants", "catalog-barcodes", "product-deletion"])
        client.removeQueries({ queryKey: [key, id], exact: true });
    },
  });
  return (
    <section className="product-deletion" aria-label="Eliminar producto archivado">
      <h3>Eliminar definitivamente</h3>
      <p>Para productos archivados sin existencias, historial ni dependencias. Esta acción no se puede deshacer.</p>
      {!open ? (
        <button className="secondary-button danger-outline" type="button" disabled={submitted} onClick={() => setOpen(true)}>
          <Trash2 size={17} aria-hidden="true" /> Revisar eliminación
        </button>
      ) : (
        <>
          {preview.isFetching && <p role="status">Comprobando historial y referencias…</p>}
          {preview.isError && <p role="alert">{preview.error.message} <button className="secondary-button" type="button" onClick={() => void preview.refetch()}>Reintentar revisión</button></p>}
          {preview.data && !preview.isFetching && !preview.isError && (
            preview.data.allowed ? (
              <form className="variant-form" onSubmit={(event) => { event.preventDefault(); if (!submitted && name === preview.data!.name) remove.mutate(); }}>
                <p>Se borrarán la ficha, sus códigos de barras y su configuración de unidades.</p>
                <label className="variant-field">
                  Escribe «{preview.data.name}» para confirmar
                  <input autoComplete="off" value={name} disabled={submitted} onChange={(event) => setName(event.target.value)} />
                </label>
                <button className="primary-button danger-button" type="submit" disabled={submitted || name !== preview.data.name}>
                  {remove.isPending ? "Eliminando…" : "Eliminar producto definitivamente"}
                </button>
              </form>
            ) : (
              <div role="alert">
                <p>No se puede eliminar porque conserva:</p>
                <ul>{preview.data.blockers.map((reason) => <li key={reason}>{reason}</li>)}</ul>
              </div>
            )
          )}
          {remove.isError && <p role="alert">{remove.error.message} Cierra la ficha y comprueba el resultado antes de volver a intentarlo.</p>}
          <button className="secondary-button" type="button" disabled={remove.isPending} onClick={() => setOpen(false)}>Cerrar revisión</button>
        </>
      )}
    </section>
  );
}
