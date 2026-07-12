#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import itertools
import json
import os
import pathlib
import re

import z3


def capitalized_names(content: str) -> list[str]:
    return [
        name for name in re.findall(r"\b([A-Z][A-Za-z'-]*)\b", content)
        if name.lower() not in {'either', 'all', 'exactly', 'only', 'none'}
    ]


def split_problem(text: str) -> tuple[str, str]:
    marker = 'In this question, assume each person either always tells the truth or always lies.'
    body = text.split(marker, 1)[1].strip()
    query = re.search(r'\b(?:Does the person at|Do [A-Z]|Does [A-Z])', body)
    if not query:
        raise ValueError('query not found')
    return body[:query.start()].strip(), body[query.start():]


def parse(text: str):
    facts_text, query_text = split_problem(text)
    fragments = [
        sentence.strip(' .')
        for sentence in re.split(r'(?<=[.!?])\s*', facts_text)
        if sentence.strip(' .')
    ]
    location_to_name: dict[str, str] = {}
    for sentence in fragments:
        match = re.fullmatch(r"([A-Z][A-Za-z'-]*) is at the (.+)", sentence)
        if match:
            location_to_name[match.group(2).strip()] = match.group(1)

    def entity(source: str) -> str:
        source = source.strip()
        prefix = 'the person at the '
        if source.lower().startswith(prefix):
            location = source[len(prefix):]
            return location_to_name.get(location, 'LOCATION:' + location)
        return source

    raw: list[tuple] = []
    names: set[str] = set(location_to_name.values())
    unparsed: list[str] = []
    for sentence in fragments:
        if re.fullmatch(r"([A-Z][A-Za-z'-]*) is at the (.+)", sentence):
            continue
        if re.search(
            r' thinks their (?:friend is lying|neighbor is telling the truth)| saw a firetruck',
            sentence,
            re.I,
        ):
            continue

        direct_true = re.fullmatch(r'(.+?) tells the truth', sentence, re.I)
        if direct_true and ' says ' not in sentence.lower():
            subject = entity(direct_true.group(1))
            names.add(subject)
            raw.append(('fact', subject, True))
            continue
        direct_false = re.fullmatch(r'(.+?) lies', sentence, re.I)
        if direct_false and ' says ' not in sentence.lower():
            subject = entity(direct_false.group(1))
            names.add(subject)
            raw.append(('fact', subject, False))
            continue

        statement = re.fullmatch(r'(.+?) says (.+)', sentence, re.I)
        if not statement:
            unparsed.append(sentence)
            continue
        speaker = entity(statement.group(1))
        content = statement.group(2).strip()
        lowered = content.lower()
        names.add(speaker)

        cardinal = any((
            re.match(r'exactly one of ', lowered),
            re.match(r'only one of ', lowered),
            re.match(r'exactly two of ', lowered),
            re.match(r'either exactly two of ', lowered),
            re.match(r'either all three of ', lowered),
            re.match(r'either exactly one of ', lowered),
            re.match(r'.+ all tell the truth', lowered),
        ))
        if cardinal:
            people = capitalized_names(content)
            if len(people) != 3:
                unparsed.append(sentence)
                continue
            names.update(people)
            if re.match(r'exactly one of .* tell[s]? the truth', lowered):
                allowed = {1}
            elif re.match(r'only one of .* tell[s]? the truth', lowered):
                allowed = {1}
            elif re.match(r'only one of .* lies', lowered):
                allowed = {2}
            elif re.match(r'exactly two of .* tell[s]? the truth', lowered):
                allowed = {2}
            elif re.match(r'either exactly two of .* tell the truth or none of them', lowered):
                allowed = {0, 2}
            elif re.match(r'either all three of .* tell the truth or only one of them', lowered):
                allowed = {1, 3}
            elif re.match(r'either exactly one of .* tells? the truth,? or all three', lowered):
                allowed = {1, 3}
            elif re.match(r'either all three of .* lie,? or two of them tell the truth', lowered):
                allowed = {0, 2}
            elif re.match(r'.* all tell the truth', lowered):
                allowed = {3}
            else:
                unparsed.append(sentence)
                continue
            raw.append(('cardinality', speaker, tuple(people), allowed))
            continue

        direct_true = re.fullmatch(r'(.+?) tells the truth', content, re.I)
        if direct_true:
            target = entity(direct_true.group(1))
            names.add(target)
            raw.append(('equivalence', speaker, target, True))
            continue
        direct_false = re.fullmatch(r'(.+?) lies', content, re.I)
        if direct_false:
            target = entity(direct_false.group(1))
            names.add(target)
            raw.append(('equivalence', speaker, target, False))
            continue
        unparsed.append(sentence)

    def resolve(name: str) -> str:
        if name.startswith('LOCATION:'):
            return location_to_name.get(name[len('LOCATION:'):], name)
        return name

    names = {resolve(name) for name in names}
    resolved: list[tuple] = []
    for item in raw:
        if item[0] == 'fact':
            resolved.append(('fact', resolve(item[1]), item[2]))
        elif item[0] == 'equivalence':
            resolved.append(('equivalence', resolve(item[1]), resolve(item[2]), item[3]))
        else:
            resolved.append((
                'cardinality', resolve(item[1]), tuple(resolve(name) for name in item[2]), item[3]
            ))

    queries = [
        resolve('LOCATION:' + location)
        for location in re.findall(r'Does the person at the (.+?) tell the truth\?', query_text)
    ]
    if not queries:
        match = re.search(r'Do (.+?) tell the truth\?', query_text)
        if match:
            source = match.group(1).replace(', and ', ',').replace(' and ', ',')
            queries = [item.strip(' ,') for item in source.split(',') if item.strip(' ,')]
    if not queries:
        match = re.search(r'Does ([A-Z][A-Za-z\'-]*) tell the truth\?', query_text)
        if match:
            queries = [match.group(1)]
    return names, resolved, queries, unparsed


def solve(text: str) -> str:
    names, constraints, queries, unparsed = parse(text)
    if unparsed:
        raise ValueError(f'unparsed statements: {unparsed}')
    variables = {
        name: z3.Bool('truth_' + str(index))
        for index, name in enumerate(sorted(names))
    }
    solver = z3.Solver()
    for constraint in constraints:
        if constraint[0] == 'fact':
            solver.add(variables[constraint[1]] == bool(constraint[2]))
        elif constraint[0] == 'equivalence':
            target = variables[constraint[2]] if constraint[3] else z3.Not(variables[constraint[2]])
            solver.add(variables[constraint[1]] == target)
        else:
            count = z3.Sum([z3.If(variables[name], 1, 0) for name in constraint[2]])
            statement = z3.Or([count == value for value in sorted(constraint[3])])
            solver.add(variables[constraint[1]] == statement)

    answers: list[str] = []
    for query in queries:
        if query not in variables:
            answers.append('unknown')
            continue
        solver.push()
        solver.add(variables[query])
        can_be_true = solver.check() == z3.sat
        solver.pop()
        solver.push()
        solver.add(z3.Not(variables[query]))
        can_be_false = solver.check() == z3.sat
        solver.pop()
        if can_be_true and can_be_false:
            answers.append('unknown')
        elif can_be_true:
            answers.append('yes')
        elif can_be_false:
            answers.append('no')
        else:
            answers.append('unknown')
    return ', '.join(answers)


def main() -> None:
    root = pathlib.Path(os.environ.get('BBEH_TASK_ROOT', '.external/bbeh/bbeh/benchmark_tasks'))
    task_path = root / 'bbeh_web_of_lies' / 'task.json'
    examples = json.loads(task_path.read_text())['examples']
    rows = []
    for index, example in enumerate(examples):
        try:
            prediction = solve(example['input'])
            error = None
        except Exception as exc:
            prediction = None
            error = f'{type(exc).__name__}: {exc}'
        rows.append({
            'index': index,
            'prediction': prediction,
            'target': example['target'],
            'correct': prediction == example['target'],
            'error': error,
        })
    correct = sum(row['correct'] for row in rows)
    payload = {
        'protocol': (
            'Post-replication exact controlled-English-to-SAT compiler. Statements are converted '
            'to Boolean equivalences and exact-cardinality constraints; each query is checked under '
            'both truth assignments.'
        ),
        'task': 'bbeh_web_of_lies',
        'n': len(rows),
        'correct': correct,
        'accuracy': correct / len(rows),
        'coverage': sum(row['prediction'] is not None for row in rows) / len(rows),
        'task_sha256': hashlib.sha256(task_path.read_bytes()).hexdigest(),
        'code_sha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
        'errors': [row for row in rows if not row['correct']],
    }
    output = pathlib.Path('artifacts/web_lies_exact_v5')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps({key: payload[key] for key in ('n', 'correct', 'accuracy', 'coverage')}, indent=2))


if __name__ == '__main__':
    main()
