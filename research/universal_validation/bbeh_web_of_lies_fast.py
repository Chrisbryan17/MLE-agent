#!/usr/bin/env python3
from __future__ import annotations

import z3

import bbeh_exact_robust as core


def z3_satisfiable(constraints, fixed):
    names = sorted(set(fixed) | {name for constraint in constraints for name in constraint.scope})
    variables = {name: z3.Bool('truth_' + str(index)) for index, name in enumerate(names)}
    solver = z3.Solver()
    for name, value in fixed.items():
        solver.add(variables[name] == bool(value))
    for constraint in constraints:
        alternatives = []
        for allowed in constraint.allowed:
            alternatives.append(z3.And([
                variables[name] == bool(value)
                for name, value in zip(constraint.scope, allowed)
            ]))
        solver.add(z3.Or(alternatives) if alternatives else z3.BoolVal(False))
    return solver.check() == z3.sat


core._csp_satisfiable = z3_satisfiable
solve = core.solve_web_of_lies


if __name__ == '__main__':
    raise SystemExit('Import solve(text) from this module.')
