// Adaptado de Tremor (https://tremor.so), tremorlabs/tremor, Apache-2.0. Cambios: cva, lucide, dialog nativo.
import { forwardRef, type HTMLAttributes, type TableHTMLAttributes, type TdHTMLAttributes, type ThHTMLAttributes } from "react";
import { cx } from "./utils";

const TableRoot = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, forwardedRef) => (
    <div ref={forwardedRef}>
      <div className={cx("w-full overflow-auto whitespace-nowrap", className)} {...props}>
        {children}
      </div>
    </div>
  ),
);

TableRoot.displayName = "TableRoot";

const Table = forwardRef<HTMLTableElement, TableHTMLAttributes<HTMLTableElement>>(
  ({ className, ...props }, forwardedRef) => (
    <table
      ref={forwardedRef}
      className={cx("w-full caption-bottom border-b border-line", className)}
      {...props}
    />
  ),
);

Table.displayName = "Table";

const TableHead = forwardRef<
  HTMLTableSectionElement,
  HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, forwardedRef) => (
  <thead ref={forwardedRef} className={cx("bg-sunken", className)} {...props} />
));

TableHead.displayName = "TableHead";

const TableHeaderCell = forwardRef<
  HTMLTableCellElement,
  ThHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, forwardedRef) => (
  <th
    ref={forwardedRef}
    className={cx(
      "border-b border-line px-4 py-3.5 text-left text-sm font-semibold text-ink",
      className,
    )}
    {...props}
  />
));

TableHeaderCell.displayName = "TableHeaderCell";

const TableBody = forwardRef<
  HTMLTableSectionElement,
  HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, forwardedRef) => (
  <tbody
    ref={forwardedRef}
    className={cx("divide-y divide-line", className)}
    {...props}
  />
));

TableBody.displayName = "TableBody";

const TableRow = forwardRef<HTMLTableRowElement, HTMLAttributes<HTMLTableRowElement>>(
  ({ className, ...props }, forwardedRef) => (
    <tr
      ref={forwardedRef}
      className={cx(
        "[&_td:last-child]:pr-4 [&_th:last-child]:pr-4",
        "[&_td:first-child]:pl-4 [&_th:first-child]:pl-4",
        className,
      )}
      {...props}
    />
  ),
);

TableRow.displayName = "TableRow";

const TableCell = forwardRef<HTMLTableCellElement, TdHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, forwardedRef) => (
    <td
      ref={forwardedRef}
      className={cx("p-4 text-sm text-muted", className)}
      {...props}
    />
  ),
);

TableCell.displayName = "TableCell";

export {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRoot,
  TableRow,
};
