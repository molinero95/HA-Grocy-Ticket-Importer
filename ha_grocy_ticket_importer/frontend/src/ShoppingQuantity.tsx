import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useModal } from "./useModal";
import { setShoppingQuantity } from "./api";
import type { ShoppingItem, ShoppingResponse } from "./types";

export function ShoppingQuantity({ item, onClose }: { item: ShoppingItem; onClose: () => void }) {
  const client = useQueryClient();
  const [amount, setAmount] = useState(String(item.amount));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const attempted = useRef(false);
  const dialog = useModal(() => { if (!busy) onClose(); });
  return <div ref={dialog} tabIndex={-1} className="detail-backdrop" role="dialog" aria-modal="true" aria-label="Modificar cantidad">
    <section className="detail-panel confirmation-panel">
      <h2>Modificar cantidad</h2><p>{item.name}</p>
      <form className="variant-form" onSubmit={async event => {
        event.preventDefault();
        if (attempted.current) return;
        attempted.current = true; setBusy(true);
        try {
          await client.cancelQueries({ queryKey: ["shopping"] });
          const result = await setShoppingQuantity(item, amount, crypto.randomUUID());
          client.setQueryData<ShoppingResponse>(["shopping"], previous => previous && ({ ...previous, items: previous.items.map(row => row.id === item.id ? { ...row, amount: Number(result.amount) } : row) }));
          void client.invalidateQueries({ queryKey: ["inventory"] });
          onClose();
        } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
      }}>
        <label className="variant-field">Cantidad para comprar ({item.unit})<input type="number" min="0.01" step="0.01" required value={amount} disabled={busy || attempted.current} onChange={event => setAmount(event.target.value)} /></label>
        {error && <p role="alert">{error} Cierra y vuelve a consultar la lista antes de otra operación.</p>}
        <div className="variant-buttons"><button className="secondary-button" type="button" disabled={busy} onClick={onClose}>Cancelar</button><button className="primary-button" disabled={busy || attempted.current || !Number.isFinite(Number(amount)) || Number(amount) <= 0}>Guardar cantidad</button></div>
      </form>
    </section>
  </div>;
}
