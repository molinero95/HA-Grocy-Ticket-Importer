import { useEffect, useRef, useState } from "react";
import { identifyProductPhoto } from "./api";
import type { ProductSuggestion } from "./api";

/** Complete photo stays in browser memory until the explicit OpenAI action. */
export function ProductRecognition({
  barcode,
  capturedFrame,
  onUseName,
}: {
  barcode: string;
  capturedFrame?: Blob;
  onUseName: (name: string) => void;
}) {
  const [photo, setPhoto] = useState<Blob | null>(capturedFrame ?? null);
  const [preview, setPreview] = useState("");
  const [suggestion, setSuggestion] = useState<ProductSuggestion | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const pending = useRef(false);
  const attempted = useRef(false);
  const [submitted, setSubmitted] = useState(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current++;
    };
  }, []);
  useEffect(() => {
    generation.current++;
    attempted.current = false;
    setSubmitted(false);
    setPhoto(capturedFrame ?? null);
    setSuggestion(null);
    setError("");
  }, [barcode, capturedFrame]);
  useEffect(() => {
    if (!photo || !URL.createObjectURL) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(photo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);
  async function analyze() {
    if (!photo || pending.current || attempted.current) return;
    attempted.current = true;
    setSubmitted(true);
    pending.current = true;
    setBusy(true);
    setError("");
    setSuggestion(null);
    const episode = generation.current;
    try {
      const result = await identifyProductPhoto(barcode, photo);
      if (mounted.current && episode === generation.current)
        setSuggestion(result.suggestion);
    } catch (e) {
      if (mounted.current && episode === generation.current)
        setError((e as Error).message);
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return (
    <section className="product-recognition">
      <h3>Identificar con una foto</h3>
      <p>
        Fotografía el producto completo y su etiqueta. Al pulsar Analizar se
        enviará la foto completa a OpenAI para sugerir su nombre.
      </p>
      {preview && (
        <img
          src={preview}
          alt="Foto completa que se enviará a OpenAI"
          className="recognition-preview"
        />
      )}
      <label className="variant-field">
        Fotografía completa del producto
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            generation.current++;
            attempted.current = false;
            setSubmitted(false);
            event.target.value = "";
            setSuggestion(null);
            setError("");
            if (file && file.size > 8 * 1024 * 1024) {
              setPhoto(null);
              setError("La imagen supera 8 MiB");
            } else setPhoto(file ?? null);
          }}
        />
      </label>
      <button
        className="secondary-button"
        type="button"
        disabled={!photo || busy || submitted}
        onClick={() => void analyze()}
      >
        {busy ? "Analizando foto…" : "Analizar foto con OpenAI"}
      </button>
      {error && (
        <p role="alert">{error} Selecciona otra foto para un nuevo análisis.</p>
      )}
      {suggestion && (
        <div aria-live="polite">
          {suggestion.name ? (
            <>
              <p>
                Nombre sugerido: <strong>{suggestion.name}</strong>
              </p>
              {suggestion.brand && <p>Marca: {suggestion.brand}</p>}
              {suggestion.size_text && (
                <p>Formato visible: {suggestion.size_text}</p>
              )}
              <p>
                {suggestion.confidence === "low"
                  ? "Identificación poco segura. Revisa la etiqueta."
                  : "Sugerencia de OpenAI. Revisa que corresponde al producto."}
              </p>
              <button
                className="secondary-button"
                type="button"
                onClick={() => onUseName(suggestion.name)}
              >
                Usar nombre sugerido
              </button>
            </>
          ) : (
            <p>
              No se pudo identificar con suficiente claridad. Prueba otra foto o
              escribe el nombre.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
