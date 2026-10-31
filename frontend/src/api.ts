import type { ShoppingResponse } from './types';
/** Relative URLs preserve the Home Assistant ingress prefix. */
export async function getShopping(): Promise<ShoppingResponse> {
  const response = await fetch('api/v1/shopping', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('No se ha podido cargar la lista de la compra');
  return response.json() as Promise<ShoppingResponse>;
}
