// Base del panel: portado de src/coordinator/web/panel.html

const NICE: Record<string, string> = {
  Arraijan: "Arraiján",
  "Arraijan cabecera": "Arraiján cabecera",
  "Arraijan Cabecera": "Arraiján Cabecera",
  "Barrio Colon": "Barrio Colón",
  "Hospital Nicolas Solano": "Hospital Nicolás Solano",
};

export function fold(value: string | null | undefined): string {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

export function niceName(name: string | null | undefined): string {
  const raw = String(name ?? "");
  return NICE[raw] ?? raw;
}

export function prettyDistrict(value: string | null | undefined): string {
  const key = fold(value);
  if (key.includes("chorrera")) return "La Chorrera";
  if (key.includes("arraijan")) return "Arraiján";
  return String(value ?? "");
}
