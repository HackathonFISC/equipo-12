// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import { forwardRef, type HTMLAttributes } from "react";
import { cx } from "./utils";

interface BarListItem {
  name: string;
  value: number;
  href?: string;
}

interface BarListProps extends HTMLAttributes<HTMLUListElement> {
  data: BarListItem[];
}

const BarList = forwardRef<HTMLUListElement, BarListProps>(
  ({ data = [], className, ...props }, forwardedRef) => {
    const maxValue = Math.max(...data.map((item) => item.value), 0);

    return (
      <ul
        ref={forwardedRef}
        className={cx("space-y-2", className)}
        {...props}
      >
        {data.map((item) => {
          const width =
            item.value === 0 || maxValue === 0
              ? 0
              : Math.max((item.value / maxValue) * 100, 2);
          return (
            <li
              key={item.name}
              className="flex items-center gap-3 text-sm text-ink"
            >
              {item.href ? (
                <a
                  href={item.href}
                  className="w-28 shrink-0 truncate hover:underline"
                >
                  {item.name}
                </a>
              ) : (
                <span className="w-28 shrink-0 truncate">{item.name}</span>
              )}
              <div className="h-2 min-w-0 flex-1 rounded-full bg-sunken">
                <div
                  className="h-full rounded-full bg-[#312d2a]"
                  style={{ width: `${width}%` }}
                />
              </div>
              <span className="w-12 shrink-0 text-right tabular-nums text-muted">
                {item.value}
              </span>
            </li>
          );
        })}
      </ul>
    );
  },
);

BarList.displayName = "BarList";

export { BarList, type BarListItem, type BarListProps };
