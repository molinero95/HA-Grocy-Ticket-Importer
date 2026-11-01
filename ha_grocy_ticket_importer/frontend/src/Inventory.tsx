import { useDebouncedValue } from "./useDebouncedValue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Minus, Plus, ShoppingBasket } from "lucide-react";
import { BarcodeScanner } from "./BarcodeScanner";
import { ProductDetail } from "./ProductDetail";
import { CreateProduct } from "./CreateProduct";
import {
  getArchivedProducts,
  getInventory,
  lookupBarcode,
  stepShopping,
} from "./api";
import { isBarcode } from "./barcodes";

const normalize = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .trim();
const hasLowStock = (amount: string, threshold = "0") =>
  amount.trim() !== "" && Number.isFinite(Number(amount)) && Number(amount) <= Number(threshold);

export function Inventory({ archived = false }: { archived?: boolean }) {
  const client = useQueryClient();
  const inventory = useQuery({
    queryKey: [archived ? "archived" : "inventory"],
    queryFn: archived ? getArchivedProducts : getInventory,
  });
  const [query, setQuery] = useState("");
  const [selectedProductId, setSelectedProductId] = useState<number | null>(
    null,
  );
  const [creating, setCreating] = useState(false);
  const [creationCode, setCreationCode] = useState("");
  const [captured, setCaptured] = useState<{ code: string; frame: Blob } | null>(null);
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
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["inventory"] }),
        client.invalidateQueries({ queryKey: ["shopping"] }),
      ]),
  });
  const items = useMemo(
    () =>
      (inventory.data?.items ?? []).filter((item) =>
        isBarcode(code)
          ? code === lookupCode && item.id === barcode.data
          : normalize(item.name).includes(normalize(code)),
      ),
    [inventory.data, code, lookupCode, barcode.data],
  );
  return (
    <main>
      <div className="heading inventory-heading">
        <div>
          <span className="eyebrow">
            {archived ? "CATÁLOGO GUARDADO" : "LO QUE TIENES EN CASA"}
          </span>
          <h2>{archived ? "Productos archivados" : "Mi despensa"}</h2>
          <p>
            {archived
              ? "Consulta, restaura o elimina productos archivados sin uso."
              : "Stock de Grocy y cantidades pendientes de compra."}
          </p>
        </div>
        <div className="inventory-heading-actions">
          <span className="count">{items.length} artículos</span>
          {!archived && (
            <button
              className="primary-button"
              onClick={() => { setCreationCode(""); setCreating(true); }}
            >
              <Plus size={18} aria-hidden="true" /> Nuevo producto
            </button>
          )}
        </div>
      </div>
      <div className="search-box">
        <input
          aria-label="Buscar por nombre o código de barras"
          placeholder="Nombre o código de barras"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <BarcodeScanner onDetect={setQuery} onCapture={archived ? undefined : (code, frame) => setCaptured({ code, frame })} />
      </div>
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
        <div><p role="status">Código de barras no asociado a ningún producto</p>{!archived && <button className="secondary-button" onClick={() => { setCreationCode(code); setCreating(true); }}>Dar de alta este código</button>}</div>
      )}
      <div className="items">
        {items.map((item) => (
          <article
            className={"item inventory-item" + (!archived && item.stock_warning_enabled !== false && hasLowStock(item.amount, item.stock_threshold) ? " out-of-stock" : "")}
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
                {!archived && item.stock_warning_enabled !== false && hasLowStock(item.amount, item.stock_threshold) && (
                  <span className="stock-status">{Number(item.amount) <= 0 ? "Sin existencias" : "Stock bajo"}</span>
                )}
              </div>
            </div>
            {archived ? (
              <button
                className="secondary-button"
                onClick={() => setSelectedProductId(item.id)}
              >
                Ver producto
              </button>
            ) : Number(item.shopping_amount) === 0 ? (
              <button
                className="cart-button"
                disabled={step.isPending}
                aria-label={"Añadir a compra: " + item.name}
                onClick={() => step.mutate({ id: item.id, direction: "plus" })}
              >
                <ShoppingBasket size={17} /> Añadir
              </button>
            ) : (
              <div className="quantity">
                <button
                  disabled={step.isPending || !item.shopping_can_subtract}
                  aria-label={"Quitar de compra: " + item.name}
                  onClick={() =>
                    step.mutate({ id: item.id, direction: "minus" })
                  }
                >
                  <Minus size={17} />
                </button>
                <span>
                  {item.shopping_amount} {item.shopping_unit}
                </span>
                <button
                  disabled={step.isPending}
                  aria-label={"Añadir a compra: " + item.name}
                  onClick={() =>
                    step.mutate({ id: item.id, direction: "plus" })
                  }
                >
                  <Plus size={17} />
                </button>
              </div>
            )}
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
            <p>Prueba con otro nombre o código de barras.</p>
          </div>
        )}
      {creating && (
        <CreateProduct
          initialBarcode={creationCode}
          initialFrame={captured?.code === creationCode ? captured.frame : undefined}
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
