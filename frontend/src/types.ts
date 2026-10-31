export type ShoppingItem = { id: number; name: string; amount: number; unit: string; done: boolean; product_id: number | null; image_url: string | null };
export type MatchCandidate = { id: number; name: string; score?: number };
export type AlexaMatch = { key: string; name: string; candidates: MatchCandidate[]; selected_product_id?: number | null };
export type ShoppingResponse = { items: ShoppingItem[]; pending_matches: AlexaMatch[]; shopping_error: boolean; pending_matches_error: boolean };
