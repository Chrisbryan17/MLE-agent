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
import bbeh_temporal_sequence_exact_v2 as temporal
import bbeh_web_of_lies_exact_v7 as web
import bbeh_word_sorting_exact_v5 as word

ROOT = pathlib.Path(os.environ.get('BBEH_TASK_ROOT', '.external/bbeh/bbeh/benchmark_tasks'))
OUT = pathlib.Path('artifacts/exact_closeout_v4')

SOLVERS = {
    'bbeh_boolean_expressions': core.solve_boolean_expressions,
    'bbeh_dyck_languages': core.solve_dyck_languages,
    'bbeh_hyperbaton': adaptive.solve_hyperbaton,
    'bbeh_multistep_arithmetic': multistep.solve,
    'bbeh_object_counting': adaptive.solve_object_counting,
    'bbeh_shuffled_objects': shuffled.solve,
    'bbeh_web_of_lies': web.solve,
    'bbeh_word_sorting': word.solve,
    'bbeh_spatial_reasoning': spatial.solve,
    'bbeh_temporal_sequence': temporal.solve,
}

MODULES = (
    'bbeh_exact_robust.py',
    'bbeh_adaptive_exact_v2.py',
    'bbeh_multistep_exact_v4.py',
    'bbeh_shuffled_exact_v3.py',
    'bbeh_spatial_exact.py',
    'bbeh_temporal_sequence_exact_v2.py',
    'bbeh_web_of_lies_exact_v7.py',
    'bbeh_word_sorting_exact_v5.py',
    'bbeh_exact_closeout_v4.py',
)


def percentile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        'protocol': (
            'Post-replication adaptive exact closeout on the pinned public BBEH corpus. '
            'Every official example counts; exceptions and abstentions count wrong. '
            'This is benchmark-development evidence, not a sealed unseen-test estimate.'
        ),
        'pinned_bbeh_commit': '80d12ca916b7158f22293fcf3144f4d3d854d4be',
        'environment': {'python': sys.version, 'platform': platform.platform()},
        'tasks': {},
    }
    all_times = []
    total = correct = 0
    for task, solver in SOLVERS.items():
        task_path = ROOT / task / 'task.json'
        examples = json.loads(task_path.read_text())['examples']
        rows = []
        timings = []
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
            ok = prediction is not None and str(prediction).strip() == str(example['target']).strip()
            rows.append({
                'index': index,
                'prediction': prediction,
                'target': example['target'],
                'correct': bool(ok),
                'latency_seconds': elapsed,
                'error': error,
            })
        task_correct = sum(row['correct'] for row in rows)
        n = len(rows)
        correct += task_correct
        total += n
        report['tasks'][task] = {
            'n': n,
            'correct': task_correct,
            'accuracy': task_correct / n,
            'coverage': sum(row['prediction'] is not None for row in rows) / n,
            'median_ms': statistics.median(timings) * 1000,
            'p95_ms': percentile(timings, 0.95) * 1000,
            'throughput_per_second': n / sum(timings),
            'task_sha256': hashlib.sha256(task_path.read_bytes()).hexdigest(),
            'errors': [row for row in rows if not row['correct']],
        }
        print(task, task_correct, '/', n, flush=True)
    report['aggregate'] = {
        'implemented_tasks': len(SOLVERS),
        'n': total,
        'correct': correct,
        'micro_accuracy': correct / total,
        'macro_accuracy': sum(value['accuracy'] for value in report['tasks'].values()) / len(report['tasks']),
        'coverage': sum(value['coverage'] * value['n'] for value in report['tasks'].values()) / total,
        'median_ms': statistics.median(all_times) * 1000,
        'p95_ms': percentile(all_times, 0.95) * 1000,
        'throughput_per_second': total / sum(all_times),
        'peak_rss_kb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    report['code_sha256'] = {
        name: hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()
        for name in MODULES
    }
    (OUT / 'results.json').write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report['aggregate'], indent=2))


if __name__ == '__main__':
    main()
