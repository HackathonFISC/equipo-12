// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import { forwardRef, type HTMLAttributes } from "react";
import { cx } from "./utils";

const categoryColors: Record<string, string> = {
  blue: "bg-info",
  cyan: "bg-water",
  amber: "bg-pending",
  gray: "bg-simulated",
  emerald: "bg-approved",
};

function barClass(color: string | undefined): string {
  if (!color) return "bg-simulated";
  if (color.startsWith("bg-")) return color;
  return categoryColors[color] ?? "bg-simulated";
}

interface CategoryBarProps extends HTMLAttributes<HTMLDivElement> {
  values: number[];
  colors?: string[];
  marker?: number;
}

const CategoryBar = forwardRef<HTMLDivElement, CategoryBarProps>(
  ({ values = [], colors = ["blue", "cyan", "amber", "gray", "emerald"], marker, className, ...props }, forwardedRef) => {
    const total = values.reduce((sum, value) => sum + value, 0);
    const markerPercent =
      marker === undefined ? undefined : Math.min(100, Math.max(0, marker));

    return (
      <div
        ref={forwardedRef}
        className={cx(className)}
        aria-label="Category bar"
        aria-valuenow={markerPercent}
        {...props}
      >
        <div className="relative flex h-2 w-full items-center">
          <div className="flex h-full flex-1 items-center gap-0.5 overflow-hidden rounded-full">
            {values.map((value, index) => {
              const percentage = total > 0 ? (value / total) * 100 : 0;
              return (
                <div
                  key={`item-${index}`}
                  className={cx(
                    "h-full",
                    barClass(colors[index]),
                    percentage === 0 && "hidden",
                  )}
                  style={{ width: `${percentage}%` }}
                />
              );
            })}
          </div>
          {markerPercent !== undefined ? (
            <div
              className="absolute w-2 -translate-x-1/2"
              style={{ left: `${markerPercent}%` }}
            >
              <div
                className={cx(
                  "mx-auto h-4 w-1 rounded-full bg-ink ring-2 ring-surface",
                )}
              />
            </div>
          ) : null}
        </div>
      </div>
    );
  },
);

CategoryBar.displayName = "CategoryBar";

export { CategoryBar, type CategoryBarProps };
