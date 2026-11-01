import { useModal } from "./useModal";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
  onOpenProduct,
}: {
  onClose: () => void;
  onOpenProduct?: (id: number) => void;
}) {
  const dialog = useModal(onClose);
  const client = useQueryClient();
  const units = useQuery({
    queryKey: ["catalog-units"],
    queryFn: getCatalogUnits,
  });
  const [name, setName] = useState("");
  const [barcode, setBarcode] = useState("");
  const [unit, setUnit] = useState("");
  const [initialStock, setInitialStock] = useState("0");
  const [packSize, setPackSize] = useState("1");
  const [photoMessage, setPhotoMessage] = useState("");
  const isPack = units.data?.some(
    (value) =>
      value.id === Number(unit) && value.name.toLowerCase().includes("pack"),
  );
  const save = useMutation({
    mutationFn: createCatalogProduct,
    onSuccess: async (response, submitted) => {
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
      <section className="detail-panel">
        <div className="detail-heading">
          <h2>Nuevo producto</h2>
          <button onClick={onClose}>Cerrar</button>
        </div>
        {units.isError && (
          <p role="alert">
            No se pudieron cargar las unidades de Grocy.{" "}
            <button onClick={() => void units.refetch()}>Reintentar</button>
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
              <button onClick={() => onOpenProduct(save.data.product_id)}>
                Abrir ficha del producto
              </button>
            )}
          </>
        ) : (
          <form
            className="variant-form"
            onSubmit={(event) => {
              event.preventDefault();
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
            <BarcodeScanner onDetect={setBarcode} />
            <PhotoPreview barcode={barcode} />
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
            <label className="variant-field">
              Stock inicial
              <input
                type="number"
                min="0"
                step="0.01"
                value={initialStock}
                onChange={(event) => setInitialStock(event.target.value)}
              />
            </label>
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
              </p>
            )}
            <button
              type="submit"
              disabled={
                save.isPending ||
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
              Guardar producto
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
