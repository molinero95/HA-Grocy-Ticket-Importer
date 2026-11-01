import type {
  ShoppingResponse,
  InventoryResponse,
  ProductVariantsResponse,
} from "./types";

/** The document's base element points at the ingress root; credentials stay same-origin. */
const base = "api/v1/";
let csrfToken: string | undefined;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function token(): Promise<string> {
  if (csrfToken) return csrfToken;
  // Auth status is deliberately public, so the login form can bootstrap CSRF.
  return (await getAuthStatus()).csrf_token;
}

const errorMessages: Record<string, string> = {
  operation_in_progress:
    "Hay otra operación en curso. Actualiza los datos antes de continuar.",
  invalid_credentials: "Contraseña incorrecta.",
  stale_or_invalid_candidate:
    "La sugerencia ha cambiado. Actualiza la lista y vuelve a elegir.",
  selection_failed: "No se pudo guardar la selección. Actualiza la lista.",
  shopping_update_failed:
    "No se pudo confirmar el cambio. Actualiza la lista antes de reintentar.",
  shopping_remove_failed:
    "No se pudo confirmar la eliminación. Actualiza la lista.",
  catalog_edit_uncertain:
    "No se pudo confirmar el cambio. Comprueba la ficha en Grocy antes de reintentar.",
  invalid_payload: "Los datos enviados no son válidos. Actualiza la página.",
  catalog_units_unavailable: "No se pudieron cargar las unidades de Grocy.",
  barcodes_unavailable: "No se pudieron cargar los códigos de barras.",
  import_in_progress: "Hay una importación en curso. Espera a que termine.",
  single_receipt_required: "Selecciona un solo ticket.",
  unsupported_receipt_format: "El ticket debe ser PDF, JPG o PNG.",
  receipt_extraction_failed:
    "No se pudo leer el ticket. Comprueba la conexión y la configuración de OpenAI.",
  receipt_not_found: "No se encontró el ticket. Vuelve a abrirlo.",
  invalid_receipt_items: "Revisa los nombres y las piezas por pack del ticket.",
  receipt_preview_failed:
    "No se pudo simular la importación. Comprueba la conexión.",
  receipt_preview_rejected:
    "Grocy ha rechazado la simulación. Revisa los productos.",
  preview_required: "Simula el ticket antes de importarlo.",
  receipt_changed_since_preview:
    "El ticket ha cambiado. Vuelve a simular antes de importarlo.",
  receipt_already_submitted:
    "Este ticket ya se ha enviado. Comprueba el stock antes de continuar.",
  receipt_commit_uncertain:
    "No se pudo confirmar toda la importación. Comprueba Grocy antes de reintentar.",
};

async function request<T>(
  path: string,
  method = "GET",
  body?: object | FormData,
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers["X-CSRF-Token"] = await token();
  if (body && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  const response = await fetch(base + path, {
    method,
    credentials: "same-origin",
    headers,
    body:
      body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  });
  const data = (await response.json().catch(() => ({}))) as {
    error?: string;
    details?: string;
  };
  if (!response.ok) {
    if (response.status === 401 || response.status === 403)
      csrfToken = undefined;
    if (response.status === 401 && path !== "auth/login")
      window.dispatchEvent(new Event("despensa:session-expired"));
    throw new ApiError(
      data.details ??
        (data.error ? (errorMessages[data.error] ?? data.error) : undefined) ??
        "No se pudo completar la operación. Comprueba la conexión.",
      response.status,
    );
  }
  return data as T;
}

export const getShopping = () => request<ShoppingResponse>("shopping");
export const toggleShopping = (id: number, done: boolean) =>
  request("shopping/" + id + "/toggle", "POST", { done });
export const clearCompletedShopping = () =>
  request<{ removed: number }>("shopping/clear-completed", "POST");
export const removeShopping = (id: number) =>
  request("shopping/" + id, "DELETE");
export const chooseAlexaMatch = (key: string, productId: number) =>
  request("alexa/matches/" + encodeURIComponent(key) + "/choose", "POST", {
    product_id: productId,
  });
export const getInventory = () => request<InventoryResponse>("inventory");
export async function lookupBarcode(code: string): Promise<number | null> {
  return (
    await request<{ product_id: number | null }>(
      "barcodes/" + encodeURIComponent(code),
    )
  ).product_id;
}
export const stepShopping = (id: number, direction: "plus" | "minus") =>
  request("shopping/products/" + id + "/step", "POST", { direction });
export const getProductVariants = (id: number) =>
  request<ProductVariantsResponse>("products/" + id + "/variants");
export const saveProductVariant = (id: number, variant: VariantInput) =>
  request("products/" + id + "/variants", "POST", variant);
export async function uploadReceipt(file: File): Promise<ReceiptUpload> {
  const form = new FormData();
  form.append("ticket", file);
  return request<ReceiptUpload>("receipts", "POST", form);
}
export const previewReceipt = (
  id: string,
  items: { name: string; purchase_units: string; pieces_per_pack: number }[],
) =>
  request<{ preview: string; ready_to_commit: boolean }>(
    "receipts/" + encodeURIComponent(id) + "/preview",
    "POST",
    { items },
  );
export const commitReceipt = (id: string) =>
  request<{ status: string; output: string }>(
    "receipts/" + encodeURIComponent(id) + "/commit",
    "POST",
  );
export async function getCatalogUnits(): Promise<CatalogUnit[]> {
  return (await request<{ units: CatalogUnit[] }>("catalog/units")).units;
}
export const createCatalogProduct = (value: CatalogProductInput) =>
  request<{ product_id: number; created: boolean }>(
    "catalog/products",
    "POST",
    value,
  );
export const editCatalogProduct = (id: number, name: string, unitId: number) =>
  request("catalog/products/" + id, "PATCH", {
    name,
    unit_id: unitId || undefined,
  });
export const adjustCatalogStock = (
  id: number,
  desired: string,
  expected: string,
) =>
  request("catalog/products/" + id + "/stock", "POST", {
    desired_amount: desired,
    expected_amount: expected,
  });
export async function getCatalogBarcodes(id: number): Promise<string[]> {
  return (
    await request<{ barcodes: string[] }>(
      "catalog/products/" + id + "/barcodes",
    )
  ).barcodes;
}
export const saveCatalogBarcode = (
  id: number,
  barcode: string,
  oldBarcode?: string,
) =>
  request(
    "catalog/products/" +
      id +
      "/barcodes" +
      (oldBarcode ? "/" + encodeURIComponent(oldBarcode) : ""),
    oldBarcode ? "PATCH" : "POST",
    { barcode },
  );
export const removeCatalogBarcode = (id: number, code: string) =>
  request(
    "catalog/products/" + id + "/barcodes/" + encodeURIComponent(code),
    "DELETE",
  );
export async function uploadCatalogPhoto(id: number, file: File) {
  const form = new FormData();
  form.append("photo", file);
  return request("catalog/products/" + id + "/photo", "POST", form);
}
export async function getDuplicateCandidates(): Promise<DuplicateGroup[]> {
  return (await request<{ groups: DuplicateGroup[] }>("catalog/duplicates"))
    .groups;
}
export const getMergePreview = (sourceId: number, targetId: number) =>
  request<MergePreview>(
    "catalog/merge-preview?" +
      new URLSearchParams({
        source_id: String(sourceId),
        target_id: String(targetId),
      }),
  );
export const getCatalogAudit = () => request<CatalogAudit>("catalog/audit");
export async function getAuthStatus(): Promise<AuthStatus> {
  const status = await request<AuthStatus>("auth/status");
  csrfToken = status.csrf_token;
  return status;
}
export async function loginStandalone(password: string): Promise<void> {
  try {
    const result = await request<AuthStatus>("auth/login", "POST", {
      password,
    });
    csrfToken = result.csrf_token;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401)
      throw new Error("Contraseña incorrecta");
    throw error;
  }
}
export async function logoutStandalone(): Promise<void> {
  await request("auth/logout", "POST");
  csrfToken = undefined;
}

export type PhotoLookup = {
  barcode: string;
  name: string;
  image_url: string | null;
  source_url: string;
  attribution: string;
};
export const lookupPhoto = (code: string) =>
  request<{ photo: PhotoLookup | null }>("photos/" + encodeURIComponent(code));
export const saveDiscoveredPhoto = (id: number, code: string) =>
  request<{ saved: boolean; image_url: string | null }>(
    "catalog/products/" + id + "/photo-lookup",
    "POST",
    { barcode: code },
  );
export type CatalogProduct = {
  active?: boolean;
  id: number;
  name: string;
  unit_id: number;
  purchase_unit_id: number;
  stock_amount: string;
  image_url: string | null;
  is_pack: boolean;
  pack_size: number;
  barcodes: string[];
  units: CatalogUnit[];
};
export const getCatalogProduct = (id: number) =>
  request<CatalogProduct>("catalog/products/" + id);
export type VariantInput = {
  barcode: string;
  name: string;
  supermarket: string;
  brand: string;
  units_per_purchase: string;
};
export type ReceiptItem = {
  name: string;
  quantity: number | string;
  pieces_per_pack?: number;
  purchase_units?: string;
};
export type Receipt = { items: ReceiptItem[]; [key: string]: unknown };
export type ReceiptUpload = { receipt_id: string; receipt: Receipt };
export type CatalogUnit = { id: number; name: string };
export type CatalogProductInput = {
  name: string;
  barcode: string;
  unit_id: number;
  initial_stock: string;
  pack_size: string;
};
export type DuplicateCandidate = {
  id: number;
  name: string;
  barcodes: string[];
};
export type DuplicateGroup = { reason: string; items: DuplicateCandidate[] };
export type MergeProduct = {
  id: number;
  name: string;
  stock_amount: string;
  unit_id: number;
  purchase_unit_id: number;
  pack_size: number;
  barcodes: string[];
};
export type MergePreview = {
  source: MergeProduct;
  target: MergeProduct;
  source_variants: unknown[];
  target_variants: unknown[];
  blockers: string[];
  audit?: {
    collections: {
      collection: string;
      label: string;
      status: string;
      count: number | null;
      references: {
        id: number | null;
        product_id: number | null;
        field: string;
      }[];
    }[];
  };
  can_merge: false;
};
export type CatalogAudit = {
  schema_version: number;
  source: string;
  products: {
    id: number;
    name: string;
    stock_amount: string;
    barcodes: string[];
    shopping_entry_ids: number[];
    variants: unknown[];
  }[];
  barcode_conflicts: unknown[];
  unlinked_shopping_entries: number[];
  shopping_notes?: unknown[];
};
export type AuthStatus = {
  authenticated: boolean;
  ingress: boolean;
  csrf_token: string;
};
export const consumeCatalogProduct = (
  id: number,
  amount: string,
  expected: string,
  replenish: boolean,
  operationId: string,
) =>
  request<{ shopping_error: boolean; shopping_added: boolean }>(
    "catalog/products/" + id + "/consume",
    "POST",
    {
      amount,
      expected_amount: expected,
      add_to_list: replenish,
      operation_id: operationId,
    },
  );

export const getArchivedProducts = () =>
  request<InventoryResponse>("catalog/archived");
export const setCatalogProductActive = (
  id: number,
  name: string,
  active: boolean,
  operationId: string,
) =>
  request("catalog/products/" + id + "/active", "POST", {
    expected_name: name,
    active,
    operation_id: operationId,
  });

export const savePurchaseConfiguration = (
  id: number,
  purchaseUnit: number,
  factor: string,
  expected: { unit_id: number; purchase_unit_id: number; factor: number },
  operationId: string,
) =>
  request("catalog/products/" + id + "/purchase", "POST", {
    purchase_unit_id: purchaseUnit,
    factor,
    expected,
    operation_id: operationId,
  });

export type ShoppingOptions = {
  id: number;
  name: string;
  units: { id: number; name: string; factor: string }[];
};
export const getShoppingOptions = (id: number) =>
  request<ShoppingOptions>("shopping/products/" + id + "/options");
export const addShoppingAmount = (
  id: number,
  amount: string,
  unitId: number,
  operationId: string,
) =>
  request("shopping/products/" + id + "/add", "POST", {
    amount,
    unit_id: unitId,
    operation_id: operationId,
  });
