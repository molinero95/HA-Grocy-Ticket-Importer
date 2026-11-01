import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { discoverProduct } from "./api";
import type { ProductDiscoveryCandidate } from "./api";
import { isBarcode } from "./barcodes";

/** Search results are suggestions. Only an explicit choice changes the creation form. */
export function ProductDiscovery({ name, barcode, onUse }: {
  name: string;
  barcode: string;
  onUse: (candidate: ProductDiscoveryCandidate) => void;
}) {
  const identity = JSON.stringify([name.trim(), barcode.trim()]);
  const generation = useRef(0);
  const mounted = useRef(true);
  const pending = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    identity: string;
    candidates: ProductDiscoveryCandidate[];
  } | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; generation.current++; };
  }, []);
  useEffect(() => {
    generation.current++;
    setResult(null);
    setError("");
  }, [identity]);
  async function search() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setResult(null);
    setError("");
    const episode = generation.current;
    try {
      const found = await discoverProduct(name.trim(), barcode.trim());
      if (mounted.current && episode === generation.current)
        setResult({ identity, candidates: found.candidates });
    } catch (e) {
      if (mounted.current && episode === generation.current)
        setError((e as Error).message);
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return <section className="product-discovery">
    <h3>Buscar imagen y código</h3>
    <p>Usa un nombre con marca y formato. Enviaremos ese nombre a OpenAI para buscar en catálogos públicos, con coste en tu cuenta.</p>
    <button className="secondary-button" type="button"
      disabled={busy || name.trim().length < 3 || Boolean(barcode.trim() && !isBarcode(barcode.trim()))}
      onClick={() => void search()}>
      <Search size={18} aria-hidden="true" />
      {busy ? "Buscando en catálogos…" : "Buscar imagen y código con IA"}
    </button>
    {error && <p role="alert">{error} Puedes volver a pulsar para reintentar.</p>}
    {result?.identity === identity && <div aria-live="polite">
      {result.candidates.length === 0 ? <p>No se encontraron coincidencias con código verificable. Puedes continuar con tu foto y el código manual.</p> : <>
        <p>Revisa marca, variante y tamaño. Elige solo el mismo envase y formato.</p>
        {result.candidates.map(candidate => <article className="discovery-candidate" key={candidate.barcode}>
          {candidate.image_url && <img src={candidate.image_url} alt={"Imagen de catálogo: " + candidate.name} referrerPolicy="no-referrer" />}
          <strong>{candidate.name}</strong>
          <p>Código: {candidate.barcode}</p>
          {!candidate.image_url && <p>Este catálogo no tiene imagen para el producto.</p>}
          <a href={candidate.search_source_url} target="_blank" rel="noopener noreferrer">Ver fuente de la búsqueda</a>
          <a href={candidate.source_url} target="_blank" rel="noopener noreferrer">{candidate.attribution}</a>
          <button className="secondary-button" type="button" onClick={() => onUse(candidate)}>
            {candidate.image_url ? "Usar código e imagen" : "Usar este código"}
          </button>
        </article>)}
      </>}
    </div>}
  </section>;
}
