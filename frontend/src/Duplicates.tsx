import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { getDuplicateCandidates, getMergePreview } from './api';

function MergeComparison({ sourceId, targetId, onClose }: { sourceId: number; targetId: number; onClose: () => void }) {
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['merge-preview', sourceId, targetId], queryFn: () => getMergePreview(sourceId, targetId) });
  return <section className="notice" aria-label="Vista previa de fusión"><h3>Comparación sin cambios</h3>{isLoading && <p>Consultando Grocy…</p>}{isError && <p role="alert">{error.message} <button onClick={() => void refetch()}>Reintentar</button></p>}{data && <><p><strong>Origen:</strong> {data.source.name} (ID {data.source.id}) · {data.source.stock_amount} unidades (ID {data.source.unit_id}) · envase ×{data.source.pack_size}</p><p><strong>Destino:</strong> {data.target.name} (ID {data.target.id}) · {data.target.stock_amount} unidades (ID {data.target.unit_id}) · envase ×{data.target.pack_size}</p><p><strong>Códigos origen:</strong> {data.source.barcodes.join(', ') || 'Ninguno'}</p><p><strong>Códigos destino:</strong> {data.target.barcodes.join(', ') || 'Ninguno'}</p><p><strong>Variantes:</strong> {data.source_variants.length} en origen, {data.target_variants.length} en destino</p><ul>{data.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul><p><strong>Fusión deshabilitada.</strong> No se ha modificado ningún dato.</p></>}<button onClick={onClose}>Cerrar comparación</button></section>;
}

export function Duplicates() {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['duplicates'], queryFn: getDuplicateCandidates });
  const [pair, setPair] = useState<[number, number] | null>(null);
  return <main><div className="heading"><div><span className="eyebrow">REVISIÓN DEL CATÁLOGO</span><h2>Posibles duplicados</h2><p>Coincidencias por nombre o código. No se fusiona ni elimina ningún producto automáticamente.</p></div><button onClick={() => void refetch()}>Volver a analizar</button></div>
    {pair && <MergeComparison sourceId={pair[0]} targetId={pair[1]} onClose={() => setPair(null)}/>}
    {isLoading && <p>Cargando candidatos…</p>}{isError && <p role="alert" className="notice">No se pudo analizar el catálogo. <button onClick={() => void refetch()}>Reintentar</button></p>}
    {data?.length === 0 && <p>No se han detectado posibles duplicados.</p>}
    <div className="items">{data?.map((group, index) => <article className="item" key={index}><div><strong>{group.reason}</strong><ul>{group.items.map(item => <li key={item.id}>{item.name} (ID {item.id}){item.barcodes.length > 0 && <small> · {item.barcodes.join(', ')}</small>}</li>)}</ul>{group.items.length >= 2 && <button onClick={() => setPair([group.items[0].id, group.items[1].id])}>Comparar los dos primeros</button>}<small>Revisa los productos antes de decidir si deben combinarse. La fusión está deshabilitada por seguridad.</small></div></article>)}</div>
  </main>;
}
