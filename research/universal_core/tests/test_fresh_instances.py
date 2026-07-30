from __future__ import annotations

import pytest

from universal_core.contracts import FailureStatus
from universal_core.runner import UniversalCoreRunner

from .generators import (
    generate_affine_package,
    generate_filter_count_package,
    generate_graph_package,
    generate_keyword_relation_package,
    generate_ordering_package,
    generate_sort_package,
)


@pytest.mark.parametrize("demonstration_count", [3, 5, 10, 20])
@pytest.mark.parametrize("generator", [
    generate_affine_package,
    generate_sort_package,
    generate_filter_count_package,
    generate_graph_package,
    generate_ordering_package,
])
def test_exact_families_support_variable_demonstration_budgets(
    demonstration_count, generator, tmp_path
) -> None:
    package, targets = generator(
        seed=1000 + demonstration_count,
        demonstration_count=demonstration_count,
        hidden_count=8,
    )
    result = UniversalCoreRunner.default().run(
        package, tmp_path / generator.__name__ / str(demonstration_count)
    )
    assert result.status is FailureStatus.SOLVED
    assert tuple(row.prediction for row in result.predictions) == targets


def test_fixed_release_gates_on_fresh_hidden_rows(tmp_path) -> None:
    exact_generators = (
        generate_affine_package,
        generate_sort_package,
        generate_filter_count_package,
        generate_graph_package,
        generate_ordering_package,
    )
    demo_counts = (3, 5, 10, 20)
    exact_correct = 0
    exact_total = 0
    exact_solved = 0
    for family_index, generator in enumerate(exact_generators):
        for run_index, demonstration_count in enumerate(demo_counts):
            package, targets = generator(
                seed=10_000 + family_index * 100 + run_index,
                demonstration_count=demonstration_count,
                hidden_count=50,
            )
            result = UniversalCoreRunner.default().run(
                package, tmp_path / "exact" / generator.__name__ / str(demonstration_count)
            )
            for row, target in zip(result.predictions, targets):
                exact_total += 1
                exact_solved += row.status is FailureStatus.SOLVED
                exact_correct += row.prediction == target

    semantic_correct = 0
    semantic_total = 0
    semantic_solved = 0
    for run_index, demonstration_count in enumerate((3, 5, 20)):
        package, targets = generate_keyword_relation_package(
            seed=20_000 + run_index,
            demonstration_count=demonstration_count,
            hidden_count=100,
        )
        result = UniversalCoreRunner.default().run(
            package, tmp_path / "semantic" / str(demonstration_count)
        )
        for row, target in zip(result.predictions, targets):
            semantic_total += 1
            semantic_solved += row.status is FailureStatus.SOLVED
            semantic_correct += row.prediction == target

    assert exact_total == 1_000
    assert exact_correct / exact_total >= 0.95
    assert semantic_total == 300
    assert semantic_correct / semantic_total >= 0.80
    assert (exact_solved + semantic_solved) / (exact_total + semantic_total) >= 0.90
