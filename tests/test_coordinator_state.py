"""PlanState transitions for the coordinator panel."""

from __future__ import annotations

import unittest

from src.contracts import DecisionAction
from src.coordinator.state import TRANSITIONS, PlanState, transition


class PlanStateTransitionTests(unittest.TestCase):
    def test_transition_map_exact_legal_edges(self) -> None:
        expected = {
            (PlanState.BORRADOR, None, False): PlanState.PENDIENTE,
            (PlanState.PENDIENTE, DecisionAction.APPROVE, False): PlanState.APROBADO,
            (PlanState.PENDIENTE, DecisionAction.REJECT, False): PlanState.RECHAZADO,
            (PlanState.PENDIENTE, DecisionAction.CORRECT, False): PlanState.BORRADOR,
            (PlanState.APROBADO, DecisionAction.REJECT, False): PlanState.RECHAZADO,
            (PlanState.BORRADOR, None, True): PlanState.ERROR_PARCIAL,
            (PlanState.PENDIENTE, None, True): PlanState.ERROR_PARCIAL,
        }
        self.assertEqual(TRANSITIONS, expected)

    def test_legal_human_transitions(self) -> None:
        self.assertIs(
            transition(PlanState.BORRADOR, None),
            PlanState.PENDIENTE,
        )
        self.assertIs(
            transition(PlanState.PENDIENTE, DecisionAction.APPROVE),
            PlanState.APROBADO,
        )
        self.assertIs(
            transition(PlanState.PENDIENTE, DecisionAction.REJECT),
            PlanState.RECHAZADO,
        )
        self.assertIs(
            transition(PlanState.PENDIENTE, DecisionAction.CORRECT),
            PlanState.BORRADOR,
        )
        self.assertIs(
            transition(PlanState.APROBADO, DecisionAction.REJECT),
            PlanState.RECHAZADO,
        )

    def test_failure_transitions(self) -> None:
        self.assertIs(
            transition(PlanState.BORRADOR, None, failed=True),
            PlanState.ERROR_PARCIAL,
        )
        self.assertIs(
            transition(PlanState.PENDIENTE, DecisionAction.APPROVE, failed=True),
            PlanState.ERROR_PARCIAL,
        )

    def test_plan_state_members_match_names(self) -> None:
        expected = {
            "BORRADOR",
            "PENDIENTE",
            "APROBADO",
            "RECHAZADO",
            "ERROR_PARCIAL",
        }
        self.assertEqual({m.name for m in PlanState}, expected)
        for member in PlanState:
            self.assertEqual(member.value, member.name)

    def test_illegal_from_borrador(self) -> None:
        for action in DecisionAction:
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    transition(PlanState.BORRADOR, action)

    def test_illegal_from_pendiente_without_action(self) -> None:
        with self.assertRaises(ValueError):
            transition(PlanState.PENDIENTE, None)

    def test_illegal_from_terminal_states(self) -> None:
        terminal = (PlanState.APROBADO, PlanState.RECHAZADO, PlanState.ERROR_PARCIAL)
        cases: list[tuple[PlanState, DecisionAction | None, bool]] = []
        for state in terminal:
            cases.append((state, None, False))
            for action in DecisionAction:
                cases.append((state, action, False))
            cases.append((state, None, True))
        for current, action, failed in cases:
            if current is PlanState.APROBADO and action is DecisionAction.REJECT and not failed:
                continue
            with self.subTest(current=current, action=action, failed=failed):
                with self.assertRaises(ValueError):
                    transition(current, action, failed=failed)


if __name__ == "__main__":
    unittest.main()
