import type { ShoppingResponse, InventoryResponse } from './types';

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
