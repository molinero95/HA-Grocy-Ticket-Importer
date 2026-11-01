import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { saveStockThreshold } from "./api";

export function ProductThreshold({ id, threshold, unit, warningEnabled = true }: { id: number; threshold: string; unit: string; warningEnabled?: boolean }) {
  const client = useQueryClient();
  const [desired, setDesired] = useState<string | null>(null);
  const [expected, setExpected] = useState<{amount: string; enabled: boolean}>();
  const [desiredEnabled, setDesiredEnabled] = useState<boolean | null>(null);
  const enabled = desiredEnabled ?? warningEnabled;
  const amount = desired ?? threshold;
  const save = useMutation({
    mutationFn: () => saveStockThreshold(id, amount, expected?.amount ?? threshold, enabled, expected?.enabled ?? warningEnabled),
    retry: false,
    onSuccess: async () => {
      await Promise.all([client.invalidateQueries({ queryKey: ["product", id] }), client.invalidateQueries({ queryKey: ["inventory"] })]);
      setDesired(null); setDesiredEnabled(null); setExpected(undefined);
    },
  });
  return <section>
    <h3>Umbral de aviso de stock</h3>
    <p>El producto aparecerá en amarillo con esta cantidad o menos. Por defecto: 0. Solo cambia el aviso visual.</p>
    <form className="variant-form" onSubmit={event => { event.preventDefault(); if (!save.isPending) save.mutate(); }}>
      <label className="variant-field">Umbral mínimo ({unit})<input type="number" min="0" max="999999.99" step="0.01" value={amount} disabled={save.isPending} onChange={event => { setExpected(previous => previous ?? {amount: threshold, enabled: warningEnabled}); setDesired(event.target.value); }} /></label>
      <label className="stock-alert-toggle"><input type="checkbox" checked={!enabled} disabled={save.isPending} onChange={event => { setExpected(previous => previous ?? {amount: threshold, enabled: warningEnabled}); setDesiredEnabled(!event.target.checked); }} />No avisar de stock bajo</label>
      <button className="secondary-button" disabled={save.isPending || !amount.trim() || !Number.isFinite(Number(amount)) || Number(amount) < 0 || Number(amount) >= 1000000 || (Number(amount) === Number(threshold) && enabled === warningEnabled)}>Guardar umbral</button>
      {save.isError && <p role="alert">{save.error.message}</p>}
      {save.isSuccess && <p role="status">Umbral guardado</p>}
    </form>
  </section>;
}
