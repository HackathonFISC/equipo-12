"""Sixteen deterministic allocation cases. MODO=test never calls a provider."""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from src.config import PROJECT_ROOT, load_runtime_config
from src.contracts import (
    GeoPrecision,
    NormalizedIncidentCluster,
    ProvenanceTag,
    ReportInput,
    SectorId,
    VulnerabilityFlag,
)
from src.coordinator.service import _OPERATIONAL_PRELOAD_REPORTS, _load_sample_reports_fixture
from src.ingestion.agent import ingest_report
from src.ingestion.deduplicator import deduplicate_reports
from src.orchestration.agent import orchestrate
from src.planner.draft import build_plan
from src.planner.solver import DEFAULT_FLEET, Truck, solve
from src.priority import rank_clusters, score_cluster
from src.prioritization.agent import prioritize_clusters

_RESULTS_PATH = PROJECT_ROOT / "evals" / "results_allocation.json"

_PLACE_COORDS: dict[str, tuple[float, float]] = {
    "VISTA_ALEGRE_CHINO": (8.95, -79.7),
    "VISTA_ALEGRE_XTRA": (8.95, -79.716),
    "BURUNGA_CENTRO": (8.97, -79.68),
    "NUEVO_CHORRILLO": (8.93, -79.72),
    "ARRAIJAN_CABECERA": (8.938, -79.65),
    "HOSPITAL_NICOLAS_SOLANO": (8.882, -79.782),
    "EL_COCO": (8.87, -79.85),
    "GUADALUPE": (8.89, -79.82),
    "PUERTO_CAIMITO": (8.872, -79.83),
    "BARRIO_COLON": (8.88, -79.782),
    "CERRO_SILVESTRE": (8.91, -79.66),
    "VACAMONTE": (8.94, -79.67),
}


def _cluster(
    cluster_id: str,
    sector_id: SectorId,
    *,
    hours: int,
    affected: int,
    flags: list[VulnerabilityFlag] | None = None,
    report_count: int = 1,
    latitude: float | None = None,
    longitude: float | None = None,
    geo_precision: GeoPrecision = GeoPrecision.POINT,
    requires_human_review: bool = False,
    place_id: str = "",
) -> NormalizedIncidentCluster:
    if flags is None:
        flags = [VulnerabilityFlag.NINGUNA]
    return NormalizedIncidentCluster(
        cluster_id=cluster_id,
        sector_id=sector_id,
        source_report_ids=[f"{cluster_id}-r{i}" for i in range(report_count)],
        report_count=report_count,
        max_duration_hours=hours,
        estimated_affected_count=affected,
        vulnerability_flags=flags,
        requires_human_review=requires_human_review,
        latitude=latitude,
        longitude=longitude,
        geo_precision=geo_precision,
        place_id=place_id,
    )


def _coords(place_key: str) -> tuple[float, float]:
    return _PLACE_COORDS[place_key]


def _report(report_id: str, text: str) -> ReportInput:
    return ReportInput(
        report_id=report_id,
        raw_text=text,
        source_channel="whatsapp",
        provenance=ProvenanceTag.SYNTHETIC_DEMO,
        timestamp=datetime(2026, 10, 16, tzinfo=UTC),
    )


def _preload_reports() -> list[ReportInput]:
    records = _load_sample_reports_fixture() + [dict(item) for item in _OPERATIONAL_PRELOAD_REPORTS]
    reports: list[ReportInput] = []
    for record in records:
        raw = record.get("raw_text", "")
        raw_text = raw if isinstance(raw, str) else str(raw)
        fixture_id = record.get("report_id")
        report_id = (
            fixture_id.strip()
            if isinstance(fixture_id, str) and fixture_id.strip()
            else f"preload-{len(reports)}"
        )
        channel = record.get("source_channel", "panel")
        source_channel = channel.strip() if isinstance(channel, str) and channel.strip() else "panel"
        provenance_raw = record.get("provenance", ProvenanceTag.SYNTHETIC_DEMO.value)
        try:
            provenance = ProvenanceTag(str(provenance_raw))
        except ValueError:
            provenance = ProvenanceTag.SYNTHETIC_DEMO
        reports.append(
            ReportInput(
                report_id=report_id,
                raw_text=raw_text,
                source_channel=source_channel,
                provenance=provenance,
                timestamp=datetime(2026, 10, 16, 12, 0, tzinfo=UTC),
            )
        )
    return reports


def _fleet_capacity() -> dict[str, int]:
    return {truck.vehicle_id: truck.capacity_liters for truck in DEFAULT_FLEET}


def _capacity_ok(assignments: list) -> bool:
    used: dict[str, int] = {truck.vehicle_id: 0 for truck in DEFAULT_FLEET}
    caps = _fleet_capacity()
    for item in assignments:
        used[item.vehicle_id] = used.get(item.vehicle_id, 0) + item.volume_liters
    return all(used.get(vid, 0) <= caps[vid] for vid in caps)


@dataclass(frozen=True)
class AllocationEvalCase:
    case_id: str
    group: str
    name: str
    run: Callable[[], tuple[bool, str]]


def _case_alloc_01() -> tuple[bool, str]:
    hospital = _cluster(
        "hospital-colon",
        SectorId.CHORRERA_BARRIO_COLON,
        hours=72,
        affected=500,
        flags=[VulnerabilityFlag.HOSPITAL_SALUD],
    )
    el_coco = _cluster(
        "el-coco",
        SectorId.CHORRERA_EL_COCO,
        hours=18,
        affected=140,
        flags=[VulnerabilityFlag.NINGUNA],
    )
    hospital_score = score_cluster(hospital).score
    coco_score = score_cluster(el_coco).score
    ok = hospital_score > coco_score
    return ok, f"hospital={hospital_score} el_coco={coco_score}"


def _case_alloc_02() -> tuple[bool, str]:
    vista = _cluster(
        "vista-alegre",
        SectorId.ARRAIJAN_VISTA_ALEGRE,
        hours=48,
        affected=240,
        flags=[VulnerabilityFlag.ESCUELA, VulnerabilityFlag.ADULTOS_MAYORES],
    )
    silvestre = _cluster(
        "cerro-silvestre",
        SectorId.ARRAIJAN_CERRO_SILVESTRE,
        hours=6,
        affected=20,
        flags=[VulnerabilityFlag.NINGUNA],
    )
    ok = score_cluster(vista).score > score_cluster(silvestre).score
    return ok, f"vista={score_cluster(vista).score} silvestre={score_cluster(silvestre).score}"


def _case_alloc_03() -> tuple[bool, str]:
    clusters = [
        _cluster(
            "colon-hospital",
            SectorId.CHORRERA_BARRIO_COLON,
            hours=72,
            affected=500,
            flags=[VulnerabilityFlag.HOSPITAL_SALUD],
        ),
        _cluster(
            "guadalupe-clinic",
            SectorId.CHORRERA_GUADALUPE,
            hours=60,
            affected=200,
            flags=[VulnerabilityFlag.HOSPITAL_SALUD],
        ),
        _cluster(
            "burunga-families",
            SectorId.ARRAIJAN_BURUNGA,
            hours=48,
            affected=160,
            flags=[VulnerabilityFlag.INFANTES, VulnerabilityFlag.ADULTOS_MAYORES],
        ),
        _cluster(
            "nuevo-chorrillo",
            SectorId.ARRAIJAN_NUEVO_CHORRILLO,
            hours=12,
            affected=40,
            flags=[VulnerabilityFlag.NINGUNA],
        ),
    ]
    expected = [
        "colon-hospital",
        "guadalupe-clinic",
        "burunga-families",
        "nuevo-chorrillo",
    ]
    ranked_ids = [item.cluster_id for item in rank_clusters(clusters)]
    prioritized = prioritize_clusters(clusters)
    priority_ids = [item.priority.cluster_id for item in prioritized.items]
    ok = ranked_ids == expected and priority_ids == expected
    return ok, f"rank={ranked_ids} agent={priority_ids}"


def _case_alloc_04() -> tuple[bool, str]:
    capped_a = _cluster(
        "cluster-aaa",
        SectorId.CHORRERA_GUADALUPE,
        hours=300,
        affected=100_000,
        flags=[
            VulnerabilityFlag.HOSPITAL_SALUD,
            VulnerabilityFlag.ESCUELA,
            VulnerabilityFlag.ADULTOS_MAYORES,
            VulnerabilityFlag.INFANTES,
            VulnerabilityFlag.ALBERGUE,
        ],
    )
    capped_b = _cluster(
        "cluster-bbb",
        SectorId.CHORRERA_EL_COCO,
        hours=168,
        affected=50_000,
        flags=[
            VulnerabilityFlag.HOSPITAL_SALUD,
            VulnerabilityFlag.ESCUELA,
            VulnerabilityFlag.ADULTOS_MAYORES,
        ],
    )
    score_a = score_cluster(capped_a)
    score_b = score_cluster(capped_b)
    ranked = rank_clusters([capped_b, capped_a])
    ok = (
        score_a.score == 100.0
        and score_b.score == 100.0
        and score_a.breakdown[0].points == 40.0
        and score_a.breakdown[2].points == 30.0
        and [item.cluster_id for item in ranked] == ["cluster-aaa", "cluster-bbb"]
    )
    return ok, f"scores=({score_a.score},{score_b.score}) order={[i.cluster_id for i in ranked]}"


def _case_alloc_05() -> tuple[bool, str]:
    base = dict(hours=36, affected=120, flags=[VulnerabilityFlag.ESCUELA])
    one = _cluster("vol-1", SectorId.ARRAIJAN_CABECERA, report_count=1, **base)
    many = _cluster("vol-50", SectorId.ARRAIJAN_CABECERA, report_count=50, **base)
    single = score_cluster(one)
    flooded = score_cluster(many)
    ok = (
        single.score == flooded.score
        and single.breakdown == flooded.breakdown
    )
    return ok, f"score={single.score}"


def _case_alloc_06() -> tuple[bool, str]:
    cabecera = _cluster(
        "cabecera-noisy",
        SectorId.ARRAIJAN_CABECERA,
        hours=12,
        affected=30,
        flags=[VulnerabilityFlag.NINGUNA],
        report_count=25,
    )
    caimito = _cluster(
        "caimito-quiet",
        SectorId.CHORRERA_PUERTO_CAIMITO,
        hours=96,
        affected=120,
        flags=[VulnerabilityFlag.ADULTOS_MAYORES],
        report_count=1,
    )
    ranked = rank_clusters([cabecera, caimito])
    ok = ranked[0].cluster_id == "caimito-quiet"
    return ok, f"first={ranked[0].cluster_id}"


def _case_alloc_07() -> tuple[bool, str]:
    runtime = load_runtime_config()
    xtra_text = "Xtra de Vista Alegre: tres dias sin agua y 20 familias"
    hospital_text = (
        "El Hospital Nicolas Solano lleva 72 horas sin agua y atiende 500 personas"
    )
    extracted = []
    for index in range(5):
        extracted.append(
            ingest_report(_report(f"xtra-{index}", xtra_text), config=runtime).extracted
        )
    extracted.append(
        ingest_report(_report("hospital-1", hospital_text), config=runtime).extracted
    )
    clusters = deduplicate_reports(extracted)
    ranked = rank_clusters(clusters)
    top = ranked[0].cluster_id if ranked else ""
    hospital_cluster = next(
        (c for c in clusters if c.sector_id == SectorId.CHORRERA_BARRIO_COLON),
        None,
    )
    ok = hospital_cluster is not None and ranked and ranked[0] == score_cluster(hospital_cluster)
    return ok, f"top_cluster={top} hospital_id={hospital_cluster.cluster_id if hospital_cluster else None}"


def _case_alloc_08() -> tuple[bool, str]:
    clusters = [
        _cluster("p8-a", SectorId.CHORRERA_BARRIO_COLON, hours=48, affected=200, flags=[VulnerabilityFlag.HOSPITAL_SALUD]),
        _cluster("p8-b", SectorId.ARRAIJAN_BURUNGA, hours=24, affected=80, flags=[VulnerabilityFlag.INFANTES]),
        _cluster("p8-c", SectorId.CHORRERA_EL_COCO, hours=12, affected=30, flags=[VulnerabilityFlag.NINGUNA]),
    ]
    expected = rank_clusters(clusters)
    agent = prioritize_clusters(clusters)
    ok = agent.priorities == expected
    return ok, f"match={ok} scores={[p.score for p in agent.priorities]}"


def _case_alloc_09() -> tuple[bool, str]:
    lat_lon = [
        ("s1", SectorId.CHORRERA_BARRIO_COLON, "HOSPITAL_NICOLAS_SOLANO", 400),
        ("s2", SectorId.CHORRERA_EL_COCO, "EL_COCO", 380),
        ("s3", SectorId.CHORRERA_GUADALUPE, "GUADALUPE", 360),
        ("s4", SectorId.CHORRERA_PUERTO_CAIMITO, "PUERTO_CAIMITO", 340),
        ("s5", SectorId.ARRAIJAN_BURUNGA, "BURUNGA_CENTRO", 320),
        ("s6", SectorId.ARRAIJAN_VISTA_ALEGRE, "VISTA_ALEGRE_CHINO", 300),
        ("s7", SectorId.ARRAIJAN_CABECERA, "ARRAIJAN_CABECERA", 280),
        ("s8", SectorId.ARRAIJAN_NUEVO_CHORRILLO, "NUEVO_CHORRILLO", 260),
    ]
    clusters: list[NormalizedIncidentCluster] = []
    scores = []
    for cluster_id, sector, place, affected in lat_lon:
        lat, lon = _coords(place)
        clusters.append(
            _cluster(
                cluster_id,
                sector,
                hours=72,
                affected=affected,
                latitude=lat,
                longitude=lon,
            )
        )
        scores.append(score_cluster(clusters[-1]))
    result = solve(clusters, scores)
    ok = _capacity_ok(result.assignments) and "ortools-routing" in result.constraints
    return ok, f"assignments={len(result.assignments)} unserved={len(result.unserved)} constraints={result.constraints}"


def _case_alloc_10() -> tuple[bool, str]:
    lat, lon = _coords("EL_COCO")
    far = _cluster(
        "far-shift",
        SectorId.CHORRERA_EL_COCO,
        hours=48,
        affected=100,
        latitude=lat,
        longitude=lon,
    )
    fleet = [Truck("cisterna-1", 10_000, 35)]
    scores = [score_cluster(far)]
    result = solve([far], scores, fleet=fleet)
    ok = result.assignments == [] and SectorId.CHORRERA_EL_COCO.value in result.unserved
    return ok, f"assignments={len(result.assignments)} unserved={result.unserved}"


def _case_alloc_11() -> tuple[bool, str]:
    lat, lon = _coords("BARRIO_COLON")
    known = _cluster(
        "known-colon",
        SectorId.CHORRERA_BARRIO_COLON,
        hours=24,
        affected=50,
        latitude=lat,
        longitude=lon,
    )
    unknown = _cluster(
        "unknown-sector",
        SectorId.UNKNOWN,
        hours=48,
        affected=80,
        latitude=None,
        longitude=None,
        geo_precision=GeoPrecision.UNKNOWN,
        requires_human_review=True,
    )
    missing_coords = _cluster(
        "missing-coords",
        SectorId.ARRAIJAN_CABECERA,
        hours=36,
        affected=60,
        latitude=None,
        longitude=None,
    )
    plan = build_plan(
        [known, unknown, missing_coords],
        rank_clusters([known, unknown, missing_coords]),
    )
    assigned = {item.sector_id.value for item in plan.assignments}
    unserved = set(plan.unserved_demand)
    ok = (
        SectorId.UNKNOWN.value not in assigned
        and SectorId.UNKNOWN.value in unserved
        and SectorId.ARRAIJAN_CABECERA.value in unserved
        and SectorId.CHORRERA_BARRIO_COLON.value in assigned
    )
    return ok, f"assigned={assigned} unserved={unserved}"


def _case_alloc_12() -> tuple[bool, str]:
    chino_lat, chino_lon = _coords("VISTA_ALEGRE_CHINO")
    point = _cluster(
        "vista-chino",
        SectorId.ARRAIJAN_VISTA_ALEGRE,
        hours=48,
        affected=60,
        latitude=chino_lat,
        longitude=chino_lon,
        geo_precision=GeoPrecision.POINT,
    )
    sector_wide = _cluster(
        "vista-sector",
        SectorId.ARRAIJAN_VISTA_ALEGRE,
        hours=72,
        affected=200,
        latitude=chino_lat,
        longitude=chino_lon,
        geo_precision=GeoPrecision.SECTOR,
        requires_human_review=True,
    )
    plan = build_plan(
        [point, sector_wide],
        rank_clusters([point, sector_wide]),
    )
    volumes = [item.volume_liters for item in plan.assignments]
    ok = (
        len(plan.assignments) == 1
        and volumes == [900]
        and SectorId.ARRAIJAN_VISTA_ALEGRE.value not in plan.unserved_demand
        and "no se sumó" in plan.explanation
    )
    return ok, f"assignments={volumes} unserved={plan.unserved_demand}"


def _case_alloc_13() -> tuple[bool, str]:
    specs = [
        ("full-a", SectorId.CHORRERA_BARRIO_COLON, "HOSPITAL_NICOLAS_SOLANO"),
        ("full-b", SectorId.ARRAIJAN_BURUNGA, "BURUNGA_CENTRO"),
        ("full-c", SectorId.CHORRERA_GUADALUPE, "GUADALUPE"),
    ]
    clusters = []
    for cluster_id, sector, place in specs:
        lat, lon = _coords(place)
        clusters.append(
            _cluster(
                cluster_id,
                sector,
                hours=48,
                affected=200,
                latitude=lat,
                longitude=lon,
            )
        )
    plan = build_plan(clusters, rank_clusters(clusters))
    ok = len(plan.assignments) == 3 and plan.unserved_demand == []
    return ok, f"assignments={len(plan.assignments)} unserved={plan.unserved_demand}"


def _case_alloc_14() -> tuple[bool, str]:
    high_lat, high_lon = _coords("HOSPITAL_NICOLAS_SOLANO")
    low_lat, low_lon = _coords("EL_COCO")
    high = _cluster(
        "scarce-high",
        SectorId.CHORRERA_BARRIO_COLON,
        hours=96,
        affected=300,
        flags=[VulnerabilityFlag.HOSPITAL_SALUD],
        latitude=high_lat,
        longitude=high_lon,
    )
    low = _cluster(
        "scarce-low",
        SectorId.CHORRERA_EL_COCO,
        hours=12,
        affected=300,
        flags=[VulnerabilityFlag.NINGUNA],
        latitude=low_lat,
        longitude=low_lon,
    )
    fleet = [Truck("cisterna-1", 6_000, 480)]
    scores = rank_clusters([high, low])
    result = solve([high, low], scores, fleet=fleet)
    served = {item.sector_id for item in result.assignments}
    ok = (
        len(result.assignments) == 1
        and SectorId.CHORRERA_BARRIO_COLON in served
        and SectorId.CHORRERA_EL_COCO.value in result.unserved
    )
    return ok, f"served={[s.value for s in served]} unserved={result.unserved}"


def _case_alloc_15() -> tuple[bool, str]:
    chino_lat, chino_lon = _coords("VISTA_ALEGRE_CHINO")
    xtra_lat, xtra_lon = _coords("VISTA_ALEGRE_XTRA")
    chino = _cluster(
        "route-chino",
        SectorId.ARRAIJAN_VISTA_ALEGRE,
        hours=48,
        affected=80,
        latitude=chino_lat,
        longitude=chino_lon,
        geo_precision=GeoPrecision.POINT,
        place_id="VISTA_ALEGRE_CHINO",
    )
    xtra = _cluster(
        "route-xtra",
        SectorId.ARRAIJAN_VISTA_ALEGRE,
        hours=36,
        affected=70,
        latitude=xtra_lat,
        longitude=xtra_lon,
        geo_precision=GeoPrecision.POINT,
        place_id="VISTA_ALEGRE_XTRA",
    )
    plan = build_plan([chino, xtra], rank_clusters([chino, xtra]))
    sector_hits = [a.sector_id for a in plan.assignments]
    ok = (
        len(plan.assignments) == 2
        and sector_hits.count(SectorId.ARRAIJAN_VISTA_ALEGRE) == 2
    )
    return ok, f"assignments={len(plan.assignments)} sectors={sector_hits}"


def _case_alloc_16() -> tuple[bool, str]:
    result = orchestrate(_preload_reports())
    plan = result.plan
    ok = (
        result.requires_human_approval is True
        and "priority-v1" in plan.constraints_satisfied
        and "ortools-routing" in plan.constraints_satisfied
        and len(plan.assignments) >= 6
        and _capacity_ok(plan.assignments)
        and all(item.formula_version == "priority-v1" for item in result.priorities)
    )
    return ok, (
        f"assignments={len(plan.assignments)} "
        f"constraints={plan.constraints_satisfied} "
        f"vehicles={sorted({a.vehicle_id for a in plan.assignments})} "
        f"priorities={len(result.priorities)}"
    )


def _run_case(fn: Callable[[], tuple[bool, str]]) -> tuple[bool, str]:
    try:
        return fn()
    except Exception as exc:
        return False, f"exception: {exc}\n{traceback.format_exc()}"


CASES: tuple[AllocationEvalCase, ...] = (
    AllocationEvalCase("ALLOC-01", "priority_order", "hospital outranks el coco", lambda: _run_case(_case_alloc_01)),
    AllocationEvalCase("ALLOC-02", "priority_order", "vista alegre outranks cerro silvestre", lambda: _run_case(_case_alloc_02)),
    AllocationEvalCase("ALLOC-03", "priority_order", "four-cluster ground-truth order", lambda: _run_case(_case_alloc_03)),
    AllocationEvalCase("ALLOC-04", "priority_order", "tie-break and caps", lambda: _run_case(_case_alloc_04)),
    AllocationEvalCase("ALLOC-05", "volume_invariance", "report_count does not change score", lambda: _run_case(_case_alloc_05)),
    AllocationEvalCase("ALLOC-06", "volume_invariance", "low volume does not outrank need", lambda: _run_case(_case_alloc_06)),
    AllocationEvalCase("ALLOC-07", "volume_invariance", "dedup then hospital ranks first", lambda: _run_case(_case_alloc_07)),
    AllocationEvalCase("ALLOC-08", "volume_invariance", "agent preserves deterministic scores", lambda: _run_case(_case_alloc_08)),
    AllocationEvalCase("ALLOC-09", "constraint_compliance", "vehicle capacity respected", lambda: _run_case(_case_alloc_09)),
    AllocationEvalCase("ALLOC-10", "constraint_compliance", "tight shift leaves stop unserved", lambda: _run_case(_case_alloc_10)),
    AllocationEvalCase("ALLOC-11", "constraint_compliance", "unknown and missing coords unserved", lambda: _run_case(_case_alloc_11)),
    AllocationEvalCase("ALLOC-12", "constraint_compliance", "sector mention withheld when point exists", lambda: _run_case(_case_alloc_12)),
    AllocationEvalCase("ALLOC-13", "demand_coverage", "full coverage when capacity allows", lambda: _run_case(_case_alloc_13)),
    AllocationEvalCase("ALLOC-14", "demand_coverage", "priority-first under scarcity", lambda: _run_case(_case_alloc_14)),
    AllocationEvalCase("ALLOC-15", "demand_coverage", "two vista alegre points routed", lambda: _run_case(_case_alloc_15)),
    AllocationEvalCase("ALLOC-16", "demand_coverage", "preload orchestrator pipeline", lambda: _run_case(_case_alloc_16)),
)


def _ratio(matches: int, total: int) -> float:
    if total == 0:
        return 0.0
    return matches / total


def run_allocation_evals(results_path: Path | None = None) -> dict[str, object]:
    """Run every allocation case in MODO=test and write the metric artifact."""
    runtime = load_runtime_config()
    if runtime.modo != "test":
        raise RuntimeError("allocation evals refuse to run unless MODO=test")

    rows: list[dict[str, object]] = []
    passed_count = 0
    group_pass: dict[str, int] = {
        "priority_order": 0,
        "volume_invariance": 0,
        "constraint_compliance": 0,
        "demand_coverage": 0,
    }
    group_totals: dict[str, int] = {key: 0 for key in group_pass}
    for case in CASES:
        group_totals[case.group] = group_totals.get(case.group, 0) + 1

    for case in CASES:
        passed, detail = case.run()
        passed_count += int(passed)
        group_pass[case.group] += int(passed)
        rows.append(
            {
                "case_id": case.case_id,
                "group": case.group,
                "name": case.name,
                "passed": passed,
                "detail": detail,
            }
        )

    total = len(CASES)
    payload: dict[str, object] = {
        "modo": runtime.modo,
        "case_count": total,
        "group_counts": group_totals,
        "metrics": {
            "case_accuracy": _ratio(passed_count, total),
            "priority_order_accuracy": _ratio(group_pass["priority_order"], group_totals["priority_order"]),
            "volume_invariance_rate": _ratio(group_pass["volume_invariance"], group_totals["volume_invariance"]),
            "constraint_compliance_rate": _ratio(group_pass["constraint_compliance"], group_totals["constraint_compliance"]),
            "demand_coverage_accuracy": _ratio(group_pass["demand_coverage"], group_totals["demand_coverage"]),
        },
        "cases": rows,
    }
    destination = results_path or _RESULTS_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    payload = run_allocation_evals()
    metrics = payload["metrics"]
    print(f"cases={payload['case_count']} modo={payload['modo']}")
    if isinstance(metrics, dict):
        for name, value in metrics.items():
            print(f"{name}={value}")


if __name__ == "__main__":
    main()
