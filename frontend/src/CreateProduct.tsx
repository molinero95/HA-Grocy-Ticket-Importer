import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { createCatalogProduct, getCatalogUnits } from './api';
import { isBarcode } from './barcodes';

export function CreateProduct({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const units = useQuery({ queryKey: ['catalog-units'], queryFn: getCatalogUnits });
  const [name, setName] = useState('');
  const [barcode, setBarcode] = useState('');
  const [unit, setUnit] = useState('');
  const [initialStock, setInitialStock] = useState('0');
  const [packSize, setPackSize] = useState('1');
  const [result, setResult] = useState('');
  const save = useMutation({ mutationFn: createCatalogProduct, onSuccess: response => { setResult(response.created ? 'Producto creado correctamente' : 'Este producto ya existía; no se ha duplicado'); void client.invalidateQueries({ queryKey: ['inventory'] }); } });
  return <div className="detail-backdrop" role="dialog" aria-modal="true" aria-label="Crear producto"><section className="detail-panel"><div className="detail-heading"><h2>Nuevo producto</h2><button onClick={onClose}>Cerrar</button></div>
    {units.isError && <p role="alert">No se pudieron cargar las unidades de Grocy. <button onClick={() => void units.refetch()}>Reintentar</button></p>}
    <form className="variant-form" onSubmit={event => { event.preventDefault(); save.mutate({ name: name.trim(), barcode: barcode.trim(), unit_id: Number(unit), initial_stock: initialStock, pack_size: packSize }); }}>
      <label className="variant-field">Nombre<input required maxLength={200} value={name} onChange={event => setName(event.target.value)}/></label>
      <label className="variant-field">Código de barras (opcional)<input value={barcode} onChange={event => setBarcode(event.target.value)}/></label>
      <label className="variant-field">Unidad<select required value={unit} onChange={event => setUnit(event.target.value)}><option value="">Seleccionar unidad</option>{units.data?.map(value => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>
      <label className="variant-field">Stock inicial<input type="number" min="0" step="0.01" value={initialStock} onChange={event => setInitialStock(event.target.value)}/></label>
      <label className="variant-field">Piezas por envase (si seleccionas pack)<input type="number" min="1" max="1000" step="1" value={packSize} onChange={event => setPackSize(event.target.value)}/></label>
      {save.isError && <p role="alert" className="notice">{save.error.message}</p>}{result && <p role="status">{result}</p>}
      <button type="submit" disabled={save.isPending || !unit || !name.trim() || Boolean(barcode && !isBarcode(barcode)) || !(Number(initialStock) >= 0) || !Number.isInteger(Number(packSize)) || Number(packSize) < 1}>Guardar producto</button>
    </form></section></div>;
}
