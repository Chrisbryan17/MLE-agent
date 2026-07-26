from __future__ import annotations

import bbeh_zebra_exact_v3 as zebra


DUPLICATE_HONDA_PUZZLE = """There are 3 people next to each other in a row in positions 1, 2, 3 who have the following characteristics.
Everyone has a different name: Alice, Bob, Cara.
Everyone drives a different car: Honda, Ford, BMW.
Everyone drives a different motorbike: Honda, Yamaha, Ducati.
Using the clues provided below, answer the question at the end.
Some of clues provided might be irrelevant to the puzzle.
Clue 1: Alice is in the first position.
Clue 2: Bob is in the second position.
Clue 3: Cara is in the third position.
Clue 4: The person who drives the Honda is next to Bob.
Question: What position is Bob at?"""


def test_duplicate_surface_forms_are_typed_not_conflated() -> None:
    problem = zebra.parse_problem(DUPLICATE_HONDA_PUZZLE)
    hondas = problem.surface_to_entities["Honda"]
    assert len(hondas) == 2
    assert hondas[0] != hondas[1]
    assert {problem.entity_category[value] for value in hondas} == {
        "car",
        "motorbike",
    }


def test_duplicate_surface_ambiguity_does_not_poison_invariant_query() -> None:
    assert zebra.solve(DUPLICATE_HONDA_PUZZLE) == "2"


def test_eats_context_resolves_duplicate_kiwis_to_fruit() -> None:
    text = """There are 3 people next to each other in a row in positions 1, 2, 3 who have the following characteristics.
Everyone has a different name: Alice, Bob, Cara.
Everyone likes a different fruit: kiwis, pears, apples.
Everyone likes a different favorite animal: kiwis, cats, dogs.
Using the clues provided below, answer the question at the end.
Clue 1: The person who eats kiwis is Alice.
Question: What position is Alice at?"""
    problem = zebra.parse_problem(text)
    choices = zebra.compile_clue_choices(problem.clues[0], problem)
    assert len(choices) == 1
    relation = choices[0]
    kiwi = next(
        value
        for value in relation.values
        if problem.entity_surface.get(value) == "kiwis"
    )
    assert problem.entity_category[kiwi] == "fruit"


def test_ambiguous_duplicate_query_uses_first_declared_type() -> None:
    text = """There are 3 people next to each other in a row in positions 1, 2, 3 who have the following characteristics.
Everyone drives a different car: Honda, Ford, BMW.
Everyone drives a different motorbike: Honda, Yamaha, Ducati.
Using the clues provided below, answer the question at the end.
Clue 1: The person who drives the Ford is in the first position.
Clue 2: The person who drives the BMW is in the second position.
Clue 3: The person who drives the Honda is in the third position.
Question: What position is the person who drives the Honda at?"""
    assert zebra.solve(text) == "3"


def test_repeated_ambiguous_surface_can_resolve_to_distinct_typed_entities() -> None:
    problem = zebra.parse_problem(DUPLICATE_HONDA_PUZZLE)
    choices = zebra.compile_clue_choices(
        "The person who drives the Honda is somewhere to the left of the person who drives the Honda.",
        problem,
    )
    assert any(relation.values[0] != relation.values[1] for relation in choices)


def test_duplicate_query_prefers_first_declared_typed_value() -> None:
    text = """There are 3 people next to each other in a row in positions 1, 2, 3 who have the following characteristics.
Everyone has a different favorite hobby: biking, chess, camping.
Everyone likes a different physical activity: biking, running, skiing.
Using the clues provided below, answer the question at the end.
Clue 1: The person who likes chess is in the first position.
Clue 2: The person who likes camping is in the third position.
Clue 3: The person who likes running is in the first position.
Clue 4: The person who likes skiing is in the second position.
Question: What position is the person who likes biking at?"""
    assert zebra.solve(text) == "2"


def test_minimum_entropy_global_type_resolution_breaks_lexical_tie() -> None:
    text = """There are 3 people next to each other in a row in positions 1, 2, 3 who have the following characteristics.
Everyone has a different name: Alice, Bob, Cara.
Everyone has a different favorite hobby: biking, chess, camping.
Everyone likes a different physical activity: biking, running, skiing.
Using the clues provided below, answer the question at the end.
Clue 1: The person who likes chess is in the second position.
Clue 2: The person who likes camping is in the third position.
Clue 3: The person who likes running is in the second position.
Clue 4: The person who likes biking is Alice.
Question: What position is Alice at?"""
    assert zebra.solve(text) == "1"
