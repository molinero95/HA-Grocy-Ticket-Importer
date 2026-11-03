import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, X, Save, RotateCcw, Trash2, Plus } from "lucide-react";
import { deleteAlexaAlias, getAlexaAliases, getInventory, saveAlexaAlias, updateAlexaAlias } from "./api";
import type { AlexaAlias } from "./api";

type AliasRow = AlexaAlias & { pending?: boolean };
type Draft = { name: string; productId: string };
const empty: Draft = { name: "", productId: "" };
const normalize = (text: string) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es").trim().replace(/\s+/g, " ");
function AliasNameSelect({ label, value, names, disabled, onChange }: {
  label: string; value: string; names: string[]; disabled: boolean; onChange: (value: string) => void;
}) {
  const [manual, setManual] = useState(false);
  return <>
    <select aria-label={label} value={manual ? "__write_alias__" : value} disabled={disabled} onChange={event => {
      if (event.target.value === "__write_alias__") setManual(true);
      else { setManual(false); onChange(event.target.value); }
    }}>
      <option value="">Elige un alias</option>
      {names.map(name => <option key={name} value={name}>{name}</option>)}
      <option value="__write_alias__">Escribir otro alias…</option>
    </select>
    {manual && <input className="alias-custom-name" aria-label={`Escribir ${label.toLocaleLowerCase("es")}`} placeholder="Escribe el alias" maxLength={200} value={value} disabled={disabled} onChange={event => onChange(event.target.value)} />}
  </>;
}
export function AlexaAliases() {
  const client = useQueryClient();
  const lock = useRef(false);
  const [search, setSearch] = useState("");
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [newAlias, setNewAlias] = useState<Draft>(empty);
  const [omitted, setOmitted] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const aliases = useQuery({ queryKey: ["alexa-aliases"], queryFn: getAlexaAliases });
  const inventory = useQuery({ queryKey: ["inventory"], queryFn: getInventory });
  const products = [...(inventory.data?.items ?? [])].sort((a, b) => a.name.localeCompare(b.name, "es"));
  const savedRows = aliases.data?.aliases ?? [];
  const savedNames = new Set(savedRows.map(alias => normalize(alias.name)));
  const pendingNames = [...new Map((aliases.data?.suggestions ?? []).map(name => [normalize(name), name])).values()];
  const rows: AliasRow[] = [...savedRows, ...pendingNames.filter(name => !savedNames.has(normalize(name)) && !omitted.includes(normalize(name))).map(name => ({ key: "pending:" + normalize(name), name, product_id: 0, pending: true }))];
  const knownNames = [...new Map([...(aliases.data?.suggestions ?? []), ...rows.map(alias => alias.name), ...Object.values(drafts).map(draft => draft.name), newAlias.name].filter(Boolean).map(name => [normalize(name), name])).values()].sort((a, b) => a.localeCompare(b, "es"));
  const productName = (id: number) => id === 0 ? "Sin asociar" : products.find(product => product.id === id)?.name ?? `Producto no disponible (#${id})`;
  const query = normalize(search);
  const matches = (alias: AlexaAlias) => normalize(alias.name).includes(query) || normalize(productName(alias.product_id)).includes(query);
  const clearDraft = (key: string) => setDrafts(previous => { const next = { ...previous }; delete next[key]; return next; });
  const save = useMutation({
    mutationFn: ({ original, draft }: { original?: AlexaAlias; draft: Draft; draftKey?: string }) => original
      ? updateAlexaAlias(original, draft.name.trim(), Number(draft.productId))
      : saveAlexaAlias(draft.name.trim(), Number(draft.productId)),
    retry: false,
    onSuccess: async (_, { original, draft, draftKey }) => {
      if (draftKey) clearDraft(draftKey); else setNewAlias(empty);
      for (const row of rows) if (normalize(row.name) === normalize(draft.name)) clearDraft(row.key);
      setOmitted(previous => previous.filter(name => name !== normalize(draft.name)));
      setMessage(original ? "Alias actualizado" : "Alias añadido");
      await client.invalidateQueries({ queryKey: ["alexa-aliases"] });
    },
    onSettled: () => { lock.current = false; },
  });
  const remove = useMutation({
    mutationFn: (alias: AlexaAlias) => deleteAlexaAlias(alias.key, alias.product_id),
    retry: false,
    onSuccess: async (_, alias) => {
      clearDraft(alias.key); setOmitted(previous => [...previous, normalize(alias.name)]); setMessage("Alias eliminado");
      await client.invalidateQueries({ queryKey: ["alexa-aliases"] });
    },
    onSettled: () => { lock.current = false; },
  });
  const busy = save.isPending || remove.isPending;
  const valid = (draft: Draft) => Boolean(draft.name.trim() && products.some(product => String(product.id) === draft.productId));
  const changed = () => { save.reset(); remove.reset(); setMessage(""); };
  function persist(draft: Draft, row?: AliasRow) {
    if (lock.current || !valid(draft)) return;
    lock.current = true; changed(); save.mutate({ draft: { ...draft }, original: row?.pending ? undefined : row, draftKey: row?.key });
  }
  const options = products.map(product => <option key={product.id} value={product.id}>{product.name}</option>);
  return <main className="aliases-page">
    <h2>Alias de Alexa</h2>
    <p>Elige el alias a la izquierda y su producto a la derecha. Guarda cada fila para aplicar sus cambios. Si un alias ya existe, la nueva asociación sustituye a la anterior.</p>
    <div className="search-box alias-search">
      <Search size={20} aria-hidden="true" />
      <input type="search" aria-label="Buscar alias o producto" placeholder="Buscar alias o producto" value={search} onChange={event => setSearch(event.target.value)} />
      {search && <button type="button" className="alias-search-clear" aria-label="Borrar búsqueda de alias" onClick={() => setSearch("")}><X size={18} aria-hidden="true" /></button>}
    </div>
    {aliases.isLoading && <p role="status">Cargando alias…</p>}
    {aliases.isError && <p role="alert">No se pudieron cargar los alias. <button onClick={() => void aliases.refetch()}>Reintentar alias</button></p>}
    {inventory.isLoading && <p role="status">Cargando productos…</p>}
    {inventory.isError && <p role="alert">No se pudieron cargar los productos. <button onClick={() => void inventory.refetch()}>Reintentar productos</button></p>}
    {message && <p role="status" className="notice">{message}</p>}
    {save.isError && <p role="alert">{save.error.message}</p>}
    {remove.isError && <p role="alert">{remove.error.message}</p>}
    {aliases.isSuccess && <>
      <p className="alias-count" aria-live="polite">{rows.filter(matches).length} de {rows.length} alias</p>
      <table className="alias-table" aria-label="Alias y productos de Alexa">
        <thead><tr><th scope="col">Alias de Alexa</th><th scope="col">Producto de Despensa</th><th scope="col" className="alias-actions-heading">Acciones</th></tr></thead>
        <tbody>
          {rows.map(alias => {
            const draft = drafts[alias.key] ?? { name: alias.name, productId: String(alias.product_id) };
            const dirty = draft.name !== alias.name || draft.productId !== String(alias.product_id);
            const missing = !alias.pending && !products.some(product => product.id === alias.product_id);
            return <tr key={alias.key} hidden={!matches(alias)}>
              <td><AliasNameSelect label={`Alias: ${alias.name}`} value={draft.name} names={knownNames} disabled={busy} onChange={name => { changed(); setDrafts(previous => ({ ...previous, [alias.key]: { ...draft, name } })); }} /></td>
              <td><select aria-label={`Producto para ${alias.name}`} title={productName(Number(draft.productId))} value={draft.productId} disabled={busy || !inventory.isSuccess} onChange={event => { changed(); setDrafts(previous => ({ ...previous, [alias.key]: { ...draft, productId: event.target.value } })); }}>
                {alias.pending && <option value="0">Sin asociar</option>}{missing && <option value={alias.product_id} disabled>{productName(alias.product_id)}</option>}{options}
              </select>{alias.pending && <small className="alias-unavailable">Pendiente de asociar</small>}{missing && <small className="alias-unavailable">Producto no disponible</small>}</td>
              <td className="alias-row-actions">
                <button className="alias-icon-button" type="button" aria-label={`Guardar alias ${alias.name}`} title="Guardar cambios" disabled={busy || !dirty || !valid(draft) || aliases.isError} onClick={() => persist(draft, alias)}><Save size={18} aria-hidden="true" /></button>
                <button className="alias-icon-button" type="button" aria-label={`Descartar cambios de ${alias.name}`} title="Descartar cambios" disabled={busy || !dirty} onClick={() => { clearDraft(alias.key); changed(); }}><RotateCcw size={18} aria-hidden="true" /></button>
                <button className="alias-icon-button" type="button" aria-label={`${alias.pending ? "Ocultar fila" : "Eliminar alias"} ${alias.name}`} title={alias.pending ? "Ocultar fila sin asociación" : "Eliminar alias"} disabled={busy} onClick={() => { if (lock.current) return; changed(); if (alias.pending) { setOmitted(previous => [...previous, normalize(alias.name)]); clearDraft(alias.key); setMessage("Fila sin asociación ocultada"); return; } lock.current = true; remove.mutate(alias); }}><Trash2 size={18} aria-hidden="true" /></button>
              </td>
            </tr>;
          })}
          <tr className="alias-new-row">
            <td><AliasNameSelect label="Nuevo alias" value={newAlias.name} names={knownNames} disabled={busy} onChange={name => { changed(); setNewAlias({ ...newAlias, name }); }} /></td>
            <td><select aria-label="Producto del nuevo alias" value={newAlias.productId} disabled={busy || !inventory.isSuccess} onChange={event => { changed(); setNewAlias({ ...newAlias, productId: event.target.value }); }}><option value="">Elige un producto</option>{options}</select></td>
            <td className="alias-row-actions"><button type="button" className="secondary-button" disabled={busy || !valid(newAlias) || aliases.isError} onClick={() => persist(newAlias)}><Plus size={18} aria-hidden="true" />Añadir alias</button></td>
          </tr>
        </tbody>
      </table>
      {rows.length === 0 ? <p className="alias-empty">Todavía no hay alias. Añade el primero en la tabla.</p> : query && !rows.some(matches) && <p className="alias-empty">No hay alias ni productos que coincidan con la búsqueda.</p>}
    </>}
  </main>;
}
