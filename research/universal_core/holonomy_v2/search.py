from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .grammar import TaskGrammar, build_task_grammar
from .loops import build_loops
from .program import Program
from .residuals import ResidualReport, check_residuals
from .types import Abstention, FailureCode, SearchConfig, SearchStats


@dataclass(frozen=True)
class CandidateRecord:
    program: Program
    report: ResidualReport
    replay_error: int

    @property
    def rank(self) -> tuple[int, float]:
        return (self.program.cost, -self.report.optional_score)

    def to_data(self) -> dict[str, Any]:
        return {
            "program": self.program.to_data(),
            "program_digest": self.program.digest,
            "cost": self.program.cost,
            "replay_error": self.replay_error,
            "report": self.report.to_data(),
        }


@dataclass(frozen=True)
class SearchResult:
    program: Program | None
    report: ResidualReport | None
    abstention: Abstention | None
    candidates: tuple[CandidateRecord, ...]
    stats: SearchStats


def _replay_error(program: Program, demonstrations: tuple[Any, ...]) -> int:
    errors = 0
    for item in demonstrations:
        inp = item.input if hasattr(item, "input") else item["input"]
        expected = item.output if hasattr(item, "output") else item["output"]
        try:
            actual = program.run(inp)
        except Exception:
            errors += 1
            continue
        if actual != expected:
            errors += 1
    return errors


def search_candidates(
    instructions: str,
    demonstrations: Iterable[Any],
    config: SearchConfig,
    *,
    grammar: TaskGrammar | None = None,
) -> SearchResult:
    demos = tuple(demonstrations)
    active_grammar = grammar or build_task_grammar(instructions, demos, config)
    stats = SearchStats()
    accepted: list[CandidateRecord] = []
    seen: set[str] = set()
    budget_hit = False

    for program in active_grammar.programs:
        if stats.generated >= config.limits.max_candidates:
            budget_hit = True
            break
        stats.generated += 1
        if program.digest in seen:
            stats.pruned_duplicate += 1
            continue
        seen.add(program.digest)
        replay_error = _replay_error(program, demos)
        stats.evaluated += 1
        report = check_residuals(program, build_loops(program, demos, active_grammar))
        if replay_error or not report.mandatory_pass:
            stats.pruned_loop += 1
            continue
        accepted.append(CandidateRecord(program, report, replay_error))

    if not accepted:
        code = FailureCode.SEARCH_BUDGET_EXCEEDED if budget_hit else FailureCode.GRAMMAR_EXHAUSTED
        return SearchResult(
            program=None,
            report=None,
            abstention=Abstention(code, "no accepted candidate", stats.to_data()),
            candidates=(),
            stats=stats,
        )

    accepted.sort(key=lambda item: (item.rank, item.program.digest))
    best = accepted[0]
    tied = [item for item in accepted if item.rank == best.rank]
    if len(tied) > 1:
        return SearchResult(
            program=None,
            report=None,
            abstention=Abstention(
                FailureCode.AMBIGUOUS_PROGRAM,
                "multiple equal-rank candidates fit all mandatory paths",
                {"candidate_digests": [item.program.digest for item in tied]},
            ),
            candidates=tuple(accepted),
            stats=stats,
        )

    return SearchResult(
        program=best.program,
        report=best.report,
        abstention=None,
        candidates=tuple(accepted),
        stats=stats,
    )
