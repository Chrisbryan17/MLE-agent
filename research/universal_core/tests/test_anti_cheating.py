from __future__ import annotations

from pathlib import Path

from universal_core.canonical import canonical_json_bytes, sha256_hex
from universal_core.contracts import TaskPackage
from universal_core.runner import UniversalCoreRunner

from .generators import generate_affine_package, generate_sort_package


def test_randomized_task_names_do_not_change_solver_or_predictions(tmp_path) -> None:
    a, targets = generate_sort_package(seed=11, task_name="alpha-private-name", hidden_count=20)
    b, _ = generate_sort_package(seed=11, task_name="completely-different-name", hidden_count=20)
    assert a.package_digest == b.package_digest
    ra = UniversalCoreRunner.default().run(a, tmp_path / "a")
    rb = UniversalCoreRunner.default().run(b, tmp_path / "b")
    assert tuple(row.prediction for row in ra.predictions) == targets
    assert tuple(row.prediction for row in rb.predictions) == targets
    assert ra.solver_digest == rb.solver_digest


def test_demonstration_order_does_not_change_affine_solver(tmp_path) -> None:
    package, targets = generate_affine_package(seed=77, demonstration_count=10, hidden_count=20)
    reordered = TaskPackage(
        package.instructions,
        tuple(reversed(package.demonstrations)),
        package.hidden_inputs,
        package.output_schema,
        {"task_name": "another-name"},
    )
    original_result = UniversalCoreRunner.default().run(package, tmp_path / "original")
    reordered_result = UniversalCoreRunner.default().run(reordered, tmp_path / "reordered")
    assert original_result.solver_digest == reordered_result.solver_digest
    assert tuple(row.prediction for row in reordered_result.predictions) == targets


def test_hidden_input_hashes_are_absent_from_demonstrations() -> None:
    package, _ = generate_sort_package(seed=91, demonstration_count=20, hidden_count=100)
    demonstration_hashes = {
        sha256_hex(canonical_json_bytes(demo.input)) for demo in package.demonstrations
    }
    hidden_hashes = {
        sha256_hex(canonical_json_bytes(row)) for row in package.hidden_inputs
    }
    assert demonstration_hashes.isdisjoint(hidden_hashes)


def test_production_code_has_no_benchmark_routes_or_test_generator_imports() -> None:
    root = Path(__file__).parents[1]
    production = [path for path in root.glob("*.py") if path.name != "__init__.py"]
    forbidden = ("bbeh_", "correction_ledger", "input_hash_answer", "tests.generators")
    for path in production:
        source = path.read_text()
        assert not any(token in source for token in forbidden), (path, forbidden)
