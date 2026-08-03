import pytest

from universal_core.holonomy_v2.types import (
    Abstention,
    EngineLimits,
    FailureCode,
    SearchConfig,
)


def test_default_limits_are_bounded() -> None:
    limits = EngineLimits()
    assert limits.max_depth == 6
    assert limits.max_candidates == 50_000
    assert limits.max_steps == 100_000
    assert limits.to_data()["max_depth"] == 6


def test_nonpositive_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        EngineLimits(max_depth=0)


def test_abstention_has_typed_code() -> None:
    item = Abstention(FailureCode.GRAMMAR_EXHAUSTED, "no accepted candidate", {})
    assert item.code is FailureCode.GRAMMAR_EXHAUSTED


def test_search_config_round_trip_data() -> None:
    config = SearchConfig()
    assert config.to_data()["limits"]["max_candidates"] == 50_000
