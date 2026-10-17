// Base del panel: portado de src/coordinator/web/panel.html

import type { PlaceAnchor } from "../components/panel/contracts";
import { fold, niceName, prettyDistrict } from "./text";

export interface ParseSectorHint {
  sector_id: string;
  name: string;
  district?: string;
}

export interface ParseFreeTextResult {
  hours: number | null;
  people: number | null;
  matchedAnchor: PlaceAnchor | null;
  matchedSector: ParseSectorHint | null;
  confidence: number;
  vulnerabilities: string[];
}

export interface ApplyParsedResult {
  hours: number | null;
  hoursBucket: string | null;
  people: number | null;
  district: string;
  sectorId: string;
  location: string;
  latitude: number | null;
  longitude: number | null;
  locationPrecision: "precise" | "approximate";
  vulnerabilities: string[];
}

export interface SynthesizeInput {
  district?: string;
  sectorId?: string;
  sectorLabel?: string;
  location?: string;
  statedHours?: number | null;
  selectedHours?: number | null;
  people?: string;
  details?: string;
  vulnerabilities?: string[];
  useChatText?: boolean;
  chatText?: string;
}

export function snapHours(hours: number | null | undefined): string | null {
  if (hours == null || !Number.isFinite(hours)) return null;
  if (hours <= 12) return "6";
  if (hours <= 24) return "18";
  if (hours <= 48) return "36";
  return "72";
}

export function parseFreeText(
  text: string,
  places: PlaceAnchor[],
  sectors: ParseSectorHint[],
): ParseFreeTextResult {
  const folded = fold(text);
  let hours: number | null = null;
  const hourMatch = text.match(/(\d+)\s*horas?/i);
  if (hourMatch) hours = Number(hourMatch[1]);
  else if (/tres\s+dias|3\s+dias/.test(folded)) hours = 72;
  else if (/dos\s+dias|2\s+dias/.test(folded)) hours = 48;
  else if (/un\s+dia|1\s+dia/.test(folded)) hours = 24;

  let people: number | null = null;
  const peopleMatch = text.match(/(\d+)\s*personas?/i);
  if (peopleMatch) people = Number(peopleMatch[1]);
  else {
    const familyMatch = text.match(/(\d+)\s*familias?/i);
    if (familyMatch) people = Number(familyMatch[1]);
  }

  let matchedAnchor: PlaceAnchor | null = null;
  let bestLen = 0;
  for (const place of places) {
    const names = [place.name, ...(place.aliases ?? [])];
    for (const name of names) {
      const key = fold(name);
      if (key && folded.includes(key) && key.length > bestLen) {
        bestLen = key.length;
        matchedAnchor = place;
      }
    }
  }

  let matchedSector: ParseSectorHint | null = null;
  let sectorLen = 0;
  for (const sector of sectors) {
    const key = fold(sector.name);
    if (key && folded.includes(key) && key.length > sectorLen) {
      sectorLen = key.length;
      matchedSector = sector;
    }
  }

  const vulnerabilities: string[] = [];
  if (/adultos?\s+mayores|anciano/.test(folded)) {
    vulnerabilities.push("adultos mayores");
  }
  if (/hospital|atencion medica|clinica/.test(folded)) {
    vulnerabilities.push("hospital");
  }
  if (/infantes|ninos|bebes/.test(folded)) {
    vulnerabilities.push("ninos");
  }
  if (/escuela|colegio/.test(folded)) {
    vulnerabilities.push("escuela");
  }
  if (/albergue/.test(folded)) {
    vulnerabilities.push("albergue");
  }

  let confidence = 0.2;
  if (matchedAnchor) confidence = 0.85;
  else if (matchedSector) confidence = 0.55;
  if (hours != null) confidence += 0.05;
  if (people != null) confidence += 0.05;
  confidence = Math.min(1, confidence);

  return {
    hours,
    people,
    matchedAnchor,
    matchedSector,
    confidence,
    vulnerabilities,
  };
}

export function applyParsed(
  parsed: ParseFreeTextResult,
  sectors: ParseSectorHint[],
): ApplyParsedResult {
  const sector =
    (parsed.matchedAnchor
      ? sectors.find((s) => s.sector_id === parsed.matchedAnchor?.sector_id)
      : null) ?? parsed.matchedSector;

  const district = sector ? prettyDistrict(sector.district ?? sector.name) : "";
  const sectorId = sector?.sector_id ?? "";
  let location = "";
  let latitude: number | null = null;
  let longitude: number | null = null;
  let locationPrecision: "precise" | "approximate" = "approximate";

  if (parsed.matchedAnchor) {
    location = niceName(parsed.matchedAnchor.name);
    latitude = parsed.matchedAnchor.latitude;
    longitude = parsed.matchedAnchor.longitude;
    locationPrecision = "approximate";
  } else if (sector) {
    location = niceName(sector.name);
  }

  return {
    hours: parsed.hours,
    hoursBucket: snapHours(parsed.hours),
    people: parsed.people,
    district,
    sectorId,
    location,
    latitude,
    longitude,
    locationPrecision,
    vulnerabilities: parsed.vulnerabilities,
  };
}

export function synthesize(input: SynthesizeInput): string {
  if (input.useChatText && input.chatText?.trim()) {
    return input.chatText.trim();
  }
  const hours =
    input.statedHours != null ? input.statedHours : input.selectedHours;
  const people = String(input.people ?? "").trim();
  const location = String(input.location ?? "").trim();
  const sectorLabel =
    input.sectorLabel ??
    (input.sectorId ? input.sectorId.replace(/_/g, " ") : "sector desconocido");
  const district = input.district ? prettyDistrict(input.district) : "";
  const placeRef = location || sectorLabel;
  const where = district
    ? `${district}, ${sectorLabel} (${placeRef})`
    : `${sectorLabel} (${placeRef})`;
  let sentence = `En ${where} llevamos ${hours ?? "?"} horas sin agua, ${people || "?"} personas afectadas`;
  const vulns = input.vulnerabilities ?? [];
  if (vulns.length) sentence += `. Hay ${vulns.join(", ")}`;
  const details = String(input.details ?? "").trim();
  if (details) sentence += `. ${details}`;
  return sentence.replace(/\s+/g, " ").trim();
}
