#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re

PEOPLE = ('Alice', 'Bob', 'Claire', 'Dave', 'Eve', 'Fred', 'Gertrude')
PERSON_ALT = '|'.join(PEOPLE)


def normalize_value(value: str) -> str:
    return re.sub(r'^(?:a|an|the)\s+', '', value.strip(), flags=re.I)


def solve(text: str) -> str | None:
    intro, remainder = text.split('\n', 1)
    assignments = intro[intro.rfind(':') + 1:].strip().rstrip('.')
    state: dict[str, str] = {}
    for person in PEOPLE:
        match = re.search(
            rf'\b{person}\s+(?:gets|is dancing with|has|is playing)\s+(.+?)'
            rf'(?=,\s+(?:{PERSON_ALT})\b|,\s+and\s+(?:{PERSON_ALT})\b|$)',
            assignments,
        )
        if not match:
            return None
        state[person] = normalize_value(match.group(1))

    narrative, query = re.split(
        r'At the end of (?:the semester|the dance|the game|the match|the event),',
        remainder,
        maxsplit=1,
    )
    actions: dict[str, tuple[str, ...]] = {}
    for clause in re.split(r'\b(?:First|Then|Finally),\s*', narrative):
        clause = clause.strip().rstrip('. ')
        if not clause or clause.startswith(('Throughout', 'As the ')):
            continue
        action_match = re.search(r"\(let's call it Action (\d+)\)", clause)
        action_number = action_match.group(1) if action_match else None
        core = re.sub(r"\s*\(let's call it Action \d+\)", '', clause).strip()

        repeat = re.fullmatch(r'Action (\d+) repeats', core)
        if repeat:
            operation = actions.get(repeat.group(1))
            if operation is None:
                return None
        else:
            swap = re.match(
                rf'({PERSON_ALT}) and ({PERSON_ALT}) '
                r'(?:switch partners|trade positions|swap balls|swap books|swap their gifts)',
                core,
            )
            if swap:
                operation = ('swap', swap.group(1), swap.group(2))
            elif 'discuss something' in core or 'nothing happens' in core:
                operation = ('noop',)
            else:
                return None

        if operation[0] == 'swap':
            _, first, second = operation
            state[first], state[second] = state[second], state[first]
        if action_number:
            actions[action_number] = operation

    query_match = re.match(
        r'\s*([A-Za-z]+)\s+(?:has|is dancing with|is playing)\s*(?:the)?\s*',
        query,
    )
    if not query_match:
        return None
    person = query_match.group(1)
    options = {
        letter: normalize_value(value)
        for letter, value in re.findall(r'\(([A-G])\)\s*(.+)', query)
    }
    answer = next((letter for letter, value in options.items() if value == state[person]), None)
    return f'({answer})' if answer else None


def main() -> None:
    root = pathlib.Path(os.environ.get('BBEH_TASK_ROOT', '.external/bbeh/bbeh/benchmark_tasks'))
    task_path = root / 'bbeh_shuffled_objects' / 'task.json'
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
            'correct': prediction is not None and prediction == example['target'],
            'error': error,
        })
    correct = sum(row['correct'] for row in rows)
    payload = {
        'protocol': (
            'Post-replication adaptive exact cell. Compiles initial assignments, swaps, named action '
            'macros, repeats, discussions, and no-ops into a deterministic permutation state machine.'
        ),
        'task': 'bbeh_shuffled_objects',
        'n': len(rows),
        'correct': correct,
        'accuracy': correct / len(rows),
        'coverage': sum(row['prediction'] is not None for row in rows) / len(rows),
        'task_sha256': hashlib.sha256(task_path.read_bytes()).hexdigest(),
        'code_sha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
        'errors': [row for row in rows if not row['correct']],
    }
    output = pathlib.Path('artifacts/shuffled_exact_v3')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps({key: payload[key] for key in ('n', 'correct', 'accuracy', 'coverage')}, indent=2))


if __name__ == '__main__':
    main()
