import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { discoverProduct, discoverGenericPhotos } from "./api";
import type { ProductDiscoveryCandidate } from "./api";
import { isBarcode } from "./barcodes";

/** Search results remain suggestions until the user chooses a candidate. */
export function ProductDiscovery({ name, barcode, onUse, productId, currentImage, disabled = false }: {
  name: string;
  barcode: string;
  productId?: number;
  currentImage?: string | null;
  disabled?: boolean;
  onUse: (candidate: ProductDiscoveryCandidate) => void;
}) {
  const identity = JSON.stringify([name.trim(), barcode.trim(), productId, currentImage]);
  const generation = useRef(0);
  const mounted = useRef(true);
  const pending = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    identity: string;
    generic: boolean;
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
  async function search(generic = false) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setResult(null);
    setError("");
    const episode = generation.current;
    try {
      const found = await (generic && productId ? discoverGenericPhotos(name.trim(), productId) : productId ? discoverProduct(name.trim(), "", productId) : discoverProduct(name.trim(), barcode.trim()));
      if (mounted.current && episode === generation.current)
        setResult({ identity, generic, candidates: found.candidates });
    } catch (e) {
      if (mounted.current && episode === generation.current)
        setError((e as Error).message);
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return <section className="product-discovery">
    <h3>{productId ? "Buscar foto por nombre" : "Buscar imagen y código"}</h3>
    {productId && <>
      <p>Para alimentos como ajo o fruta, busca una foto genérica por nombre en Wikimedia Commons. No necesita código de barras y no tiene coste de IA.</p>
      <button className="secondary-button" type="button" disabled={disabled || busy || name.trim().length < 3} onClick={() => void search(true)}>
        <Search size={18} aria-hidden="true" /> Buscar foto genérica
      </button>
    </>}
    <p>Para un producto envasado, usa un nombre con marca y formato. Enviaremos ese nombre a OpenAI para buscar en catálogos públicos, con coste en tu cuenta.</p>
    <button className="secondary-button" type="button"
      disabled={disabled || busy || name.trim().length < 3 || Boolean(barcode.trim() && !isBarcode(barcode.trim()))}
      onClick={() => void search()}>
      <Search size={18} aria-hidden="true" />
      {productId ? "Buscar foto con IA" : "Buscar imagen y código con IA"}
    </button>
    {busy && <p role="status">Buscando imágenes…</p>}
    {error && <p role="alert">{error} Puedes continuar sin imagen o subir una foto desde la ficha.</p>}
    {result?.identity === identity && <div aria-live="polite">
      {result.candidates.length === 0 ? <p>{result.generic ? "No se encontraron fotos genéricas disponibles para este nombre." : "No se encontraron coincidencias con código verificable."} {productId && !result.generic ? "Para un alimento sin envase, prueba Buscar foto genérica. " : ""}Puedes continuar sin seleccionar una imagen.</p> : <>
        <p>{result.generic ? "Elige una foto que represente el producto. Se guardará solo la imagen, sin añadir un código de barras." : "Revisa marca, variante y tamaño. Elige solo el mismo envase y formato."}</p>
        {result.candidates.map(candidate => <article className="discovery-candidate" key={candidate.file_id || candidate.barcode}>
          {candidate.image_url && <img src={candidate.image_url} alt={(candidate.kind === "generic" ? "Foto genérica: " : "Imagen de catálogo: ") + candidate.name} referrerPolicy="no-referrer" />}
          <strong>{candidate.name}</strong>
          <p>{candidate.kind === "generic" ? "Foto genérica · Sin código de barras" : "Código: " + candidate.barcode}</p>
          {!candidate.image_url && <p>Este catálogo no tiene imagen para el producto.</p>}
          <a href={candidate.search_source_url} target="_blank" rel="noopener noreferrer">Ver fuente de la búsqueda</a>
          <a href={candidate.source_url} target="_blank" rel="noopener noreferrer">{candidate.attribution}</a>
          {(productId ? candidate.image_url && candidate.discovery_token : (!barcode.trim() || barcode.trim() === candidate.barcode || candidate.image_url)) && <button className="secondary-button" type="button" disabled={disabled || busy} onClick={() => onUse(candidate)}>
            {productId ? (currentImage ? "Sustituir foto por esta imagen" : "Usar esta foto") : candidate.image_url ? (barcode.trim() && barcode.trim() !== candidate.barcode ? "Usar imagen y conservar código" : "Usar código e imagen") : "Usar este código"}
          </button>}
        </article>)}
      </>}
    </div>}
  </section>;
}
