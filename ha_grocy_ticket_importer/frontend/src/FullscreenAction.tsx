import { useEffect, useState } from "react";
import { Maximize, Minimize } from "lucide-react";

export function FullscreenAction() {
  const [full, setFull] = useState(Boolean(document.fullscreenElement));
  const [message, setMessage] = useState("");
  useEffect(() => {
    const changed = () => setFull(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, []);
  const toggle = async () => {
    setMessage("");
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (document.fullscreenEnabled && document.documentElement.requestFullscreen)
        await document.documentElement.requestFullscreen();
      else throw new Error("unavailable");
    } catch {
      setMessage("Home Assistant o este navegador no permite pantalla completa aquí. Puedes seguir usando Despensa con su navegación interna.");
    }
  };
  return <div className="fullscreen-action">
    <button aria-label={full ? "Salir de pantalla completa" : "Pantalla completa"} onClick={() => void toggle()}>
      {full ? <Minimize size={24} aria-hidden="true" /> : <Maximize size={24} aria-hidden="true" />}
      <span>{full ? "Salir de pantalla completa" : "Pantalla completa"}<small>Según lo permita Home Assistant o el navegador</small></span>
    </button>
    {message && <p role="status">{message}</p>}
  </div>;
}
