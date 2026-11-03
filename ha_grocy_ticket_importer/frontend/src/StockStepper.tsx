import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Minus, Plus } from "lucide-react";
import { adjustCatalogStock, getInventory } from "./api";
import type { InventoryResponse } from "./types";

/** Coalesce an intentional burst into one absolute, journaled stock command. */
export function StockStepper({ id, name, amount, unit }: { id: number; name: string; amount: string; unit: string }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(true);
  const pending = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const target = useRef(0);
  const baseline = useRef(amount);
  const blocked = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const known = amount.trim() !== "" && Number.isFinite(Number(amount)) && Number(amount) >= 0;
  const cents = draft ?? Math.round(Number(amount) * 1000);
  const kg = /^(kg|kilograms?|kilogramos?)$/i.test(unit.trim());
  function change(direction: number) {
    if (!known || pending.current || blocked.current) return;
    if (draft === null) baseline.current = amount;
    const next = Math.max(0, cents + direction * (kg ? 100 : 1000));
    target.current = next;
    setDraft(next);
    clearTimeout(timer.current);
    // An already requested edit still commits if the user changes tabs.
    timer.current = setTimeout(async () => {
      if (target.current === Math.round(Number(baseline.current) * 1000)) { if (mounted.current) setDraft(null); return; }
      pending.current = true;
      if (mounted.current) setBusy(true);
      const desired = String(target.current / 1000);
      try {
        await client.cancelQueries({ queryKey: ["inventory"] });
        const result = await adjustCatalogStock(id, desired, baseline.current, crypto.randomUUID(), true);
        client.setQueryData<InventoryResponse>(["inventory"], previous => previous && ({ ...previous, items: previous.items.map(row => row.id === id ? { ...row, amount: result.after } : row) }));
        void client.invalidateQueries({ queryKey: ["product", id] });
        if (mounted.current) setDraft(null);
      } catch (e) {
        blocked.current = true;
        if (mounted.current) { setError((e as Error).message); setDraft(null); }
      } finally { pending.current = false; if (mounted.current) setBusy(false); }
    }, 500);
  }
  return <div className="stock-controls">
    <div className="quantity" aria-label={"Stock de " + name} aria-busy={busy}>
      <button type="button" disabled={!known || busy || Boolean(error) || cents <= 0} aria-label={"Reducir stock: " + name} onClick={() => change(-1)}><Minus size={17} /></button>
      <span>{known ? String(cents / 1000) : "?"} {unit}</span>
      <button type="button" disabled={!known || busy || Boolean(error)} aria-label={"Aumentar stock: " + name} onClick={() => change(1)}><Plus size={17} /></button>
    </div>
    {(busy || draft !== null) && <small role="status">{busy ? "Guardando stock…" : "Stock pendiente de guardar…"}</small>}
    {error && <div className="row-error" role="alert">{error}<button className="secondary-button" type="button" disabled={busy} onClick={async () => {
      setBusy(true);
      try { const fresh = await getInventory(); client.setQueryData(["inventory"], fresh); blocked.current = false; setError(""); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
    }}>Consultar stock de nuevo</button></div>}
  </div>;
}
