import { Button, Dialog } from "../tremor";
import type { DetailDialogProps } from "./contracts";

export function DetailDialog({
  open,
  clusterId,
  sectorName,
  clusterMeta,
  priority,
  onClose,
}: DetailDialogProps) {
  const title = clusterId
    ? `Detalle · ${clusterId}`
    : sectorName
      ? `Detalle · ${sectorName}`
      : "Detalle";

  return (
    <Dialog
      id="detailDialog"
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      aria-label={title}
      className="max-w-xl"
    >
      <h2 className="font-display text-xl font-semibold text-ink">{title}</h2>
      {sectorName ? (
        <p className="mt-1 text-sm text-muted">
          Sector: <span className="font-medium text-ink">{sectorName}</span>
        </p>
      ) : null}

      <div className="mt-4 space-y-3 text-sm text-ink">
        {Object.keys(clusterMeta).length > 0 ? (
          <dl className="divide-y divide-line rounded-md border border-line">
            {Object.entries(clusterMeta).map(([key, value]) => (
              <div key={key} className="grid grid-cols-[minmax(0,38%)_1fr] gap-2 px-3 py-2">
                <dt className="font-medium text-muted">{key}</dt>
                <dd className="break-words">{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-muted">Sin metadatos adicionales para este cluster.</p>
        )}

        {priority ? (
          <div className="rounded-md border border-line bg-sunken p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              Prioridad · {priority.formula_version}
            </p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{priority.score}</p>
            <p className="mt-2 text-sm text-muted">{priority.explanation}</p>
            {priority.breakdown.length > 0 ? (
              <ul className="mt-3 space-y-1 text-sm">
                {priority.breakdown.map((item) => (
                  <li key={item.factor} className="flex justify-between gap-2">
                    <span>{item.factor}</span>
                    <span className="font-medium tabular-nums">{item.points}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-6 flex justify-end">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cerrar
        </Button>
      </div>
    </Dialog>
  );
}
