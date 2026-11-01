import { useModal } from "./useModal";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowUpRight, Check, X } from "lucide-react";
import {
  createCatalogProduct,
  getCatalogUnits,
  saveDiscoveredPhoto,
} from "./api";
import { isBarcode } from "./barcodes";
import { BarcodeScanner } from "./BarcodeScanner";
import { PhotoPreview } from "./ProductPhotos";

export function CreateProduct({
  onClose,
  onOpenProduct, initialName = "", submitProduct = createCatalogProduct, zeroStockOnly = false, oneAttempt = false, initialBarcode = "", initialFrame,
}: {
  onClose: () => void;
  onOpenProduct?: (id: number) => void;
  initialName?: string;
  initialBarcode?: string;
  initialFrame?: Blob;
  submitProduct?: typeof createCatalogProduct;
  zeroStockOnly?: boolean;
  oneAttempt?: boolean;
}) {
  const dialog = useModal(onClose);
  const client = useQueryClient();
  const units = useQuery({
    queryKey: ["catalog-units"],
    queryFn: getCatalogUnits,
  });
  const [name, setName] = useState(initialName);
  const [attempted, setAttempted] = useState(false);
  const [barcode, setBarcode] = useState(initialBarcode);
  const [captured, setCaptured] = useState<{ code: string; frame: Blob } | null>(initialFrame ? { code: initialBarcode, frame: initialFrame } : null);
  const [unit, setUnit] = useState("");
  const [initialStock, setInitialStock] = useState("0");
  const [packSize, setPackSize] = useState("1");
  const [photoMessage, setPhotoMessage] = useState("");
  const isPack = units.data?.some(
    (value) =>
      value.id === Number(unit) && value.name.toLowerCase().includes("pack"),
  );
  const save = useMutation({
    mutationFn: submitProduct,
    onSuccess: async (response, submitted) => {
      await client.invalidateQueries({ queryKey: ["shopping"] });
      // Never attach metadata to an existing duplicate as a side effect of creation.
      if (response.created && submitted.barcode) {
        try {
          await saveDiscoveredPhoto(response.product_id, submitted.barcode);
        } catch {
          setPhotoMessage(
            "El producto está creado. No se pudo guardar su foto; puedes añadirla desde la ficha.",
          );
        }
      }
      await client.invalidateQueries({ queryKey: ["inventory"] });
    },
  });
  return (
    <div
      ref={dialog}
      tabIndex={-1}
      className="detail-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Crear producto"
    >
      <section className="detail-panel create-product-panel">
        <div className="detail-heading">
          <h2>Nuevo producto</h2>
          <button
            className="secondary-button create-product-close"
            type="button"
            aria-label="Cerrar"
            title="Cerrar"
            onClick={onClose}
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>
        {units.isError && (
          <p role="alert">
            No se pudieron cargar las unidades de Grocy.{" "}
            <button
              className="secondary-button"
              type="button"
              onClick={() => void units.refetch()}
            >
              Reintentar
            </button>
          </p>
        )}
        {save.data ? (
          <>
            <p role="status">
              {save.data.created
                ? "Producto creado correctamente"
                : "Este producto ya existía; no se ha duplicado ni modificado su stock"}
            </p>
            {photoMessage && <p>{photoMessage}</p>}
            {onOpenProduct && (
              <button
                className="primary-button create-product-submit"
                type="button"
                onClick={() => onOpenProduct(save.data.product_id)}
              >
                <ArrowUpRight size={18} aria-hidden="true" />
                Abrir ficha del producto
              </button>
            )}
          </>
        ) : (
          <form
            className="variant-form create-product-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (save.isPending || (oneAttempt && attempted)) return;
              if (oneAttempt) setAttempted(true);
              save.mutate({
                name: name.trim(),
                barcode: barcode.trim(),
                unit_id: Number(unit),
                initial_stock: initialStock,
                pack_size: isPack ? packSize : "1",
              });
            }}
          >
            <label className="variant-field">
              Nombre
              <input
                required
                maxLength={200}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="variant-field">
              Código de barras (opcional)
              <input
                inputMode="numeric"
                value={barcode}
                onChange={(event) => setBarcode(event.target.value)}
              />
            </label>
            <BarcodeScanner onDetect={setBarcode} onCapture={(code, frame) => setCaptured({ code, frame })} label="Escanear código" />
            <PhotoPreview barcode={barcode} onUseName={setName} capturedFrame={captured?.code === barcode ? captured.frame : undefined} />
            <label className="variant-field">
              Unidad
              <select
                aria-label="Unidad"
                required
                value={unit}
                onChange={(event) => setUnit(event.target.value)}
              >
                <option value="">Seleccionar unidad</option>
                {units.data?.map((value) => (
                  <option key={value.id} value={value.id}>
                    {value.name}
                  </option>
                ))}
              </select>
            </label>
            {zeroStockOnly ? <p>Se crea sin existencias. La cantidad y nota de la compra se conservan.</p> : <label className="variant-field">
              Stock inicial
              <input
                type="number"
                min="0"
                step="0.01"
                value={initialStock}
                onChange={(event) => setInitialStock(event.target.value)}
              />
            </label>}
            {isPack && (
              <>
                <label className="variant-field">
                  Piezas por pack
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    step="1"
                    value={packSize}
                    onChange={(event) => setPackSize(event.target.value)}
                  />
                </label>
                <p>
                  El stock se guarda en piezas. Por ejemplo, 2 packs de 5 suman
                  10 piezas.
                </p>
              </>
            )}
            {save.isError && (
              <p role="alert" className="notice">
                {save.error.message}
                {oneAttempt && " Cierra el formulario y comprueba el catálogo y la lista antes de otra operación."}
              </p>
            )}
            <button
              className="primary-button create-product-submit"
              type="submit"
              disabled={
                save.isPending || (oneAttempt && attempted) ||
                !unit ||
                !name.trim() ||
                Boolean(barcode && !isBarcode(barcode)) ||
                !(Number(initialStock) >= 0) ||
                (isPack &&
                  (!Number.isInteger(Number(packSize)) ||
                    Number(packSize) < 1 ||
                    Number(packSize) > 1000))
              }
            >
              <Check size={18} aria-hidden="true" />
              Guardar producto
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
