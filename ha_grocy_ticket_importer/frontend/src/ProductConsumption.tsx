import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { consumeCatalogProduct } from "./api";

export function ProductConsumption({
  id,
  amount,
  unit,
}: {
  id: number;
  amount: string;
  unit: string;
}) {
  const client = useQueryClient();
  const [quantity, setQuantity] = useState("1");
  const [replenish, setReplenish] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const mutation = useMutation({
    mutationFn: () =>
      consumeCatalogProduct(
        id,
        quantity,
        amount,
        replenish,
        crypto.randomUUID(),
      ),
    retry: false,
    onMutate: () => setSubmitted(true),
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["product", id] }),
        client.invalidateQueries({ queryKey: ["inventory"] }),
        client.invalidateQueries({ queryKey: ["shopping"] }),
      ]),
  });
  return (
    <section>
      <h3>Consumir producto</h3>
      <p>
        Disponible: {amount} {unit}
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!submitted) mutation.mutate();
        }}
      >
        <label className="variant-field">
          Cantidad a consumir
          <input
            required
            type="number"
            min="0.01"
            step="0.01"
            max={amount}
            value={quantity}
            disabled={submitted}
            onChange={(event) => setQuantity(event.target.value)}
          />
        </label>
        <label>
          <input
            type="checkbox"
            checked={replenish}
            disabled={submitted}
            onChange={(event) => setReplenish(event.target.checked)}
          />{" "}
          Añadir la misma cantidad a la lista de la compra
        </label>
        <button
          type="submit"
          disabled={
            submitted ||
            !(Number(quantity) > 0) ||
            Number(quantity) > Number(amount)
          }
        >
          Consumir
        </button>
      </form>
      {mutation.data && (
        <p role={mutation.data.shopping_error ? "alert" : "status"}>
          {mutation.data.shopping_error
            ? "Stock consumido. No se pudo añadir a la lista; hazlo desde Mi despensa. No repitas el consumo."
            : "Consumo registrado."}
        </p>
      )}
      {mutation.isError && (
        <p role="alert">
          {mutation.error.message} Comprueba el stock antes de abrir de nuevo
          esta ficha.
        </p>
      )}
    </section>
  );
}
