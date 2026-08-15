from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .mechanistic_trace import validate_trace


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


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _increment_nested(
    counts: dict[str, dict[str, int]],
    outer: str,
    inner: str,
) -> None:
    bucket = counts.setdefault(outer, {})
    bucket[inner] = bucket.get(inner, 0) + 1


def _sorted_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {key: int(counts[key]) for key in sorted(counts)}


def _sorted_nested(
    counts: Mapping[str, Mapping[str, int]],
) -> dict[str, dict[str, int]]:
    return {
        outer: _sorted_counts(counts[outer])
        for outer in sorted(counts)
    }


def build_trace_diagnosis(
    traces: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    ordered = sorted(traces, key=lambda item: str(item.get("task_id", "")))
    terminal_status_counts: dict[str, int] = {}
    generator_skip_counts: dict[str, dict[str, int]] = {}
    candidate_fit_counts: dict[str, dict[str, int]] = {}
    hidden_failure_counts: dict[str, dict[str, int]] = {}
    hidden_failure_message_counts: dict[str, dict[str, int]] = {}
    accepted_selected_kind_counts: dict[str, int] = {}
    ambiguous_kind_set_counts: dict[str, int] = {}
    total_event_count = 0

    for trace in ordered:
        validate_trace(trace)
        events_value = trace["events"]
        events = [dict(item) for item in events_value]
        total_event_count += len(events)
        candidate_meta: dict[str, dict[str, str]] = {}
        for event in events:
            if event.get("event") != "candidate_proposed":
                continue
            candidate_id = str(event["candidate_id"])
            candidate_meta[candidate_id] = {
                "generator": str(event.get("generator", "UNKNOWN")),
                "kind": str(event.get("candidate_kind", "UNKNOWN")),
            }

        terminal_status = str(trace["terminal_status"])
        _increment(terminal_status_counts, terminal_status)

        for event in events:
            name = event.get("event")
            if name == "generator_skip":
                _increment_nested(
                    generator_skip_counts,
                    str(event.get("generator", "UNKNOWN")),
                    str(event.get("reason", "UNKNOWN")),
                )
            elif name == "candidate_fit_decision":
                candidate_id = str(event.get("candidate_id", ""))
                generator = candidate_meta.get(candidate_id, {}).get("generator", "UNKNOWN")
                _increment_nested(
                    candidate_fit_counts,
                    generator,
                    str(event.get("decision", "UNKNOWN")),
                )
            elif name == "hidden_execution" and event.get("outcome") == "FAILED":
                candidate_id = str(event.get("candidate_id", ""))
                kind = str(
                    event.get("candidate_kind")
                    or candidate_meta.get(candidate_id, {}).get("kind", "UNKNOWN")
                )
                exception_type = str(event.get("exception_type", "UNKNOWN"))
                exception_message = str(event.get("exception_message", ""))
                _increment_nested(hidden_failure_counts, kind, exception_type)
                _increment_nested(
                    hidden_failure_message_counts,
                    kind,
                    f"{exception_type}:{exception_message}",
                )

        final_events = [
            event for event in events if event.get("event") == "final_decision"
        ]
        final = final_events[0]
        if terminal_status == "ACCEPTED":
            selected = str(final.get("selected_candidate_id", ""))
            kind = candidate_meta.get(selected, {}).get("kind", "UNKNOWN")
            _increment(accepted_selected_kind_counts, kind)
        elif terminal_status == "AMBIGUOUS_PROGRAM":
            kinds = sorted({
                candidate_meta.get(str(candidate_id), {}).get("kind", "UNKNOWN")
                for candidate_id in final.get("candidate_ids", [])
            })
            _increment(ambiguous_kind_set_counts, "+".join(kinds) or "NONE")

    body: dict[str, Any] = {
        "schema_version": 1,
        "trace_count": len(ordered),
        "total_event_count": total_event_count,
        "terminal_status_counts": _sorted_counts(terminal_status_counts),
        "generator_skip_counts": _sorted_nested(generator_skip_counts),
        "candidate_fit_counts": _sorted_nested(candidate_fit_counts),
        "hidden_failure_counts": _sorted_nested(hidden_failure_counts),
        "hidden_failure_message_counts": _sorted_nested(hidden_failure_message_counts),
        "accepted_selected_kind_counts": _sorted_counts(accepted_selected_kind_counts),
        "ambiguous_kind_set_counts": _sorted_counts(ambiguous_kind_set_counts),
    }
    body["diagnosis_digest"] = _digest(body)
    return body


def write_diagnosis(
    diagnosis: Mapping[str, Any],
    path: Path | str,
) -> Path:
    expected = dict(diagnosis)
    digest = expected.pop("diagnosis_digest", None)
    if not isinstance(digest, str) or digest != _digest(expected):
        raise ValueError("diagnosis digest mismatch")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical(diagnosis))
    return output
