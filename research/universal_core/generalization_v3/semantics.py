"""Typed/scoped evidence representation and oracle-vs-extracted error accounting.

No uncontrolled natural-language parsing or universal semantic understanding is claimed.
The interface explicitly rejects evidence lacking typed/scope/provenance fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

TYPES = frozenset({"person", "organization", "document", "transaction", "event", "time", "quantity"})
QUANTIFIERS = frozenset({"exists", "forall", "none"})
POLARITIES = frozenset({"positive", "negative"})


@dataclass(frozen=True)
class Fact:
    subject: str
    predicate: str
    object: str
    subject_type: str
    object_type: str
    polarity: str
    quantifier: str
    valid_from: str | None
    valid_until: str | None
    source_id: str
    span_start: int
    span_end: int

    @classmethod
    def from_mapping(cls, data: Mapping[str, object], sources: Mapping[str, str]) -> "Fact":
        missing = set(cls.__dataclass_fields__) - set(data)
        if missing:
            raise ValueError(f"missing evidence fields: {sorted(missing)}")
        if data["subject_type"] not in TYPES or data["object_type"] not in TYPES:
            raise ValueError("unknown semantic type")
        if data["polarity"] not in POLARITIES or data["quantifier"] not in QUANTIFIERS:
            raise ValueError("invalid logical scope")
        source = data["source_id"]
        if source not in sources:
            raise ValueError("missing source provenance")
        start, end = data["span_start"], data["span_end"]
        if type(start) is not int or type(end) is not int or not (0 <= start < end <= len(sources[source])):
            raise ValueError("invalid evidence offsets")
        for key in ("subject", "predicate", "object"):
            if not isinstance(data[key], str) or not data[key].strip():
                raise ValueError(f"invalid {key}")
        for name in ("valid_from", "valid_until"):
            if data[name] is not None and (not isinstance(data[name], str) or not data[name]):
                raise ValueError("invalid temporal boundary")
        if data["valid_from"] is not None and data["valid_until"] is not None and data["valid_from"] > data["valid_until"]:
            raise ValueError("inverted temporal scope")
        return cls(**{name: data[name] for name in cls.__dataclass_fields__})


def evaluate_extraction(oracle: Sequence[Fact], predicted: Sequence[Fact]) -> dict[str, float | int]:
    """Exact fact matching; one semantic mistake invalidates the fact."""
    a, b = set(oracle), set(predicted)
    tp = len(a & b)
    precision = tp / len(b) if b else (1.0 if not a else 0.0)
    recall = tp / len(a) if a else 1.0
    return {"correct": tp, "oracle": len(a), "predicted": len(b), "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "exact_document": int(a == b)}


def evidence_answer(facts: Sequence[Fact], subject: str, predicate: str, object: str, at: str | None = None) -> bool | None:
    """Bounded existential QA; does not collapse universal or negated scopes."""
    relevant = [f for f in facts if f.subject == subject and f.predicate == predicate and f.object == object
                and f.quantifier == "exists" and (at is None or ((f.valid_from is None or f.valid_from <= at)
                                                            and (f.valid_until is None or at <= f.valid_until)))]
    signs = {f.polarity for f in relevant}
    return True if signs == {"positive"} else False if signs == {"negative"} else None
