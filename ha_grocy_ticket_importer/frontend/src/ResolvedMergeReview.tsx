import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { commitResolvedMerge, getMergeResolutionOptions, previewMergeResolution } from "./api";
import type { MergeResolution, ResolvedMergePreview } from "./api";

const pieces = new Set(["piece", "pieces", "unidad", "unidades"]);
const packs = new Set(["pack", "paquete", "envase"]);
export function ResolvedMergeReview({ pair, onSwap, onClose, onBack, onMerged }: {
  pair: [number, number]; onSwap: () => void; onClose: () => void; onBack: () => void; onMerged: () => void;
}) {
  const options = useQuery({ queryKey: ["merge-resolution-options", pair], queryFn: () => getMergeResolutionOptions(...pair), retry: false, staleTime: 0 });
  const [form, setForm] = useState<MergeResolution | null>(null);
  const [review, setReview] = useState<ResolvedMergePreview | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [attempted, setAttempted] = useState(false);
  const submitted = useRef(false);
  const revision = useRef(0);
  const [previewError, setPreviewError] = useState("");
  useEffect(() => {
    if (!options.data || form) return;
    const data = options.data;
    const unit = data.units.find(item => item.id === data.target.unit_id && !packs.has(item.name.toLowerCase()))
      ?? data.units.find(item => pieces.has(item.name.toLowerCase())) ?? data.units[0];
    if (!unit) return;
    const sourceSame = data.source.unit_id === unit.id, targetSame = data.target.unit_id === unit.id;
    const purchase = data.units.find(item => item.id === data.target.purchase_unit_id);
    const keepPack = pieces.has(unit.name.toLowerCase()) && purchase && packs.has(purchase.name.toLowerCase());
    setForm({ final_name: data.target.name, unit_id: unit.id, source_factor: sourceSame ? "1" : "", target_factor: targetSame ? "1" : "",
      purchase_unit_id: keepPack ? purchase.id : unit.id, pack_size: keepPack ? String(data.target.pack_size) : "1",
      final_stock: sourceSame && targetSame ? String(Number(data.source.stock_amount) + Number(data.target.stock_amount)) : "" });
  }, [options.data, form]);
  const preview = useMutation({
    mutationFn: ({ value }: { value: MergeResolution; revision: number }) => previewMergeResolution(...pair, value),
    retry: false,
    onSuccess: (data, variables) => { if (variables.revision === revision.current) setReview(data); },
    onError: (error, variables) => { if (variables.revision === revision.current) setPreviewError(error.message); },
  });
  const merge = useMutation({ mutationFn: () => commitResolvedMerge(review!, confirmation, crypto.randomUUID()), retry: false, onSuccess: onMerged });
  const locked = attempted || preview.isPending;
  function edit(patch: Partial<MergeResolution>) {
    revision.current++; setReview(null); setConfirmation(""); setPreviewError("");
    setForm(previous => previous && ({ ...previous, ...patch }));
  }
  const units = options.data?.units ?? [];
  const unitName = (id: number) => units.find(unit => unit.id === id)?.name ?? String(id);
  const total = form && options.data && form.source_factor && form.target_factor
    ? Number(options.data.source.stock_amount) * Number(form.source_factor) + Number(options.data.target.stock_amount) * Number(form.target_factor) : NaN;
  return <section className="item audit-panel merge-resolution" aria-label="Definir combinación final">
    <h3>Información final de combinación</h3>
    <div className="variant-buttons"><button className="secondary-button" disabled={merge.isPending} onClick={onClose}>Cerrar revisión</button><button className="secondary-button" disabled={attempted} onClick={onBack}>Volver a combinación directa</button></div>
    {options.isPending && <p role="status">Consultando unidades, stock y referencias…</p>}
    {options.isError && <p role="alert">{options.error.message} <button className="secondary-button" onClick={() => void options.refetch()}>Reintentar datos</button></p>}
    {options.data && form && <>
      <label className="variant-field">Producto que conservarás<select value={options.data.target.id} disabled={locked} onChange={event => { if (Number(event.target.value) !== options.data!.target.id) onSwap(); }}>{[options.data.target, options.data.source].map(product => <option key={product.id} value={product.id}>{product.name} (ID {product.id})</option>)}</select></label>
      <p>Se conservará el ID {options.data.target.id}, su descripción y su fotografía. El otro producto se integrará y desaparecerá.</p>
      <div className="variant-form">
        <label className="variant-field">Nombre final<input maxLength={200} value={form.final_name} disabled={locked} onChange={event => edit({ final_name: event.target.value })} /></label>
        <label className="variant-field">Unidad de stock final<select value={form.unit_id} disabled={locked} onChange={event => {
          const id = Number(event.target.value);
          edit({ unit_id: id, purchase_unit_id: id, pack_size: "1", source_factor: options.data!.source.unit_id === id ? "1" : "", target_factor: options.data!.target.unit_id === id ? "1" : "", final_stock: "", threshold_amount: undefined });
        }}>{units.filter(unit => !packs.has(unit.name.toLowerCase())).map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}</select></label>
        {["source", "target"].map(key => {
          const side = key as "source" | "target"; const product = options.data![side]; const field = side === "source" ? "source_factor" : "target_factor";
          return <label className="variant-field" key={side}>Equivalencia de {product.name}
            <span>1 {unitName(product.unit_id)} de este producto equivale a:</span>
            <input aria-label={`Equivalencia de ${product.name}`} type="number" min="0.000001" step="0.000001" value={form[field]} disabled={locked || product.unit_id === form.unit_id} onChange={event => edit({ [field]: event.target.value, final_stock: "" })} />
            <span>{unitName(form.unit_id)} finales · stock actual: {product.stock_amount} {unitName(product.unit_id)}</span>
          </label>;
        })}
        <label className="variant-field">Stock final que debe quedar<input type="number" min="0" max="1000000" step="0.01" disabled={locked} value={form.final_stock} onChange={event => edit({ final_stock: event.target.value })} /></label>
        {Number.isFinite(total) && <button className="secondary-button" type="button" disabled={locked} onClick={() => edit({ final_stock: String(Math.round(total * 100) / 100) })}>Usar suma convertida ({Number(total.toFixed(6))} {unitName(form.unit_id)})</button>}
        <p>Indica el total real que quedará. Si difiere de la suma convertida, se registrará un ajuste de inventario.</p>
        <label className="variant-field">Unidad de compra final<select disabled={locked} value={form.purchase_unit_id} onChange={event => edit({ purchase_unit_id: Number(event.target.value), pack_size: "1" })}>{units.filter(unit => unit.id === form.unit_id || (pieces.has(unitName(form.unit_id).toLowerCase()) && packs.has(unit.name.toLowerCase()))).map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}</select></label>
        {form.purchase_unit_id !== form.unit_id && <label className="variant-field">Piezas por envase final<input type="number" min="1" max="1000" step="1" value={form.pack_size} disabled={locked} onChange={event => edit({ pack_size: event.target.value })} /></label>}
        <label className="variant-field">Umbral de stock bajo final (opcional)<input type="number" min="0" max="1000000" step="0.01" placeholder="Conservar su equivalencia" value={form.threshold_amount ?? ""} disabled={locked} onChange={event => edit({ threshold_amount: event.target.value || undefined })} /></label>
        <button className="primary-button" type="button" disabled={locked || !form.final_name.trim() || !form.source_factor || !form.target_factor || form.final_stock === ""} onClick={() => {
          revision.current++; setReview(null); setConfirmation(""); setPreviewError(""); preview.mutate({ value: { ...form }, revision: revision.current });
        }}>{preview.isPending ? "Calculando resultado…" : "Revisar resultado final"}</button>
      </div>
      {previewError && <p role="alert">{previewError}</p>}
      {review && <div className="merge-result" aria-label="Resultado final revisado">
        <h4>Resultado de la combinación</h4>
        <dl><dt>Producto final</dt><dd>{review.resolution.final_name} (ID {review.target.id})</dd><dt>Suma convertida</dt><dd>{review.combined_stock} {review.unit_name}</dd><dt>Stock final</dt><dd>{review.resolution.final_stock} {review.unit_name}</dd><dt>Ajuste de inventario</dt><dd>{review.stock_correction} {review.unit_name}</dd><dt>Umbral final</dt><dd>{review.resolution.threshold_amount} {review.unit_name}</dd></dl>
        {review.blockers.length > 0 && <div role="alert"><strong>Referencias que requieren revisión</strong><ul>{review.blockers.map(reason => <li key={reason}>{reason}</li>)}</ul></div>}
        {review.can_merge && <form className="variant-form" onSubmit={event => {
          event.preventDefault(); if (submitted.current || confirmation !== review.resolution.final_name) return;
          submitted.current = true; setAttempted(true); merge.mutate();
        }}>
          <p>Las unidades, cantidades y precios del historial se convertirán antes de reunir los productos. La combinación y el ajuste final no se pueden deshacer desde Despensa.</p>
          <label className="variant-field">Escribe «{review.resolution.final_name}» para confirmar combinación<input autoComplete="off" value={confirmation} disabled={attempted} onChange={event => setConfirmation(event.target.value)} /></label>
          <button className="primary-button danger-button" disabled={attempted || confirmation !== review.resolution.final_name}>{merge.isPending ? "Aplicando combinación…" : "Combinar con estos datos finales"}</button>
        </form>}
      </div>}
    </>}
    {merge.isError && <p role="alert">{merge.error.message} No repitas la operación sin comprobar ambos productos y el stock en Grocy.</p>}
  </section>;
}
