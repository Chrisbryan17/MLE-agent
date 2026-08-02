from dataclasses import dataclass
from typing import Any

from universal_core.holonomy_v2.atoms import derive_atoms


@dataclass(frozen=True)
class Demo:
    input: Any
    output: Any


def test_derives_fields_constants_labels_and_symbols() -> None:
    demos = (
        Demo(
            input=[{"name": "a", "rank": 2}, {"name": "b", "rank": 1}],
            output=["b", "a"],
        ),
    )
    atoms = derive_atoms("Order by rank, then return name.", demos)
    assert ("rank",) in atoms.field_paths
    assert ("name",) in atoms.field_paths
    assert 1 in atoms.constants
    assert 2 in atoms.constants
    assert "a" in atoms.symbols
    assert "b" in atoms.symbols


def test_task_identifier_is_not_retained() -> None:
    demos = (Demo(input={"x": 1}, output=2),)
    atoms = derive_atoms("Return x plus one.", demos, task_id="secret-row-family")
    assert "secret-row-family" not in repr(atoms)


def test_atom_data_is_deterministic() -> None:
    demos = (Demo(input={"b": 2, "a": 1}, output="yes"),)
    left = derive_atoms("Return yes.", demos)
    right = derive_atoms("Return yes.", tuple(reversed(demos)))
    assert left.to_data() == right.to_data()
