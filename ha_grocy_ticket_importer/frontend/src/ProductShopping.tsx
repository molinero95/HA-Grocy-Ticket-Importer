import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { addShoppingAmount, getShoppingOptions } from "./api";

export function ProductShopping({ id }: { id: number }) {
  const client = useQueryClient();
  const options = useQuery({
    queryKey: ["shopping-options", id],
    queryFn: () => getShoppingOptions(id),
  });
  const [amount, setAmount] = useState("1");
  const [unit, setUnit] = useState<number>();
  const [submitted, setSubmitted] = useState(false);
  const selected = unit ?? options.data?.units[0]?.id;
  const mutation = useMutation({
    mutationFn: () =>
      addShoppingAmount(id, amount, selected!, crypto.randomUUID()),
    onMutate: () => setSubmitted(true),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["inventory"] }),
        client.invalidateQueries({ queryKey: ["shopping"] }),
      ]),
  });
  return (
    <section>
      <h3>Añadir cantidad a la compra</h3>
      {options.isError && (
        <p role="alert">
          No se pudieron verificar las unidades.{" "}
          <button onClick={() => void options.refetch()}>Reintentar</button>
        </p>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <label className="variant-field">
          Cantidad para comprar
          <input
            required
            type="number"
            min="0.01"
            step="0.01"
            disabled={submitted}
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </label>
        <label className="variant-field">
          Unidad de la cantidad
          <select
            disabled={submitted}
            value={selected ?? ""}
            onChange={(event) => setUnit(Number(event.target.value))}
          >
            {options.data?.units.map((value) => (
              <option value={value.id} key={value.id}>
                {value.name}
              </option>
            ))}
          </select>
        </label>
        <button disabled={!selected || submitted || !(Number(amount) > 0)}>
          Añadir cantidad
        </button>
      </form>
      {mutation.isSuccess && <p role="status">Cantidad añadida a la lista.</p>}
      {mutation.isError && <p role="alert">{mutation.error.message}</p>}
    </section>
  );
}
