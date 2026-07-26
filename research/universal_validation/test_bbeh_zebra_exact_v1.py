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
