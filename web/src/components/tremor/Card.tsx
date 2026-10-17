// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import { forwardRef, type ComponentPropsWithoutRef } from "react";
import { cx } from "./utils";

interface CardProps extends ComponentPropsWithoutRef<"div"> {}

const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, ...props }, forwardedRef) => (
    <div
      ref={forwardedRef}
      className={cx(
        "relative w-full rounded-lg border border-[#e3e2df] bg-[#fafaf9] p-6 text-left text-ink shadow-none",
        className,
      )}
      {...props}
    />
  ),
);

Card.displayName = "Card";

export { Card, type CardProps };
