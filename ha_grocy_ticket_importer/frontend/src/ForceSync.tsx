import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { forceShoppingSync } from "./api";

export function ForceSync({ disabled = false }: { disabled?: boolean }) {
  const client = useQueryClient();
  const busy = useRef(false);
  const [message, setMessage] = useState("");
  const mutation = useMutation({
    mutationFn: (operationId: string) => forceShoppingSync(operationId), retry: false,
    onSuccess: () => setMessage("Sincronización completada."),
    onError: () => setMessage("No se ha confirmado la sincronización. Revisa el aviso actualizado antes de volver a intentarlo."),
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: ["shopping"] });
      busy.current = false;
    },
  });
  return <div className="force-sync">
    <button className="secondary-button" type="button" disabled={disabled || mutation.isPending} onClick={() => {
      if (busy.current) return;
      busy.current = true; setMessage(""); mutation.mutate(crypto.randomUUID());
    }}>{mutation.isPending ? "Sincronizando…" : "Forzar sincronización"}</button>
    {message && <p role="status">{message}</p>}
  </div>;
}
