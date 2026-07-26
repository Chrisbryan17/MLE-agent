from __future__ import annotations

import random

import bbeh_zebra_exact_v1 as zebra


BASE_PUZZLE = """There are 3 people next to each other in a row in positions 1, 2, 3 who have the following characteristics.
Everyone has a different name: Alice, Bob, Cara.
Everyone likes a different color: red, blue, green.
Using the clues provided below, answer the question at the end.
Some of clues provided might be irrelevant to the puzzle.
Clue 1: Alice is immediately to the left of Bob.
Clue 2: Bob is immediately to the left of Cara.
Clue 3: The person who likes blue is Bob.
Clue 4: The person who likes green is Cara.
Question: What position is Alice at?"""


def test_parse_bbeh_zebra_problem_extracts_grid_clues_and_query() -> None:
    problem = zebra.parse_problem(BASE_PUZZLE)
    assert problem.size == 3
    assert problem.categories["name"] == ("Alice", "Bob", "Cara")
    assert problem.categories["color"] == ("red", "blue", "green")
    assert problem.clues[0] == "Alice is immediately to the left of Bob."
    assert problem.question == "What position is Alice at?"


def test_solve_bbeh_zebra_position_query() -> None:
    assert zebra.solve(BASE_PUZZLE) == "1"


def test_clue_order_is_metamorphic() -> None:
    prefix, tail = BASE_PUZZLE.split("Clue 1:", 1)
    clue_block, question = tail.split("Question:", 1)
    clues = [line.split(":", 1)[1].strip() for line in ("Clue 1:" + clue_block).splitlines() if line.startswith("Clue ")]
    random.Random(7).shuffle(clues)
    shuffled = prefix + "\n".join(f"Clue {i}: {clue}" for i, clue in enumerate(clues, 1)) + "\nQuestion:" + question
    assert zebra.solve(shuffled) == zebra.solve(BASE_PUZZLE) == "1"


def test_irrelevant_but_consistent_clue_does_not_change_answer() -> None:
    augmented = BASE_PUZZLE.replace(
        "Question:",
        "Clue 5: The person who likes red is not Bob.\nQuestion:",
    )
    assert zebra.solve(augmented) == "1"


def test_ambiguous_problem_abstains() -> None:
    ambiguous = """There are 3 people next to each other in a row in positions 1, 2, 3 who have the following characteristics.
Everyone has a different name: Alice, Bob, Cara.
Using the clues provided below, answer the question at the end.
Clue 1: Alice is somewhere to the left of Cara.
Question: What position is Alice at?"""
    assert zebra.solve(ambiguous) is None


def test_compile_position_and_end_variants() -> None:
    values = ("Alice", "Bob", "Cara")
    cases = {
        "Alice is in the second position.": zebra.Relation("position", ("Alice",), 2),
        "Alice is in the 2nd position.": zebra.Relation("position", ("Alice",), 2),
        "Alice is in position 2.": zebra.Relation("position", ("Alice",), 2),
        "Alice is at position 2.": zebra.Relation("position", ("Alice",), 2),
        "Alice is in the last position.": zebra.Relation("last", ("Alice",)),
        "Alice is at the far right.": zebra.Relation("last", ("Alice",)),
        "Alice is at the left end.": zebra.Relation("position", ("Alice",), 1),
        "Alice is at the right end.": zebra.Relation("last", ("Alice",)),
    }
    for clue, expected in cases.items():
        assert zebra.compile_clue(clue, values) == expected


def test_compile_directly_between_variant() -> None:
    relation = zebra.compile_clue(
        "Bob is directly between Alice and Cara.",
        ("Alice", "Bob", "Cara"),
    )
    assert relation == zebra.Relation("between_immediate", ("Bob", "Alice", "Cara"))


def test_unknown_relational_language_fails_closed() -> None:
    try:
        zebra.compile_clue(
            "Alice is two spaces away from Bob.",
            ("Alice", "Bob", "Cara"),
        )
    except ValueError as exc:
        assert "uncompiled clue" in str(exc).lower()
    else:
        raise AssertionError("unknown relation was silently compiled as equality")


def test_fixed_position_entities_compile_and_solve() -> None:
    fixed = """There are 3 people next to each other in a row in positions 1, 2, 3 who have the following characteristics.
Everyone has a different name: Alice, Bob, Cara.
Using the clues provided below, answer the question at the end.
Clue 1: Alice is the person at the 2nd position.
Question: What position is Alice at?"""
    assert zebra.solve(fixed) == "2"


def test_fixed_position_can_be_left_operand() -> None:
    fixed = """There are 3 people next to each other in a row in positions 1, 2, 3 who have the following characteristics.
Everyone has a different name: Alice, Bob, Cara.
Using the clues provided below, answer the question at the end.
Clue 1: The person at the 2nd position is immediately to the left of Alice.
Question: What position is Alice at?"""
    assert zebra.solve(fixed) == "3"
