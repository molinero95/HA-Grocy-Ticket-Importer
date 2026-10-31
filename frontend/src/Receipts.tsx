import { useState } from 'react';
import { previewReceipt, uploadReceipt } from './api';
import type { ReceiptUpload } from './api';

type EditableItem = { name: string; purchase_units: string; pieces_per_pack: number };
export function Receipts() {
  const [receipt, setReceipt] = useState<ReceiptUpload | null>(null);
  const [items, setItems] = useState<EditableItem[]>([]);
  const [preview, setPreview] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const update = (index: number, patch: Partial<EditableItem>) => { setItems(previous => previous.map((item, i) => i === index ? { ...item, ...patch } : item)); setPreview(''); };
  async function upload(file: File) {
    setBusy(true); setError(''); setPreview(''); setReceipt(null);
    try {
      const result = await uploadReceipt(file);
      setReceipt(result);
      setItems(result.receipt.items.map(item => ({ name: item.name, purchase_units: String(item.quantity), pieces_per_pack: item.pieces_per_pack ?? 1 })));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function simulate() {
    if (!receipt) return;
    setBusy(true); setError(''); setPreview('');
    try { const result = await previewReceipt(receipt.receipt_id, items); setPreview(result.preview); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <main><div className="heading"><div><span className="eyebrow">IMPORTACIÓN SEGURA</span><h2>Escanear ticket</h2><p>Revisa los artículos antes de simular su entrada en Grocy.</p></div></div>
    <label className="variant-field">Foto o PDF del ticket<input type="file" accept="image/jpeg,image/png,application/pdf" capture="environment" disabled={busy} onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file); }}/></label>
    {busy && <p role="status">Procesando…</p>}{error && <p role="alert" className="notice">{error}</p>}
    {receipt && <section><h3>Revisión de artículos</h3><p>Las cantidades deben coincidir con el ticket. Puedes corregir nombres y unidades por envase.</p>
      {items.map((item, index) => <div className="variant-form" key={index}><label className="variant-field">Artículo<input value={item.name} onChange={event => update(index, { name: event.target.value })}/></label><label className="variant-field">Cantidad del ticket<input type="number" min="0.001" step="any" value={item.purchase_units} onChange={event => update(index, { purchase_units: event.target.value })}/></label><label className="variant-field">Piezas por envase<input type="number" min="1" max="1000" step="1" value={item.pieces_per_pack} onChange={event => update(index, { pieces_per_pack: Number(event.target.value) })}/></label></div>)}
      <button disabled={busy || items.some(item => !item.name.trim() || !Number.isInteger(item.pieces_per_pack) || item.pieces_per_pack < 1 || item.pieces_per_pack > 1000)} onClick={() => void simulate()}>Simular importación</button>
      {preview && <section><h3>Resultado de la simulación</h3><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{preview}</pre><p>La simulación no modifica el inventario. La confirmación definitiva se incorporará en un paso separado.</p></section>}
    </section>}</main>;
}
