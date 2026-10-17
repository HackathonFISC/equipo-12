# Flujo de supervisión humana

El coordinador revisa el borrador del plan (prioridades y rutas con motor de demostración), puede corregir datos, y solo con **APROBAR** se persiste el despacho y se encola la outbox **simulada** (no es WhatsApp ni un canal real). Rechazar deja traza de auditoría sin notificaciones.

```mermaid
flowchart TD
    A[ingest_report] --> B[deduplicate_reports]
    B --> C["PlanEngine<br/>(priority_engine priority-v1, SYNTHETIC_DEMO)"]
    C --> D[plan en estado BORRADOR]
    D --> E[submit_for_review → PENDIENTE]
    E --> F["Paso humano: coordinador revisa el plan"]
    F --> G{HumanDecision}

    G -->|APPROVE| H["Transacción SQLite:<br/>plan + outbox SIMULATED + auditoría"]
    H --> I[APROBADO]

    G -->|REJECT| J["Solo auditoría<br/>(sin outbox)"]
    J --> K[RECHAZADO]

    G -->|CORRECT| L[Correcciones → BORRADOR]
    L --> M[Debe volver a submit_for_review]
    M --> E

    style F fill:#e8f4fc,stroke:#0366d6
```

Ninguna rama escribe en la outbox sin una decisión **APPROVE**. Los pesos de prioridad y el solver mostrados aquí son stub de demostración, no política oficial del IDAAN.
