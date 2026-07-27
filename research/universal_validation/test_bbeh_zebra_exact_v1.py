from __future__ import annotations

import random

import bbeh_zebra_exact_v2 as zebra


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


def test_pure_python_csp_solves_large_grid_without_z3(monkeypatch) -> None:
    monkeypatch.setattr(zebra, "z3", None)
    puzzle = """There are 5 people next to each other in a row in positions 1, 2, 3, 4, 5 who have the following characteristics.
Everyone has a different name: Alice, Bob, Cara, Diego, Eve.
Everyone likes a different color: red, blue, green, black, white.
Using the clues provided below, answer the question at the end.
Clue 1: Alice is the person at the 1st position.
Clue 2: Bob is immediately to the left of Cara.
Clue 3: Cara is the person at the 3rd position.
Clue 4: Diego is next to Eve.
Clue 5: Diego is somewhere to the left of Eve.
Clue 6: The person who likes red is Alice.
Clue 7: The person who likes blue is Bob.
Clue 8: The person who likes green is Cara.
Clue 9: The person who likes black is Diego.
Question: What position is Eve at?"""
    assert zebra.solve(puzzle) == "5"


def test_csp_matches_bruteforce_on_random_small_instances() -> None:
    rng = random.Random(19)
    problem = zebra.Problem(
        size=4,
        categories={
            "name": ("A", "B", "C", "D"),
            "color": ("red", "blue", "green", "black"),
        },
        clues=(),
        question="What position is A at?",
    )
    values = tuple(value for category in problem.categories.values() for value in category)
    relation_kinds = ("equal", "not_equal", "left", "next", "immediate_left")

    for _ in range(80):
        relations: list[zebra.Relation] = []
        for _ in range(rng.randint(2, 8)):
            left, right = rng.sample(values, 2)
            relations.append(zebra.Relation(rng.choice(relation_kinds), (left, right)))
        if rng.random() < 0.7:
            entity = rng.choice(values)
            relations.append(zebra.Relation("position", (entity,), rng.randint(1, 4)))
        if rng.random() < 0.3:
            relations.append(zebra.Relation("end", (rng.choice(values),)))

        assert zebra._solve_csp(problem, relations) == zebra._solve_small(problem, relations)
