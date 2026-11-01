import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { savePurchaseConfiguration } from "./api";
import type { CatalogProduct } from "./api";

export function ProductPurchase({
  product,
  onSaved,
}: {
  product: CatalogProduct;
  onSaved: () => Promise<void>;
}) {
  const [unit, setUnit] = useState(product.purchase_unit_id);
  const [factor, setFactor] = useState(String(product.pack_size));
  const [submitted, setSubmitted] = useState(false);
  const mutation = useMutation({
    mutationFn: () =>
      savePurchaseConfiguration(
        product.id,
        unit,
        unit === product.unit_id ? "1" : factor,
        {
          unit_id: product.unit_id,
          purchase_unit_id: product.purchase_unit_id,
          factor: product.pack_size,
        },
        crypto.randomUUID(),
      ),
    onMutate: () => setSubmitted(true),
    onSuccess: onSaved,
  });
  const changed =
    unit !== product.purchase_unit_id ||
    (unit !== product.unit_id && Number(factor) !== product.pack_size);
  return (
    <section>
      <h3>Unidad de compra</h3>
      <p>
        El stock permanece en{" "}
        {product.units.find((value) => value.id === product.unit_id)?.name}.
        Cambiar el pack afecta a compras futuras; no convierte las existencias
        actuales.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <label className="variant-field">
          Unidad para comprar
          <select
            value={unit}
            disabled={submitted}
            onChange={(event) => setUnit(Number(event.target.value))}
          >
            {product.units
              .filter(
                (value) =>
                  value.id === product.unit_id ||
                  ["pack", "paquete", "envase"].includes(
                    value.name.toLowerCase(),
                  ),
              )
              .map((value) => (
                <option value={value.id} key={value.id}>
                  {value.name}
                </option>
              ))}
          </select>
        </label>
        {unit !== product.unit_id && (
          <label className="variant-field">
            Piezas por pack
            <input
              required
              type="number"
              min="1"
              max="1000"
              step="1"
              value={factor}
              disabled={submitted}
              onChange={(event) => setFactor(event.target.value)}
            />
          </label>
        )}
        <button
          type="submit"
          disabled={
            submitted ||
            !changed ||
            (unit !== product.unit_id &&
              (!Number.isInteger(Number(factor)) ||
                Number(factor) < 1 ||
                Number(factor) > 1000))
          }
        >
          Guardar unidad de compra
        </button>
        {mutation.isError && (
          <p role="alert">
            {mutation.error.message} Vuelve a abrir la ficha después de
            comprobar la configuración.
          </p>
        )}
      </form>
    </section>
  );
}
