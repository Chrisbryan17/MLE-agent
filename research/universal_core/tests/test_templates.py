from __future__ import annotations

from universal_core.induction import HeuristicProposalBackend
from universal_core.templates import TemplateSynthesizer, synthesize_ordering_solver


def test_ordering_template_solves_unseen_entity_names() -> None:
    solver = synthesize_ordering_solver(
        entities=("mira", "noah", "orion"),
        before=(("mira", "orion"), ("noah", "orion")),
        adjacent=(("mira", "noah"),),
    )
    assert solver.run({"query": "last"}) == "orion"
    assert solver.run({"query": "order"}) in (
        ["mira", "noah", "orion"],
        ["noah", "mira", "orion"],
    )


def test_template_synthesizer_compiles_operator_proposal(task_package) -> None:
    proposal = HeuristicProposalBackend().propose(
        task_package.instructions, task_package.demonstrations, task_package.output_schema
    )[0]
    candidate = TemplateSynthesizer().synthesize(proposal)
    assert candidate.run([["q", 8], ["p", 2]]) == [["p", 2], ["q", 8]]
    assert candidate.trust_level == "trusted_operator"
    assert len(candidate.digest) == 64


def test_template_synthesizer_compiles_affine_proposal(affine_package) -> None:
    proposal = next(
        p
        for p in HeuristicProposalBackend().propose(
            affine_package.instructions,
            affine_package.demonstrations,
            affine_package.output_schema,
        )
        if p.program_data.get("template") == "affine"
    )
    candidate = TemplateSynthesizer().synthesize(proposal)
    assert candidate.run(7) == 23
    assert candidate.trust_level == "template"
