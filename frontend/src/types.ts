export type ShoppingItem = { id: number; name: string; amount: number; unit: string; done: boolean; product_id: number | null; image_url: string | null };
export type MatchCandidate = { id: number; name: string; score?: number };
export type AlexaMatch = { key: string; name: string; candidates: MatchCandidate[]; selected_product_id?: number | null };
export type ShoppingResponse = { items: ShoppingItem[]; pending_matches: AlexaMatch[]; shopping_error: boolean; pending_matches_error: boolean };
export type InventoryItem = { id: number; name: string; amount: string; unit: string; image_url: string | null; shopping_amount: string; shopping_step: string; shopping_unit: string; shopping_can_subtract: boolean };
export type InventoryResponse = { items: InventoryItem[] };
export type ProductVariant = { barcode: string; name: string; supermarket: string; brand: string; units_per_purchase: number };
export type ProductVariantsResponse = { product: { id: number; name: string }; variants: ProductVariant[] };
