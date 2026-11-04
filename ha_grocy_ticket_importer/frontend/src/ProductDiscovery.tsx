import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { discoverProduct, discoverWebPhotos } from "./api";
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
  const [query, setQuery] = useState(name);
  useEffect(() => { if (productId) setQuery(name); }, [name, productId]);
  const identity = JSON.stringify([name.trim(), barcode.trim(), productId, currentImage, productId ? query.trim() : ""]);
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
      const found = await (productId ? discoverWebPhotos(name.trim(), query.trim(), productId) : discoverProduct(name.trim(), barcode.trim()));
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
    <h3>{productId ? "Buscar foto por nombre" : "Buscar imagen y código"}</h3>
    {productId ? <>
      <label className="variant-field">Nombre para buscar la foto<input value={query} maxLength={200} disabled={disabled || busy} onChange={event => setQuery(event.target.value)} /></label>
      <p>OpenAI buscará fotos en páginas de fabricantes y tiendas, sin necesitar código de barras. Puedes añadir marca y formato sin cambiar el nombre del producto. La búsqueda tiene coste en tu cuenta.</p>
    </> : <p>Para un producto envasado, usa un nombre con marca y formato. Enviaremos ese nombre a OpenAI para buscar en catálogos públicos, con coste en tu cuenta.</p>}
    <button className="secondary-button" type="button"
      disabled={disabled || busy || (productId ? query.trim() : name.trim()).length < 3 || Boolean(barcode.trim() && !isBarcode(barcode.trim()))}
      onClick={() => void search()}>
      <Search size={18} aria-hidden="true" />
      {productId ? "Buscar foto con IA" : "Buscar imagen y código con IA"}
    </button>
    {busy && <p role="status">Buscando imágenes…</p>}
    {error && <p role="alert">{error} Puedes continuar sin imagen o subir una foto desde la ficha.</p>}
    {result?.identity === identity && <div aria-live="polite">
      {result.candidates.length === 0 ? <p>{productId ? "No se encontró una fotografía disponible. Prueba un nombre más concreto con marca y formato." : "No se encontraron coincidencias con código verificable."} Puedes continuar sin seleccionar una imagen.</p> : <>
        <p>Revisa marca, variante y tamaño antes de elegir la foto.</p>
        {result.candidates.map(candidate => <article className="discovery-candidate" key={candidate.kind === "web" ? candidate.image_url : candidate.file_id || candidate.barcode}>
          {candidate.image_url && <img src={candidate.image_url} alt={(candidate.kind === "generic" ? "Foto genérica: " : candidate.kind === "web" ? "Fotografía encontrada: " : "Imagen de catálogo: ") + candidate.name} referrerPolicy="no-referrer" />}
          <strong>{candidate.name}</strong>
          <p>{candidate.kind === "generic" ? "Foto genérica · Sin código de barras" : candidate.kind === "web" ? "Fotografía sugerida · Sin código de barras" : "Código: " + candidate.barcode}</p>
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
