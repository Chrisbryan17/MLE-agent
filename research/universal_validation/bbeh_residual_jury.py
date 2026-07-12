#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request
from typing import Any

MODEL = os.environ.get('BBEH_JURY_MODEL', 'openai/o4-mini')
ENDPOINT = 'https://models.github.ai/inference/chat/completions'
ROOT = pathlib.Path(os.environ.get('BBEH_ROOT', '.external/bbeh'))
OUT = pathlib.Path('artifacts/bbeh_residual_jury')
TASKS = (
    'bbeh_boardgame_qa',
    'bbeh_buggy_tables',
    'bbeh_geometric_shapes',
    'bbeh_linguini',
    'bbeh_object_properties',
    'bbeh_time_arithmetic',
    'bbeh_zebra_puzzles',
)

INSTRUCTIONS = {
    'bbeh_boardgame_qa': (
        'Perform defeasible rule reasoning. Derive facts to a fixed point, apply stated rule '
        'preferences when conclusions conflict, and answer exactly proved, disproved, or unknown.'
    ),
    'bbeh_buggy_tables': (
        'Reconstruct the corrupted table cells from row/column patterns and constraints, then '
        'compute the requested statistic exactly. Return only the final value.'
    ),
    'bbeh_geometric_shapes': (
        'Parse the SVG path geometry, determine the closed shape or requested geometric property, '
        'and return exactly the final answer token.'
    ),
    'bbeh_linguini': (
        'Infer the hidden linguistic system from the demonstrations, including morphology, word '
        'order, case and agreement, then answer the test item exactly.'
    ),
    'bbeh_object_properties': (
        'Track every object and property update in order. Apply either/neither and set-membership '
        'logic exactly, then return the requested answer.'
    ),
    'bbeh_time_arithmetic': (
        'Solve the first time/date problem, substitute the derived value into the second problem '
        'as instructed, and perform all calendar/time arithmetic exactly.'
    ),
    'bbeh_zebra_puzzles': (
        'Solve the full logic-grid puzzle using all-different, equality, adjacency, immediate-left, '
        'relative-order and endpoint constraints. Return only the requested position.'
    ),
}

SYSTEM = (
    'You are a meticulous benchmark solver. Solve every numbered item independently. '
    'Return only one valid JSON object mapping each numeric item id string to its exact final '
    'answer. Do not include explanations or markdown. Never omit a key.'
)


def canonical(value: Any) -> str:
    return str(value).strip()


def normalized(value: Any) -> str:
    text = canonical(value).lower()
    text = re.sub(r'\s+', ' ', text)
    if re.fullmatch(r'[a-z]', text):
        return f'({text})'
    return text


def extract_json(content: str) -> dict[str, Any]:
    content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip(), flags=re.S | re.I)
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', content, re.S)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise TypeError('Expected JSON object')
    result = {}
    for key, answer in value.items():
        match = re.search(r'\d+', str(key))
        if match:
            result[match.group(0)] = canonical(answer)
    return result


def build_prompt(task: str, items: list[tuple[int, dict[str, Any]]]) -> str:
    parts = [INSTRUCTIONS[task], '', 'TEST ITEMS:', '']
    for index, example in items:
        parts.extend((f'ITEM {index}:', example['input'], ''))
    parts.append('Return only the JSON answer map.')
    return '\n'.join(parts)


def request_batch(task: str, items: list[tuple[int, dict[str, Any]]], retries: int = 10):
    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': build_prompt(task, items)},
        ],
    }
    last = None
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
                'ok': True, 'answers': answers, 'status': status,
                'headers': headers, 'usage': decoded.get('usage'),
                'latency_seconds': time.time() - started, 'raw_message': message,
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors='replace')
            last = {'type': 'HTTPError', 'status': exc.code, 'headers': dict(exc.headers), 'body': body}
            if exc.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(int(exc.headers.get('Retry-After', '30')) + 5)
        except Exception as exc:
            last = {'type': type(exc).__name__, 'message': str(exc)}
            time.sleep(min(180, 20 * (attempt + 1)))
    return {'ok': False, 'error': last}


def make_batches(examples, max_items=6, max_chars=85000):
    current = []
    size = 0
    for index, example in enumerate(examples):
        chars = len(example['input'])
        if current and (len(current) >= max_items or size + chars > max_chars):
            yield current
            current, size = [], 0
        current.append((index, example))
        size += chars
    if current:
        yield current


def solve_task(task, examples, checkpoint):
    predictions = checkpoint.setdefault('predictions', {})
    raw_batches = checkpoint.setdefault('raw_batches', [])
    for batch in make_batches(examples):
        pending = [(i, ex) for i, ex in batch if str(i) not in predictions]
        if not pending:
            continue
        queue = [pending]
        while queue:
            subset = queue.pop(0)
            result = request_batch(task, subset)
            raw_batches.append({'ids': [i for i, _ in subset], 'result': result})
            if result.get('ok'):
                predictions.update(result['answers'])
            elif len(subset) > 1:
                midpoint = len(subset) // 2
                queue.extend((subset[:midpoint], subset[midpoint:]))
        (OUT / f'{task}.checkpoint.json').write_text(json.dumps(checkpoint, indent=2, default=str))
        print(task, len(predictions), '/', len(examples), flush=True)
        time.sleep(35)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        'protocol': 'Frozen residual-task jury; inputs only in prompts; predictions sealed before scoring.',
        'model': MODEL, 'tasks': {},
    }
    task_data = {}
    for task in TASKS:
        path = ROOT / 'bbeh' / 'benchmark_tasks' / task / 'task.json'
        examples = json.loads(path.read_text())['examples']
        task_data[task] = examples
        checkpoint_path = OUT / f'{task}.checkpoint.json'
        checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {
            'task': task, 'model': MODEL,
            'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        solve_task(task, examples, checkpoint)
        predictions = checkpoint.get('predictions', {})
        sealed = {
            'task': task, 'model': MODEL, 'input_sha256': checkpoint['input_sha256'],
            'predictions': predictions,
            'prediction_sha256': hashlib.sha256(json.dumps(predictions, sort_keys=True).encode()).hexdigest(),
            'raw_batches': checkpoint.get('raw_batches', []),
        }
        (OUT / f'{task}.predictions.json').write_text(json.dumps(sealed, indent=2, default=str))

    for task in TASKS:
        sealed = json.loads((OUT / f'{task}.predictions.json').read_text())
        examples = task_data[task]
        rows = []
        for index, example in enumerate(examples):
            prediction = sealed['predictions'].get(str(index))
            correct = prediction is not None and normalized(prediction) == normalized(example['target'])
            rows.append({'index': index, 'prediction': prediction, 'target': example['target'], 'correct': bool(correct)})
        correct = sum(row['correct'] for row in rows)
        report['tasks'][task] = {
            'n': len(rows), 'correct': correct, 'accuracy': correct / len(rows),
            'coverage': sum(row['prediction'] is not None for row in rows) / len(rows),
            'prediction_sha256': sealed['prediction_sha256'],
            'errors': [row for row in rows if not row['correct']],
        }
    n = sum(item['n'] for item in report['tasks'].values())
    correct = sum(item['correct'] for item in report['tasks'].values())
    report['aggregate'] = {
        'n': n, 'correct': correct, 'micro_accuracy': correct / n,
        'macro_accuracy': sum(item['accuracy'] for item in report['tasks'].values()) / len(report['tasks']),
    }
    (OUT / 'results.json').write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report['aggregate'], indent=2))


if __name__ == '__main__':
    main()
