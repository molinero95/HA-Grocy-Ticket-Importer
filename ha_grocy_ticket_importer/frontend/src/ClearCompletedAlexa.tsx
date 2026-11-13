import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { clearCompletedAlexa } from "./api";

export function ClearCompletedAlexa() {
  const busy = useRef(false);
  const [message, setMessage] = useState("");
  const mutation = useMutation({
    mutationFn: clearCompletedAlexa, retry: false,
    onSuccess: () => setMessage("Completados de Alexa eliminados."),
    onError: () => setMessage("Limpieza sin confirmar. Comprueba Alexa antes de volver a intentarlo."),
    onSettled: () => { busy.current = false; },
  });
  return <div className="force-sync">
    <button className="secondary-button" type="button" disabled={mutation.isPending} onClick={() => {
      if (busy.current || !window.confirm("¿Eliminar todos los artículos completados de Alexa? Los pendientes se conservan.")) return;
      busy.current = true; setMessage(""); mutation.mutate(crypto.randomUUID());
    }}>{mutation.isPending ? "Limpiando Alexa…" : "Limpiar completados de Alexa"}</button>
    {message && <p role="status">{message}</p>}
  </div>;
}
