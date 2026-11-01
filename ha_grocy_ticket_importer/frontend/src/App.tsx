import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ProductDetail } from "./ProductDetail";
import { Inventory } from "./Inventory";
import { Receipts } from "./Receipts";
import { Duplicates } from "./Duplicates";
import { ShoppingBasket, Package, ScanBarcode, RefreshCw } from "lucide-react";
import {
  chooseAlexaMatch,
  clearCompletedShopping,
  getAuthStatus,
  getShopping,
  loginStandalone,
  logoutStandalone,
  removeShopping,
  toggleShopping,
} from "./api";
import type { AlexaMatch } from "./types";

function Suggestions({ match }: { match: AlexaMatch }) {
  const client = useQueryClient();
  const [selected, setSelected] = useState(
    String(match.selected_product_id ?? ""),
  );
  const mutation = useMutation({
    mutationFn: (id: number) => chooseAlexaMatch(match.key, id),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["shopping"] }),
  });
  return (
    <details className="suggestions">
      <summary>Elegir producto para «{match.name}»</summary>
      <div className="suggestion-options">
        <label htmlFor={"choice-" + match.key}>Producto sugerido</label>
        <select
          id={"choice-" + match.key}
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
        >
          <option value="">Mantener artículo original</option>
          {match.candidates.map((candidate) => (
            <option key={candidate.id} value={candidate.id}>
              {candidate.name}
            </option>
          ))}
        </select>
        <button
          disabled={mutation.isPending}
          onClick={() => mutation.mutate(selected ? Number(selected) : 0)}
        >
          {selected ? "Guardar elección" : "Mantener original"}
        </button>
        {mutation.isError && <p role="alert">{mutation.error.message}</p>}
      </div>
    </details>
  );
}
function AuthenticatedApp() {
  const client = useQueryClient();
  const [view, setView] = useState<
    "shopping" | "inventory" | "actions" | "receipts" | "duplicates"
  >("shopping");
  const [selectedProductId, setSelectedProductId] = useState<number | null>(
    null,
  );
  const [actionError, setActionError] = useState("");
  const [busyItemId, setBusyItemId] = useState<number | null>(null);
  const toggle = useMutation({
    mutationFn: ({ id, done }: { id: number; done: boolean }) =>
      toggleShopping(id, done),
    onMutate: ({ id }) => setBusyItemId(id),
    onSettled: () => setBusyItemId(null),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["shopping"] }),
    onError: (error: Error) => setActionError(error.message),
  });
  const clearCompleted = useMutation({
    mutationFn: clearCompletedShopping,
    onSuccess: () => void client.invalidateQueries({ queryKey: ["shopping"] }),
    onError: (error: Error) => setActionError(error.message),
  });
  const remove = useMutation({
    mutationFn: removeShopping,
    onMutate: (id) => setBusyItemId(id),
    onSettled: () => setBusyItemId(null),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["shopping"] }),
    onError: (error: Error) => setActionError(error.message),
  });
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["shopping"],
    queryFn: getShopping,
  });
  const matches = new Map(
    (data?.pending_matches ?? []).map((match) => [match.key, match]),
  );
  const assigned = new Set<string>();
  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <span className="brand-mark">
            <Package size={23} />
          </span>
          <div>
            <span className="eyebrow">TU HOGAR, ORGANIZADO</span>
            <h1>Despensa</h1>
          </div>
        </div>
        <button
          className="icon-button"
          onClick={() => void client.invalidateQueries({ type: "active" })}
          aria-label="Actualizar"
          disabled={isFetching}
        >
          <RefreshCw size={19} />
        </button>
      </header>
      <nav className="tabs" aria-label="Secciones">
        <button
          className={view === "shopping" ? "active" : ""}
          onClick={() => setView("shopping")}
        >
          <ShoppingBasket size={18} /> Lista de la compra
        </button>
        <button
          className={view === "inventory" ? "active" : ""}
          onClick={() => setView("inventory")}
        >
          <Package size={18} /> Mi despensa
        </button>
        <button
          className={
            ["actions", "receipts", "duplicates"].includes(view) ? "active" : ""
          }
          onClick={() => setView("actions")}
        >
          <ScanBarcode size={18} /> Acciones
        </button>
      </nav>
      {view === "actions" ? (
        <main>
          <h2>Acciones</h2>
          <div className="action-grid">
            <button onClick={() => setView("receipts")}>Escanear ticket</button>
            <button onClick={() => setView("inventory")}>
              Añadir o consumir producto
            </button>
            <button onClick={() => setView("duplicates")}>
              Revisar duplicados y auditoría
            </button>
          </div>
        </main>
      ) : view === "inventory" ? (
        <Inventory />
      ) : view === "receipts" ? (
        <Receipts />
      ) : view === "duplicates" ? (
        <Duplicates />
      ) : (
        <main>
          <div className="heading">
            <div>
              <span className="eyebrow">TODO A MANO</span>
              <h2>Lista de la compra</h2>
              <p>
                Artículos que necesitas comprar, sincronizados con tu hogar.
              </p>
            </div>
            <div>
              <span className="count">{data?.items.length ?? 0} artículos</span>
              {data?.items.some((item) => item.done) && (
                <button
                  disabled={
                    clearCompleted.isPending ||
                    toggle.isPending ||
                    remove.isPending
                  }
                  onClick={() => {
                    if (
                      window.confirm(
                        "¿Eliminar todos los artículos marcados como comprados?",
                      )
                    ) {
                      setActionError("");
                      clearCompleted.mutate();
                    }
                  }}
                >
                  Eliminar comprados (
                  {data.items.filter((item) => item.done).length})
                </button>
              )}
            </div>
          </div>
          {isLoading && <p role="status">Cargando artículos…</p>}
          {isError && (
            <div role="alert" className="notice">
              No se pudo cargar la lista.{" "}
              <button onClick={() => void refetch()}>Reintentar</button>
            </div>
          )}
          {actionError && (
            <p role="alert" className="notice">
              {actionError}
            </p>
          )}
          {data?.pending_matches_error && (
            <p role="alert" className="notice">
              No se pudieron cargar las sugerencias de Alexa. Actualiza para
              volver a intentarlo.
            </p>
          )}
          {data?.shopping_error && (
            <p role="alert" className="notice">
              Grocy no está disponible en este momento.
            </p>
          )}
          <div className="items">
            {data?.items.map((item) => {
              const key = item.name
                .normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "")
                .toLowerCase()
                .trim();
              const match = matches.get(key);
              if (match) assigned.add(key);
              return (
                <article className="item" key={item.id}>
                  <div className="item-main">
                    <span
                      className={item.done ? "item-icon done" : "item-icon"}
                    >
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
                      <strong className={item.done ? "completed" : ""}>
                        {item.product_id ? (
                          <button
                            className="product-name"
                            onClick={() =>
                              setSelectedProductId(item.product_id)
                            }
                          >
                            {item.name}
                          </button>
                        ) : (
                          item.name
                        )}
                      </strong>
                      <small>
                        {item.amount} {item.unit}
                      </small>
                    </div>
                  </div>
                  <div className="item-actions">
                    <button
                      disabled={
                        toggle.isPending ||
                        remove.isPending ||
                        clearCompleted.isPending
                      }
                      onClick={() => {
                        setActionError("");
                        toggle.mutate({ id: item.id, done: !item.done });
                      }}
                    >
                      {busyItemId === item.id
                        ? "Guardando…"
                        : item.done
                          ? "↩ Pendiente"
                          : "✓ Comprado"}
                    </button>
                    <button
                      className="remove-button"
                      disabled={
                        remove.isPending ||
                        toggle.isPending ||
                        clearCompleted.isPending
                      }
                      onClick={() => {
                        setActionError("");
                        remove.mutate(item.id);
                      }}
                      aria-label={"Quitar " + item.name}
                    >
                      Quitar
                    </button>
                  </div>
                  {match && <Suggestions match={match} />}
                </article>
              );
            })}
            {data?.pending_matches
              .filter((match) => !assigned.has(match.key))
              .map((match) => (
                <article className="item" key={match.key}>
                  <div className="item-main">
                    <span className="item-icon">
                      <ShoppingBasket size={19} />
                    </span>
                    <div>
                      <strong>{match.name}</strong>
                      <small>Pendiente de revisar desde Alexa</small>
                    </div>
                  </div>
                  <Suggestions match={match} />
                </article>
              ))}
          </div>
          {data && !data.items.length && !data.pending_matches.length && (
            <div className="empty">
              <ShoppingBasket size={30} />
              <h3>Todo al día</h3>
              <p>Tu lista de la compra está vacía.</p>
            </div>
          )}
        </main>
      )}
      {selectedProductId !== null && (
        <ProductDetail
          key={selectedProductId}
          id={selectedProductId}
          onClose={() => setSelectedProductId(null)}
        />
      )}
      <footer>Despensa 1.0 · Versión en desarrollo</footer>
    </div>
  );
}

export function App() {
  const client = useQueryClient();
  const clearSession = () => {
    // Keep the observed auth query attached so the login screen updates immediately.
    // Cancel reads first: a late response must not restore the previous user's data.
    void client.cancelQueries();
    client.setQueryData(["auth-status"], {
      authenticated: false,
      ingress: false,
      csrf_token: "",
    });
  };
  useEffect(() => {
    const expire = () => {
      clearSession();
    };
    window.addEventListener("despensa:session-expired", expire);
    return () => window.removeEventListener("despensa:session-expired", expire);
  }, [client]);
  const auth = useQuery({
    queryKey: ["auth-status"],
    queryFn: getAuthStatus,
    retry: false,
  });
  useEffect(() => {
    if (auth.data?.authenticated === false) {
      // Run after the private view unmounts; removing observed queries sooner
      // can recreate them during that view's final render and start new reads.
      void client.cancelQueries({
        predicate: (query) => query.queryKey[0] !== "auth-status",
      });
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "auth-status",
      });
      client.getMutationCache().clear();
    }
  }, [auth.data?.authenticated, client]);
  const [password, setPassword] = useState("");
  const login = useMutation({
    mutationFn: () => loginStandalone(password),
    onSuccess: () => {
      setPassword("");
      void client.invalidateQueries({ queryKey: ["auth-status"] });
    },
  });
  const logout = useMutation({
    mutationFn: logoutStandalone,
    onSuccess: () => {
      clearSession();
    },
  });
  if (auth.isPending)
    return (
      <main className="shell">
        <p role="status">Comprobando sesión…</p>
      </main>
    );
  if (auth.isError)
    return (
      <main className="shell">
        <p role="alert">No se pudo comprobar la sesión.</p>
        <button onClick={() => void auth.refetch()}>Reintentar</button>
      </main>
    );
  if (!auth.data.authenticated)
    return (
      <main className="shell">
        <h1>Despensa</h1>
        <h2>Iniciar sesión</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            login.mutate();
          }}
        >
          <label>
            Contraseña
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button type="submit" disabled={login.isPending}>
            Entrar
          </button>
          {login.isError && <p role="alert">{login.error.message}</p>}
        </form>
      </main>
    );
  return (
    <>
      <AuthenticatedApp />
      {!auth.data.ingress && (
        <footer className="shell">
          <button
            type="button"
            disabled={logout.isPending}
            onClick={() => logout.mutate()}
          >
            Cerrar sesión
          </button>
          {logout.isError && <p role="alert">{logout.error.message}</p>}
        </footer>
      )}
    </>
  );
}
