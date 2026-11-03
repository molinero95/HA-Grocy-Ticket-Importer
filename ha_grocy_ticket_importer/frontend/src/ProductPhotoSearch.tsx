import { useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { ProductDiscovery } from "./ProductDiscovery";
import { saveNameDiscoveredPhoto } from "./api";

export function ProductPhotoSearch({ id, name, imageUrl, disabled, onSaved }: {
  id: number; name: string; imageUrl: string | null; disabled: boolean; onSaved: () => Promise<void>;
}) {
  const pending = useRef(false);
  const save = useMutation({
    mutationFn: (token: string) => saveNameDiscoveredPhoto(id, token, Boolean(imageUrl)),
    retry: false,
    onSuccess: async () => { await onSaved(); },
    onSettled: () => { pending.current = false; },
  });
  return <>
    <ProductDiscovery name={name} barcode="" productId={id} currentImage={imageUrl} disabled={disabled || save.isPending} onUse={candidate => {
      if (pending.current || disabled || !candidate.discovery_token) return;
      pending.current = true; save.mutate(candidate.discovery_token);
    }} />
    {save.isPending && <p role="status">Guardando fotografía…</p>}
    {save.isError && <p role="alert">{save.error.message} Actualiza la ficha antes de volver a elegir.</p>}
    {save.isSuccess && <p role="status">{save.data.saved ? "Fotografía guardada" : "No se pudo aplicar la imagen; la fotografía anterior se conserva."}</p>}
  </>;
}
