from __future__ import annotations

from sagt_agent.domain.runtime import FlowState, Phase

_PHASE_ORDER = {
    Phase.INIT: 1,
    Phase.PLANNING: 2,
    Phase.GENERATING: 3,
    Phase.COMPLETE: 4,
}


def can_transition_phase(from_phase: str, to_phase: str) -> bool:
    if not to_phase:
        return False
    if not from_phase or from_phase == to_phase:
        return True
    if from_phase not in _PHASE_ORDER or to_phase not in _PHASE_ORDER:
        return False
    return _PHASE_ORDER[to_phase] >= _PHASE_ORDER[from_phase]


def validate_phase_transition(from_phase: str, to_phase: str) -> None:
    if not can_transition_phase(from_phase, to_phase):
        raise ValueError(f'invalid phase transition: "{from_phase}" -> "{to_phase}"')


def can_transition_flow(from_flow: str, to_flow: str) -> bool:
    if not to_flow:
        return False
    if not from_flow or from_flow == to_flow:
        return True
    if from_flow == FlowState.GENERATING:
        return to_flow in {FlowState.REVIEWING, FlowState.REVISING, FlowState.STEERING}
    if from_flow == FlowState.REVIEWING:
        return to_flow in {FlowState.GENERATING, FlowState.REVISING, FlowState.STEERING}
    if from_flow == FlowState.REVISING:
        return to_flow in {FlowState.GENERATING, FlowState.STEERING}
    if from_flow == FlowState.STEERING:
        return to_flow in {FlowState.GENERATING, FlowState.REVIEWING, FlowState.REVISING}
    return False


def validate_flow_transition(from_flow: str, to_flow: str) -> None:
    if not can_transition_flow(from_flow, to_flow):
        raise ValueError(f'invalid flow transition: "{from_flow}" -> "{to_flow}"')
