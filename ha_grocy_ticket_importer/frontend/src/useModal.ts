import { useEffect, useRef } from "react";
import { useModalNavigation } from "./navigation";

let openModals = 0;
let originalOverflow = "";
/** Trap keyboard focus in the active dialog, restore focus and release scroll. */
export function useModal(onClose: () => void, enabled = true) {
  const navigation = useModalNavigation();
  const ref = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const element = ref.current;
    if (!enabled || !element) return;
    const unregister = navigation?.register(() => close.current());
    const previousFocus = document.activeElement as HTMLElement | null;
    if (openModals++ === 0) {
      originalOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    const focusable = () =>
      Array.from(
        element.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), select:not(:disabled), a[href], [tabindex="0"]',
        ),
      ).filter((node) => node.getClientRects().length > 0);
    (focusable()[0] ?? element).focus();
    const keydown = (event: KeyboardEvent) => {
      if (document.activeElement?.closest('[role="dialog"]') !== element)
        return;
      if (event.key === "Escape") {
        event.preventDefault();
        close.current();
      }
      if (event.key === "Tab") {
        const nodes = focusable();
        const first = nodes[0];
        const last = nodes[nodes.length - 1];
        if (!first) {
          event.preventDefault();
          element.focus();
        } else if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      unregister?.();
      document.removeEventListener("keydown", keydown);
      if (--openModals === 0) document.body.style.overflow = originalOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [enabled, navigation]);
  return ref;
}
