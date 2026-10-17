// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import {
  useEffect,
  useRef,
  type ComponentPropsWithoutRef,
  type ReactNode,
} from "react";
import { cx, focusRing } from "./utils";

interface DialogProps extends Omit<ComponentPropsWithoutRef<"dialog">, "open"> {
  children?: ReactNode;
  className?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  "aria-label"?: string;
}

export function Dialog({
  open = false,
  onOpenChange,
  children,
  className,
  id,
  "aria-label": ariaLabel,
  ...props
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open) {
      if (!el.open) el.showModal();
    } else if (el.open) {
      el.close();
    }
  }, [open]);

  return (
    <dialog
      id={id}
      ref={ref}
      aria-label={ariaLabel}
      className={cx(
        "fixed left-1/2 top-1/2 z-50 m-0 w-[95vw] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-md border border-line bg-surface p-6 text-ink shadow-lg",
        "open:animate-dialogContentShow backdrop:animate-dialogOverlayShow backdrop:bg-black/70",
        focusRing,
        className,
      )}
      {...props}
      onClose={() => onOpenChange?.(false)}
      onClick={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        const inside =
          event.clientX >= rect.left &&
          event.clientX <= rect.right &&
          event.clientY >= rect.top &&
          event.clientY <= rect.bottom;
        if (!inside) onOpenChange?.(false);
      }}
    >
      {children}
    </dialog>
  );
}

Dialog.displayName = "Dialog";

export type { DialogProps };
