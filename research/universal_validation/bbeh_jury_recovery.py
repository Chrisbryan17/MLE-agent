#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request
from typing import Any

ENDPOINT = 'https://models.github.ai/inference/chat/completions'
ROOT = pathlib.Path(os.environ.get('BBEH_ROOT', '.external/bbeh'))
OUT = pathlib.Path('artifacts/bbeh_jury_recovery')

SHARDS = {
    'language': {
        'model': 'openai/gpt-4.1',
        'tasks': (
            'bbeh_disambiguation_qa',
            'bbeh_movie_recommendation',
            'bbeh_nycc',
            'bbeh_sarc_triples',
            'bbeh_linguini',
            'bbeh_object_properties',
            'bbeh_buggy_tables',
        ),
    },
    'world': {
        'model': 'openai/gpt-4o',
        'tasks': (
            'bbeh_causal_understanding',
            'bbeh_sportqa',
            'bbeh_boardgame_qa',
            'bbeh_geometric_shapes',
            'bbeh_time_arithmetic',
            'bbeh_zebra_puzzles',
        ),
    },
}

INSTRUCTIONS = {
    'bbeh_causal_understanding': 'Apply ordinary human causal judgment, distinguishing actual causation from background conditions and abnormal interventions.',
    'bbeh_disambiguation_qa': 'Resolve references using syntax, discourse coherence, and commonsense. Return the exact requested option or answer.',
    'bbeh_movie_recommendation': 'Choose the movie most similar in genre, themes, tone, audience, and narrative structure.',
    'bbeh_nycc': 'Choose the funniest New Yorker-style caption: concise, scene-specific, surprising, and socially observant.',
    'bbeh_sarc_triples': 'Identify the sarcastic sentence whose literal wording conflicts with its context.',
    'bbeh_sportqa': 'Use sports rules, event structure, chronology, and physical plausibility.',
    'bbeh_boardgame_qa': 'Perform defeasible rule reasoning to a fixed point. Respect stated priorities and answer proved, disproved, or unknown exactly as requested.',
    'bbeh_buggy_tables': 'Reconstruct corrupted table cells from row and column patterns, then compute the requested result exactly.',
    'bbeh_geometric_shapes': 'Parse the described SVG or geometry, track all operations, and return only the requested final property or answer token.',
    'bbeh_linguini': 'Infer the hidden language from demonstrations, including morphology, case, agreement, and word order, then translate or classify exactly.',
    'bbeh_object_properties': 'Track every object and property update in order, including set membership, either/neither, exceptions, and overwrites.',
    'bbeh_time_arithmetic': 'Solve both linked time/date stages exactly, substitute the first result into the second, and respect calendar and timezone details.',
    'bbeh_zebra_puzzles': 'Solve the complete finite-domain logic puzzle using all-different, equality, ordering, adjacency, offsets, endpoints, and disjunction constraints.',
}

SYSTEM = (
    'Solve each numbered benchmark item independently and carefully. '
    'Return only one valid JSON object mapping each numeric item id string to its exact final answer. '
    'Do not include explanations, markdown, or omitted keys.'
)


def canonical(value: Any) -> str:
    text = str(value).strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.S | re.I)
    return text.strip()


def normalized(value: Any) -> str:
    text = canonical(value).lower()
    text = re.sub(r'\s+', ' ', text)
    if re.fullmatch(r'[a-z]', text):
        return f'({text})'
    return text


def extract_json(content: str) -> dict[str, str]:
    cleaned = canonical(content)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', cleaned, re.S)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise TypeError('Expected a JSON object')
    output: dict[str, str] = {}
    for key, answer in value.items():
        match = re.search(r'\d+', str(key))
        if match:
            output[match.group(0)] = canonical(answer)
    return output


def build_prompt(task: str, items: list[tuple[int, dict[str, Any]]]) -> str:
    parts = [INSTRUCTIONS[task], '', 'TEST ITEMS:', '']
    for index, example in items:
        parts.extend((f'ITEM {index}:', example['input'], ''))
    parts.append('Return only the JSON answer map.')
    return '\n'.join(parts)


def request_batch(model: str, task: str, items: list[tuple[int, dict[str, Any]]], retries: int = 8) -> dict[str, Any]:
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': build_prompt(task, items)},
        ],
    }
    last: dict[str, Any] | None = None
    for attempt in range(retries):
        started = time.time()
        try:
            request = urllib.request.Request(
                ENDPOINT,
                data=json.dumps(payload).encode(),
                headers={
                    'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
                    'Content-Type': 'application/json',
                    'Accept': 'application/vnd.github+json',
                },
            )
            with urllib.request.urlopen(request, timeout=1200) as response:
                raw = response.read().decode(errors='replace')
                headers = dict(response.headers)
                status = response.status
            decoded = json.loads(raw)
            message = decoded['choices'][0]['message']
            content = message.get('content') or message.get('reasoning_content') or ''
            answers = extract_json(content)
            missing = [str(index) for index, _ in items if str(index) not in answers]
            if missing:
                raise ValueError(f'Missing ids: {missing}')
            return {
                'ok': True,
                'answers': answers,
                'status': status,
                'headers': headers,
                'usage': decoded.get('usage'),
                'latency_seconds': time.time() - started,
                'raw_message': message,
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors='replace')
            last = {
                'type': 'HTTPError', 'status': exc.code,
                'headers': dict(exc.headers), 'body': body,
            }
            if exc.code not in (408, 429, 500, 502, 503, 504):
                break
            retry_after = int(exc.headers.get('Retry-After', '30'))
            time.sleep(retry_after + 7)
        except Exception as exc:
            last = {'type': type(exc).__name__, 'message': str(exc)}
            time.sleep(min(180, 20 * (attempt + 1)))
    return {'ok': False, 'error': last}


def batches(examples: list[dict[str, Any]], max_items: int = 20, max_chars: int = 70000):
    current: list[tuple[int, dict[str, Any]]] = []
    chars = 0
    for index, example in enumerate(examples):
        size = len(example['input'])
        if current and (len(current) >= max_items or chars + size > max_chars):
            yield current
            current, chars = [], 0
        current.append((index, example))
        chars += size
    if current:
        yield current


def solve_task(model: str, task: str, examples: list[dict[str, Any]]) -> dict[str, Any]:
    checkpoint_path = OUT / f'{task}.checkpoint.json'
    checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {
        'task': task,
        'model': model,
        'predictions': {},
        'raw_batches': [],
    }
    predictions = checkpoint['predictions']
    for batch in batches(examples):
        pending = [(index, example) for index, example in batch if str(index) not in predictions]
        if not pending:
            continue
        queue = [pending]
        while queue:
            subset = queue.pop(0)
            result = request_batch(model, task, subset)
            checkpoint['raw_batches'].append({'ids': [index for index, _ in subset], 'result': result})
            if result.get('ok'):
                predictions.update(result['answers'])
            elif len(subset) > 1:
                midpoint = len(subset) // 2
                queue.extend((subset[:midpoint], subset[midpoint:]))
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2, default=str))
        print(task, len(predictions), '/', len(examples), flush=True)
        time.sleep(35)
    return checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--shard', required=True, choices=sorted(SHARDS))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    specification = SHARDS[args.shard]
    model = specification['model']
    report: dict[str, Any] = {
        'protocol': 'Recovery jury with serialized per-model execution. Prompts contain inputs only; all prediction files are sealed before labels are scored.',
        'shard': args.shard,
        'model': model,
        'tasks': {},
    }
    task_data: dict[str, list[dict[str, Any]]] = {}

    for task in specification['tasks']:
        path = ROOT / 'bbeh' / 'benchmark_tasks' / task / 'task.json'
        examples = json.loads(path.read_text())['examples']
        task_data[task] = examples
        checkpoint = solve_task(model, task, examples)
        predictions = checkpoint['predictions']
        sealed = {
            'task': task,
            'model': model,
            'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'predictions': predictions,
            'prediction_sha256': hashlib.sha256(json.dumps(predictions, sort_keys=True).encode()).hexdigest(),
            'raw_batches': checkpoint['raw_batches'],
        }
        (OUT / f'{task}.predictions.json').write_text(json.dumps(sealed, indent=2, default=str))

    # Scoring begins only after every task in this shard has a sealed prediction artifact.
    for task in specification['tasks']:
        sealed = json.loads((OUT / f'{task}.predictions.json').read_text())
        examples = task_data[task]
        rows = []
        for index, example in enumerate(examples):
            prediction = sealed['predictions'].get(str(index))
            correct = prediction is not None and normalized(prediction) == normalized(example['target'])
            rows.append({
                'index': index,
                'prediction': prediction,
                'target': example['target'],
                'correct': bool(correct),
            })
        correct = sum(row['correct'] for row in rows)
        report['tasks'][task] = {
            'n': len(rows),
            'correct': correct,
            'accuracy': correct / len(rows),
            'coverage': sum(row['prediction'] is not None for row in rows) / len(rows),
            'prediction_sha256': sealed['prediction_sha256'],
            'errors': [row for row in rows if not row['correct']],
        }

    n = sum(value['n'] for value in report['tasks'].values())
    correct = sum(value['correct'] for value in report['tasks'].values())
    report['aggregate'] = {
        'tasks': len(report['tasks']),
        'n': n,
        'correct': correct,
        'micro_accuracy': correct / n,
        'macro_accuracy': sum(value['accuracy'] for value in report['tasks'].values()) / len(report['tasks']),
        'coverage': sum(value['coverage'] * value['n'] for value in report['tasks'].values()) / n,
    }
    report['code_sha256'] = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
    (OUT / f'{args.shard}.results.json').write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report['aggregate'], indent=2))


if __name__ == '__main__':
    main()
