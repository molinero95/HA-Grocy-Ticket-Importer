import { useQuery } from '@tanstack/react-query';
import { getDuplicateCandidates } from './api';

export function Duplicates() {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['duplicates'], queryFn: getDuplicateCandidates });
  return <main><div className="heading"><div><span className="eyebrow">REVISIÓN DEL CATÁLOGO</span><h2>Posibles duplicados</h2><p>Coincidencias por nombre o código. No se fusiona ni elimina ningún producto automáticamente.</p></div><button onClick={() => void refetch()}>Volver a analizar</button></div>
    {isLoading && <p>Cargando candidatos…</p>}{isError && <p role="alert" className="notice">No se pudo analizar el catálogo. <button onClick={() => void refetch()}>Reintentar</button></p>}
    {data?.length === 0 && <p>No se han detectado posibles duplicados.</p>}
    <div className="items">{data?.map((group, index) => <article className="item" key={index}><div><strong>{group.reason}</strong><ul>{group.items.map(item => <li key={item.id}>{item.name} (ID {item.id}){item.barcodes.length > 0 && <small> · {item.barcodes.join(', ')}</small>}</li>)}</ul><small>Revisa estos artículos en Grocy antes de decidir si deben combinarse. La fusión está deshabilitada por seguridad.</small></div></article>)}</div>
  </main>;
}
