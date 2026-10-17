// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ComponentPropsWithoutRef } from "react";
import { cx } from "./utils";

const badgeVariants = cva(
  "inline-flex items-center gap-x-1 whitespace-nowrap rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset",
  {
    variants: {
      variant: {
        default: "bg-info/10 text-info ring-info/30",
        neutral: "bg-draft/10 text-draft ring-draft/30",
        success: "rounded-full bg-[#e5f3e8] text-[#3d6b4c] ring-0",
        error: "bg-rejected/10 text-rejected ring-rejected/30",
        warning: "bg-pending/10 text-pending ring-pending/30",
        simulated: "bg-simulated/10 text-simulated ring-simulated/30",
        synthetic: "bg-synthetic/10 text-synthetic ring-synthetic/30",
        partial: "bg-partial/10 text-partial ring-partial/30",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

interface BadgeProps
  extends ComponentPropsWithoutRef<"span">,
    VariantProps<typeof badgeVariants> {}

const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, ...props }, forwardedRef) => (
    <span
      ref={forwardedRef}
      className={cx(badgeVariants({ variant }), className)}
      {...props}
    />
  ),
);

Badge.displayName = "Badge";

export { Badge, badgeVariants, type BadgeProps };
