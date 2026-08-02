from universal_core.holonomy_v2.fibers import (
    FiberSchema,
    FiberValue,
    Observation,
    TransportSignature,
    schema_distance,
)
from universal_core.holonomy_v2.types import FiberKind


def test_record_schema_ignores_key_order() -> None:
    left = FiberSchema.infer({"b": 2, "a": 1})
    right = FiberSchema.infer({"a": 9, "b": 4})
    assert left == right
    assert left.kind is FiberKind.RECORD
    assert tuple(name for name, _ in left.fields) == ("a", "b")


def test_table_schema_tracks_row_shape() -> None:
    schema = FiberSchema.infer([{"id": "a", "score": 2}, {"id": "b", "score": 5}])
    assert schema.kind is FiberKind.TABLE
    assert schema.item is not None
    assert schema.item.kind is FiberKind.RECORD


def test_graph_schema_requires_edges() -> None:
    schema = FiberSchema.infer({"nodes": ["a", "b"], "edges": [["a", "b"]]})
    assert schema.kind is FiberKind.GRAPH


def test_bool_is_not_integer() -> None:
    assert FiberSchema.infer(True).kind is FiberKind.BOOLEAN
    assert FiberSchema.infer(1).kind is FiberKind.INTEGER


def test_schema_round_trip_and_distance() -> None:
    schema = FiberSchema.infer({"x": [1, 2]})
    assert FiberSchema.from_data(schema.to_data()) == schema
    assert schema_distance(schema, schema) == 0
    assert schema_distance(schema, FiberSchema.infer({"x": ["a"]})) > 0


def test_typed_value_and_observation() -> None:
    inp = FiberValue.of({"x": 1})
    out = FiberValue.of(2)
    item = Observation(3, inp, out)
    assert item.index == 3
    assert item.input.schema.kind is FiberKind.RECORD
    sig = TransportSignature(item.input.schema, item.output.schema)
    assert sig.source == item.input.schema
