from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from . import grid_induction as gi
from .component_select import component_select_programs
from .mechanistic_trace import TraceRecorder
from .marker_recolor import marker_recolor_programs
from .panel_combine import panel_programs
from .region_fill import region_programs


Grid = list[list[int]]
Program = dict[str, Any]
Demo = tuple[Grid, Grid]
Proposal = dict[str, Any]

_FROZEN_CORE_COMMIT = "1d7c489bcdbff755d638b35ad47ce62bd4fe829d"


def _emit(recorder: TraceRecorder | None, event: str, **data: Any) -> None:
    if recorder is not None:
        recorder.emit(event, **data)


def _store(recorder: TraceRecorder | None, value: Any) -> str | None:
    return recorder.store(value) if recorder is not None else None


def _shape(grid: Grid) -> list[int]:
    return [len(grid), len(grid[0])]


def _difference_coordinates(output: Grid, target: Grid) -> list[list[int]] | None:
    if _shape(output) != _shape(target):
        return None
    return [
        [row, col]
        for row in range(len(target))
        for col in range(len(target[0]))
        if output[row][col] != target[row][col]
    ]


def _dimension_program(demos: Sequence[Demo], kind: str) -> tuple[Program, ...]:
    first_source, first_target = demos[0]
    if len(first_target) % len(first_source) or len(first_target[0]) % len(first_source[0]):
        return ()
    rows = len(first_target) // len(first_source)
    cols = len(first_target[0]) // len(first_source[0])
    if rows < 1 or cols < 1:
        return ()
    return ({"kind": kind, "rows": rows, "cols": cols},)


def _component_rank_programs(demos: Sequence[Demo]) -> tuple[Program, ...]:
    common_backgrounds = set(cell for row in demos[0][0] for cell in row)
    for source, _ in demos[1:]:
        common_backgrounds.intersection_update(cell for row in source for cell in row)
    programs: list[Program] = []
    for background in sorted(common_backgrounds):
        for mode in ("rank", "extreme"):
            program = gi._component_rank_program(demos, background, mode)
            if program is not None:
                programs.append(program)
    return tuple(programs)


def _generator_batches(demos: Sequence[Demo]) -> tuple[tuple[str, tuple[Program, ...], str | None], ...]:
    fixed: tuple[Program, ...] = (
        {"kind": "identity"},
        {"kind": "rotate", "turns": 1},
        {"kind": "rotate", "turns": 2},
        {"kind": "rotate", "turns": 3},
        {"kind": "reflect", "axis": "columns"},
        {"kind": "reflect", "axis": "rows"},
        {"kind": "reflect", "axis": "main"},
        {"kind": "reflect", "axis": "anti"},
    )
    mapped = gi._color_map(demos)
    color_programs = (mapped,) if mapped is not None else ()
    crop_programs = tuple(
        {"kind": "crop", "background": background}
        for background in sorted({cell for source, _ in demos for row in source for cell in row})
    )
    panel, panel_reason = panel_programs(demos)
    region, region_reason = region_programs(demos)
    component_select, component_reason = component_select_programs(demos)
    marker_recolor, marker_reason = marker_recolor_programs(demos)
    return (
        ("fixed", fixed, None),
        ("color_map", color_programs, None if color_programs else "NO_CONSISTENT_COLOR_MAP"),
        ("scale", _dimension_program(demos, "scale"), "NO_INTEGER_DIMENSION_RATIO"),
        ("tile", _dimension_program(demos, "tile"), "NO_INTEGER_DIMENSION_RATIO"),
        ("crop", crop_programs, None if crop_programs else "NO_SOURCE_COLOR"),
        (
            "component_rank",
            _component_rank_programs(demos),
            None if _component_rank_programs(demos) else "NO_DERIVED_COMPONENT_RANK_PROGRAM",
        ),
        ("marker_recolor", marker_recolor, marker_reason),
        ("panel", panel, panel_reason),
        ("region", region, region_reason),
        ("component_select", component_select, component_reason),
    )


def _proposals(demos: Sequence[Demo], recorder: TraceRecorder | None) -> tuple[Proposal, ...]:
    proposals: list[Proposal] = []
    for generator, programs, reason in _generator_batches(demos):
        _emit(recorder, "generator_start", generator=generator)
        if not programs:
            _emit(recorder, "generator_skip", generator=generator, reason=reason or "NO_PROGRAM")
            continue
        for ordinal, program in enumerate(programs):
            candidate_id = f"{generator}:{ordinal:04d}"
            program_digest = gi._digest(program)
            program_ref = _store(recorder, program)
            if program_ref is not None and program_ref != program_digest:
                raise ValueError("program object digest mismatch")
            proposal: Proposal = {
                "candidate_id": candidate_id,
                "generator": generator,
                "program": program,
                "program_digest": program_digest,
            }
            proposals.append(proposal)
            _emit(
                recorder,
                "candidate_proposed",
                candidate_id=candidate_id,
                generator=generator,
                generator_ordinal=ordinal,
                candidate_kind=str(program["kind"]),
                program_digest=program_digest,
                program_ref=program_ref,
            )
        _emit(recorder, "generator_end", generator=generator, candidate_count=len(programs))
    return tuple(proposals)


def _fit_proposals(
    proposals: Sequence[Proposal],
    demos: Sequence[Demo],
    recorder: TraceRecorder | None,
) -> tuple[Proposal, ...]:
    fitting: list[Proposal] = []
    for proposal in proposals:
        execution_failed = False
        mismatch = False
        for demo_index, (source, target) in enumerate(demos):
            source_ref = _store(recorder, source)
            target_ref = _store(recorder, target)
            try:
                output = gi._apply(proposal["program"], source)
            except (KeyError, TypeError, ValueError) as exc:
                execution_failed = True
                _emit(
                    recorder,
                    "demo_execution",
                    candidate_id=proposal["candidate_id"],
                    candidate_kind=str(proposal["program"]["kind"]),
                    demo_index=demo_index,
                    outcome="FAILED",
                    source_ref=source_ref,
                    target_ref=target_ref,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                )
                continue
            matches = output == target
            mismatch = mismatch or not matches
            _emit(
                recorder,
                "demo_execution",
                candidate_id=proposal["candidate_id"],
                candidate_kind=str(proposal["program"]["kind"]),
                demo_index=demo_index,
                outcome="MATCH" if matches else "MISMATCH",
                source_ref=source_ref,
                target_ref=target_ref,
                output_ref=_store(recorder, output),
                source_shape=_shape(source),
                target_shape=_shape(target),
                output_shape=_shape(output),
                difference_coordinates=[] if matches else _difference_coordinates(output, target),
            )
        if execution_failed:
            decision = "DEMO_EXECUTION_FAILED"
        elif mismatch:
            decision = "DEMO_MISMATCH"
        else:
            decision = "FITS_ALL_DEMOS"
            fitting.append(proposal)
        _emit(
            recorder,
            "candidate_fit_decision",
            candidate_id=proposal["candidate_id"],
            candidate_kind=str(proposal["program"]["kind"]),
            decision=decision,
        )
    return tuple(fitting)


def _deduplicate(
    fitting: Sequence[Proposal],
    recorder: TraceRecorder | None,
) -> tuple[Proposal, ...]:
    by_digest: dict[str, Proposal] = {}
    for proposal in fitting:
        digest = str(proposal["program_digest"])
        if digest in by_digest:
            _emit(
                recorder,
                "candidate_duplicate",
                candidate_id=proposal["candidate_id"],
                representative_id=by_digest[digest]["candidate_id"],
                program_digest=digest,
            )
        else:
            by_digest[digest] = proposal
    return tuple(by_digest[digest] for digest in sorted(by_digest))


def _execute_hidden(
    representatives: Sequence[Proposal],
    hidden: Sequence[Grid],
    recorder: TraceRecorder | None,
) -> dict[bytes, tuple[tuple[Grid, ...], list[Proposal], str]]:
    batches: dict[bytes, tuple[tuple[Grid, ...], list[Proposal], str]] = {}
    for proposal in representatives:
        outputs: list[Grid] = []
        failed = False
        for hidden_index, value in enumerate(hidden):
            input_ref = _store(recorder, value)
            try:
                output = gi._apply(proposal["program"], value)
            except (KeyError, TypeError, ValueError) as exc:
                failed = True
                _emit(
                    recorder,
                    "hidden_execution",
                    candidate_id=proposal["candidate_id"],
                    candidate_kind=str(proposal["program"]["kind"]),
                    hidden_index=hidden_index,
                    outcome="FAILED",
                    input_ref=input_ref,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                )
                continue
            outputs.append(output)
            _emit(
                recorder,
                "hidden_execution",
                candidate_id=proposal["candidate_id"],
                candidate_kind=str(proposal["program"]["kind"]),
                hidden_index=hidden_index,
                outcome="SUCCEEDED",
                input_ref=input_ref,
                output_ref=_store(recorder, output),
                output_shape=_shape(output),
            )
        if failed:
            _emit(
                recorder,
                "hidden_batch_decision",
                candidate_id=proposal["candidate_id"],
                candidate_kind=str(proposal["program"]["kind"]),
                decision="FAILED",
            )
            continue
        output_batch = tuple(outputs)
        key = gi._canonical(output_batch)
        batch_ref = _store(recorder, output_batch) or gi._digest(output_batch)
        _emit(
            recorder,
            "hidden_batch_decision",
            candidate_id=proposal["candidate_id"],
            candidate_kind=str(proposal["program"]["kind"]),
            decision="COMPLETED",
            batch_ref=batch_ref,
        )
        if key not in batches:
            batches[key] = (output_batch, [], batch_ref)
        batches[key][1].append(proposal)

    for _, (_, members, batch_ref) in sorted(batches.items(), key=lambda item: item[0]):
        _emit(
            recorder,
            "equivalence_class",
            batch_ref=batch_ref,
            candidate_ids=[item["candidate_id"] for item in members],
            candidate_kinds=sorted({str(item["program"]["kind"]) for item in members}),
        )
    return batches


def _finish(
    result: dict[str, Any],
    status: str,
    recorder: TraceRecorder | None,
    candidate_ids: Sequence[str],
    **data: Any,
) -> dict[str, Any]:
    if recorder is None:
        return result
    recorder.emit(
        "final_decision",
        status=status,
        candidate_ids=list(candidate_ids),
        program_digest=result.get("program_digest"),
        freeze_digest=result.get("freeze_digest"),
        prediction_digest=result.get("prediction_digest"),
        **data,
    )
    traced = dict(result)
    traced["mechanistic_trace"] = recorder.seal(status)
    return traced


def run_grid_task(task: Any, *, mechanistic: bool) -> dict[str, Any]:
    task_id = str(gi._get(task, "task_id"))
    demos = tuple(gi._demo_pair(item) for item in tuple(gi._get(task, "demonstrations")))
    hidden = tuple(gi._grid(item) for item in tuple(gi._get(task, "hidden_inputs")))
    recorder = TraceRecorder(task_id) if mechanistic else None
    _emit(
        recorder,
        "run_start",
        version=gi._VERSION,
        demo_count=len(demos),
        hidden_count=len(hidden),
        mode="GRID",
    )

    proposed = _proposals(demos, recorder)
    fitting = _fit_proposals(proposed, demos, recorder)
    representatives = _deduplicate(fitting, recorder)
    programs = tuple(item["program"] for item in representatives)
    if not representatives:
        result = gi._abstain(
            task_id,
            len(hidden),
            "GRAMMAR_EXHAUSTED",
            gi._evidence(programs, 0),
        )
        return _finish(result, "GRAMMAR_EXHAUSTED", recorder, [])

    batches = _execute_hidden(representatives, hidden, recorder)
    evidence = gi._evidence(programs, len(batches))
    if not batches:
        result = gi._abstain(task_id, len(hidden), "EXECUTION_FAILED", evidence)
        return _finish(
            result,
            "EXECUTION_FAILED",
            recorder,
            [item["candidate_id"] for item in representatives],
        )
    completed_ids = [
        item["candidate_id"]
        for _, (_, members, _) in sorted(batches.items(), key=lambda item: item[0])
        for item in members
    ]
    if len(batches) != 1:
        result = gi._abstain(task_id, len(hidden), "AMBIGUOUS_PROGRAM", evidence)
        return _finish(
            result,
            "AMBIGUOUS_PROGRAM",
            recorder,
            completed_ids,
            output_class_count=len(batches),
        )

    outputs, agreeing, batch_ref = next(iter(batches.values()))
    chosen = min(agreeing, key=lambda item: gi._digest(item["program"]))
    program_digest = gi._digest(chosen["program"])
    freeze_digest = gi._digest({"version": gi._VERSION, "program_digest": program_digest})
    predictions = [
        {"status": "ACCEPTED", "prediction": deepcopy(item)}
        for item in outputs
    ]
    result = {
        "task_id": task_id,
        "tier": "V2.2-GRID",
        "program_digest": program_digest,
        "freeze_digest": freeze_digest,
        "prediction_digest": gi._digest(predictions),
        "evidence": evidence,
        "predictions": predictions,
    }
    return _finish(
        result,
        "ACCEPTED",
        recorder,
        [item["candidate_id"] for item in agreeing],
        selected_candidate_id=chosen["candidate_id"],
        output_batch_ref=batch_ref,
    )


def attach_delegate_trace(task: Any, result: Mapping[str, Any]) -> dict[str, Any]:
    task_id = str(gi._get(task, "task_id"))
    demos = tuple(gi._get(task, "demonstrations"))
    hidden = tuple(gi._get(task, "hidden_inputs"))
    recorder = TraceRecorder(task_id)
    recorder.emit(
        "run_start",
        version=gi._VERSION,
        demo_count=len(demos),
        hidden_count=len(hidden),
        mode="DELEGATED",
    )
    recorder.emit(
        "delegate_boundary",
        delegate="research.universal_core.holonomy_v2.blind_adapter.run_public_task_v2",
        visibility="OPAQUE_FROZEN_CORE",
        frozen_core_commit=_FROZEN_CORE_COMMIT,
    )
    recorder.emit(
        "final_decision",
        status="DELEGATED",
        candidate_ids=[],
        program_digest=result.get("program_digest"),
        freeze_digest=result.get("freeze_digest"),
        prediction_digest=result.get("prediction_digest"),
    )
    traced = dict(result)
    traced["mechanistic_trace"] = recorder.seal("DELEGATED")
    return traced
