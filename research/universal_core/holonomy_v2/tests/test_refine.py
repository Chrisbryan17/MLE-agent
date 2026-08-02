from universal_core.holonomy_v2.loops import LoopKind
from universal_core.holonomy_v2.refine import Counterexample, refine_from_counterexample


def test_failed_state_cycle_requests_context_field() -> None:
    item = Counterexample(
        kind=LoopKind.STATE_CYCLE,
        note="phase changes the same symbol pair",
        details={"context_field": "phase"},
    )
    refinement = refine_from_counterexample(item)
    assert refinement.state_fields == ("phase",)
    assert refinement.reason == "context-dependent transport"
