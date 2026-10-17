// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import { forwardRef, type ComponentPropsWithoutRef } from "react";
import { cx } from "./utils";

interface CardProps extends ComponentPropsWithoutRef<"div"> {}

const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, ...props }, forwardedRef) => (
    <div
      ref={forwardedRef}
      className={cx(
        "relative w-full rounded-lg bg-surface p-5 text-left text-ink shadow-[0_8px_28px_rgba(22,52,75,0.045)] ring-1 ring-line",
        className,
      )}
      {...props}
    />
  ),
);

Card.displayName = "Card";

export { Card, type CardProps };
