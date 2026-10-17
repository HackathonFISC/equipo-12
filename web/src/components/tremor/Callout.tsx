// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ComponentPropsWithoutRef, type ElementType, type ReactElement } from "react";
import { cx } from "./utils";

const calloutVariants = cva(
  "flex flex-col overflow-hidden rounded-md border p-4 text-sm",
  {
    variants: {
      variant: {
        default: "border-info/30 bg-info/10 text-info",
        warning: "border-synthetic/40 bg-synthetic/10 text-synthetic",
        error: "border-rejected/40 bg-rejected/10 text-rejected",
        success: "border-approved/40 bg-approved/10 text-approved",
        neutral: "border-line bg-sunken text-ink",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

interface CalloutProps
  extends ComponentPropsWithoutRef<"div">,
    VariantProps<typeof calloutVariants> {
  title: string;
  icon?: ElementType | ReactElement;
}

const Callout = forwardRef<HTMLDivElement, CalloutProps>(
  ({ title, icon: Icon, className, variant, children, ...props }, forwardedRef) => (
    <div
      ref={forwardedRef}
      className={cx(calloutVariants({ variant }), className)}
      {...props}
    >
      <div className="flex items-start">
        {Icon && typeof Icon === "function" ? (
          <Icon className="mr-1.5 h-5 w-5 shrink-0" aria-hidden="true" />
        ) : (
          Icon
        )}
        <span className="font-semibold">{title}</span>
      </div>
      <div className={cx("overflow-y-auto", children ? "mt-2" : "")}>
        {children}
      </div>
    </div>
  ),
);

Callout.displayName = "Callout";

export { Callout, calloutVariants, type CalloutProps };
