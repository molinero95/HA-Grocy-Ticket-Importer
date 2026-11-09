import { useEffect, useState } from "react";
import type { ShoppingResponse } from "./types";

type SyncHealth = NonNullable<ShoppingResponse["sync"]>;

/** Use a server-provided duration and the browser's receipt time, never its server date. */
export function SyncPause({ sync, receivedAt }: { sync: SyncHealth; receivedAt: number }) {
  const [now, setNow] = useState(Date.now);
  const duration = sync.retry_after_seconds;
  const valid = typeof duration === "number" && Number.isFinite(duration) && duration >= 0 && duration <= 3600;
  const deadline = receivedAt + (valid ? duration : 0) * 1000;
  useEffect(() => {
    setNow(Date.now());
    if (!valid || deadline <= Date.now()) return;
    const timer = window.setInterval(() => {
      const current = Date.now();
      setNow(current);
      if (current >= deadline) window.clearInterval(timer);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [deadline, valid]);
  if (!valid) return <>Sincronización con Alexa en pausa automática. Tiempo restante sin confirmar. Actualiza la lista para consultarlo.</>;
  const minutes = Math.max(0, Math.ceil((deadline - now) / 60_000));
  return minutes > 0
    ? <>Sincronización con Alexa en pausa automática. Reintentará en {minutes} min. Puedes seguir usando la lista.</>
    : <>El plazo de pausa de Alexa ha terminado. Esperando una nueva comprobación; actualiza la lista para consultar el estado.</>;
}
