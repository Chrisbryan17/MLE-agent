#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import statistics
from typing import Any

ROOT = pathlib.Path('artifacts/final_closure')
DOWNLOADS = ROOT / 'downloads'
OUT = ROOT / 'report'


def read_jsons() -> list[tuple[pathlib.Path, dict[str, Any]]]:
    values = []
    for path in sorted(DOWNLOADS.rglob('*.json')):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        if isinstance(data, dict):
            values.append((path, data))
    return values


def task_metrics(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = data.get('tasks')
    if not isinstance(tasks, dict):
        return {}
    result = {}
    for name, value in tasks.items():
        if not isinstance(value, dict):
            continue
        n = value.get('n')
        correct = value.get('correct')
        accuracy = value.get('accuracy')
        if n is None and isinstance(value.get('sol'), dict):
            n = value['sol'].get('n')
            accuracy = value['sol'].get('accuracy')
        if n is None or accuracy is None:
            continue
        n = int(n)
        if correct is None:
            correct = round(float(accuracy) * n)
        result[name] = {
            'n': n, 'correct': int(correct), 'accuracy': float(accuracy),
            'coverage': float(value.get('coverage', 1.0)),
        }
    return result


def classify_artifacts(values: list[tuple[pathlib.Path, dict[str, Any]]]) -> dict[str, list[tuple[pathlib.Path, dict[str, Any]]]]:
    groups = {'exact': [], 'semantic': [], 'residual': [], 'livebench': [], 'documents': [], 'other': []}
    for path, data in values:
        text = str(path).lower() + ' ' + str(data.get('protocol', '')).lower() + ' ' + str(data.get('name', '')).lower()
        if 'livebench' in text and isinstance(data.get('tasks'), dict):
            groups['livebench'].append((path, data))
        elif 'document_end_to_end' in text or ('datasets' in data and 'sample_size_per_domain' in data):
            groups['documents'].append((path, data))
        elif 'residual' in text and isinstance(data.get('tasks'), dict):
            groups['residual'].append((path, data))
        elif 'semantic' in text and isinstance(data.get('tasks'), dict):
            groups['semantic'].append((path, data))
        elif 'exact' in text and isinstance(data.get('tasks'), dict):
            groups['exact'].append((path, data))
        else:
            groups['other'].append((path, data))
    return groups


def choose_latest(items: list[tuple[pathlib.Path, dict[str, Any]]]) -> tuple[pathlib.Path, dict[str, Any]] | None:
    if not items:
        return None
    return sorted(items, key=lambda pair: pair[0].stat().st_mtime)[-1]


def harmonic(values: list[float]) -> float:
    if not values or any(value <= 0 for value in values):
        return 0.0
    return len(values) / sum(1.0 / value for value in values)


def merge_bbeh(groups: dict[str, list[tuple[pathlib.Path, dict[str, Any]]]]) -> dict[str, Any]:
    sources = []
    merged: dict[str, dict[str, Any]] = {}
    conflicts = []
    for group in ('exact', 'semantic', 'residual'):
        selected = choose_latest(groups[group])
        if selected is None:
            continue
        path, data = selected
        metrics = task_metrics(data)
        sources.append({'group': group, 'path': str(path), 'tasks': sorted(metrics)})
        for task, value in metrics.items():
            if task in merged:
                conflicts.append({'task': task, 'kept': merged[task], 'discarded': value, 'source': group})
                continue
            merged[task] = {**value, 'source': group}
    total_n = sum(value['n'] for value in merged.values())
    total_correct = sum(value['correct'] for value in merged.values())
    accuracies = [value['accuracy'] for value in merged.values()]
    return {
        'sources': sources, 'tasks': merged, 'conflicts': conflicts,
        'aggregate': {
            'task_count': len(merged), 'n': total_n, 'correct': total_correct,
            'micro_accuracy': total_correct / total_n if total_n else 0.0,
            'macro_accuracy': statistics.mean(accuracies) if accuracies else 0.0,
            'harmonic_accuracy': harmonic(accuracies),
        },
        'structural_pass': len(merged) == 23 and total_n == 4520,
    }


def compare_exact(groups: dict[str, list[tuple[pathlib.Path, dict[str, Any]]]]) -> dict[str, Any]:
    candidates = groups['exact']
    comparisons = []
    for index, (path_a, data_a) in enumerate(candidates):
        tasks_a = task_metrics(data_a)
        for path_b, data_b in candidates[index + 1:]:
            tasks_b = task_metrics(data_b)
            common = sorted(set(tasks_a) & set(tasks_b))
            same = all(tasks_a[task] == tasks_b[task] for task in common)
            comparisons.append({
                'a': str(path_a), 'b': str(path_b), 'common_tasks': len(common),
                'matching': same,
                'mismatches': [task for task in common if tasks_a[task] != tasks_b[task]],
            })
    full = [item for item in comparisons if item['common_tasks'] >= 8 and item['matching']]
    return {
        'candidate_count': len(candidates), 'comparisons': comparisons,
        'pass': len(candidates) >= 2 and bool(full),
    }


def select_complete_livebench(groups: dict[str, list[tuple[pathlib.Path, dict[str, Any]]]]) -> dict[str, Any]:
    ranked = []
    for path, data in groups['livebench']:
        aggregate = data.get('aggregate', {})
        n = int(aggregate.get('n', 0))
        coverage = float(aggregate.get('coverage', 0.0))
        ranked.append((n, coverage, path, data))
    if not ranked:
        return {'pass': False, 'reason': 'missing'}
    _, _, path, data = sorted(ranked, key=lambda item: (item[0], item[1]))[-1]
    aggregate = data.get('aggregate', {})
    n = int(aggregate.get('n', 0))
    coverage = float(aggregate.get('coverage', 0.0))
    tasks = task_metrics(data)
    return {
        'path': str(path), 'aggregate': aggregate, 'tasks': tasks,
        'pass': n == 200 and coverage == 1.0 and len(tasks) == 3,
    }


def select_documents(groups: dict[str, list[tuple[pathlib.Path, dict[str, Any]]]]) -> dict[str, Any]:
    selected = choose_latest(groups['documents'])
    if selected is None:
        return {'pass': False, 'reason': 'missing'}
    path, data = selected
    datasets = data.get('datasets', {})
    required = {'contract_nli', 'finqa', 'scifact', 'tabfact', 'redocred'}
    sample_counts = {
        name: int(value.get('sample', {}).get('n', 0))
        for name, value in datasets.items() if isinstance(value, dict)
    }
    full_counts = {
        name: int(value.get('full_split_rows', 0))
        for name, value in datasets.items() if isinstance(value, dict)
    }
    return {
        'path': str(path), 'aggregate': data.get('aggregate'),
        'sample_counts': sample_counts, 'full_split_rows': full_counts,
        'pass': set(datasets) == required and all(sample_counts.get(name, 0) == 100 for name in required)
                and all(full_counts.get(name, 0) > 0 for name in required),
    }


def hashes() -> dict[str, str]:
    result = {}
    for path in sorted(DOWNLOADS.rglob('*')):
        if path.is_file():
            result[str(path.relative_to(DOWNLOADS))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    values = read_jsons()
    groups = classify_artifacts(values)
    bbeh = merge_bbeh(groups)
    exact_replication = compare_exact(groups)
    livebench = select_complete_livebench(groups)
    documents = select_documents(groups)
    gates = {
        'livebench_complete': bool(livebench.get('pass')),
        'bbeh_4520_complete': bool(bbeh.get('structural_pass')),
        'documents_complete': bool(documents.get('pass')),
        'exact_replication_complete': bool(exact_replication.get('pass')),
    }
    report = {
        'name': 'World-to-Graph-to-Reasoning Final Validation Closure',
        'gates': gates, 'closed': all(gates.values()),
        'bbeh': bbeh, 'livebench': livebench, 'documents': documents,
        'exact_replication': exact_replication,
        'artifact_hashes': hashes(),
        'artifact_inventory': {
            group: [str(path) for path, _ in items] for group, items in groups.items()
        },
    }
    (OUT / 'FINAL_CLOSURE.json').write_text(json.dumps(report, indent=2, default=str))
    lines = [
        '# Final Validation Closure', '',
        f"**All gates closed:** {report['closed']}", '',
        '| Gate | Status |', '|---|---|',
    ]
    for gate, passed in gates.items():
        lines.append(f"| {gate} | {'PASS' if passed else 'OPEN'} |")
    lines.extend(('', '## BBEH', '', '```json', json.dumps(bbeh.get('aggregate'), indent=2), '```',
                  '', '## LiveBench', '', '```json', json.dumps(livebench.get('aggregate'), indent=2), '```',
                  '', '## Documents', '', '```json', json.dumps(documents.get('aggregate'), indent=2), '```'))
    (OUT / 'FINAL_CLOSURE.md').write_text('\n'.join(lines) + '\n')
    if not report['closed']:
        raise SystemExit('One or more validation gates remain open; inspect FINAL_CLOSURE.json')


if __name__ == '__main__':
    main()
