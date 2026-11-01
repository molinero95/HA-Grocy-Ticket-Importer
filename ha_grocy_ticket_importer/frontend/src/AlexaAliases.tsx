import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteAlexaAlias, getAlexaAliases, getInventory, saveAlexaAlias } from "./api";

export function AlexaAliases() {
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [productId, setProductId] = useState("");
  const aliases = useQuery({ queryKey: ["alexa-aliases"], queryFn: getAlexaAliases });
  const inventory = useQuery({ queryKey: ["inventory"], queryFn: getInventory });
  const save = useMutation({
    mutationFn: () => saveAlexaAlias(name.trim(), Number(productId)),
    onSuccess: async () => {
      setName("");
      await client.invalidateQueries({ queryKey: ["alexa-aliases"] });
    },
  });
  const remove = useMutation({
    mutationFn: deleteAlexaAlias,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["alexa-aliases"] });
    },
  });
  const products = inventory.data?.items ?? [];
  return (
    <main>
      <h2>Alias de Alexa</h2>
      <p>Asocia diferentes nombres de Alexa a un mismo producto de Despensa.</p>
      <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
        <label htmlFor="alexa-alias-name">Nombre en Alexa</label>
        <input id="alexa-alias-name" required maxLength={200} value={name}
          onChange={(event) => setName(event.target.value)} placeholder="Ej. leche normal" />
        <label htmlFor="alexa-alias-product">Producto de Despensa</label>
        <select id="alexa-alias-product" required value={productId}
          onChange={(event) => setProductId(event.target.value)}>
          <option value="">Selecciona un producto</option>
          {products.map((product) => (
            <option key={product.id} value={product.id}>{product.name}</option>
          ))}
        </select>
        <button type="submit" disabled={save.isPending || !productId || !name.trim()}>
          {save.isPending ? "Guardando…" : "Guardar alias"}
        </button>
      </form>
      {save.isError && <p role="alert">{save.error.message}</p>}
      {aliases.isLoading && <p>Cargando alias…</p>}
      {aliases.isError && <p role="alert">No se pudieron cargar los alias.</p>}
      <ul>
        {(aliases.data?.aliases ?? []).map((alias) => (
          <li key={alias.key}>
            <strong>{alias.name}</strong> → {products.find((p) => p.id === alias.product_id)?.name ?? `Producto #${alias.product_id}`}
            <button type="button" disabled={remove.isPending}
              onClick={() => remove.mutate(alias.key)} aria-label={`Eliminar alias ${alias.name}`}>
              Eliminar
            </button>
          </li>
        ))}
      </ul>
      {remove.isError && <p role="alert">{remove.error.message}</p>}
    </main>
  );
}
