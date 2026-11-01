import { ProductShopping } from "./ProductShopping";
import { ProductPurchase } from "./ProductPurchase";
import { useModal } from "./useModal";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { isBarcode } from "./barcodes";
import { useState } from "react";
import { BarcodeScanner } from "./BarcodeScanner";
import { PhotoPreview } from "./ProductPhotos";
import { X } from "lucide-react";
import {
  getCatalogProduct,
  saveDiscoveredPhoto,
  setCatalogProductActive,
  adjustCatalogStock,
  editCatalogProduct,
  getCatalogBarcodes,
  saveCatalogBarcode,
  removeCatalogBarcode,
  uploadCatalogPhoto,
  getCatalogUnits,
  getProductVariants,
  saveProductVariant,
} from "./api";
import type { VariantInput } from "./api";

const empty: VariantInput = {
  barcode: "",
  name: "",
  supermarket: "",
  brand: "",
  units_per_purchase: "1",
};
export function ProductDetail({
  id,
  onClose,
  stockAmount = "0",
  stockUnit = "ud.",
}: {
  id: number;
  onClose: () => void;
  stockAmount?: string;
  stockUnit?: string;
}) {
  const dialog = useModal(onClose);
  const client = useQueryClient();
  const product = useQuery({
    queryKey: ["product", id],
    queryFn: () => getCatalogProduct(id),
  });
  const currentUnit =
    product.data?.units.find((unit) => unit.id === product.data?.unit_id)
      ?.name ?? stockUnit;
  const [expectedStock, setExpectedStock] = useState<string>();
  const currentStock = product.data?.stock_amount ?? stockAmount;
  const [photoMessage, setPhotoMessage] = useState("");
  const refreshProduct = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["product", id] }),
      client.invalidateQueries({ queryKey: ["shopping-options", id] }),
      client.invalidateQueries({ queryKey: ["inventory"] }),
      client.invalidateQueries({ queryKey: ["shopping"] }),
    ]);
  };
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["variants", id],
    queryFn: () => getProductVariants(id),
  });
  const barcodes = useQuery({
    queryKey: ["catalog-barcodes", id],
    queryFn: () => getCatalogBarcodes(id),
  });
  const removeBarcode = useMutation({
    mutationFn: (barcode: string) => removeCatalogBarcode(id, barcode),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["catalog-barcodes", id] });
    },
  });
  const [barcodeInput, setBarcodeInput] = useState("");
  const [oldBarcode, setOldBarcode] = useState<string | undefined>();
  const saveBarcode = useMutation({
    mutationFn: () => saveCatalogBarcode(id, barcodeInput, oldBarcode),
    onSuccess: async () => {
      const code = barcodeInput;
      setBarcodeInput("");
      setOldBarcode(undefined);
      try {
        await saveDiscoveredPhoto(id, code);
      } catch {
        setPhotoMessage(
          "Código guardado. No se pudo buscar la foto; puedes añadir una manualmente.",
        );
      }
      await refreshProduct();
      void client.invalidateQueries({ queryKey: ["catalog-barcodes", id] });
      void client.invalidateQueries({ queryKey: ["variants", id] });
    },
  });
  const lifecycle = useMutation({
    mutationFn: (active: boolean) =>
      setCatalogProductActive(
        id,
        product.data!.name,
        active,
        crypto.randomUUID(),
      ),
    onSuccess: async () => {
      await refreshProduct();
      await client.invalidateQueries({ queryKey: ["archived"] });
      onClose();
    },
  });
  const [photo, setPhoto] = useState<File | null>(null);
  const uploadPhoto = useMutation({
    mutationFn: (file: File) => uploadCatalogPhoto(id, file),
    onSuccess: () => {
      setPhoto(null);
      void refreshProduct();
    },
  });
  const [editingBarcode, setEditingBarcode] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [desiredStock, setDesiredStock] = useState<string | null>(null);
  const targetStock = desiredStock ?? currentStock;
  const [stockMessage, setStockMessage] = useState("");
  const adjustStock = useMutation({
    mutationFn: () =>
      adjustCatalogStock(id, targetStock, expectedStock ?? currentStock),
    onSuccess: () => {
      setStockMessage("Stock actualizado correctamente");
      setDesiredStock(null);
      setExpectedStock(undefined);
      void refreshProduct();
    },
    onError: () => setStockMessage(""),
  });
  const [editingProduct, setEditingProduct] = useState(false);
  const [productName, setProductName] = useState("");
  const [productUnit, setProductUnit] = useState("");
  const units = useQuery({
    queryKey: ["catalog-units"],
    queryFn: getCatalogUnits,
    enabled: editingProduct,
  });
  const updateProduct = useMutation({
    mutationFn: () => editCatalogProduct(id, productName, Number(productUnit)),
    onSuccess: () => {
      setEditingProduct(false);
      void refreshProduct();
      void client.invalidateQueries({ queryKey: ["variants", id] });
    },
  });
  const [form, setForm] = useState<VariantInput>(empty);
  const save = useMutation({
    mutationFn: (value: VariantInput) => saveProductVariant(id, value),
    onSuccess: () => {
      setEditing(false);
      setForm(empty);
      void refreshProduct();
      void client.invalidateQueries({ queryKey: ["catalog-barcodes", id] });
      void client.invalidateQueries({ queryKey: ["variants", id] });
    },
    onError: () => {},
  });
  const field = (key: keyof VariantInput, label: string, required = false) => (
    <label className="variant-field">
      {label}
      <input
        value={form[key]}
        required={required}
        readOnly={key === "barcode" && editingBarcode !== null}
        maxLength={
          key === "name"
            ? 200
            : key === "supermarket" || key === "brand"
              ? 120
              : undefined
        }
        onChange={(e) =>
          setForm((prev) => ({ ...prev, [key]: e.target.value }))
        }
      />
    </label>
  );
  return (
    <div
      ref={dialog}
      tabIndex={-1}
      className="detail-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Ficha de producto"
    >
      <section className="detail-panel">
        <div className="detail-heading">
          <div>
            <span className="eyebrow">PRODUCTO GENÉRICO</span>
            <h2>{data?.product.name ?? "Ficha de producto"}</h2>
          </div>
          <button onClick={onClose} aria-label="Cerrar ficha">
            <X size={21} />
          </button>
        </div>
        {isLoading && <p>Cargando variantes…</p>}
        {isError && (
          <p role="alert">
            No se pudieron cargar las variantes.{" "}
            <button onClick={() => void refetch()}>Reintentar</button>
          </p>
        )}
        {data && (
          <>
            <button
              type="button"
              onClick={() => {
                setProductName(data.product.name);
                setProductUnit("");
                setEditingProduct(true);
              }}
            >
              Editar producto genérico
            </button>
            {editingProduct && (
              <form
                className="variant-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  updateProduct.mutate();
                }}
              >
                <h3>Editar producto</h3>
                <label className="variant-field">
                  Nombre
                  <input
                    required
                    maxLength={200}
                    value={productName}
                    onChange={(event) => setProductName(event.target.value)}
                  />
                </label>
                <label className="variant-field">
                  Unidad de medida
                  <select
                    value={productUnit}
                    onChange={(event) => setProductUnit(event.target.value)}
                  >
                    <option value="">Conservar unidad actual</option>
                    {units.data?.map((unit) => (
                      <option key={unit.id} value={unit.id}>
                        {unit.name}
                      </option>
                    ))}
                  </select>
                </label>
                {units.isError && (
                  <p role="alert">
                    No se pudieron cargar las unidades. Se conservará la unidad
                    actual.
                  </p>
                )}
                {updateProduct.isError && (
                  <p role="alert">{updateProduct.error.message}</p>
                )}
                <div className="variant-buttons">
                  <button
                    type="button"
                    onClick={() => setEditingProduct(false)}
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={updateProduct.isPending || !productName.trim()}
                  >
                    Guardar cambios
                  </button>
                </div>
              </form>
            )}
            {product.data && (
              <ProductPurchase
                key={
                  String(product.data.purchase_unit_id) +
                  ":" +
                  String(product.data.pack_size)
                }
                product={product.data}
                onSaved={refreshProduct}
              />
            )}
            <h3>Fotografía</h3>
            {product.data?.image_url && (
              <img
                className="product-photo"
                src={product.data.image_url}
                alt={"Fotografía de " + product.data.name}
                referrerPolicy="no-referrer"
              />
            )}
            {photoMessage && <p role="status">{photoMessage}</p>}
            <form
              className="variant-form"
              onSubmit={(event) => {
                event.preventDefault();
                if (photo) uploadPhoto.mutate(photo);
              }}
            >
              <label className="variant-field">
                Elegir fotografía (JPG, PNG o WebP, máximo 8 MiB)
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  capture="environment"
                  onChange={(event) =>
                    setPhoto(event.target.files?.[0] ?? null)
                  }
                />
              </label>
              <button
                type="submit"
                disabled={
                  uploadPhoto.isPending ||
                  !photo ||
                  photo.size > 8 * 1024 * 1024
                }
              >
                Guardar fotografía
              </button>
              {uploadPhoto.isError && (
                <p role="alert">{uploadPhoto.error.message}</p>
              )}
              {uploadPhoto.isSuccess && (
                <p role="status">Fotografía guardada</p>
              )}
            </form>
            <h3>Códigos de barras</h3>
            {barcodes.isError && (
              <p role="alert">
                No se pudieron cargar los códigos.{" "}
                <button onClick={() => void barcodes.refetch()}>
                  Reintentar
                </button>
              </p>
            )}
            {barcodes.data?.map((code) => (
              <p key={code}>
                <code>{code}</code>{" "}
                <button
                  type="button"
                  onClick={() => {
                    setOldBarcode(code);
                    setBarcodeInput(code);
                  }}
                >
                  Modificar
                </button>{" "}
                <button
                  type="button"
                  disabled={removeBarcode.isPending}
                  onClick={() => {
                    if (
                      window.confirm(
                        "¿Eliminar únicamente el código " +
                          code +
                          "? El producto y su stock se conservarán.",
                      )
                    )
                      removeBarcode.mutate(code);
                  }}
                >
                  Eliminar código
                </button>
              </p>
            ))}
            {removeBarcode.isError && (
              <p role="alert">{removeBarcode.error.message}</p>
            )}
            <form
              className="variant-form"
              onSubmit={(event) => {
                event.preventDefault();
                saveBarcode.mutate();
              }}
            >
              <label className="variant-field">
                {oldBarcode
                  ? "Sustituir código " + oldBarcode
                  : "Asociar nuevo código"}
                <input
                  inputMode="numeric"
                  value={barcodeInput}
                  onChange={(event) => setBarcodeInput(event.target.value)}
                  placeholder="8 a 14 dígitos"
                />
              </label>
              <BarcodeScanner onDetect={setBarcodeInput} />
              <PhotoPreview barcode={barcodeInput} />
              <div className="variant-buttons">
                {oldBarcode && (
                  <button
                    type="button"
                    onClick={() => {
                      setOldBarcode(undefined);
                      setBarcodeInput("");
                    }}
                  >
                    Cancelar
                  </button>
                )}
                <button
                  type="submit"
                  disabled={saveBarcode.isPending || !isBarcode(barcodeInput)}
                >
                  Guardar código
                </button>
              </div>
              {saveBarcode.isError && (
                <p role="alert">{saveBarcode.error.message}</p>
              )}
            </form>
            {product.data?.active !== false && <ProductShopping id={id} />}
            <h3>Existencias</h3>
            {product.isError && (
              <p role="alert">
                No se pudo verificar el stock.{" "}
                <button onClick={() => void product.refetch()}>
                  Reintentar
                </button>
              </p>
            )}
            <p>
              Stock actual: {currentStock} {currentUnit}. Ajusta el número de
              piezas o kilogramos disponibles, no los envases completos. Indica
              la cantidad total que queda.
            </p>
            <form
              className="variant-form"
              onSubmit={(event) => {
                event.preventDefault();
                adjustStock.mutate();
              }}
            >
              <label className="variant-field">
                Cantidad final
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={targetStock}
                  onChange={(event) => {
                    setExpectedStock((previous) => previous ?? currentStock);
                    setDesiredStock(event.target.value);
                  }}
                />
              </label>
              <button
                type="submit"
                disabled={
                  !product.data ||
                  product.isError ||
                  adjustStock.isPending ||
                  !targetStock ||
                  Number(targetStock) < 0 ||
                  Number(targetStock) === Number(currentStock)
                }
              >
                Actualizar stock
              </button>
              {adjustStock.isError && (
                <p role="alert">{adjustStock.error.message}</p>
              )}
              {stockMessage && <p role="status">{stockMessage}</p>}
            </form>
            <h3>
              {product.data?.active === false
                ? "Producto archivado"
                : "Archivar producto"}
            </h3>
            <p>
              Archivar oculta el producto de Mi despensa y conserva sus códigos,
              fotos e historial. Puedes restaurarlo desde Archivados. Requiere
              stock cero y no tener referencias activas.
            </p>
            <button
              type="button"
              disabled={
                !product.data ||
                lifecycle.isPending ||
                (product.data.active !== false && Number(currentStock) !== 0)
              }
              onClick={() => {
                if (
                  window.confirm(
                    product.data?.active === false
                      ? "¿Restaurar este producto?"
                      : "¿Archivar este producto conservando su historial?",
                  )
                )
                  lifecycle.mutate(product.data?.active === false);
              }}
            >
              {product.data?.active === false
                ? "Restaurar producto"
                : "Archivar producto"}
            </button>
            {lifecycle.isError && <p role="alert">{lifecycle.error.message}</p>}
            <h3>Variantes por supermercado</h3>
            {data.variants.length === 0 ? (
              <p>Este producto aún no tiene variantes asociadas.</p>
            ) : (
              <ul className="variant-list">
                {data.variants.map((v) => (
                  <li key={v.barcode}>
                    <strong>{v.name}</strong>
                    <span>
                      {[v.supermarket, v.brand].filter(Boolean).join(" · ") ||
                        "Sin supermercado"}
                    </span>
                    <code>{v.barcode}</code>
                    <small>{v.units_per_purchase} unidades por compra</small>
                    <button
                      className="variant-edit"
                      onClick={() => {
                        setEditingBarcode(v.barcode);
                        setForm({
                          barcode: v.barcode,
                          name: v.name,
                          supermarket: v.supermarket,
                          brand: v.brand,
                          units_per_purchase: String(v.units_per_purchase),
                        });
                        setEditing(true);
                      }}
                    >
                      Editar
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="variant-note">
              Todas las variantes comparten el stock del producto genérico en
              Grocy.
            </p>
            <button
              className="variant-add"
              onClick={() => {
                setEditingBarcode(null);
                setForm(empty);
                setEditing(true);
              }}
            >
              + Añadir variante
            </button>
            {editing && (
              <form
                className="variant-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  save.mutate(form);
                }}
              >
                <h3>
                  {data.variants.some((v) => v.barcode === form.barcode)
                    ? "Editar variante"
                    : "Nueva variante"}
                </h3>
                {field("barcode", "Código de barras", true)}
                {!editingBarcode && (
                  <BarcodeScanner
                    onDetect={(code) =>
                      setForm((previous) => ({ ...previous, barcode: code }))
                    }
                  />
                )}
                {field("name", "Nombre de la variante", true)}
                {field("supermarket", "Supermercado")}
                {field("brand", "Marca")}
                {field("units_per_purchase", "Unidades por compra", true)}
                {save.isError && (
                  <p role="alert" className="notice">
                    {save.error.message}
                  </p>
                )}
                <div className="variant-buttons">
                  <button type="button" onClick={() => setEditing(false)}>
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={
                      save.isPending ||
                      !isBarcode(form.barcode) ||
                      !form.name.trim() ||
                      !(Number(form.units_per_purchase) > 0)
                    }
                  >
                    Guardar variante
                  </button>
                </div>
              </form>
            )}
          </>
        )}
      </section>
    </div>
  );
}
