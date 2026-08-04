from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


_TRACE_SCHEMA = "mechanistic-grid-trace-v1"


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _normalized(value: Any) -> Any:
    try:
        return json.loads(_canonical(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise TypeError("trace values must be JSON-safe") from exc


def _content_body(trace: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": trace["schema"],
        "objects": trace["objects"],
        "events": trace["events"],
        "terminal_status": trace["terminal_status"],
    }


def _object_references(value: Any) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str) and key.endswith("_ref"):
                if not isinstance(item, str):
                    raise ValueError("object reference must be a digest string")
                found.append(item)
            else:
                found.extend(_object_references(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_object_references(item))
    return tuple(found)


def _events_named(events: list[Mapping[str, Any]], name: str) -> list[Mapping[str, Any]]:
    return [item for item in events if item.get("event") == name]


def validate_trace(trace: Mapping[str, Any]) -> None:
    if not isinstance(trace, Mapping):
        raise ValueError("trace must be a mapping")
    if trace.get("schema") != _TRACE_SCHEMA:
        raise ValueError("unknown trace schema")
    task_id = trace.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("trace task_id must be non-empty")

    objects = trace.get("objects")
    if not isinstance(objects, Mapping):
        raise ValueError("trace objects must be a mapping")
    for key, value in objects.items():
        if not isinstance(key, str) or _digest(value) != key:
            raise ValueError("trace object digest mismatch")

    events_value = trace.get("events")
    if not isinstance(events_value, list):
        raise ValueError("trace events must be a list")
    events: list[Mapping[str, Any]] = []
    for ordinal, item in enumerate(events_value):
        if not isinstance(item, Mapping):
            raise ValueError("trace event must be a mapping")
        if item.get("ordinal") != ordinal:
            raise ValueError("trace event ordinals must be contiguous")
        if not isinstance(item.get("event"), str) or not item["event"]:
            raise ValueError("trace event name must be non-empty")
        events.append(item)
        for reference in _object_references(item):
            if reference not in objects:
                raise ValueError("unknown object reference")

    if trace.get("event_count") != len(events):
        raise ValueError("trace event count mismatch")

    proposed_events = _events_named(events, "candidate_proposed")
    proposed_ids: list[str] = []
    for item in proposed_events:
        candidate_id = item.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("candidate proposal requires an id")
        if candidate_id in proposed_ids:
            raise ValueError("candidate ids must be unique")
        proposed_ids.append(candidate_id)
    proposed = set(proposed_ids)

    fit_events = _events_named(events, "candidate_fit_decision")
    fit_by_candidate: dict[str, list[Mapping[str, Any]]] = {}
    for item in fit_events:
        candidate_id = item.get("candidate_id")
        if candidate_id not in proposed:
            raise ValueError("fit decision references unknown candidate")
        fit_by_candidate.setdefault(str(candidate_id), []).append(item)
    for candidate_id in proposed_ids:
        if len(fit_by_candidate.get(candidate_id, [])) != 1:
            raise ValueError("candidate requires exactly one terminal demonstration decision")

    duplicate_events = _events_named(events, "candidate_duplicate")
    duplicates: dict[str, str] = {}
    for item in duplicate_events:
        candidate_id = item.get("candidate_id")
        representative_id = item.get("representative_id")
        if candidate_id not in proposed or representative_id not in proposed:
            raise ValueError("duplicate event references unknown candidate")
        if candidate_id == representative_id:
            raise ValueError("duplicate candidate cannot represent itself")
        if candidate_id in duplicates:
            raise ValueError("candidate has multiple duplicate decisions")
        duplicates[str(candidate_id)] = str(representative_id)

    fitting = {
        candidate_id
        for candidate_id, items in fit_by_candidate.items()
        if items[0].get("decision") == "FITS_ALL_DEMOS"
    }
    representatives = fitting - set(duplicates)

    hidden_batch_events = _events_named(events, "hidden_batch_decision")
    hidden_by_candidate: dict[str, list[Mapping[str, Any]]] = {}
    for item in hidden_batch_events:
        candidate_id = item.get("candidate_id")
        if candidate_id not in representatives:
            raise ValueError("hidden-batch decision references non-representative candidate")
        hidden_by_candidate.setdefault(str(candidate_id), []).append(item)
    for candidate_id in sorted(representatives):
        if len(hidden_by_candidate.get(candidate_id, [])) != 1:
            raise ValueError("fitting candidate requires exactly one terminal hidden-batch decision")

    run_starts = _events_named(events, "run_start")
    if len(run_starts) > 1:
        raise ValueError("trace has multiple run-start events")
    if run_starts:
        hidden_count = run_starts[0].get("hidden_count")
        if type(hidden_count) is not int or hidden_count < 0:
            raise ValueError("run-start hidden count must be non-negative")
        hidden_events = _events_named(events, "hidden_execution")
        by_candidate: dict[str, list[Mapping[str, Any]]] = {}
        for item in hidden_events:
            candidate_id = item.get("candidate_id")
            if candidate_id not in representatives:
                raise ValueError("hidden execution references non-representative candidate")
            by_candidate.setdefault(str(candidate_id), []).append(item)
        expected_indices = list(range(hidden_count))
        for candidate_id in sorted(representatives):
            indices = sorted(int(item.get("hidden_index", -1)) for item in by_candidate.get(candidate_id, []))
            if indices != expected_indices:
                raise ValueError("hidden executions do not cover every hidden input")

    completed: dict[str, str] = {}
    for candidate_id, items in hidden_by_candidate.items():
        item = items[0]
        decision = item.get("decision")
        if decision == "COMPLETED":
            batch_ref = item.get("batch_ref")
            if not isinstance(batch_ref, str) or batch_ref not in objects:
                raise ValueError("completed hidden batch requires an object reference")
            completed[candidate_id] = batch_ref
        elif decision != "FAILED":
            raise ValueError("unknown hidden-batch decision")

    class_events = _events_named(events, "equivalence_class")
    memberships: dict[str, list[str]] = {}
    for item in class_events:
        batch_ref = item.get("batch_ref")
        candidate_ids = item.get("candidate_ids")
        if not isinstance(batch_ref, str) or batch_ref not in objects:
            raise ValueError("equivalence class requires a known batch")
        if not isinstance(candidate_ids, list) or not candidate_ids:
            raise ValueError("equivalence class requires candidate ids")
        for candidate_id in candidate_ids:
            if candidate_id not in completed:
                raise ValueError("equivalence class references incomplete candidate")
            if completed[str(candidate_id)] != batch_ref:
                raise ValueError("equivalence class batch mismatch")
            memberships.setdefault(str(candidate_id), []).append(batch_ref)
    for candidate_id in sorted(completed):
        if memberships.get(candidate_id) != [completed[candidate_id]]:
            raise ValueError("completed candidate requires exactly one equivalence class")

    final_events = _events_named(events, "final_decision")
    if len(final_events) != 1:
        raise ValueError("trace requires exactly one final decision")
    final = final_events[0]
    terminal_status = trace.get("terminal_status")
    if not isinstance(terminal_status, str) or final.get("status") != terminal_status:
        raise ValueError("trace terminal status mismatch")
    final_candidates = final.get("candidate_ids", [])
    if not isinstance(final_candidates, list) or any(item not in proposed for item in final_candidates):
        raise ValueError("final decision references unknown candidate")

    expected_trace_digest = _digest(_content_body(trace))
    if trace.get("trace_digest") != expected_trace_digest:
        raise ValueError("trace digest mismatch")
    expected_envelope = _digest({"task_id": task_id, "trace_digest": expected_trace_digest})
    if trace.get("envelope_digest") != expected_envelope:
        raise ValueError("trace envelope digest mismatch")


class TraceRecorder:
    def __init__(self, task_id: str) -> None:
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("trace task_id must be non-empty")
        self._task_id = task_id
        self._objects: dict[str, Any] = {}
        self._object_bytes: dict[str, bytes] = {}
        self._events: list[dict[str, Any]] = []

    def store(self, value: Any) -> str:
        normalized = _normalized(value)
        encoded = _canonical(normalized)
        digest = hashlib.sha256(encoded).hexdigest()
        if digest in self._object_bytes and self._object_bytes[digest] != encoded:
            raise ValueError("trace object digest collision")
        self._object_bytes[digest] = encoded
        self._objects.setdefault(digest, normalized)
        return digest

    def emit(self, event: str, **data: Any) -> None:
        if not isinstance(event, str) or not event:
            raise ValueError("trace event name must be non-empty")
        if "ordinal" in data or "event" in data:
            raise ValueError("trace event data contains reserved key")
        item = _normalized({
            "ordinal": len(self._events),
            "event": event,
            **data,
        })
        self._events.append(item)

    def seal(self, terminal_status: str) -> dict[str, Any]:
        if not isinstance(terminal_status, str) or not terminal_status:
            raise ValueError("terminal status must be non-empty")
        trace: dict[str, Any] = {
            "schema": _TRACE_SCHEMA,
            "task_id": self._task_id,
            "objects": {key: self._objects[key] for key in sorted(self._objects)},
            "events": deepcopy(self._events),
            "event_count": len(self._events),
            "terminal_status": terminal_status,
        }
        trace["trace_digest"] = _digest(_content_body(trace))
        trace["envelope_digest"] = _digest({
            "task_id": self._task_id,
            "trace_digest": trace["trace_digest"],
        })
        validate_trace(trace)
        return trace


def write_trace(trace: Mapping[str, Any], path: Path | str) -> Path:
    validate_trace(trace)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical(trace))
    return output
