import { useEffect, useRef, useState } from "react";
import { Camera, X } from "lucide-react";
import { useModal } from "./useModal";

function CameraDialog({ onClose, onCapture, onChooseFile }: {
  onClose: () => void; onCapture: (file: File) => void; onChooseFile: () => void;
}) {
  const dialog = useModal(onClose);
  const video = useRef<HTMLVideoElement>(null);
  const stop = useRef<() => void>(() => {});
  const alive = useRef(true);
  const generation = useRef(0);
  const capturing = useRef(false);
  const accepted = useRef(false);
  const [attempt, setAttempt] = useState(0);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoUrl, setPhotoUrl] = useState("");
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; generation.current++; stop.current(); };
  }, []);
  useEffect(() => {
    if (!photo) { setPhotoUrl(""); return; }
    const url = URL.createObjectURL(photo);
    setPhotoUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);
  useEffect(() => {
    if (photo) return;
    setReady(false); setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Este navegador no permite abrir la cámara aquí. Abre Despensa mediante HTTPS o elige una foto o PDF.");
      return;
    }
    let cancelled = false;
    let stream: MediaStream | undefined;
    let released = false;
    const element = video.current;
    const release = () => {
      if (released) return;
      released = true;
      stream?.getTracks().forEach(track => track.stop());
      if (element) element.srcObject = null;
    };
    stop.current = release;
    void navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 2560 } },
    }).then(async media => {
      if (cancelled) { media.getTracks().forEach(track => track.stop()); return; }
      stream = media;
      if (!element) { release(); return; }
      element.srcObject = media;
      await element.play();
      if (!cancelled && !released && element.readyState >= 2 && element.videoWidth && element.videoHeight) setReady(true);
    }).catch(() => {
      release();
      if (!cancelled) setError("No hay acceso a la cámara. Permite la cámara en Home Assistant o en el navegador, o elige una foto o PDF.");
    });
    return () => { cancelled = true; release(); };
  }, [attempt, photo]);
  function capture() {
    const element = video.current;
    if (!ready || !element || !element.videoWidth || !element.videoHeight || capturing.current) return;
    capturing.current = true; setBusy(true); setError("");
    const episode = generation.current;
    const fail = () => {
      if (!alive.current || episode !== generation.current) return;
      capturing.current = false; setBusy(false);
      setError("No se pudo capturar la foto. Vuelve a abrir la cámara o elige un archivo.");
    };
    try {
      const canvas = document.createElement("canvas");
      const scale = Math.min(1, 2560 / Math.max(element.videoWidth, element.videoHeight));
      canvas.width = Math.max(1, Math.round(element.videoWidth * scale));
      canvas.height = Math.max(1, Math.round(element.videoHeight * scale));
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Canvas unavailable");
      context.drawImage(element, 0, 0, canvas.width, canvas.height);
      stop.current(); setReady(false);
      canvas.toBlob(blob => {
        if (!alive.current || episode !== generation.current) return;
        if (!blob || blob.size > 8 * 1024 * 1024) { fail(); return; }
        setPhoto(new File([blob], `ticket-${Date.now()}.jpg`, { type: "image/jpeg" }));
        capturing.current = false; setBusy(false);
      }, "image/jpeg", 0.92);
    } catch { stop.current(); setReady(false); fail(); }
  }
  function retake() {
    generation.current++; capturing.current = false; setBusy(false); setReady(false);
    setPhoto(null); setAttempt(previous => previous + 1);
  }
  return <div ref={dialog} tabIndex={-1} className="scanner-backdrop" role="dialog" aria-modal="true" aria-label="Cámara del ticket">
    <section className="scanner-panel receipt-camera-panel">
      <div className="scanner-heading"><strong>Foto del ticket</strong><button type="button" aria-label="Cerrar cámara del ticket" onClick={onClose}><X size={22} aria-hidden="true" /></button></div>
      {photo ? <img className="receipt-camera-photo" src={photoUrl || undefined} alt="Foto capturada del ticket" /> : <video ref={video} playsInline muted hidden={Boolean(error)} aria-label="Vista previa del ticket" onCanPlay={() => { const element = video.current; if (element?.srcObject && element.videoWidth && element.videoHeight) setReady(true); }} />}
      {!photo && !error && <p role="status">{busy ? "Preparando la foto…" : ready ? "Encuadra el ticket completo, con buena luz y el texto enfocado." : "Abriendo cámara…"}</p>}
      {photo && <p>Comprueba que se lee todo el ticket antes de usar la foto.</p>}
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="receipt-camera-actions">
        {photo ? <>
          <button key="retake" className="secondary-button" type="button" onClick={retake}>Repetir foto</button>
          <button key="accept" className="primary-button" type="button" onClick={() => { if (accepted.current) return; accepted.current = true; onCapture(photo); onClose(); }}>Usar esta foto</button>
        </> : error ? <>
          <button key="retry" className="secondary-button" type="button" onClick={retake}>Volver a abrir cámara</button>
          <button key="file" className="secondary-button" type="button" onClick={() => { onClose(); onChooseFile(); }}>Elegir foto o PDF</button>
        </> : <button key="capture" className="primary-button" type="button" disabled={!ready || busy} onClick={capture}><Camera size={20} aria-hidden="true" />Capturar foto</button>}
      </div>
    </section>
  </div>;
}

export function ReceiptCamera({ disabled, onCapture, onChooseFile }: {
  disabled: boolean; onCapture: (file: File) => void; onChooseFile: () => void;
}) {
  const [open, setOpen] = useState(false);
  return <>
    <button className="primary-button receipt-camera-button" type="button" disabled={disabled || open} onClick={() => setOpen(true)}><Camera size={20} aria-hidden="true" />Tomar foto del ticket</button>
    {open && <CameraDialog onClose={() => setOpen(false)} onCapture={onCapture} onChooseFile={onChooseFile} />}
  </>;
}
