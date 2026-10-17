# Flujo de supervisión humana y pipeline completo

AguaJusta Oeste ejecuta el pipeline multiagente **antes** de mostrar el borrador al coordinador. Ningún paso escribe avisos a residentes hasta una decisión humana **`APPROVE`**. Los pesos `priority-v1`, la flota y OR-Tools son parámetros de prototipo (`ASSUMPTION`), no política oficial del IDAAN.

## Pipeline operativo

1. **`orchestrate`** (`src/orchestration/agent.py`) — secuencia determinística tras `POST /api/reports` o flujos equivalentes.
2. **Agente 1 — `ingest_report`** — extracción + guardrails (`src/ingestion/agent.py`, `src/ingestion/guardrails.py`).
3. **`deduplicate_reports`** — geolocalización y Haversine **800 m** (`src/ingestion/deduplicator.py`, `src/ingestion/geolocator.py`).
4. **Agente 2 — `prioritize_clusters`** — contexto cualitativo + **`priority-v1`** vía `score_cluster_tool` (`src/prioritization/agent.py`, `src/priority.py`).
5. **Agente 3 — `plan_assignment`** — **`solve_assignment`** con **OR-Tools** (`src/planner/agent.py`, `src/planner/solver.py`).
6. Plan en estado **`BORRADOR`** → **`submit_for_review`** → **`PENDIENTE`**.
7. **Compuerta humana** — `APPROVE` / `REJECT` / `CORRECT` (`src/coordinator/service.py`).
8. Solo **`APPROVE`**: transacción SQLite (plan + auditoría) + outbox **`SIMULATED`** (`src/communication/outbox.py`).

Entradas de UI: **`/ciudadano`** (reportes ciudadanos) y **`/admin`** (precarga, revisión, mapa, trazas).

```mermaid
flowchart TD
    subgraph UI["Entradas web"]
        CI["/ciudadano"]
        AD["/admin"]
    end

    CI --> ORCH["orchestrate"]
    AD --> ORCH

    ORCH --> A1["Agente 1: ingest_report"]
    A1 --> DED["deduplicate_reports<br/>Haversine 800 m"]
    DED --> A2["Agente 2: prioritize_clusters<br/>priority-v1"]
    A2 --> A3["Agente 3: plan_assignment<br/>OR-Tools"]
    A3 --> BOR["BORRADOR"]

    BOR --> PEND["submit_for_review → PENDIENTE"]
    PEND --> HUM["Coordinador revisa<br/>desglose + rutas + trazas"]
    HUM --> DEC{HumanDecision}

    DEC -->|APPROVE| TX["SQLite BEGIN IMMEDIATE<br/>plan + auditoría"]
    TX --> OB["Outbox SIMULATED"]
    OB --> APR["APROBADO"]

    DEC -->|REJECT| AUD["Solo auditoría<br/>sin outbox"]
    AUD --> REJ["RECHAZADO"]

    DEC -->|CORRECT| BOR2["Correcciones → BORRADOR"]
    BOR2 --> PEND

    style HUM fill:#e8f4fc,stroke:#0366d6
```

## Reglas de la compuerta

| Decisión | Persistencia de plan | Outbox `SIMULATED` | Estado final |
|----------|----------------------|--------------------|--------------|
| `APPROVE` | Sí | Sí (por sector asignado / no atendido) | `APROBADO` |
| `REJECT` | Traza de auditoría | No | `RECHAZADO` |
| `CORRECT` | Actualiza borrador | No (hasta nuevo APPROVE) | `BORRADOR` → reenvío a `PENDIENTE` |

**Invariante:** `dispatches_without_approve = 0` (ver `evals/eval_supervision.py`).

## Qué no hace este flujo

- No envía WhatsApp a números de reportes ciudadanos.
- No consulta averías en tiempo real del IDAAN.
- No trata el volumen de quejas repetidas como factor de prioridad (`report_count` invariante).
