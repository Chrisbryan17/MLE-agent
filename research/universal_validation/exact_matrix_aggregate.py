#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

TASKS = (
    'bbeh_boolean_expressions',
    'bbeh_dyck_languages',
    'bbeh_hyperbaton',
    'bbeh_multistep_arithmetic',
    'bbeh_object_counting',
    'bbeh_shuffled_objects',
    'bbeh_web_of_lies',
    'bbeh_word_sorting',
    'bbeh_spatial_reasoning',
    'bbeh_temporal_sequence',
)


def main():
    source = Path('artifacts/exact_matrix_download')
    output = Path('artifacts/exact_matrix_final')
    output.mkdir(parents=True, exist_ok=True)
    tasks = {}
    for task in TASKS:
        matches = list(source.rglob(f'{task}.json'))
        if len(matches) != 1:
            raise RuntimeError(f'Expected one artifact for {task}, found {matches}')
        tasks[task] = json.loads(matches[0].read_text())
    n = sum(value['n'] for value in tasks.values())
    correct = sum(value['correct'] for value in tasks.values())
    payload = {
        'protocol': 'Independent GitHub-hosted matrix replication. Ten exact cells execute in isolated jobs; every official example counts.',
        'tasks': tasks,
        'aggregate': {
            'implemented_tasks': len(tasks),
            'n': n,
            'correct': correct,
            'micro_accuracy': correct / n,
            'macro_accuracy': sum(value['accuracy'] for value in tasks.values()) / len(tasks),
            'coverage': sum(value['coverage'] * value['n'] for value in tasks.values()) / n,
            'median_of_task_medians_ms': sorted(value['median_ms'] for value in tasks.values())[len(tasks)//2],
            'slowest_task_p95_ms': max(value['p95_ms'] for value in tasks.values()),
        },
        'artifact_sha256': {
            task: hashlib.sha256(next(source.rglob(f'{task}.json')).read_bytes()).hexdigest()
            for task in TASKS
        },
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    if n != 2000:
        raise RuntimeError(f'Expected 2,000 examples, got {n}')
    (output / 'results.json').write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps(payload['aggregate'], indent=2))


if __name__ == '__main__':
    main()
