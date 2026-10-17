import type { ToastProps } from "./contracts";
import { cx } from "../tremor";

export function Toast({ message, visible }: ToastProps) {
  const show = visible && message.length > 0;

  return (
    <div
      id="toast"
      role="status"
      aria-live="polite"
      className={cx(
        "fixed bottom-6 left-1/2 z-[60] max-w-[min(92vw,28rem)] -translate-x-1/2 rounded-md border px-4 py-3 text-sm font-medium shadow-lg",
        "border-info/30 bg-info/10 text-info",
        !show && "hidden",
      )}
    >
      {message}
    </div>
  );
}
