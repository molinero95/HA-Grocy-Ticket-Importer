import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { getDuplicateCandidates, getMergePreview } from './api';

export function Duplicates() {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['duplicates'], queryFn: getDuplicateCandidates });
  const [pair, setPair] = useState<[number, number] | null>(null);
  return <main><div className="heading"><div><span className="eyebrow">REVISIÓN DEL CATÁLOGO</span><h2>Posibles duplicados</h2><p>Coincidencias por nombre o código. No se fusiona ni elimina ningún producto automáticamente.</p></div><button onClick={() => void refetch()}>Volver a analizar</button></div>
    {isLoading && <p>Cargando candidatos…</p>}{isError && <p role="alert" className="notice">No se pudo analizar el catálogo. <button onClick={() => void refetch()}>Reintentar</button></p>}
    {data?.length === 0 && <p>No se han detectado posibles duplicados.</p>}
    {pair && <section className="item"><h3>Vista previa de fusión (solo lectura)</h3><button type="button" onClick={() => setPair(null)}>Cerrar</button>{preview.isLoading && <p>Comprobando productos…</p>}{preview.isError && <p role="alert">{preview.error.message}</p>}{preview.data && <><p><strong>Origen:</strong> {preview.data.source.name} · {preview.data.source.stock_amount} unidades (unidad Grocy {preview.data.source.unit_id}) · códigos: {preview.data.source.barcodes.join(', ') || 'ninguno'}</p><p><strong>Destino:</strong> {preview.data.target.name} · {preview.data.target.stock_amount} unidades (unidad Grocy {preview.data.target.unit_id}) · códigos: {preview.data.target.barcodes.join(', ') || 'ninguno'}</p><p>Variantes: {preview.data.source_variants.length} en origen y {preview.data.target_variants.length} en destino.</p><strong>Bloqueos de seguridad:</strong><ul>{preview.data.blockers.map(blocker => <li key={blocker}>{blocker}</li>)}</ul><p>No se ha modificado ningún dato.</p></>}</section>}
    <div className="items">{data?.map((group, index) => <article className="item" key={index}><div><strong>{group.reason}</strong><ul>{group.items.map(item => <li key={item.id}>{item.name} (ID {item.id}){item.barcodes.length > 0 && <small> · {item.barcodes.join(', ')}</small>}</li>)}</ul>{group.items.length >= 2 && <button onClick={() => setPair([group.items[0].id, group.items[1].id])}>Comparar los dos primeros</button>}<small>Revisa los productos antes de decidir si deben combinarse. La fusión está deshabilitada por seguridad.</small></div></article>)}</div>
  </main>;
}
