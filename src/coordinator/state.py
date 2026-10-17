"""Plan lifecycle states for the coordinator panel (local until shared contracts)."""

from __future__ import annotations

from enum import StrEnum

from src.contracts import DecisionAction


class PlanState(StrEnum):
    BORRADOR = "BORRADOR"
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    ERROR_PARCIAL = "ERROR_PARCIAL"


_TERMINAL = frozenset({PlanState.APROBADO, PlanState.RECHAZADO, PlanState.ERROR_PARCIAL})


def transition(
    current: PlanState,
    action: DecisionAction | None,
    *,
    failed: bool = False,
) -> PlanState:
    if failed:
        if current in (PlanState.BORRADOR, PlanState.PENDIENTE):
            return PlanState.ERROR_PARCIAL
        raise ValueError(f"cannot enter ERROR_PARCIAL from {current}")

    if current == PlanState.BORRADOR:
        if action is None:
            return PlanState.PENDIENTE
        raise ValueError(f"illegal transition from {current} with action {action}")

    if current == PlanState.PENDIENTE:
        if action == DecisionAction.APPROVE:
            return PlanState.APROBADO
        if action == DecisionAction.REJECT:
            return PlanState.RECHAZADO
        if action == DecisionAction.CORRECT:
            return PlanState.BORRADOR
        raise ValueError(f"illegal transition from {current} with action {action}")

    if current in _TERMINAL:
        raise ValueError(f"illegal transition from terminal state {current}")

    raise ValueError(f"unknown state {current}")
