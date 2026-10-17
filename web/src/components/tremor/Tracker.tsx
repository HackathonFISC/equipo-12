// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import { forwardRef, type HTMLAttributes } from "react";
import { cx } from "./utils";

const trackerColors: Record<string, string> = {
  water: "bg-water",
  pending: "bg-pending",
  rejected: "bg-rejected",
  partial: "bg-partial",
  info: "bg-info",
  simulated: "bg-simulated",
  approved: "bg-approved",
};

interface TrackerBlockProps {
  key?: string | number;
  color?: string;
  tooltip?: string;
}

function blockClass(color: string | undefined): string {
  if (!color) return "bg-sunken";
  if (color.startsWith("bg-")) return color;
  return trackerColors[color] ?? "bg-sunken";
}

interface TrackerProps extends HTMLAttributes<HTMLDivElement> {
  data: TrackerBlockProps[];
}

const Tracker = forwardRef<HTMLDivElement, TrackerProps>(
  ({ data = [], className, ...props }, forwardedRef) => (
    <div
      ref={forwardedRef}
      className={cx("flex h-8 w-full items-center gap-px", className)}
      {...props}
    >
      {data.map((block, index) => (
        <div
          key={block.key ?? index}
          title={block.tooltip}
          className={cx(
            "size-full min-w-0 rounded-[4px] first:rounded-l-[4px] last:rounded-r-[4px]",
            blockClass(block.color),
          )}
        />
      ))}
    </div>
  ),
);

Tracker.displayName = "Tracker";

export { Tracker, type TrackerBlockProps, type TrackerProps };
