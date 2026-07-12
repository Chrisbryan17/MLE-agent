#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import resource
import statistics
import sys
import time

import bbeh_exact_robust as core
import bbeh_spatial_exact as spatial
import bbeh_temporal_sequence_exact as temporal

SOLVERS = dict(core.SOLVERS)
SOLVERS['bbeh_spatial_reasoning'] = spatial.solve
SOLVERS['bbeh_temporal_sequence'] = temporal.solve


def percentile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', required=True, choices=sorted(SOLVERS))
    parser.add_argument('--root', default=os.environ.get('BBEH_TASK_ROOT', '.external/bbeh/bbeh/benchmark_tasks'))
    parser.add_argument('--output', default='artifacts/exact_matrix')
    args = parser.parse_args()

    task_path = pathlib.Path(args.root) / args.task / 'task.json'
    examples = json.loads(task_path.read_text())['examples']
    solver = SOLVERS[args.task]
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
        correct = prediction is not None and str(prediction).strip() == str(example['target']).strip()
        rows.append({
            'index': index, 'prediction': prediction, 'target': example['target'],
            'correct': bool(correct), 'latency_seconds': elapsed, 'error': error,
        })
        if (index + 1) % 25 == 0:
            print(args.task, index + 1, '/', len(examples), flush=True)

    correct = sum(row['correct'] for row in rows)
    output = pathlib.Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        'task': args.task,
        'n': len(rows),
        'correct': correct,
        'accuracy': correct / len(rows),
        'coverage': sum(row['prediction'] is not None for row in rows) / len(rows),
        'median_ms': statistics.median(timings) * 1000,
        'p95_ms': percentile(timings, 0.95) * 1000,
        'throughput_per_second': len(rows) / sum(timings),
        'peak_rss_kb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'task_sha256': hashlib.sha256(task_path.read_bytes()).hexdigest(),
        'errors': [row for row in rows if not row['correct']],
    }
    (output / f'{args.task}.json').write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps({key: payload[key] for key in ('task', 'n', 'correct', 'accuracy', 'coverage', 'median_ms', 'p95_ms')}, indent=2))


if __name__ == '__main__':
    main()
