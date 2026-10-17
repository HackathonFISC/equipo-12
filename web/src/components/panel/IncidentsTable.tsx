import { useMemo, useState } from "react";
import {
  Badge,
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
  planned: "success",
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
  const [rowMenu, setRowMenu] = useState<string | null>(null);
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
    <div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-[#585655]">Filtros aplicados</span>
        <span className="rounded-full border border-[#d6d5d2] bg-[#f6f4f3] px-2 py-0.5 text-xs">
          Distrito {district === "all" ? "Panamá Oeste" : district}
        </span>
        <label className="sr-only" htmlFor="searchReports">
          Buscar incidencias
        </label>
        <input
          id="searchReports"
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          className="sr-only"
        />
        <select
          id="districtFilter"
          aria-label="Filtrar por distrito"
          value={district}
          onChange={(event) => setDistrict(event.target.value as DistrictFilter)}
          className="sr-only"
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
          className="h-8 rounded border border-[#d6d5d2] bg-white px-2 text-sm"
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
              <TableHeaderCell>
                <span className="sr-only">Acciones</span>
              </TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visible.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="py-8 text-center text-muted">
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
                  <TableCell className="font-medium text-[#00688b]">{row.code}</TableCell>
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
                  <TableCell className="relative w-10 text-right">
                    <button
                      type="button"
                      aria-label={`Más opciones de ${row.code}`}
                      aria-expanded={rowMenu === row.clusterId}
                      className="px-2 tracking-[0.2em] text-[#1c1c1a]"
                      onClick={(event) => {
                        event.stopPropagation();
                        setRowMenu((current) =>
                          current === row.clusterId ? null : row.clusterId,
                        );
                      }}
                    >
                      ···
                    </button>
                    {rowMenu === row.clusterId ? (
                      <div
                        role="menu"
                        className="absolute right-2 top-8 z-20 min-w-[9rem] rounded border border-[#00688b] bg-white py-1 text-left shadow-[0_1px_4px_rgba(28,28,26,0.16)]"
                      >
                        <button
                          type="button"
                          role="menuitem"
                          className="block w-full px-3 py-1.5 text-left text-sm hover:bg-[#f6f4f3]"
                          onClick={(event) => {
                            event.stopPropagation();
                            setRowMenu(null);
                            openRow(row.clusterId);
                          }}
                        >
                          Ver detalle
                        </button>
                      </div>
                    ) : null}
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
    </div>
  );
}
