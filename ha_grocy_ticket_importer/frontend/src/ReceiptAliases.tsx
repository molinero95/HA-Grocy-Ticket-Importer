import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Save, RotateCcw, Trash2 } from "lucide-react";
import { deleteReceiptAlias, getReceiptAliases, updateReceiptAlias } from "./api";
import type { ReceiptAlias } from "./api";

type Draft = { merchant: string; source_name: string; product_id: number };
const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
export function ReceiptAliases() {
  const client = useQueryClient();
  const data = useQuery({ queryKey: ["receipt-aliases"], queryFn: getReceiptAliases, retry: false });
  const [search, setSearch] = useState("");
  const [shop, setShop] = useState("");
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [deleting, setDeleting] = useState<ReceiptAlias | null>(null);
  const [message, setMessage] = useState("");
  const lock = useRef(false);
  const rowKey = (row: ReceiptAlias) => JSON.stringify([row.merchant, row.source_name]);
  const products = data.data?.products ?? [];
  const rows = data.data?.aliases ?? [];
  const shops = [...new Set(rows.map(row => row.merchant))];
  const productName = (id: number) => products.find(product => product.id === id)?.name ?? `Producto no disponible (#${id})`;
  const mutation = useMutation({
    mutationFn: ({ row, draft }: { row: ReceiptAlias; draft?: Draft }) => draft ? updateReceiptAlias(row, draft) : deleteReceiptAlias(row),
    retry: false,
    onSuccess: async (_, { row, draft }) => {
      setDrafts(previous => { const next = { ...previous }; delete next[rowKey(row)]; return next; });
      if (!draft && shop === row.merchant && rows.filter(item => item.merchant === shop).length === 1) setShop("");
      setDeleting(null); setMessage(draft ? "Asociación de ticket actualizada" : "Asociación de ticket eliminada");
      await Promise.all([client.invalidateQueries({ queryKey: ["receipt-aliases"] }), client.invalidateQueries({ queryKey: ["receipt-review"] })]);
    },
    onSettled: () => { lock.current = false; },
  });
  function submit(row: ReceiptAlias, draft?: Draft) {
    if (lock.current) return;
    lock.current = true; setMessage(""); mutation.mutate({ row, draft });
  }
  const visible = rows.filter(row => (!shop || row.merchant === shop) && normalize([row.merchant, row.source_name, productName(row.product_id)].join(" ")).includes(normalize(search.trim())));
  return <main className="aliases-page receipt-aliases-page">
    <h2>Alias de tickets</h2>
    <p>Esto recuerda Despensa de cada supermercado. Puedes corregir el texto y el producto o borrar la asociación. Los cambios se aplican a futuras revisiones; no modifican tickets importados ni existencias.</p>
    <div className="search-box alias-search"><Search size={20} aria-hidden="true" /><input type="search" aria-label="Buscar supermercado, texto o producto" placeholder="Buscar supermercado, texto o producto" value={search} onChange={event => setSearch(event.target.value)} /></div>
    <label className="variant-field receipt-shop-filter">Supermercado<select value={shop} onChange={event => setShop(event.target.value)}><option value="">Todos los supermercados</option>{shops.map(name => <option key={name}>{name}</option>)}</select></label>
    {data.isPending && <p role="status">Consultando asociaciones recordadas…</p>}
    {data.isError && <p role="alert">{data.error.message}</p>}
    <button className="secondary-button" disabled={data.isFetching || mutation.isPending} onClick={() => { mutation.reset(); setDrafts({}); setDeleting(null); void data.refetch(); }}>Actualizar asociaciones</button>
    {message && <p role="status" className="notice">{message}</p>}
    {mutation.isError && <p role="alert">{mutation.error.message}</p>}
    {data.isSuccess && <>
      <p>{visible.length} de {rows.length} asociaciones</p>
      <div className="receipt-alias-table-wrap"><table className="alias-table receipt-alias-table" aria-label="Asociaciones de tickets por supermercado"><thead><tr><th scope="col">Supermercado</th><th scope="col">Texto del ticket</th><th scope="col">Producto y unidades</th><th scope="col">Acciones</th></tr></thead><tbody>
        {visible.map(row => {
          const id = rowKey(row), draft = drafts[id] ?? { merchant: row.merchant, source_name: row.source_name, product_id: row.product_id };
          const chosen = products.find(product => product.id === draft.product_id);
          const dirty = draft.merchant !== row.merchant || draft.source_name !== row.source_name || draft.product_id !== row.product_id || row.stale;
          const update = (patch: Partial<Draft>) => setDrafts(previous => ({ ...previous, [id]: { ...draft, ...patch } }));
          return <tr key={id}>
            <td><input aria-label={`Supermercado de ${row.source_name} (${row.merchant})`} maxLength={200} disabled={mutation.isPending} value={draft.merchant} onChange={event => update({ merchant: event.target.value })} /></td>
            <td><input aria-label={`Texto de ${row.source_name} (${row.merchant})`} maxLength={200} disabled={mutation.isPending} value={draft.source_name} onChange={event => update({ source_name: event.target.value })} /></td>
            <td><select aria-label={`Producto para ${row.source_name} (${row.merchant})`} disabled={mutation.isPending} value={draft.product_id} onChange={event => update({ product_id: Number(event.target.value) })}>{!products.some(product => product.id === row.product_id) && <option value={row.product_id} disabled>{productName(row.product_id)}</option>}{products.map(product => <option key={product.id} value={product.id}>{product.name}</option>)}</select>
              <small>Recordado: {row.stock_unit === "kg" ? "kg" : "Piece"} · {row.pieces_per_pack} por compra</small>
              {chosen && <small>Al guardar: {chosen.stock_unit === "kg" ? "kg" : "Piece"} · {chosen.pieces_per_pack} por compra</small>}
              {row.stale && <small className="alias-unavailable">Revisar: producto ausente o unidades modificadas</small>}
            </td>
            <td><div className="alias-row-actions">
              <button className="alias-icon-button" aria-label={`Guardar ${row.source_name} (${row.merchant})`} title="Guardar asociación" disabled={mutation.isPending || !dirty || !chosen || !draft.merchant.trim() || !draft.source_name.trim()} onClick={() => submit(row, { ...draft })}><Save size={18} /></button>
              <button className="alias-icon-button" aria-label={`Descartar ${row.source_name} (${row.merchant})`} title="Descartar cambios" disabled={mutation.isPending || !drafts[id]} onClick={() => setDrafts(previous => { const next = { ...previous }; delete next[id]; return next; })}><RotateCcw size={18} /></button>
              <button className="alias-icon-button" aria-label={`Eliminar ${row.source_name} (${row.merchant})`} title="Eliminar asociación" disabled={mutation.isPending} onClick={() => setDeleting(row)}><Trash2 size={18} /></button>
            </div>{deleting && rowKey(deleting) === id && <div className="receipt-alias-confirm" role="group" aria-label="Confirmar eliminación de asociación"><p>¿Eliminar esta asociación recordada?</p><button className="secondary-button" disabled={mutation.isPending} onClick={() => setDeleting(null)}>No</button><button className="danger-button" disabled={mutation.isPending} onClick={() => submit(deleting)}>Sí, eliminar</button></div>}</td>
          </tr>;
        })}
      </tbody></table></div>
      {!visible.length && <p>{rows.length ? "No hay asociaciones que coincidan con el filtro." : "Todavía no hay asociaciones recordadas. Se guardan al importar un ticket con «Recordar»."}</p>}
    </>}
  </main>;
}
