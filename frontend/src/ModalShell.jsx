import { useEffect, useRef } from "react";

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

export default function ModalShell({
  as: As = "div",
  className = "",
  busy = false,
  onClose,
  onSubmit,
  labelledBy,
  describedBy,
  children,
}) {
  const panelRef = useRef(null);
  const previousFocus = useRef(null);

  useEffect(() => {
    previousFocus.current = document.activeElement;
    const panel = panelRef.current;
    if (!panel) {
      return undefined;
    }
    const focusables = () =>
      [...panel.querySelectorAll(FOCUSABLE)].filter((node) => !node.hasAttribute("disabled"));
    const preferred =
      focusables().find((node) => ["INPUT", "TEXTAREA", "SELECT"].includes(node.tagName)) ||
      focusables()[0];
    preferred?.focus();

    const onKeyDown = (event) => {
      if (event.key === "Escape" && !busy) {
        event.preventDefault();
        onClose?.();
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const items = focusables();
      if (!items.length) {
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      const target = previousFocus.current;
      if (target && typeof target.focus === "function") {
        target.focus();
      }
    };
  }, [busy, onClose]);

  return (
    <div
      className="overlay"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose?.()}
    >
      <As
        ref={panelRef}
        className={["modal", className].filter(Boolean).join(" ")}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        onSubmit={onSubmit}
      >
        {children}
      </As>
    </div>
  );
}
