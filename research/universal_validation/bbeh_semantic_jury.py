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
OUT = pathlib.Path('artifacts/bbeh_semantic_jury')
TASKS = (
    'bbeh_causal_understanding',
    'bbeh_disambiguation_qa',
    'bbeh_movie_recommendation',
    'bbeh_nycc',
    'bbeh_sarc_triples',
    'bbeh_sportqa',
)

INSTRUCTIONS = {
    'bbeh_causal_understanding': (
        'Answer each causal-normality question according to ordinary human causal judgment. '
        'Return exactly the answer format requested by the item.'
    ),
    'bbeh_disambiguation_qa': (
        'Resolve the ambiguous pronoun or reference using grammar, discourse coherence and '
        'commonsense. Return exactly the requested option token.'
    ),
    'bbeh_movie_recommendation': (
        'Choose the movie most similar to the listed movies in genre, themes, tone and audience. '
        'Return exactly the requested option token.'
    ),
    'bbeh_nycc': (
        'Choose the funniest New Yorker-style caption: concise, scene-specific, surprising and '
        'socially observant. Return exactly the requested option token.'
    ),
    'bbeh_sarc_triples': (
        'Identify the sentence whose literal wording conflicts with context in a sarcastic way. '
        'Return exactly the requested option token.'
    ),
    'bbeh_sportqa': (
        'Use sports rules, event structure and physical plausibility to answer the question. '
        'Return exactly the requested option token.'
    ),
}

SYSTEM = (
    'You are a meticulous benchmark jury. Solve every numbered item independently. '
    'Return only one valid JSON object mapping each numeric item id string to its exact final '
    'answer. Do not include explanations or markdown. Never omit a key.'
)


def canonical(value: Any) -> str:
    text = str(value).strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.S | re.I)
    return text.strip()


def normalized(value: Any) -> str:
    text = canonical(value).lower()
    text = re.sub(r'\s+', ' ', text)
    if re.fullmatch(r'[a-z]', text):
        return f'({text.upper()})'.lower()
    return text


def extract_json(content: str) -> dict[str, Any]:
    content = canonical(content)
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', content, re.S)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise TypeError('Expected a JSON object')
    output = {}
    for key, answer in value.items():
        match = re.search(r'\d+', str(key))
        if match:
            output[match.group(0)] = canonical(answer)
    return output


def build_prompt(task: str, items: list[tuple[int, dict[str, Any]]]) -> str:
    parts = [INSTRUCTIONS[task], '', 'TEST ITEMS:', '']
    for index, example in items:
        parts.append(f'ITEM {index}:')
        parts.append(example['input'])
        parts.append('')
    parts.append('Return only the JSON answer map.')
    return '\n'.join(parts)


def request_batch(task: str, items: list[tuple[int, dict[str, Any]]], retries: int = 10) -> dict[str, Any]:
    payload = {
        'model': MODEL,
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
            with urllib.request.urlopen(request, timeout=900) as response:
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
                'type': 'HTTPError', 'status': exc.code, 'reason': str(exc.reason),
                'headers': dict(exc.headers), 'body': body,
            }
            if exc.code not in (429, 500, 502, 503, 504):
                break
            retry_after = int(exc.headers.get('Retry-After', '30'))
            time.sleep(retry_after + 5)
        except Exception as exc:
            last = {'type': type(exc).__name__, 'message': str(exc)}
            time.sleep(min(120, 15 * (attempt + 1)))
    return {'ok': False, 'error': last}


def batches(examples: list[dict[str, Any]], max_items: int = 12, max_chars: int = 70000):
    current: list[tuple[int, dict[str, Any]]] = []
    chars = 0
    for index, example in enumerate(examples):
        size = len(example['input'])
        if current and (len(current) >= max_items or chars + size > max_chars):
            yield current
            current = []
            chars = 0
        current.append((index, example))
        chars += size
    if current:
        yield current


def solve_task(task: str, examples: list[dict[str, Any]], checkpoint: dict[str, Any]):
    predictions = checkpoint.setdefault('predictions', {})
    raw_batches = checkpoint.setdefault('raw_batches', [])
    for items in batches(examples):
        unresolved = [(i, ex) for i, ex in items if str(i) not in predictions]
        if not unresolved:
            continue
        result = request_batch(task, unresolved)
        raw_batches.append({
            'ids': [i for i, _ in unresolved],
            'result': result,
        })
        if result.get('ok'):
            predictions.update(result['answers'])
        elif len(unresolved) > 1:
            # Deterministic recursive recovery for malformed/oversized batches.
            midpoint = len(unresolved) // 2
            for subset in (unresolved[:midpoint], unresolved[midpoint:]):
                subresult = request_batch(task, subset)
                raw_batches.append({'ids': [i for i, _ in subset], 'result': subresult})
                if subresult.get('ok'):
                    predictions.update(subresult['answers'])
        (OUT / f'{task}.checkpoint.json').write_text(json.dumps(checkpoint, indent=2, default=str))
        print(task, len(predictions), '/', len(examples), flush=True)
        time.sleep(35)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        'protocol': (
            'Frozen semantic jury. Prompts contain task instructions and test inputs only; '
            'gold targets are loaded after every prediction file is sealed.'
        ),
        'model': MODEL,
        'tasks': {},
    }
    task_data: dict[str, list[dict[str, Any]]] = {}
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
        sealed = OUT / f'{task}.predictions.json'
        sealed.write_text(json.dumps({
            'task': task, 'model': MODEL,
            'input_sha256': checkpoint['input_sha256'],
            'predictions': checkpoint.get('predictions', {}),
            'prediction_sha256': hashlib.sha256(
                json.dumps(checkpoint.get('predictions', {}), sort_keys=True).encode()
            ).hexdigest(),
            'raw_batches': checkpoint.get('raw_batches', []),
        }, indent=2, default=str))

    # Separate scoring phase after all prediction artifacts exist.
    for task in TASKS:
        sealed = json.loads((OUT / f'{task}.predictions.json').read_text())
        examples = task_data[task]
        predictions = sealed['predictions']
        rows = []
        for index, example in enumerate(examples):
            prediction = predictions.get(str(index))
            correct = prediction is not None and normalized(prediction) == normalized(example['target'])
            rows.append({
                'index': index, 'prediction': prediction,
                'target': example['target'], 'correct': bool(correct),
            })
        correct = sum(row['correct'] for row in rows)
        report['tasks'][task] = {
            'n': len(rows), 'correct': correct, 'accuracy': correct / len(rows),
            'coverage': sum(row['prediction'] is not None for row in rows) / len(rows),
            'prediction_sha256': sealed['prediction_sha256'],
            'errors': [row for row in rows if not row['correct']],
        }
    report['aggregate'] = {
        'n': sum(v['n'] for v in report['tasks'].values()),
        'correct': sum(v['correct'] for v in report['tasks'].values()),
        'micro_accuracy': sum(v['correct'] for v in report['tasks'].values()) / sum(v['n'] for v in report['tasks'].values()),
        'macro_accuracy': sum(v['accuracy'] for v in report['tasks'].values()) / len(report['tasks']),
    }
    (OUT / 'results.json').write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report['aggregate'], indent=2))


if __name__ == '__main__':
    main()
