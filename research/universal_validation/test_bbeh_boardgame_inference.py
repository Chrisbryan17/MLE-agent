from __future__ import annotations

from bbeh_boardgame_inference import prove
from bbeh_boardgame_ir import Condition, Literal, Rule, Theory


def T(
    facts: set[Literal],
    rules: tuple[Rule, ...],
    query: Literal,
    preferences: set[tuple[str, str]] | None = None,
) -> Theory:
    return Theory(frozenset(facts), rules, frozenset(preferences or set()), query)


def test_direct_positive_fact_is_proved() -> None:
    q = Literal("pigeon", "bring", "woodpecker")
    assert prove(T({q}, (), q)).status == "proved"


def test_opposite_fact_is_disproved() -> None:
    q = Literal("finch", "shout", "mermaid")
    assert prove(T({q.opposite()}, (), q)).status == "disproved"


def test_rule_requires_all_antecedents() -> None:
    a = Literal("pigeon", "take", "gadwall")
    b = Literal("pigeon", "shout", "peafowl", negated=True)
    q = Literal("pigeon", "bring", "woodpecker")
    rule = Rule("Rule2", (Condition(a), Condition(b)), q)
    assert prove(T({a}, (rule,), q)).status == "unknown"


def test_variable_substitution_is_shared_across_antecedents_and_consequent() -> None:
    no_shout = Literal("pigeon", "shout", "peafowl", True)
    take = Literal("pigeon", "take", "gadwall")
    q = Literal("pigeon", "bring", "woodpecker")
    rule = Rule(
        "Rule2",
        (
            Condition(Literal("?x", "shout", "peafowl", True)),
            Condition(Literal("?x", "take", "gadwall")),
        ),
        Literal("?x", "bring", "woodpecker"),
    )
    assert prove(T({no_shout, take}, (rule,), q)).status == "proved"


def test_existential_antecedent_accepts_any_witness() -> None:
    fact = Literal("seal", "destroy", "frog")
    q = Literal("shark", "bring", "cougar", negated=True)
    rule = Rule("Rule5", (Condition(Literal("?x", "destroy", "frog"), existential=True),), q)
    assert prove(T({fact}, (rule,), q)).status == "proved"


def test_preferred_rule_defeats_conflicting_rule_only_when_both_apply() -> None:
    trigger = Literal("duck", "hug", "pigeon")
    positive = Rule("Rule1", (Condition(trigger),), Literal("pigeon", "shout", "peafowl"))
    negative = Rule("Rule8", (Condition(trigger),), Literal("pigeon", "shout", "peafowl", True))
    theory = T({trigger}, (positive, negative), positive.consequent, {("Rule1", "Rule8")})
    result = prove(theory)
    assert result.status == "proved"
    assert result.query_derivations[0].rule_id == "Rule1"


def test_unresolved_conflict_is_unknown() -> None:
    trigger = Literal("duck", "hug", "pigeon")
    q = Literal("pigeon", "shout", "peafowl")
    positive = Rule("Rule1", (Condition(trigger),), q)
    negative = Rule("Rule8", (Condition(trigger),), q.opposite())
    assert prove(T({trigger}, (positive, negative), q)).status == "unknown"


def test_preference_transitive_closure_defeats_indirectly_weaker_rule() -> None:
    trigger = Literal("a", "trigger")
    q = Literal("a", "good")
    r1 = Rule("R1", (Condition(trigger),), q)
    r3 = Rule("R3", (Condition(trigger),), q.opposite())
    prefs = {("R1", "R2"), ("R2", "R3")}
    assert prove(T({trigger}, (r1, r3), q, prefs)).status == "proved"


def test_stronger_rule_does_not_defeat_when_its_antecedent_is_unproved() -> None:
    weak_trigger = Literal("a", "weak")
    strong_trigger = Literal("a", "strong")
    q = Literal("a", "good")
    strong = Rule("R1", (Condition(strong_trigger),), q)
    weak = Rule("R8", (Condition(weak_trigger),), q.opposite())
    assert prove(T({weak_trigger}, (strong, weak), q, {("R1", "R8")})).status == "disproved"


def test_unsupported_cycle_does_not_prove_itself() -> None:
    a = Literal("a", "p")
    b = Literal("b", "q")
    rules = (Rule("R1", (Condition(b),), a), Rule("R2", (Condition(a),), b))
    assert prove(T(set(), rules, a)).status == "unknown"


def test_background_predicate_can_satisfy_opaque_descriptor() -> None:
    fact = Literal("wolf", "has", "a card that is indigo in color")
    needed = Literal("wolf", "has", "a card whose color is one of the rainbow colors")
    q = Literal("wolf", "swim", "goat")
    rule = Rule("R", (Condition(needed),), q)

    def background(required: Literal, facts: frozenset[Literal]) -> bool:
        return required == needed and fact in facts

    assert prove(T({fact}, (rule,), q), background=background).status == "proved"
