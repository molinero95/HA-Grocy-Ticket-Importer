import { useDebouncedValue } from "./useDebouncedValue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Plus, ShoppingBasket, ListFilter, X } from "lucide-react";
import { BarcodeScanner } from "./BarcodeScanner";
import { StockStepper } from "./StockStepper";
import { ProductDetail } from "./ProductDetail";
import { CreateProduct } from "./CreateProduct";
import {
  getInventory,
  lookupBarcode,
  stepShopping,
} from "./api";
import type { InventoryItem } from "./types";
import { isBarcode } from "./barcodes";

const normalize = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .trim();
const hasLowStock = (amount: string, threshold = "0") =>
  amount.trim() !== "" && Number.isFinite(Number(amount)) && Number(amount) <= Number(threshold);

type PantryFilter = "all" | "low-stock" | "shopping";
const filterLabels: Record<PantryFilter, string> = {
  all: "Todos los productos",
  "low-stock": "Falta de stock",
  shopping: "En la lista de la compra",
};
const isLowStock = (item: InventoryItem) =>
  item.stock_warning_enabled !== false && hasLowStock(item.amount, item.stock_threshold);

export function Inventory() {
  const client = useQueryClient();
  const inventory = useQuery({
    queryKey: ["inventory"],
    queryFn: getInventory,
  });
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<PantryFilter>("all");
  const [selectedProductId, setSelectedProductId] = useState<number | null>(
    null,
  );
  const [creating, setCreating] = useState(false);
  const [creationCode, setCreationCode] = useState("");
  const code = query.trim();
  const lookupCode = useDebouncedValue(code);
  // Query identity isolates late responses: a previous scan cannot change a newer search.
  const barcode = useQuery({
    queryKey: ["barcode", lookupCode],
    queryFn: () => lookupBarcode(lookupCode),
    enabled: isBarcode(lookupCode) && code === lookupCode,
    retry: false,
  });
  const step = useMutation({
    mutationFn: ({
      id,
      direction,
    }: {
      id: number;
      direction: "plus" | "minus";
    }) => stepShopping(id, direction),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["inventory"] });
      void client.invalidateQueries({ queryKey: ["shopping"] });
    },
  });
  const items = useMemo(
    () =>
      (inventory.data?.items ?? []).filter((item) => {
        const matchesSearch = isBarcode(code)
          ? code === lookupCode && item.id === barcode.data
          : normalize(item.name).includes(normalize(code));
        const matchesFilter = filter === "all" ||
          (filter === "low-stock" && isLowStock(item)) ||
          (filter === "shopping" && Number.isFinite(Number(item.shopping_amount)) && Number(item.shopping_amount) > 0);
        return matchesSearch && matchesFilter;
      }),
    [inventory.data, code, lookupCode, barcode.data, filter],
  );
  return (
    <main>
      <div className="heading inventory-heading">
        <div>
          <span className="eyebrow">
            LO QUE TIENES EN CASA
          </span>
          <h2>Mi despensa</h2>
          <p>
            Ajusta las existencias que tienes en casa.
          </p>
        </div>
        <div className="inventory-heading-actions">
          <span className="count">{items.length} artículos</span>
          <button
            className="primary-button"
            onClick={() => { setCreationCode(""); setCreating(true); }}
          >
            <Plus size={18} aria-hidden="true" /> Nuevo producto
          </button>
        </div>
      </div>
      <div className="search-box">
        <input
          aria-label="Buscar por nombre o código de barras"
          placeholder="Nombre o código de barras"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <BarcodeScanner onDetect={setQuery} />
        <div className={"inventory-filter" + (filter !== "all" ? " active" : "")} title={"Filtrar productos: " + filterLabels[filter]}>
          <ListFilter size={21} aria-hidden="true" />
          <select aria-label="Filtrar productos" value={filter} onChange={event => setFilter(event.target.value as PantryFilter)}>
            <option value="all">Todos los productos</option>
            <option value="low-stock">Falta de stock</option>
            <option value="shopping">En la lista de la compra</option>
          </select>
        </div>
      </div>
      {filter !== "all" && <div className="inventory-filter-summary" role="status">
        <span>{filterLabels[filter]}</span>
        <button type="button" aria-label="Quitar filtro" title="Mostrar todos los productos" onClick={() => setFilter("all")}><X size={16} aria-hidden="true" /></button>
      </div>}
      {inventory.isLoading && <p role="status">Cargando inventario…</p>}
      {inventory.isError && (
        <div role="alert" className="notice">
          No se ha podido cargar el inventario.{" "}
          <button onClick={() => void inventory.refetch()}>Reintentar</button>
        </div>
      )}
      {isBarcode(code) && barcode.isError && (
        <p role="alert" className="notice">
          No se pudo consultar el código.{" "}
          <button onClick={() => void barcode.refetch()}>Reintentar</button>
        </p>
      )}
      {isBarcode(code) && barcode.data === null && (
        <div><p role="status">Código de barras no asociado a ningún producto</p><button className="secondary-button" onClick={() => { setCreationCode(code); setCreating(true); }}>Dar de alta este código</button></div>
      )}
      <div className="items">
        {items.map((item) => (
          <article
            className={"item inventory-item" + (isLowStock(item) ? " out-of-stock" : "")}
            key={item.id}
            aria-busy={step.isPending && step.variables?.id === item.id}
          >
            <div className="item-main">
              <span className="item-icon">
                {item.image_url ? (
                  <img
                    className="product-thumb"
                    src={item.image_url}
                    alt=""
                    loading="lazy"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <ShoppingBasket size={19} />
                )}
              </span>
              <div>
                <button
                  className="product-name"
                  onClick={() => setSelectedProductId(item.id)}
                >
                  {item.name}
                </button>
                <small>
                  En casa: {item.amount} {item.unit}
                </small>
                {isLowStock(item) && (
                  <span className="stock-status">{Number(item.amount) <= 0 ? "Sin existencias" : "Stock bajo"}</span>
                )}
              </div>
            </div>
            <div className="pantry-actions">
              <StockStepper id={item.id} name={item.name} amount={item.amount} unit={item.unit} />
              {Number(item.shopping_amount) === 0 ? <button className="cart-button" disabled={step.isPending} aria-label={"Añadir a compra: " + item.name} onClick={() => step.mutate({ id: item.id, direction: "plus" })}><ShoppingBasket size={17} /> Añadir</button> : <small className="shopping-badge">En la compra</small>}
            </div>
            {step.isError && step.variables?.id === item.id && (
              <p className="row-error" role="alert">
                {step.error.message}
              </p>
            )}
          </article>
        ))}
      </div>
      {!inventory.isLoading &&
        !inventory.isError &&
        !barcode.isFetching &&
        !items.length && (
          <div className="empty">
            <h3>Sin resultados</h3>
            <p>{filter !== "all" ? "No hay productos que coincidan con el filtro y la búsqueda." : "Prueba con otro nombre o código de barras."}</p>
          </div>
        )}
      {creating && (
        <CreateProduct
          initialBarcode={creationCode}
          onClose={() => setCreating(false)}
          onOpenProduct={(id) => {
            setCreating(false);
            setSelectedProductId(id);
          }}
        />
      )}
      {selectedProductId !== null && (
        <ProductDetail
          key={selectedProductId}
          id={selectedProductId}
          onClose={() => setSelectedProductId(null)}
        />
      )}
    </main>
  );
}
