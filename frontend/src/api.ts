import type { ShoppingResponse, InventoryResponse, ProductVariantsResponse } from './types';

/** Relative paths preserve the Home Assistant ingress prefix. */
const base = 'api/v1/';
let csrfToken: string | undefined;

export async function getShopping(): Promise<ShoppingResponse> {
  const response = await fetch(base + 'shopping', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('No se ha podido cargar la lista de la compra');
  return response.json() as Promise<ShoppingResponse>;
}

async function token(): Promise<string> {
  if (csrfToken) return csrfToken;
  const response = await fetch(base + 'session', { credentials: 'same-origin' });
  if (!response.ok) throw new Error('No se ha podido verificar la sesión');
  const data = await response.json() as { csrf_token: string };
  csrfToken = data.csrf_token;
  return csrfToken;
}

async function mutate(path: string, method: 'POST' | 'DELETE', body?: object): Promise<void> {
  const response = await fetch(base + path, { method, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: body ? JSON.stringify(body) : undefined });
  if (!response.ok) {
    if (response.status === 403) csrfToken = undefined;
    const data = await response.json().catch(() => ({})) as { error?: string };
    throw new Error(data.error ?? 'No se ha podido guardar el cambio');
  }
}
export const toggleShopping = (id: number, done: boolean) => mutate('shopping/' + id + '/toggle', 'POST', { done });
export const removeShopping = (id: number) => mutate('shopping/' + id, 'DELETE');
export const chooseAlexaMatch = (key: string, productId: number) => mutate('alexa/matches/' + encodeURIComponent(key) + '/choose', 'POST', { product_id: productId });

export async function getInventory(): Promise<InventoryResponse> {
  const response = await fetch(base + 'inventory', { credentials: 'same-origin' });
  if (!response.ok) throw new Error('No se ha podido cargar el inventario');
  return response.json() as Promise<InventoryResponse>;
}
export async function lookupBarcode(code: string): Promise<number | null> {
  const response = await fetch(base + 'barcodes/' + encodeURIComponent(code), { credentials: 'same-origin' });
  if (!response.ok) throw new Error('No se ha podido buscar el código de barras');
  const result = await response.json() as { product_id: number | null };
  return result.product_id;
}
export async function stepShopping(productId: number, direction: 'plus' | 'minus'): Promise<void> {
  await mutate('shopping/products/' + productId + '/step', 'POST', { direction });
}

export async function getProductVariants(productId: number): Promise<ProductVariantsResponse> {
  const response = await fetch(base + 'products/' + productId + '/variants', { credentials: 'same-origin' });
  if (!response.ok) throw new Error('No se han podido cargar las variantes');
  return response.json() as Promise<ProductVariantsResponse>;
}

export type VariantInput = { barcode: string; name: string; supermarket: string; brand: string; units_per_purchase: string };
export const saveProductVariant = (productId: number, variant: VariantInput) => mutate('products/' + productId + '/variants', 'POST', variant);

export type ReceiptItem = { name: string; quantity: number | string; pieces_per_pack?: number; purchase_units?: string };
export type Receipt = { items: ReceiptItem[]; [key: string]: unknown };
export type ReceiptUpload = { receipt_id: string; receipt: Receipt };
export async function uploadReceipt(file: File): Promise<ReceiptUpload> {
  const body = new FormData();
  body.append('ticket', file);
  const response = await fetch(base + 'receipts', { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': await token() }, body });
  const result = await response.json() as ReceiptUpload & { error?: string };
  if (!response.ok) throw new Error(result.error ?? 'No se pudo procesar el ticket');
  return result;
}
export async function previewReceipt(id: string, items: { name: string; purchase_units: string; pieces_per_pack: number }[]): Promise<{ preview: string; ready_to_commit: boolean }> {
  const response = await fetch(base + 'receipts/' + encodeURIComponent(id) + '/preview', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: JSON.stringify({ items }) });
  const result = await response.json() as { preview: string; ready_to_commit: boolean; error?: string; details?: string };
  if (!response.ok) throw new Error(result.details ?? result.error ?? 'No se pudo simular la importación');
  return result;
}

export async function commitReceipt(id: string): Promise<{ status: string; output: string }> {
  const response = await fetch(base + 'receipts/' + encodeURIComponent(id) + '/commit', { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': await token() } });
  const result = await response.json() as { status: string; output: string; error?: string; details?: string };
  if (!response.ok) throw new Error(result.details ?? result.error ?? 'No se pudo confirmar la importación');
  return result;
}

export type CatalogUnit = { id: number; name: string };
export async function getCatalogUnits(): Promise<CatalogUnit[]> {
  const response = await fetch(base + 'catalog/units', { credentials: 'same-origin' });
  if (!response.ok) throw new Error('No se pudieron cargar las unidades');
  const result = await response.json() as { units: CatalogUnit[] };
  return result.units;
}
export type CatalogProductInput = { name: string; barcode: string; unit_id: number; initial_stock: string; pack_size: string };
export async function createCatalogProduct(value: CatalogProductInput): Promise<{ product_id: number; created: boolean }> {
  const response = await fetch(base + 'catalog/products', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: JSON.stringify(value) });
  const result = await response.json() as { product_id: number; created: boolean; error?: string; details?: string };
  if (!response.ok) throw new Error(result.details ?? result.error ?? 'No se pudo crear el producto');
  return result;
}
export async function editCatalogProduct(id: number, name: string, unitId: number): Promise<void> {
  const response = await fetch(base + 'catalog/products/' + id, { method: 'PATCH', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: JSON.stringify({ name, unit_id: unitId }) });
  const result = await response.json() as { error?: string };
  if (!response.ok) throw new Error(result.error ?? 'No se pudo actualizar el producto');
}
