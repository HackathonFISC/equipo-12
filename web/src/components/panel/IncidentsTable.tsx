import { useMemo, useState } from "react";
import {
  Badge,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRoot,
  TableRow,
} from "../tremor";
import { fold, prettyDistrict } from "../../lib/text";
import type {
  IncidentStatus,
  IncidentsTableProps,
} from "./contracts";

const STATUS_LABEL: Record<IncidentStatus, string> = {
  received: "Recibido",
  analyzing: "En análisis",
  planned: "En plan",
  approved: "Aprobado",
};

const STATUS_VARIANT: Record<
  IncidentStatus,
  "neutral" | "warning" | "default" | "success"
> = {
  received: "neutral",
  analyzing: "warning",
  planned: "default",
  approved: "success",
};

const LEVEL_CLASS = {
  high: "text-priority-high",
  medium: "text-priority-mid",
  low: "text-priority-low",
} as const;

type DistrictFilter = "all" | "Arraiján" | "La Chorrera";

function rowDistrict(sector: string, district: string | undefined): string {
  if (district) return prettyDistrict(district) || district;
  return prettyDistrict(sector);
}

export function IncidentsTable({
  rows,
  query,
  status,
  counts,
  onQueryChange,
  onStatusChange,
  onOpenDetail,
  districtFilter,
  onDistrictFilter,
  onOpen,
}: IncidentsTableProps) {
  const [localDistrict, setLocalDistrict] = useState<DistrictFilter>("all");
  const district = districtFilter ?? localDistrict;

  const visible = useMemo(() => {
    const needle = fold(query);
    return rows.filter((row) => {
      if (status !== "all" && row.status !== status) return false;
      if (district !== "all") {
        const hay = rowDistrict(row.sector, row.district);
        if (hay !== district) return false;
      }
      if (!needle) return true;
      const blob = fold(
        [row.code, row.place, row.sector, row.people, String(row.score), row.status].join(
          " ",
        ),
      );
      return blob.includes(needle);
    });
  }, [district, query, rows, status]);

  const resultsCount = `${visible.length} de ${rows.length}`;

  function setDistrict(value: DistrictFilter) {
    onDistrictFilter?.(value);
    if (districtFilter === undefined) setLocalDistrict(value);
  }

  function openRow(clusterId: string) {
    onOpen?.(clusterId);
    onOpenDetail(clusterId);
  }

  return (
    <Card>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-line bg-sunken px-3">
          <span className="sr-only">Buscar incidencias</span>
          <input
            id="searchReports"
            type="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Buscar sector o código…"
            className="h-11 min-w-0 flex-1 bg-transparent text-sm text-ink outline-none"
          />
        </label>
        <select
          id="districtFilter"
          aria-label="Filtrar por distrito"
          value={district}
          onChange={(event) => setDistrict(event.target.value as DistrictFilter)}
          className="h-11 rounded-md border border-line bg-surface px-3 text-sm text-ink"
        >
          <option value="all">Todos los distritos</option>
          <option value="Arraiján">Arraiján</option>
          <option value="La Chorrera">La Chorrera</option>
        </select>
        <select
          id="statusFilter"
          aria-label="Filtrar por estado"
          value={status}
          onChange={(event) =>
            onStatusChange(event.target.value as "all" | IncidentStatus)
          }
          className="h-11 rounded-md border border-line bg-surface px-3 text-sm text-ink"
        >
          <option value="all">Todos ({counts.all})</option>
          <option value="received">Recibido ({counts.received})</option>
          <option value="analyzing">En análisis ({counts.analyzing})</option>
          <option value="planned">En plan ({counts.planned})</option>
          <option value="approved">Aprobado ({counts.approved})</option>
        </select>
      </div>

      <TableRoot className="mt-4">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Código</TableHeaderCell>
              <TableHeaderCell>Lugar</TableHeaderCell>
              <TableHeaderCell>Sector</TableHeaderCell>
              <TableHeaderCell>Afectados</TableHeaderCell>
              <TableHeaderCell>Prioridad</TableHeaderCell>
              <TableHeaderCell>Estado</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visible.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-muted">
                  Cargue el lote para ver incidencias
                </TableCell>
              </TableRow>
            ) : (
              visible.map((row) => (
                <TableRow
                  key={row.clusterId}
                  data-cluster={row.clusterId}
                  className="cursor-pointer hover:bg-sunken"
                  onClick={() => openRow(row.clusterId)}
                >
                  <TableCell className="font-medium text-ink">{row.code}</TableCell>
                  <TableCell>{row.place}</TableCell>
                  <TableCell>{row.sector}</TableCell>
                  <TableCell>{row.people}</TableCell>
                  <TableCell className={LEVEL_CLASS[row.level]}>
                    {row.score}
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[row.status]}>
                      {STATUS_LABEL[row.status]}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableRoot>

      <p id="resultsCount" className="mt-3 text-xs text-muted">
        {resultsCount}
      </p>
    </Card>
  );
}
