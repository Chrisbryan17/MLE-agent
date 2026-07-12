#!/usr/bin/env python3
"""Independent CLUTRR systematic-generalization evaluation for SOL.

The reasoner learns only a finite binary relation-composition table from the
training split's length-2 paths. It is then frozen and folded over unseen test
paths, including chains up to length 10. Missing compositions are abstentions
and count as wrong.
"""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATASET = 'CLUTRR/v1'
CONFIGS = ('gen_train23_test2to10', 'gen_train234_test2to10')
BASE = 'https://datasets-server.huggingface.co'
PAGE = 100


def api(path, params, retries=5):
    url = BASE + path + '?' + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'SOL-research/0.1'})
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except Exception as exc:
            last = exc
            time.sleep(1.0 * (attempt + 1))
    raise last


def cache_path(config, split):
    return Path('.clutrr_cache') / f'{config}__{split}.jsonl'


def load_split(config, split):
    path = cache_path(config, split)
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        return [json.loads(line) for line in path.read_text().splitlines() if line]

    first = api('/rows', {
        'dataset': DATASET, 'config': config, 'split': split,
        'offset': 0, 'length': PAGE,
    })
    total = int(first['num_rows_total'])
    rows = [item['row'] for item in first['rows']]
    for offset in range(PAGE, total, PAGE):
        page = api('/rows', {
            'dataset': DATASET, 'config': config, 'split': split,
            'offset': offset, 'length': min(PAGE, total - offset),
        })
        rows.extend(item['row'] for item in page['rows'])
    with path.open('w') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')
    return rows


def relations(row):
    value = row['edge_types']
    return tuple(ast.literal_eval(value) if isinstance(value, str) else value)


def learn_table(rows):
    counts = collections.defaultdict(collections.Counter)
    seen_sequences = collections.defaultdict(collections.Counter)
    relation_prior = collections.Counter()
    for row in rows:
        seq = relations(row)
        target = row['target_text']
        relation_prior[target] += 1
        seen_sequences[seq][target] += 1
        if len(seq) == 2:
            counts[(seq[0], seq[1])][target] += 1
    table = {}
    conflicts = {}
    for pair, counter in counts.items():
        winner, _ = counter.most_common(1)[0]
        table[pair] = winner
        if len(counter) > 1:
            conflicts['|'.join(pair)] = dict(counter)
    memorizer = {seq: counter.most_common(1)[0][0] for seq, counter in seen_sequences.items()}
    majority = relation_prior.most_common(1)[0][0]
    return table, memorizer, majority, conflicts, counts


def fold(table, seq):
    if not seq:
        return None, []
    state = seq[0]
    proof = []
    for relation in seq[1:]:
        pair = (state, relation)
        result = table.get(pair)
        proof.append({'left': state, 'right': relation, 'result': result})
        if result is None:
            return None, proof
        state = result
    return state, proof


def stable_random(row, labels):
    digest = hashlib.sha256(row['id'].encode()).digest()
    return labels[int.from_bytes(digest[:8], 'big') % len(labels)]


def evaluate(rows, table, memorizer, majority, labels):
    systems = {
        'sol_fold': [],
        'sequence_memorizer': [],
        'last_edge': [],
        'majority': [],
        'stable_random': [],
    }
    golds = []
    proofs = []
    by_length = collections.defaultdict(lambda: collections.Counter(total=0))
    errors = []

    for row in rows:
        seq = relations(row)
        gold = row['target_text']
        pred, proof = fold(table, seq)
        predictions = {
            'sol_fold': pred,
            'sequence_memorizer': memorizer.get(seq),
            'last_edge': seq[-1] if seq else None,
            'majority': majority,
            'stable_random': stable_random(row, labels),
        }
        golds.append(gold)
        proofs.append(proof)
        length_bucket = by_length[len(seq)]
        length_bucket['total'] += 1
        for name, value in predictions.items():
            systems[name].append(value)
            length_bucket[name + '_correct'] += int(value == gold)
            length_bucket[name + '_covered'] += int(value is not None)
        if pred != gold and len(errors) < 100:
            errors.append({
                'id': row['id'], 'story': row['story'], 'query': row['query'],
                'edge_types': list(seq), 'gold': gold, 'pred': pred, 'proof': proof,
                'task_name': row.get('task_name'),
            })

    metrics = {}
    n = len(rows)
    for name, predictions in systems.items():
        metrics[name] = {
            'accuracy': sum(p == g for p, g in zip(predictions, golds)) / n,
            'coverage': sum(p is not None for p in predictions) / n,
        }
    metrics['by_length'] = {
        str(length): {
            'n': counter['total'],
            **{
                name: {
                    'accuracy': counter[name + '_correct'] / counter['total'],
                    'coverage': counter[name + '_covered'] / counter['total'],
                }
                for name in systems
            },
        }
        for length, counter in sorted(by_length.items())
    }
    return metrics, golds, systems, errors


def paired_bootstrap(golds, system, baseline, samples=10000):
    differences = [
        int(a == gold) - int(b == gold)
        for gold, a, b in zip(golds, system, baseline)
    ]
    rng = random.Random(20260712)
    draws = []
    n = len(differences)
    for _ in range(samples):
        draws.append(sum(differences[rng.randrange(n)] for _ in range(n)) / n)
    draws.sort()
    return {
        'delta': sum(differences) / n,
        'lo': draws[int(0.025 * samples)],
        'hi': draws[int(0.975 * samples)],
    }


def run_config(config):
    train = load_split(config, 'train')
    test = load_split(config, 'test')
    table, memorizer, majority, conflicts, raw_counts = learn_table(train)
    labels = sorted({row['target_text'] for row in train})
    metrics, golds, systems, errors = evaluate(test, table, memorizer, majority, labels)
    paired = paired_bootstrap(golds, systems['sol_fold'], systems['sequence_memorizer'])
    return {
        'dataset': DATASET,
        'config': config,
        'train_rows': len(train),
        'test_rows': len(test),
        'training_protocol': 'binary compositions only from length-2 train paths',
        'binary_training_rows': sum(len(relations(row)) == 2 for row in train),
        'composition_table_size': len(table),
        'composition_conflicts': conflicts,
        'relation_labels': labels,
        'metrics': metrics,
        'paired_vs_sequence_memorizer': paired,
        'errors': errors,
        'table': {'|'.join(pair): result for pair, result in sorted(table.items())},
        'table_counts': {
            '|'.join(pair): dict(counter) for pair, counter in sorted(raw_counts.items())
        },
    }


def main():
    out = Path('artifacts/clutrr_eval')
    out.mkdir(parents=True, exist_ok=True)
    reports = [run_config(config) for config in CONFIGS]
    payload = {
        'name': 'SOL finite kinship relation algebra',
        'leakage_policy': (
            'Only train rows are used to construct the binary table. Test labels are '
            'read solely for final scoring. Missing table entries abstain and count wrong.'
        ),
        'reports': reports,
    }
    (out / 'results.json').write_text(json.dumps(payload, indent=2))

    lines = [
        '# SOL CLUTRR held-out systematic generalization', '',
        '|Config|Train|Test|Binary table|SOL|Coverage|Memorizer|Last edge|',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for report in reports:
        metrics = report['metrics']
        lines.append(
            f"|{report['config']}|{report['train_rows']}|{report['test_rows']}|"
            f"{report['composition_table_size']}|{metrics['sol_fold']['accuracy']:.4f}|"
            f"{metrics['sol_fold']['coverage']:.4f}|"
            f"{metrics['sequence_memorizer']['accuracy']:.4f}|"
            f"{metrics['last_edge']['accuracy']:.4f}|"
        )
    lines += [
        '',
        'The composition table is learned only from length-2 training paths and then frozen.',
        'Test chains extend to length 10; abstentions count as wrong.',
    ]
    (out / 'RESULTS.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({
        report['config']: {
            'sol_accuracy': report['metrics']['sol_fold']['accuracy'],
            'coverage': report['metrics']['sol_fold']['coverage'],
            'memorizer': report['metrics']['sequence_memorizer']['accuracy'],
            'test_rows': report['test_rows'],
        }
        for report in reports
    }, indent=2))


if __name__ == '__main__':
    main()
