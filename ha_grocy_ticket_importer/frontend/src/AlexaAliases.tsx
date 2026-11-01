import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteAlexaAlias, getAlexaAliases, getInventory, saveAlexaAlias } from "./api";

export function AlexaAliases() {
  const client = useQueryClient();
  const [productId, setProductId] = useState("");
  const [name, setName] = useState("");
  const [adding, setAdding] = useState(false);
  const aliases = useQuery({ queryKey: ["alexa-aliases"], queryFn: getAlexaAliases });
  const inventory = useQuery({ queryKey: ["inventory"], queryFn: getInventory });
  const save = useMutation({
    mutationFn: () => saveAlexaAlias(name.trim(), Number(productId)),
    onSuccess: async () => {
      setName("");
      setAdding(false);
      await client.invalidateQueries({ queryKey: ["alexa-aliases"] });
    },
  });
  const remove = useMutation({
    mutationFn: deleteAlexaAlias,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["alexa-aliases"] });
    },
  });
  const products = [...(inventory.data?.items ?? [])].sort((a, b) =>
    a.name.localeCompare(b.name, "es")
  );
  const selected = products.find((product) => String(product.id) === productId);
  const productAliases = (aliases.data?.aliases ?? []).filter(
    (alias) => String(alias.product_id) === productId
  );
  return (
    <main className="aliases-page">
      <h2>Alias de Alexa</h2>
      <p>Selecciona un producto para consultar y administrar los nombres con los que Alexa lo reconoce.</p>
      <div className="alias-form">
        <label className="alias-field" htmlFor="alexa-alias-product">
          Producto de Despensa
          <select id="alexa-alias-product" value={productId}
            disabled={inventory.isLoading}
            onChange={(event) => {
              setProductId(event.target.value);
              setName("");
              setAdding(false);
            }}>
            <option value="">Selecciona un producto</option>
            {products.map((product) => (
              <option key={product.id} value={product.id}>{product.name}</option>
            ))}
          </select>
        </label>
        {inventory.isLoading && <p role="status">Cargando productos…</p>}
        {inventory.isError && <p role="alert">No se pudieron cargar los productos.</p>}
      </div>
      {selected && (
        <section className="alias-product-section" aria-label={`Alias de ${selected.name}`}>
          <h3>Alias de {selected.name}</h3>
          {aliases.isLoading && <p role="status">Cargando alias…</p>}
          {aliases.isError && <p role="alert">No se pudieron cargar los alias.</p>}
          {!aliases.isLoading && !aliases.isError && productAliases.length === 0 &&
            <p className="alias-empty">Este producto todavía no tiene alias.</p>}
          <ul className="alias-list">
            {productAliases.map((alias) => (
              <li className="alias-item" key={alias.key}>
                <span className="alias-item-text"><strong>{alias.name}</strong></span>
                <button className="secondary-button" type="button" disabled={remove.isPending}
                  onClick={() => remove.mutate(alias.key)}
                  aria-label={`Eliminar alias ${alias.name}`}>Eliminar</button>
              </li>
            ))}
          </ul>
          {remove.isError && <p role="alert">{remove.error.message}</p>}
          {!adding ? (
            <button className="primary-button alias-add-button" type="button"
              onClick={() => setAdding(true)}>Añadir nuevo alias</button>
          ) : (
            <form className="alias-form alias-add-form" onSubmit={(event) => {
              event.preventDefault();
              if (name.trim() && productId) save.mutate();
            }}>
              <label className="alias-field" htmlFor="alexa-alias-name">
                Nuevo nombre en Alexa
                <input id="alexa-alias-name" required maxLength={200} value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Ej. leche normal" />
              </label>
              <div className="alias-form-actions">
                <button className="secondary-button" type="button"
                  onClick={() => { setAdding(false); setName(""); }}>Cancelar</button>
                <button className="primary-button" type="submit"
                  disabled={save.isPending || !name.trim()}>
                  {save.isPending ? "Guardando…" : "Guardar alias"}
                </button>
              </div>
              {save.isError && <p role="alert">{save.error.message}</p>}
            </form>
          )}
        </section>
      )}
    </main>
  );
}
