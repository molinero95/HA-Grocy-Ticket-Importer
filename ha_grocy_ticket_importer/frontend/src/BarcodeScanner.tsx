import { useModal } from "./useModal";
import { useEffect, useRef, useState } from "react";
import { isBarcode } from "./barcodes";
import { Camera, X } from "lucide-react";

type Detection = { rawValue: string };
type Detector = { detect(source: HTMLVideoElement): Promise<Detection[]> };
type DetectorConstructor = new (options: { formats: string[] }) => Detector;

/** Camera stays local: only the detected code is sent to our same-origin API. */
export function BarcodeScanner({
  onDetect,
  label,
}: {
  onDetect: (code: string) => void;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const dialog = useModal(() => setOpen(false), open);
  const onDetectRef = useRef(onDetect);
  onDetectRef.current = onDetect;
  const video = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    if (!open) return;
    const DetectorAPI = (
      window as Window & { BarcodeDetector?: DetectorConstructor }
    ).BarcodeDetector;
    if (!DetectorAPI || !navigator.mediaDevices?.getUserMedia) {
      setError(
        "Este navegador no permite escanear. Introduce el código manualmente.",
      );
      return;
    }
    let stopped = false;
    let stream: MediaStream | undefined;
    let frame = 0;
    let scanning = false;
    let detector: Detector;
    try {
      detector = new DetectorAPI({
        formats: ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"],
      });
    } catch {
      setError(
        "Este navegador no permite escanear. Introduce el código manualmente.",
      );
      return;
    }
    const scan = async () => {
      if (stopped || !video.current) return;
      if (!scanning && video.current.readyState >= 2) {
        scanning = true;
        try {
          const results = await detector.detect(video.current);
          const code = results.find((item) =>
            isBarcode(item.rawValue),
          )?.rawValue;
          if (code && !stopped) {
            onDetectRef.current(code);
            setOpen(false);
            return;
          }
        } catch {
          if (!stopped)
            setError(
              "No se ha podido leer el código. Puedes escribirlo manualmente.",
            );
        } finally {
          scanning = false;
        }
      }
      if (!stopped) frame = requestAnimationFrame(scan);
    };
    void navigator.mediaDevices
      .getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      })
      .then(async (media) => {
        if (stopped) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = media;
        if (!video.current) return;
        video.current.srcObject = media;
        await video.current.play();
        if (!stopped) frame = requestAnimationFrame(scan);
      })
      .catch(() => {
        stream?.getTracks().forEach((track) => track.stop());
        if (!stopped)
          setError(
            "No hay acceso a la cámara. Revisa los permisos o introduce el código.",
          );
      });
    return () => {
      stopped = true;
      cancelAnimationFrame(frame);
      stream?.getTracks().forEach((track) => track.stop());
      if (video.current) video.current.srcObject = null;
    };
  }, [open]);
  return (
    <>
      <button
        className={
          label
            ? "secondary-button camera-trigger camera-trigger-labeled"
            : "camera-trigger"
        }
        type="button"
        onClick={() => {
          setError("");
          setOpen(true);
        }}
        aria-label={label ?? "Abrir cámara para escanear"}
      >
        <Camera size={19} />
        {label && <span>{label}</span>}
      </button>
      {open && (
        <div
          ref={dialog}
          tabIndex={-1}
          className="scanner-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Escáner de códigos de barras"
        >
          <div className="scanner-panel">
            <div className="scanner-heading">
              <strong>Escanear código</strong>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Cerrar cámara"
              >
                <X size={22} />
              </button>
            </div>
            <video
              ref={video}
              playsInline
              muted
              aria-label="Vista previa de cámara"
            />
            <p>Coloca el código de barras dentro de la imagen.</p>
            {error && (
              <p role="alert" className="notice">
                {error}
              </p>
            )}
          </div>
        </div>
      )}
    </>
  );
}
