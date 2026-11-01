import { createContext, useContext, useLayoutEffect, useState } from "react";

export type View = "shopping" | "inventory" | "actions" | "receipts" | "duplicates" | "aliases" | "archived";
type Entry = { session: string; view: View; layers: string[] };
type Layer = { id: string; close: () => void };
const views = new Set<View>(["shopping", "inventory", "actions", "receipts", "duplicates", "aliases", "archived"]);

/** Same-document history only: preserve the ingress URL and the host's state. */
export class AppNavigation {
  private session = crypto.randomUUID();
  private layers: Layer[] = [];
  private view: View = "shopping";
  private active = false;
  private queued = false;
  private pendingBack = false;
  private entry: Entry = { session: this.session, view: "shopping", layers: [] };
  constructor(private showView: (view: View) => void) {}
  private write = (entry: Entry, push = false) => {
    const state = { ...history.state, despensa: entry };
    if (push) history.pushState(state, "");
    else history.replaceState(state, "");
    this.entry = entry;
  };
  start = () => {
    this.active = true;
    this.write({ session: this.session, view: this.view, layers: [] });
    window.addEventListener("popstate", this.pop);
    return () => {
      this.active = false;
      window.removeEventListener("popstate", this.pop);
      this.layers = [];
      this.pendingBack = false;
    };
  };
  go = (view: View) => {
    if (view === this.view) return;
    this.view = view;
    this.showView(view);
    this.schedule();
  };
  register = (close: () => void) => {
    const layer = { id: crypto.randomUUID(), close };
    this.layers.push(layer);
    this.schedule();
    return () => {
      this.layers = this.layers.filter((item) => item !== layer);
      this.schedule();
    };
  };
  private schedule = () => {
    if (this.queued) return;
    this.queued = true;
    // Batch dialog replacement (create -> existing product) and StrictMode effects.
    queueMicrotask(() => {
      this.queued = false;
      if (this.active && !this.pendingBack) this.flush();
    });
  };
  private flush = () => {
    const ids = this.layers.map((layer) => layer.id);
    if (ids.length < this.entry.layers.length) {
      this.pendingBack = true;
      history.go(ids.length - this.entry.layers.length);
      return;
    }
    // Replace a closed dialog with its successor without a phantom Back step.
    const prefix = ids.slice(0, this.entry.layers.length);
    this.write({ ...this.entry, layers: prefix });
    if (this.entry.view !== this.view) {
      this.write({ session: this.session, view: this.view, layers: [] }, true);
    }
    for (let depth = this.entry.layers.length + 1; depth <= ids.length; depth++) {
      this.write({ session: this.session, view: this.view, layers: ids.slice(0, depth) }, true);
    }
  };
  private pop = (event: PopStateEvent) => {
    const target = event.state?.despensa as Entry | undefined;
    // Never trap root Back or reinterpret another app/session's history.
    if (!target || target.session !== this.session || !views.has(target.view) || !Array.isArray(target.layers)) return;
    this.entry = target;
    if (this.pendingBack) {
      this.pendingBack = false;
      this.flush();
      return;
    }
    const retained = this.layers.filter((layer) => target.layers.includes(layer.id));
    const closed = this.layers.filter((layer) => !target.layers.includes(layer.id));
    this.layers = retained;
    this.view = target.view;
    for (const layer of closed.reverse()) layer.close();
    this.showView(this.view);
    // Forward may reach a dialog that was closed; do not resurrect a stale form.
    this.write({ ...target, layers: retained.map((layer) => layer.id) });
  };
}

export const NavigationContext = createContext<AppNavigation | null>(null);
export function useAppNavigation() {
  const [view, showView] = useState<View>("shopping");
  const [navigation] = useState(() => new AppNavigation(showView));
  useLayoutEffect(navigation.start, [navigation]);
  return { view, setView: navigation.go, navigation };
}
export function useModalNavigation() {
  return useContext(NavigationContext);
}
