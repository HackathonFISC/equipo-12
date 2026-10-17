// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import { Plus } from "lucide-react";
import { type ComponentPropsWithoutRef, type HTMLAttributes } from "react";
import { cx } from "./utils";

function Accordion({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx(className)} {...props} />;
}

Accordion.displayName = "Accordion";

function AccordionItem({
  className,
  ...props
}: ComponentPropsWithoutRef<"details">) {
  return (
    <details
      className={cx(
        "group overflow-hidden border-b border-line first:mt-0",
        className,
      )}
      {...props}
    />
  );
}

AccordionItem.displayName = "AccordionItem";

function AccordionTrigger({
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<"summary">) {
  return (
    <summary
      className={cx(
        "flex cursor-pointer list-none items-center justify-between py-3 text-left text-sm font-medium leading-none text-ink",
        "marker:content-none [&::-webkit-details-marker]:hidden",
        "focus-visible:z-10 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-info",
        className,
      )}
      {...props}
    >
      {children}
      <Plus
        className="size-5 shrink-0 text-muted transition-transform duration-150 ease-[cubic-bezier(0.87,_0,_0.13,_1)] group-open:-rotate-45"
        aria-hidden="true"
      />
    </summary>
  );
}

AccordionTrigger.displayName = "AccordionTrigger";

function AccordionContent({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        "overflow-hidden pb-4 text-sm text-muted group-open:animate-accordionOpen",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

AccordionContent.displayName = "AccordionContent";

export { Accordion, AccordionContent, AccordionItem, AccordionTrigger };
