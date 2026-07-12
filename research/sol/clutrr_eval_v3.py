#!/usr/bin/env python3
"""SOL partial-algebra chart reasoning on held-out CLUTRR chains.

Key idea: gendered surface kinship labels are not closed or associative under
left-fold composition. We quotient them into latent relation classes, learn the
partial binary law from length-2 train paths only, and use a chart algorithm to
find valid parenthesizations of held-out chains up to length 10.
"""
from __future__ import annotations

import ast
import collections
import json
import random
from pathlib import Path

import clutrr_eval as common
import clutrr_eval_v2 as data  # installs official-Parquet load_split

CONFIGS = common.CONFIGS

ABSTRACT = {
    'son': 'child', 'daughter': 'child',
    'father': 'inv-child', 'mother': 'inv-child',
    'brother': 'sibling', 'sister': 'sibling',
    'husband': 'SO', 'wife': 'SO',
    'grandson': 'grand', 'granddaughter': 'grand',
    'grandfather': 'inv-grand', 'grandmother': 'inv-grand',
    'nephew': 'un', 'niece': 'un',
    'uncle': 'inv-un', 'aunt': 'inv-un',
    'son-in-law': 'in-law', 'daughter-in-law': 'in-law',
    'father-in-law': 'inv-in-law', 'mother-in-law': 'inv-in-law',
}

REALIZE = {
    ('child', 'male'): 'son', ('child', 'female'): 'daughter',
    ('inv-child', 'male'): 'father', ('inv-child', 'female'): 'mother',
    ('sibling', 'male'): 'brother', ('sibling', 'female'): 'sister',
    ('SO', 'male'): 'husband', ('SO', 'female'): 'wife',
    ('grand', 'male'): 'grandson', ('grand', 'female'): 'granddaughter',
    ('inv-grand', 'male'): 'grandfather', ('inv-grand', 'female'): 'grandmother',
    ('un', 'male'): 'nephew', ('un', 'female'): 'niece',
    ('inv-un', 'male'): 'uncle', ('inv-un', 'female'): 'aunt',
    ('in-law', 'male'): 'son-in-law', ('in-law', 'female'): 'daughter-in-law',
    ('inv-in-law', 'male'): 'father-in-law', ('inv-in-law', 'female'): 'mother-in-law',
}


def edge_sequence(row):
    value = row['edge_types']
    return tuple(ast.literal_eval(value) if isinstance(value, str) else value)


def target_gender(row):
    query = ast.literal_eval(row['query']) if isinstance(row['query'], str) else row['query']
    target = query[1]
    genders = {}
    for item in row['genders'].split(','):
        name, gender = item.rsplit(':', 1)
        genders[name.strip()] = gender.strip()
    if target not in genders:
        raise KeyError(f'No gender for query target {target!r}')
    return genders[target]


def learn_abstract_table(rows):
    counts = collections.defaultdict(collections.Counter)
    sequence_memory = collections.defaultdict(collections.Counter)
    prior = collections.Counter()
    for row in rows:
        sequence = edge_sequence(row)
        target = row['target_text']
        prior[target] += 1
        sequence_memory[sequence][target] += 1
        if len(sequence) == 2:
            pair = (ABSTRACT[sequence[0]], ABSTRACT[sequence[1]])
            counts[pair][ABSTRACT[target]] += 1
    table = {}
    conflicts = {}
    for pair, counter in counts.items():
        table[pair] = counter.most_common(1)[0][0]
        if len(counter) > 1:
            conflicts['|'.join(pair)] = dict(counter)
    memorizer = {sequence: counter.most_common(1)[0][0] for sequence, counter in sequence_memory.items()}
    majority = prior.most_common(1)[0][0]
    return table, memorizer, majority, counts, conflicts


def chart_compose(table, surface_sequence, gender):
    states = [ABSTRACT[relation] for relation in surface_sequence]
    n = len(states)
    chart = [[{} for _ in range(n + 1)] for _ in range(n)]
    for i, state in enumerate(states):
        chart[i][i + 1][state] = {'leaf': surface_sequence[i], 'state': state}

    for span in range(2, n + 1):
        for start in range(0, n - span + 1):
            end = start + span
            for split in range(start + 1, end):
                for left, left_proof in chart[start][split].items():
                    for right, right_proof in chart[split][end].items():
                        result = table.get((left, right))
                        if result is not None and result not in chart[start][end]:
                            chart[start][end][result] = {
                                'compose': [left, right], 'result': result,
                                'split': split, 'left': left_proof, 'right': right_proof,
                            }

    candidates = {
        REALIZE[(state, gender)]: proof
        for state, proof in chart[0][n].items()
        if (state, gender) in REALIZE
    }
    if len(candidates) == 1:
        label = next(iter(candidates))
        return label, candidates[label], sorted(chart[0][n])
    return None, {'candidates': sorted(candidates), 'latent_states': sorted(chart[0][n])}, sorted(chart[0][n])


def left_fold(table, surface_sequence, gender):
    if not surface_sequence:
        return None
    state = ABSTRACT[surface_sequence[0]]
    for surface in surface_sequence[1:]:
        state = table.get((state, ABSTRACT[surface]))
        if state is None:
            return None
    return REALIZE.get((state, gender))


def stable_random(row, labels):
    return common.stable_random(row, labels)


def evaluate(rows, table, memorizer, majority, labels):
    names = ('sol_chart', 'left_fold', 'sequence_memorizer', 'last_edge', 'majority', 'stable_random')
    predictions = {name: [] for name in names}
    golds = []
    by_length = collections.defaultdict(lambda: collections.Counter(total=0))
    errors = []
    ambiguous = 0

    for row in rows:
        sequence = edge_sequence(row)
        gender = target_gender(row)
        gold = row['target_text']
        chart_prediction, proof, final_states = chart_compose(table, sequence, gender)
        current = {
            'sol_chart': chart_prediction,
            'left_fold': left_fold(table, sequence, gender),
            'sequence_memorizer': memorizer.get(sequence),
            'last_edge': sequence[-1] if sequence else None,
            'majority': majority,
            'stable_random': stable_random(row, labels),
        }
        ambiguous += int(chart_prediction is None and len(final_states) > 1)
        golds.append(gold)
        bucket = by_length[len(sequence)]
        bucket['total'] += 1
        for name, value in current.items():
            predictions[name].append(value)
            bucket[name + '_correct'] += int(value == gold)
            bucket[name + '_covered'] += int(value is not None)
        if chart_prediction != gold and len(errors) < 200:
            errors.append({
                'id': row['id'], 'story': row['story'], 'query': row['query'],
                'edge_types': list(sequence), 'gender': gender, 'gold': gold,
                'pred': chart_prediction, 'final_states': final_states, 'proof': proof,
                'task_name': row.get('task_name'),
            })

    n = len(rows)
    metrics = {
        name: {
            'accuracy': sum(value == gold for value, gold in zip(values, golds)) / n,
            'coverage': sum(value is not None for value in values) / n,
        }
        for name, values in predictions.items()
    }
    metrics['ambiguous_rate'] = ambiguous / n
    metrics['by_length'] = {
        str(length): {
            'n': counter['total'],
            **{
                name: {
                    'accuracy': counter[name + '_correct'] / counter['total'],
                    'coverage': counter[name + '_covered'] / counter['total'],
                }
                for name in names
            },
        }
        for length, counter in sorted(by_length.items())
    }
    return metrics, golds, predictions, errors


def paired_bootstrap(golds, system, baseline, samples=10000):
    differences = [
        int(a == gold) - int(b == gold)
        for gold, a, b in zip(golds, system, baseline)
    ]
    rng = random.Random(20260712)
    n = len(differences)
    draws = [
        sum(differences[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(samples)
    ]
    draws.sort()
    return {
        'delta': sum(differences) / n,
        'lo': draws[int(0.025 * samples)],
        'hi': draws[int(0.975 * samples)],
    }


def run_config(config):
    train = data.load_split(config, 'train')
    test = data.load_split(config, 'test')
    table, memorizer, majority, counts, conflicts = learn_abstract_table(train)
    labels = sorted({row['target_text'] for row in train})
    metrics, golds, predictions, errors = evaluate(test, table, memorizer, majority, labels)
    return {
        'dataset': common.DATASET,
        'config': config,
        'train_rows': len(train), 'test_rows': len(test),
        'binary_training_rows': sum(len(edge_sequence(row)) == 2 for row in train),
        'latent_classes': sorted(set(ABSTRACT.values())),
        'partial_algebra_size': len(table),
        'partial_algebra_conflicts': conflicts,
        'protocol': (
            'Surface labels are mapped to fixed gender-quotiented classes. The partial '
            'binary law is estimated only from length-2 train rows. A CKY-style chart '
            'searches valid parenthesizations on the untouched test split.'
        ),
        'metrics': metrics,
        'paired_chart_vs_left_fold': paired_bootstrap(
            golds, predictions['sol_chart'], predictions['left_fold']
        ),
        'paired_chart_vs_memorizer': paired_bootstrap(
            golds, predictions['sol_chart'], predictions['sequence_memorizer']
        ),
        'errors': errors,
        'partial_algebra': {'|'.join(pair): value for pair, value in sorted(table.items())},
        'partial_algebra_counts': {
            '|'.join(pair): dict(counter) for pair, counter in sorted(counts.items())
        },
    }


def main():
    out = Path('artifacts/clutrr_chart')
    out.mkdir(parents=True, exist_ok=True)
    reports = [run_config(config) for config in CONFIGS]
    payload = {
        'name': 'SOL latent partial-algebra chart cell',
        'reports': reports,
        'leakage_policy': (
            'No test label is used to estimate the abstraction or composition table. '
            'The abstraction is fixed by kinship semantics; the binary table uses only '
            'length-2 train examples. Abstentions count as wrong.'
        ),
    }
    (out / 'results.json').write_text(json.dumps(payload, indent=2))

    lines = [
        '# SOL CLUTRR latent-algebra held-out results', '',
        '|Config|Train|Test|Rules|Chart|Coverage|Left fold|Memorizer|Last edge|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for report in reports:
        metrics = report['metrics']
        lines.append(
            f"|{report['config']}|{report['train_rows']}|{report['test_rows']}|"
            f"{report['partial_algebra_size']}|{metrics['sol_chart']['accuracy']:.4f}|"
            f"{metrics['sol_chart']['coverage']:.4f}|{metrics['left_fold']['accuracy']:.4f}|"
            f"{metrics['sequence_memorizer']['accuracy']:.4f}|"
            f"{metrics['last_edge']['accuracy']:.4f}|"
        )
    lines += [
        '',
        'The chart cell learns only the partial binary algebra from length-2 train paths.',
        'All test chains, including lengths up to 10, are untouched until scoring.',
    ]
    (out / 'RESULTS.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({
        report['config']: {
            'chart_accuracy': report['metrics']['sol_chart']['accuracy'],
            'coverage': report['metrics']['sol_chart']['coverage'],
            'left_fold': report['metrics']['left_fold']['accuracy'],
            'memorizer': report['metrics']['sequence_memorizer']['accuracy'],
            'test_rows': report['test_rows'],
            'rules': report['partial_algebra_size'],
        }
        for report in reports
    }, indent=2))


if __name__ == '__main__':
    main()
