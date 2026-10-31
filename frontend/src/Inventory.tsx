import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isBarcode } from './barcodes';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Minus, Plus, Search, ShoppingBasket } from 'lucide-react';
import { BarcodeScanner } from './BarcodeScanner';
import { ProductDetail } from './ProductDetail';
import { CreateProduct } from './CreateProduct';
import { getInventory, lookupBarcode, stepShopping } from './api';

export function Inventory() {
  const client = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['inventory'], queryFn: getInventory });
  const [query, setQuery] = useState('');
  const [barcodeProductId, setBarcodeProductId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const step = useMutation({ mutationFn: ({ id, direction }: { id: number; direction: 'plus' | 'minus' }) => stepShopping(id, direction), onSuccess: () => { void client.invalidateQueries({ queryKey: ['inventory'] }); void client.invalidateQueries({ queryKey: ['shopping'] }); }, onError: (e: Error) => setError(e.message) });
  const items = useMemo(() => (data?.items ?? []).filter(item => barcodeProductId !== null ? item.id === barcodeProductId : item.name.toLocaleLowerCase('es').includes(query.toLocaleLowerCase('es').trim())), [data, query, barcodeProductId]);
  useEffect(() => { if (!query.trim()) setBarcodeProductId(null); }, [query]);
  const searchBarcode = useCallback(async (value: string) => {
    setError('');
    try { const id = await lookupBarcode(value.trim()); setBarcodeProductId(id); if (id === null) setError('Código de barras no asociado a ningún producto'); }
    catch (e) { setError((e as Error).message); }
  }, []);
  return <main><div className="heading"><div><span className="eyebrow">LO QUE TIENES EN CASA</span><h2>Inventario</h2><p>Stock de Grocy y cantidades pendientes de compra.</p></div><div><span className="count">{items.length} artículos</span><button onClick={() => setCreating(true)}>+ Nuevo producto</button></div></div><div className="search-box"><Search size={19}/><input aria-label="Buscar por nombre o código de barras" placeholder="Nombre o código de barras" value={query} onChange={e => { setQuery(e.target.value); setBarcodeProductId(null); }} onKeyDown={e => { if (e.key === 'Enter' && isBarcode(query)) void searchBarcode(query); }}/><button title="Buscar código de barras" onClick={() => void searchBarcode(query)} disabled={!isBarcode(query)}>Buscar</button><BarcodeScanner onDetect={code => { setQuery(code); void searchBarcode(code); }}/></div>{isLoading && <p>Cargando inventario…</p>}{isError && <div role="alert" className="notice">No se ha podido cargar el inventario. <button onClick={() => void refetch()}>Reintentar</button></div>}{error && <p role="alert" className="notice">{error}</p>}<div className="items">{items.map(item => <article className="item inventory-item" key={item.id}><div className="item-main"><span className="item-icon"><ShoppingBasket size={19}/></span><div><button className="product-name" onClick={() => setSelectedProductId(item.id)}>{item.name}</button><small>En casa: {item.amount} {item.unit}</small></div></div><div className="quantity"><button disabled={step.isPending || !item.shopping_can_subtract} aria-label={'Quitar uno de compra: ' + item.name} onClick={() => step.mutate({ id: item.id, direction: 'minus' })}><Minus size={17}/></button><span>{item.shopping_amount} {item.shopping_unit}</span><button disabled={step.isPending} aria-label={'Añadir a compra: ' + item.name} onClick={() => step.mutate({ id: item.id, direction: 'plus' })}><Plus size={17}/></button></div></article>)}</div>{!isLoading && !isError && !items.length && <div className="empty"><h3>Sin resultados</h3><p>Prueba con otro nombre o código de barras.</p></div>}{creating && <CreateProduct onClose={() => setCreating(false)} />}{selectedProductId !== null && <ProductDetail id={selectedProductId} stockAmount={data?.items.find(item => item.id === selectedProductId)?.amount ?? '0'} stockUnit={data?.items.find(item => item.id === selectedProductId)?.unit ?? 'ud.'} onClose={() => setSelectedProductId(null)} />}</main>;
}
