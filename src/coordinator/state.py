"""Plan lifecycle states for the coordinator panel (local until shared contracts)."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from src.contracts import DecisionAction


class PlanState(StrEnum):
    BORRADOR = "BORRADOR"
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    ERROR_PARCIAL = "ERROR_PARCIAL"


TransitionKey = tuple[PlanState, DecisionAction | None, bool]

TRANSITIONS: Final[dict[TransitionKey, PlanState]] = {
    (PlanState.BORRADOR, None, False): PlanState.PENDIENTE,
    (PlanState.PENDIENTE, DecisionAction.APPROVE, False): PlanState.APROBADO,
    (PlanState.PENDIENTE, DecisionAction.REJECT, False): PlanState.RECHAZADO,
        (PlanState.PENDIENTE, DecisionAction.CORRECT, False): PlanState.BORRADOR,
        (PlanState.APROBADO, DecisionAction.REJECT, False): PlanState.RECHAZADO,
    (PlanState.BORRADOR, None, True): PlanState.ERROR_PARCIAL,
    (PlanState.PENDIENTE, None, True): PlanState.ERROR_PARCIAL,
}


def transition(
    current: PlanState,
    action: DecisionAction | None,
    *,
    failed: bool = False,
) -> PlanState:
    if failed:
        key: TransitionKey = (current, None, True)
        if key in TRANSITIONS:
            return TRANSITIONS[key]
        raise ValueError(f"cannot enter ERROR_PARCIAL from {current}")

    key = (current, action, False)
    if key not in TRANSITIONS:
        if current in (PlanState.APROBADO, PlanState.RECHAZADO, PlanState.ERROR_PARCIAL):
            raise ValueError(f"illegal transition from terminal state {current}")
        raise ValueError(f"illegal transition from {current} with action {action}")

    return TRANSITIONS[key]
