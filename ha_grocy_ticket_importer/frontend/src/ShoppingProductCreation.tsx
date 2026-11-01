import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useModal } from "./useModal";
import { CreateProduct } from "./CreateProduct";
import { ProductDetail } from "./ProductDetail";
import { chooseAlexaMatch, createShoppingProduct, getShoppingCreationContext } from "./api";
import type { CatalogProductInput, ShoppingCreationResult } from "./api";

export function ShoppingProductCreation({ sourceKey, name, onClose, onSaved }: { sourceKey: string; name: string; onClose: () => void; onSaved: () => void }) {
  const client = useQueryClient();
  const context = useQuery({ queryKey: ["shopping-creation", sourceKey], queryFn: () => getShoppingCreationContext(sourceKey), retry: false, staleTime: 0 });
  const [operationId] = useState(() => crypto.randomUUID());
  const [associationId, setAssociationId] = useState(() => crypto.randomUUID());
  const [result, setResult] = useState<ShoppingCreationResult>();
  const [attempted, setAttempted] = useState(false);
  const [viewProduct, setViewProduct] = useState(false);
  const productId = result?.product_id ?? context.data?.product_id;
  const creating = Boolean(context.data?.can_create && !result);
  const dialog = useModal(onClose, !creating);
  const associated = async () => {
    await Promise.all([client.invalidateQueries({ queryKey: ["shopping"] }), client.invalidateQueries({ queryKey: ["inventory"] })]);
    onSaved();
  };
  const choose = useMutation({
    mutationFn: () => chooseAlexaMatch(sourceKey, productId!, associationId), retry: false,
    onMutate: () => setAttempted(true), onSuccess: associated,
  });
  const submit = async (product: CatalogProductInput) => {
    const saved = await createShoppingProduct(sourceKey, context.data!, product, operationId);
    if (saved.associated) await associated();
    else { setResult(saved); void context.refetch(); }
    return saved;
  };
  if (creating) return <CreateProduct initialName={name} onClose={onClose} submitProduct={submit} zeroStockOnly oneAttempt />;
  return <div ref={dialog} tabIndex={-1} className="detail-backdrop" role="dialog" aria-modal="true" aria-label="Crear producto desde la compra">
    <section className="detail-panel">
      <div className="detail-heading"><h2>Producto para «{name}»</h2><button className="secondary-button" onClick={onClose}>Cerrar</button></div>
      {context.isFetching && <p role="status">Revisando el artículo…</p>}
      {context.isError && <p role="alert">{context.error.message}</p>}
      {productId ? <>
        <p role="status">{result?.created ? "Producto creado sin existencias." : "Este producto ya existe; no se ha duplicado ni modificado su stock."}</p>
        <p>Producto: {context.data?.product_name ?? "ID " + productId}. La cantidad y nota originales se conservan al asociarlo.</p>
        {context.data?.associated ? <button className="primary-button" onClick={() => void associated()}>Volver a la lista</button> : <>
          <p>{result?.association_uncertain ? "No se pudo confirmar la asociación. Revisa el estado antes de completar la operación." : "Comprueba el producto existente antes de usarlo para este artículo."}</p>
          <div className="shopping-creation-actions">
            <button className="secondary-button" onClick={() => setViewProduct(true)}>Ver producto</button>
            <button className="primary-button" disabled={attempted || context.isFetching || context.isError || !context.data?.can_associate} onClick={() => choose.mutate()}>Asociar este producto</button>
          </div>
        </>}
      </> : context.data && !context.data.can_create && <p>El artículo ha cambiado o ya está asociado. Actualiza la lista antes de crear otro producto.</p>}
      {choose.isError && <p role="alert">{choose.error.message}</p>}
      <button className="secondary-button" disabled={choose.isPending || context.isFetching} onClick={() => { void context.refetch().then(read => { if (read.isSuccess) { setAttempted(false); setAssociationId(crypto.randomUUID()); } }); }}>Revisar estado</button>
      {viewProduct && productId && <ProductDetail id={productId} onClose={() => setViewProduct(false)} />}
    </section>
  </div>;
}
