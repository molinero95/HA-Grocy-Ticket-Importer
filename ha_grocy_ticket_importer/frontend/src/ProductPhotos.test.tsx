import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { PhotoPreview } from "./ProductPhotos";
import * as api from "./api";
import { deferred, renderWithClient } from "./test/helpers";

vi.mock("./api", () => ({ lookupPhoto: vi.fn() }));
beforeEach(() => vi.resetAllMocks());

it("does not request a photo for a name or incomplete barcode", () => {
  const { rerender } = renderWithClient(<PhotoPreview barcode="Leche" />);
  rerender(<PhotoPreview barcode="123" />);
  expect(api.lookupPhoto).not.toHaveBeenCalled();
});

it("keeps photo discovery failure advisory without retrying the public service", async () => {
  vi.mocked(api.lookupPhoto).mockRejectedValue(
    new Error("Proveedor no disponible"),
  );
  renderWithClient(<PhotoPreview barcode="8412345678901" />);
  await screen.findByText(/Puedes guardar el producto sin foto/);
  expect(api.lookupPhoto).toHaveBeenCalledTimes(1);
});

it("does not display a stale photo after changing to a different barcode", async () => {
  const pending = deferred<Awaited<ReturnType<typeof api.lookupPhoto>>>();
  vi.mocked(api.lookupPhoto)
    .mockReturnValueOnce(pending.promise)
    .mockResolvedValue({ photo: null });
  // Keep the same QueryClient while changing props, as the product form does.
  const { rerender } = renderWithClient(
    <PhotoPreview barcode="8412345678901" />,
  );
  await waitFor(() => expect(api.lookupPhoto).toHaveBeenCalledOnce());
  rerender(<PhotoPreview barcode="12345678" />);
  await act(async () =>
    pending.resolve({
      photo: {
        barcode: "8412345678901",
        name: "Leche",
        image_url: "https://images.openfoodfacts.org/old.jpg",
        source_url: "https://world.openfoodfacts.org/product/8412345678901",
        attribution: "Open Food Facts",
      },
    }),
  );
  expect(screen.queryByRole("img")).toBeNull();
  await screen.findByText("No se encontró fotografía para este código.");
  expect(api.lookupPhoto).toHaveBeenCalledWith("12345678");
});
