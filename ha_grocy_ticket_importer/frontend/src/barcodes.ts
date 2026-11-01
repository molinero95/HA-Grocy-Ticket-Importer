/** EAN-8, UPC and EAN-13/GTIN-14; preserve leading zeroes. */
export function isBarcode(value: string): boolean {
  return /^\d{8,14}$/.test(value.trim());
}
