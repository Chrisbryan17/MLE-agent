from __future__ import annotations

import pytest

from universal_core.ir import (
    Capability,
    ConstraintSpec,
    FieldSpec,
    RelationKind,
    RelationSpec,
    TaskSpec,
    ValueType,
)


def test_ir_serialization_is_deterministic() -> None:
    spec = TaskSpec(
        input_type=ValueType.LIST,
        output_type=ValueType.LIST,
        fields=(FieldSpec("record", ValueType.RECORD),),
        capabilities=(Capability.SORT, Capability.PROJECT),
        objective="sort records by numeric field 1 ascending",
        provenance=(2, 0),
    )
    assert spec.digest == spec.digest
    assert spec.to_data()["capabilities"] == ["PROJECT", "SORT"]
    assert spec.to_data()["provenance"] == [2, 0]


def test_ir_rejects_duplicate_field_names() -> None:
    with pytest.raises(ValueError, match="duplicate field"):
        TaskSpec(
            input_type=ValueType.RECORD,
            output_type=ValueType.STRING,
            fields=(FieldSpec("x", ValueType.INTEGER), FieldSpec("x", ValueType.STRING)),
            capabilities=(),
            objective="return x",
        )


def test_ir_serializes_relations_and_constraints() -> None:
    spec = TaskSpec(
        input_type=ValueType.RECORD,
        output_type=ValueType.BOOLEAN,
        relations=(RelationSpec("before", RelationKind.ORDERING, (ValueType.SYMBOL, ValueType.SYMBOL)),),
        constraints=(ConstraintSpec("distinct_positions", {"scope": ["a", "b"]}, provenance=(1,)),),
        capabilities=(Capability.SOLVE_CONSTRAINTS,),
        objective="determine whether a precedes b",
    )
    data = spec.to_data()
    assert data["relations"][0]["kind"] == "ORDERING"
    assert data["constraints"][0]["parameters"] == {"scope": ["a", "b"]}
    assert len(spec.digest) == 64
