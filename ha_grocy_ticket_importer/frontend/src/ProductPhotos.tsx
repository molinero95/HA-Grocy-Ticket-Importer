import { useDebouncedValue } from "./useDebouncedValue";
import { useQuery } from "@tanstack/react-query";
import { isBarcode } from "./barcodes";
import { ProductRecognition } from "./ProductRecognition";
import { lookupPhoto } from "./api";

/** Lookup failure is advisory: a missing public photo must never block a save. */
export function PhotoPreview({
  barcode,
  onUseName,
  capturedFrame,
}: {
  barcode: string;
  onUseName?: (name: string) => void;
  capturedFrame?: Blob;
}) {
  const code = barcode.trim();
  const lookupCode = useDebouncedValue(code);
  const photo = useQuery({
    queryKey: ["photo-lookup", code],
    queryFn: () => lookupPhoto(code),
    enabled: isBarcode(code) && code === lookupCode,
    retry: false,
    staleTime: 300_000,
  });
  if (!isBarcode(code) || code !== lookupCode) return null;
  return (
    <div className="photo-preview" aria-live="polite">
      {photo.isFetching && <p>Buscando fotografía por código…</p>}
      {photo.isError && (
        <p>
          Puedes guardar el producto sin foto. La búsqueda no está disponible.
        </p>
      )}
      {photo.data?.photo?.name && (
        <div className="discovered-product-name">
          <p>
            Nombre encontrado: <strong>{photo.data.photo.name}</strong>
          </p>
          {onUseName && (
            <button
              className="secondary-button"
              type="button"
              onClick={() => onUseName(photo.data!.photo!.name)}
            >
              Usar este nombre
            </button>
          )}
        </div>
      )}
      {photo.data && !photo.data.photo?.image_url && (
        <p>No se encontró fotografía para este código.</p>
      )}
      {photo.data?.photo?.image_url && (
        <>
          <img
            src={photo.data.photo.image_url}
            alt="Fotografía encontrada por código"
            referrerPolicy="no-referrer"
          />
        </>
      )}
      {onUseName && (photo.isError || (photo.data && !photo.data.photo?.name)) && (
        <ProductRecognition key={code} barcode={code} capturedFrame={capturedFrame} onUseName={onUseName} />
      )}
      {photo.data?.photo && (
        <a
          href={photo.data.photo.source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {photo.data.photo.attribution}
        </a>
      )}
    </div>
  );
}
