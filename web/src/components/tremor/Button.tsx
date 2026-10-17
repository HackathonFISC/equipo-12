// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import { cva, type VariantProps } from "class-variance-authority";
import { LoaderCircle } from "lucide-react";
import { forwardRef, type ComponentPropsWithoutRef } from "react";
import { cx, focusRing } from "./utils";

const buttonVariants = cva(
  [
    "relative inline-flex min-h-[44px] items-center justify-center gap-2 whitespace-nowrap rounded-md border px-3 py-2 text-center text-sm font-medium shadow-xs transition-all duration-100 ease-in-out",
    "disabled:pointer-events-none disabled:opacity-45 disabled:shadow-none",
    focusRing,
  ],
  {
    variants: {
      variant: {
        primary:
          "min-h-8 border-transparent bg-[#312d2a] text-white hover:bg-[#1d1c1b] disabled:bg-[#312d2a]/40",
        secondary:
          "border-line bg-surface text-ink hover:bg-sunken disabled:text-muted",
        light:
          "border-transparent bg-sunken text-ink shadow-none hover:bg-line disabled:text-muted",
        ghost:
          "border-transparent bg-transparent text-muted shadow-none hover:bg-sunken disabled:text-muted",
        destructive:
          "border-transparent bg-rejected text-white hover:bg-rejected/90 disabled:bg-rejected/40",
      },
    },
    defaultVariants: {
      variant: "primary",
    },
  },
);

interface ButtonProps
  extends ComponentPropsWithoutRef<"button">,
    VariantProps<typeof buttonVariants> {
  isLoading?: boolean;
  loadingText?: string;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      isLoading = false,
      loadingText,
      className,
      disabled,
      variant,
      children,
      ...props
    },
    forwardedRef,
  ) => (
    <button
      ref={forwardedRef}
      type="button"
      className={cx(buttonVariants({ variant }), className)}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="pointer-events-none flex shrink-0 items-center justify-center gap-1.5">
          <LoaderCircle
            className="size-4 shrink-0 animate-spin"
            aria-hidden="true"
          />
          <span className="sr-only">
            {loadingText ? loadingText : "Loading"}
          </span>
          {loadingText ? loadingText : children}
        </span>
      ) : (
        children
      )}
    </button>
  ),
);

Button.displayName = "Button";

export { Button, buttonVariants, type ButtonProps };
