#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import statistics
import sys
import time
from pathlib import Path

import bbeh_exact_robust as exact

ROOT = Path(os.environ.get('BBEH_ROOT', '.external/bbeh'))
OUT = Path('artifacts/bbeh_exact_replication')


def normalized(value):
    return None if value is None else str(value).strip().lower()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = {}
    latencies = []
    all_rows = []
    started = time.perf_counter()
    for task, solver in exact.SOLVERS.items():
        path = ROOT / 'bbeh' / 'benchmark_tasks' / task / 'task.json'
        examples = json.loads(path.read_text())['examples']
        rows = []
        for index, example in enumerate(examples):
            t0 = time.perf_counter_ns()
            try:
                prediction = solver(example['input'])
                error = None
            except Exception as exc:
                prediction = None
                error = f'{type(exc).__name__}: {exc}'
            elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
            latencies.append(elapsed_ms)
            correct = normalized(prediction) == normalized(example['target'])
            row = {
                'task': task, 'index': index, 'prediction': prediction,
                'target': example['target'], 'correct': bool(correct),
                'latency_ms': elapsed_ms, 'error': error,
            }
            rows.append(row)
            all_rows.append(row)
        correct = sum(row['correct'] for row in rows)
        tasks[task] = {
            'n': len(rows), 'correct': correct,
            'accuracy': correct / len(rows),
            'coverage': sum(row['prediction'] is not None for row in rows) / len(rows),
            'errors': [row for row in rows if not row['correct']],
        }
        print(task, correct, '/', len(rows), flush=True)
    n = len(all_rows)
    total_correct = sum(row['correct'] for row in all_rows)
    payload = {
        'protocol': 'Independent GitHub Actions rerun against pinned BBEH commit.',
        'tasks': tasks,
        'aggregate': {
            'n': n, 'correct': total_correct,
            'micro_accuracy': total_correct / n,
            'macro_accuracy': sum(v['accuracy'] for v in tasks.values()) / len(tasks),
            'coverage': sum(row['prediction'] is not None for row in all_rows) / n,
            'wall_seconds': time.perf_counter() - started,
            'latency_ms_median': statistics.median(latencies),
            'latency_ms_p95': sorted(latencies)[max(0, int(.95 * len(latencies)) - 1)],
            'throughput_per_second': n / max(1e-9, time.perf_counter() - started),
            'peak_rss_kb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        'environment': {
            'python': sys.version, 'platform': platform.platform(),
            'code_sha256': hashlib.sha256(Path('bbeh_exact_robust.py').read_bytes()).hexdigest(),
            'scorer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    }
    (OUT / 'results.json').write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps(payload['aggregate'], indent=2))


if __name__ == '__main__':
    main()
