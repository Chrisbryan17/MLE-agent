from universal_core.holonomy_v2.instructions import parse_instruction_hints


def test_parses_priority_phase_capacity_and_direction() -> None:
    hints = parse_instruction_hints(
        "After phase two, red overrides blue. Capacity is at most 7. "
        "Order by rank descending and break ties by name ascending."
    )
    assert 7 in hints.numeric_constants
    assert hints.priority_terms == (("red", "blue"),)
    assert hints.order_direction == "descending"
    assert "phase two" in hints.phase_terms
    assert "rank" in hints.field_mentions
    assert "name" in hints.tie_break_fields


def test_parses_token_label_pairs_and_formula() -> None:
    hints = parse_instruction_hints(
        "The token veln means ember, and the token qor means frost. "
        "Return left + 2*right + phase modulo 5."
    )
    assert ("veln", "ember") in hints.label_pairs
    assert ("qor", "frost") in hints.label_pairs
    assert hints.modulus == 5
    assert hints.coefficients["right"] == 2
