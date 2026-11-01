import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { NavigationContext, useAppNavigation } from "./navigation";
import { ShoppingProductCreation } from "./ShoppingProductCreation";
import { ProductDetail } from "./ProductDetail";
import { Inventory } from "./Inventory";
import { Receipts } from "./Receipts";
import { Duplicates } from "./Duplicates";
import { AlexaAliases } from "./AlexaAliases";
import {
  ShoppingBasket,
  Package,
  ScanBarcode,
  RefreshCw,
  Archive,
  Tags,
  Copy,
} from "lucide-react";
import {
  chooseAlexaMatch,
  clearCompletedShopping,
  getAuthStatus,
  getShopping,
  loginStandalone,
  logoutStandalone,
  removeShopping,
  removeAlexaMatch,
  toggleShopping,
} from "./api";
import type { AlexaMatch } from "./types";

function Suggestions({
  match,
  onSaved, onCreate,
}: {
  match: AlexaMatch;
  onSaved: () => void;
  onCreate: () => void;
}) {
  const client = useQueryClient();
  const [selected, setSelected] = useState(
    String(match.selected_product_id ?? (match.requires_product ? match.candidates[0]?.id ?? "" : "")),
  );
  const [operationId] = useState(() => crypto.randomUUID());
  const mutation = useMutation({
    mutationFn: (id: number) => chooseAlexaMatch(match.key, id, operationId),
    retry: false,
    onSuccess: async () => {
      onSaved();
      await Promise.all([
        client.invalidateQueries({ queryKey: ["shopping"] }),
        client.invalidateQueries({ queryKey: ["inventory"] }),
      ]);
    },
  });
  useEffect(() => {
    if (selected && !match.candidates.some((candidate) => String(candidate.id) === selected))
      setSelected("");
  }, [match.candidates, selected]);
  return (
    <>
    <details className="suggestions">
      <summary>Elegir producto para «{match.name}»</summary>
      <div className="suggestion-options">
        {match.selection_stale && <p>El producto elegido ha cambiado o ya no está disponible. Revisa las opciones antes de guardar.</p>}
        {match.requires_product && <p>Este artículo está guardado como texto. Puedes asociarlo al producto conservando su cantidad, o quitarlo de la lista.</p>}
        <label htmlFor={"choice-" + match.key}>Producto sugerido</label>
        <select
          id={"choice-" + match.key}
          value={selected}
          disabled={mutation.isPending || mutation.isSuccess}
          onChange={(event) => setSelected(event.target.value)}
        >
          {match.requires_product
            ? <option value="" disabled>Selecciona un producto</option>
            : <option value="">Mantener artículo original</option>}
          {match.candidates.map((candidate) => (
            <option key={candidate.id} value={candidate.id}>
              {candidate.name}
            </option>
          ))}
        </select>
        <button
          disabled={mutation.isPending || mutation.isSuccess || (match.requires_product && !selected)}
          onClick={() => mutation.mutate(selected ? Number(selected) : 0)}
        >
          {selected || match.requires_product ? "Guardar elección" : "Mantener original"}
        </button>
        {mutation.isError && <p role="alert">{mutation.error.message}</p>}
      </div>
    </details>
    {!match.selected_product_id && <button className="secondary-button shopping-create-button" onClick={onCreate}>Crear producto para «{match.name}»</button>}
    </>
  );
}
function AuthenticatedApp() {
  const client = useQueryClient();
  const { view, setView, navigation } = useAppNavigation();
  const [selectedProductId, setSelectedProductId] = useState<number | null>(
    null,
  );
  const [creatingMatch, setCreatingMatch] = useState<{key: string; name: string} | null>(null);
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
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
  const removePending = useMutation({
    mutationFn: (key: string) => removeAlexaMatch(key),
    retry: false,
    onSuccess: async () => {
      setActionMessage("Artículo quitado de la lista.");
      await client.invalidateQueries({ queryKey: ["shopping"] });
    },
    onError: (error: Error) => setActionError(error.message),
  });
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["shopping"],
    queryFn: getShopping,
    refetchInterval: 5_000,
  });
  const matches = new Map(
    (data?.pending_matches ?? []).map((match) => [match.key, match]),
  );
  const normalizeName = (name: string) =>
    name
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  const assigned = new Set(
    (data?.items ?? []).map((item) => normalizeName(item.name)),
  );
  const unassigned = (data?.pending_matches ?? []).filter(
    (match) => !assigned.has(match.key),
  );
  const choiceSaved = () => {
    setActionError("");
    setActionMessage(
      "Artículo guardado en la lista. Ya puedes marcarlo como comprado o quitarlo.",
    );
  };
  return (
    <NavigationContext.Provider value={navigation}>
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
            ["actions", "receipts", "duplicates", "archived", "aliases"].includes(view)
              ? "active"
              : ""
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
            <button
              aria-label="Escanear ticket"
              aria-describedby="receipt-action-description"
              onClick={() => setView("receipts")}
            >
              <ScanBarcode size={24} aria-hidden="true" />
              <span>
                Escanear ticket
                <small id="receipt-action-description">
                  Revisar e importar una compra
                </small>
              </span>
            </button>
            <button
              aria-label="Revisar duplicados y auditoría"
              aria-describedby="audit-action-description"
              onClick={() => setView("duplicates")}
            >
              <Copy size={24} aria-hidden="true" />
              <span>
                Revisar duplicados y auditoría
                <small id="audit-action-description">
                  Consultar coincidencias del catálogo
                </small>
              </span>
            </button>
            <button
              aria-label="Productos archivados"
              aria-describedby="archive-action-description"
              onClick={() => setView("archived")}
            >
              <Archive size={24} aria-hidden="true" />
              <span>
                Productos archivados
                <small id="archive-action-description">
                  Consultar, restaurar o eliminar productos
                </small>
              </span>
            </button>
            <button aria-label="Administrar alias de Alexa" onClick={() => setView("aliases")}>
              <Tags size={24} aria-hidden="true" />
              <span>Alias de Alexa<small>Administrar nombres asociados a productos</small></span>
            </button>
          </div>
        </main>
      ) : view === "aliases" ? (
        <AlexaAliases />
      ) : view === "inventory" || view === "archived" ? (
        <Inventory key={view} archived={view === "archived"} />
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
              <span className="count">
                {(data?.items.length ?? 0) + unassigned.length} artículos
              </span>
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
          {actionMessage && (
            <p role="status" className="shopping-feedback">
              {actionMessage}
            </p>
          )}
          {data?.pending_matches_error && (
            <p role="alert" className="notice">
              No se pudieron cargar las sugerencias de Alexa. Actualiza para
              volver a intentarlo.
            </p>
          )}
          {data?.sync && !["ok", "unconfigured"].includes(data.sync.state) && (
            <p role="alert" className="notice">
              {data.sync.state === "disabled"
                ? "La sincronización con Alexa está desactivada; las sugerencias se consultan en modo lectura."
                : data.sync.state === "stale" || data.sync.state === "unknown"
                  ? "No se ha confirmado una sincronización reciente con Alexa. Revisa los logs del complemento."
                  : data.sync.reason === "note_conflict"
                    ? "Alexa no se ha sincronizado: hay artículos de texto que coinciden con productos. Asócialos con Elegir producto para conservar sus cantidades, o quita el artículo original de la lista."
                    : "Alexa no se ha sincronizado. Revisa las asociaciones y los logs del complemento antes de reintentar."}
            </p>
          )}
          {data?.shopping_error && (
            <p role="alert" className="notice">
              Grocy no está disponible en este momento.
            </p>
          )}
          <div className="items">
            {data?.items.map((item) => {
              const key = normalizeName(item.name);
              const match = matches.get(key);
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
                  {!match && !item.product_id && !item.done && <button className="secondary-button shopping-create-button" onClick={() => setCreatingMatch({key: normalizeName(item.name), name: item.name})}>Crear producto para «{item.name}»</button>}
                  {match && <Suggestions match={match} onSaved={choiceSaved} onCreate={() => setCreatingMatch({key: match.key, name: match.name})} />}
                </article>
              );
            })}
            {unassigned.map((match) => (
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
                <div className="item-actions">
                  <button
                    className="remove-button"
                    aria-label={"Quitar " + match.name}
                    disabled={
                      removePending.isPending ||
                      remove.isPending ||
                      toggle.isPending ||
                      clearCompleted.isPending
                    }
                    onClick={() => {
                      setActionError("");
                      setActionMessage("");
                      removePending.mutate(match.key);
                    }}
                  >
                    Quitar
                  </button>
                </div>
                <Suggestions match={match} onSaved={choiceSaved} onCreate={() => setCreatingMatch({key: match.key, name: match.name})} />
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
      {creatingMatch && <ShoppingProductCreation sourceKey={creatingMatch.key} name={creatingMatch.name} onClose={() => setCreatingMatch(null)} onSaved={() => { setCreatingMatch(null); choiceSaved(); }} />}
      <footer>Despensa 1.14.0</footer>
    </div>
    </NavigationContext.Provider>
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
