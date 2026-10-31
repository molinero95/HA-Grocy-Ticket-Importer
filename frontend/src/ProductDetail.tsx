import { useQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { getProductVariants } from './api';

export function ProductDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['variants', id], queryFn: () => getProductVariants(id) });
  return <div className="detail-backdrop" role="dialog" aria-modal="true" aria-label="Ficha de producto"><section className="detail-panel"><div className="detail-heading"><div><span className="eyebrow">PRODUCTO GENÉRICO</span><h2>{data?.product.name ?? 'Ficha de producto'}</h2></div><button onClick={onClose} aria-label="Cerrar ficha"><X size={21}/></button></div>{isLoading && <p>Cargando variantes…</p>}{isError && <p role="alert">No se pudieron cargar las variantes. <button onClick={() => void refetch()}>Reintentar</button></p>}{data && <><h3>Variantes por supermercado</h3>{data.variants.length === 0 ? <p>Este producto aún no tiene variantes asociadas.</p> : <ul className="variant-list">{data.variants.map(v => <li key={v.barcode}><strong>{v.name}</strong><span>{[v.supermarket, v.brand].filter(Boolean).join(' · ') || 'Sin supermercado'}</span><code>{v.barcode}</code><small>{v.units_per_purchase} unidades por compra</small></li>)}</ul>}<p className="variant-note">Todas las variantes comparten el stock del producto genérico en Grocy.</p></>}</section></div>;
}
