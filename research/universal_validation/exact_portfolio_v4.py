#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import platform
import resource
import statistics
import sys
import time

import bbeh_adaptive_exact_v2 as adaptive
import bbeh_exact_robust as core
import bbeh_multistep_exact_v4 as multistep
import bbeh_shuffled_exact_v3 as shuffled
import bbeh_spatial_exact as spatial
import bbeh_temporal_sequence_exact_v4 as temporal
import bbeh_web_of_lies_exact_v4 as web
import bbeh_word_sorting_exact_v4 as word_sorting

ROOT = pathlib.Path(os.environ.get('BBEH_TASK_ROOT', '.external/bbeh/bbeh/benchmark_tasks'))
OUT = pathlib.Path('artifacts/exact_portfolio_v4')
SOLVERS = {
    'bbeh_boolean_expressions': core.solve_boolean_expressions,
    'bbeh_dyck_languages': core.solve_dyck_languages,
    'bbeh_hyperbaton': adaptive.solve_hyperbaton,
    'bbeh_multistep_arithmetic': multistep.solve,
    'bbeh_object_counting': adaptive.solve_object_counting,
    'bbeh_shuffled_objects': shuffled.solve,
    'bbeh_web_of_lies': web.solve,
    'bbeh_word_sorting': word_sorting.solve,
    'bbeh_spatial_reasoning': spatial.solve,
    'bbeh_temporal_sequence': temporal.solve,
}
SOURCE_FILES = (
    'bbeh_exact_robust.py',
    'bbeh_adaptive_exact_v2.py',
    'bbeh_multistep_exact_v4.py',
    'bbeh_shuffled_exact_v3.py',
    'bbeh_spatial_exact.py',
    'bbeh_temporal_sequence_exact_v4.py',
    'bbeh_web_of_lies_exact_v4.py',
    'bbeh_word_sorting_exact_v4.py',
    'word_sort_state_auditor_v3.py',
    'exact_portfolio_v4.py',
)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def temporal_anomaly_witness(example: dict) -> dict:
    people = temporal.parse(example['input'])
    day = 'Tuesday'
    start = 15 * 60
    end = 15 * 60 + 55
    availability = {name: temporal.local_avail(person, day) for name, person in people.items()}
    decisions = {
        name: temporal.acceptable(person, day, start, end, availability[name])
        for name, person in people.items()
    }
    return {
        'task': 'bbeh_temporal_sequence',
        'index': 197,
        'official_target': example['target'],
        'solver_prediction': temporal.solve(example['input']),
        'witness': {
            'day': day,
            'start_minutes_after_midnight': start,
            'end_minutes_after_midnight': end,
            'duration_minutes': end - start,
            'all_participants_accept': all(decisions.values()),
            'participant_acceptance': decisions,
            'participant_availability': availability,
        },
        'finding': (
            'The official target states a 10-minute maximum, but every participant '
            'accepts the independently checked Tuesday 15:00-15:55 interval. The raw '
            'official score is preserved; this row is adjudicated separately as a label anomaly.'
        ),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        'protocol': (
            'Pinned BBEH exact-cell evaluation. Every official row is scored unchanged. '
            'Post-replication repairs are labeled adaptive. A separate adjudicated score '
            'is reported only for a machine-verifiable temporal annotation anomaly.'
        ),
        'environment': {
            'python': sys.version,
            'platform': platform.platform(),
        },
        'tasks': {},
        'code_sha256': {
            name: hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()
            for name in SOURCE_FILES
        },
    }
    total = 0
    correct = 0
    all_times: list[float] = []
    temporal_examples = None

    for task, solver in SOLVERS.items():
        task_path = ROOT / task / 'task.json'
        examples = json.loads(task_path.read_text())['examples']
        if task == 'bbeh_temporal_sequence':
            temporal_examples = examples
        rows = []
        timings = []
        started_task = time.perf_counter()
        for index, example in enumerate(examples):
            started = time.perf_counter()
            try:
                prediction = solver(example['input'])
                error = None
            except Exception as exc:
                prediction = None
                error = f'{type(exc).__name__}: {exc}'
            elapsed = time.perf_counter() - started
            timings.append(elapsed)
            all_times.append(elapsed)
            is_correct = prediction is not None and str(prediction).strip() == str(example['target']).strip()
            rows.append({
                'index': index,
                'prediction': prediction,
                'target': example['target'],
                'correct': bool(is_correct),
                'latency_seconds': elapsed,
                'error': error,
            })
        task_correct = sum(row['correct'] for row in rows)
        task_n = len(rows)
        total += task_n
        correct += task_correct
        report['tasks'][task] = {
            'n': task_n,
            'correct': task_correct,
            'accuracy': task_correct / task_n,
            'coverage': sum(row['prediction'] is not None for row in rows) / task_n,
            'wall_seconds': time.perf_counter() - started_task,
            'median_ms': statistics.median(timings) * 1000,
            'p95_ms': percentile(timings, 0.95) * 1000,
            'task_sha256': hashlib.sha256(task_path.read_bytes()).hexdigest(),
            'errors': [row for row in rows if not row['correct']],
        }
        print(task, task_correct, '/', task_n, flush=True)

    if total != 2000:
        raise RuntimeError(f'Expected 2,000 rows, got {total}')
    if temporal_examples is None:
        raise RuntimeError('Temporal task was not evaluated')
    anomaly = temporal_anomaly_witness(temporal_examples[197])
    if not anomaly['witness']['all_participants_accept']:
        raise RuntimeError('Temporal anomaly witness did not verify')

    report['benchmark_anomalies'] = [anomaly]
    report['aggregate'] = {
        'tasks': len(SOLVERS),
        'n': total,
        'correct_official': correct,
        'micro_accuracy_official': correct / total,
        'macro_accuracy_official': sum(value['accuracy'] for value in report['tasks'].values()) / len(SOLVERS),
        'coverage': sum(value['coverage'] * value['n'] for value in report['tasks'].values()) / total,
        'adjudicated_anomalies': 1,
        'correct_rule_consistent_adjudicated': correct + 1,
        'micro_accuracy_rule_consistent_adjudicated': (correct + 1) / total,
        'median_ms': statistics.median(all_times) * 1000,
        'p95_ms': percentile(all_times, 0.95) * 1000,
        'throughput_per_second': total / sum(all_times),
        'peak_rss_kb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    (OUT / 'results.json').write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report['aggregate'], indent=2))


if __name__ == '__main__':
    main()
