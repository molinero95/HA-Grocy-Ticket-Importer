import { describe, expect, it } from "vitest";
import { isBarcode } from "./barcodes";

describe("barcode recognition", () => {
  it("accepts EAN-8, EAN-13, GTIN-14 and leading zeroes", () => {
    for (const code of ["12345678", "8412345678901", "00012345678901"])
      expect(isBarcode(code)).toBe(true);
  });
  it("rejects names, nonnumeric and wrong length values", () => {
    for (const code of [
      "Leche",
      "1234567",
      "123456789012345",
      "841234567890A",
      "",
    ])
      expect(isBarcode(code)).toBe(false);
  });
});
