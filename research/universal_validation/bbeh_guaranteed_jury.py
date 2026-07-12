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
OUT = pathlib.Path('artifacts/bbeh_guaranteed_jury')

SHARDS = {
    'o1': {
        'model': 'openai/o1',
        'tasks': (
            'bbeh_boardgame_qa',
            'bbeh_buggy_tables',
            'bbeh_time_arithmetic',
            'bbeh_zebra_puzzles',
        ),
    },
    'gpt4omini': {
        'model': 'openai/gpt-4o-mini',
        'tasks': (
            'bbeh_disambiguation_qa',
            'bbeh_movie_recommendation',
            'bbeh_sarc_triples',
            'bbeh_sportqa',
        ),
    },
    'cohere': {
        'model': 'cohere/Cohere-command-a',
        'tasks': (
            'bbeh_causal_understanding',
            'bbeh_nycc',
            'bbeh_object_properties',
        ),
    },
    'phi4': {
        'model': 'microsoft/Phi-4',
        'tasks': (
            'bbeh_geometric_shapes',
            'bbeh_linguini',
        ),
    },
}

INSTRUCTIONS = {
    'bbeh_boardgame_qa': 'Perform defeasible rule reasoning to a fixed point. Respect explicit rule priorities and answer proved, disproved, or unknown in the exact requested format.',
    'bbeh_buggy_tables': 'Reconstruct corrupted cells from row and column regularities, then compute the requested statistic exactly.',
    'bbeh_time_arithmetic': 'Solve the first date/time problem, substitute its result into the second, and calculate all calendar, clock, and timezone operations exactly.',
    'bbeh_zebra_puzzles': 'Solve the complete finite-domain logic puzzle using all-different, equality, order, adjacency, immediate-left, distance, endpoint, and disjunction constraints.',
    'bbeh_disambiguation_qa': 'Resolve the ambiguous reference using grammar, discourse coherence, and commonsense. Return exactly the requested option or answer.',
    'bbeh_movie_recommendation': 'Choose the movie most similar in genre, themes, tone, audience, and narrative structure.',
    'bbeh_sarc_triples': 'Identify the sentence whose literal wording conflicts with its context in a sarcastic way.',
    'bbeh_sportqa': 'Use sports rules, event structure, chronology, and physical plausibility.',
    'bbeh_causal_understanding': 'Apply ordinary human causal judgment, distinguishing actual causes from background conditions and abnormal interventions.',
    'bbeh_nycc': 'Choose the funniest New Yorker-style caption: concise, scene-specific, surprising, and socially observant.',
    'bbeh_object_properties': 'Track every object and property update in order, including set membership, either/neither, exceptions, and overwrites.',
    'bbeh_geometric_shapes': 'Parse the SVG path or geometric construction, track every transformation, and return the exact requested shape or property.',
    'bbeh_linguini': 'Infer the hidden language from demonstrations, including morphology, case, agreement, and word order, then answer exactly.',
}

SYSTEM = (
    'Solve every numbered benchmark item independently. Return only one valid JSON object '
    'mapping each numeric item id string to its exact final answer. Do not include explanations, '
    'markdown, commentary, or omitted keys.'
)


def canonical(value: Any) -> str:
    text = str(value).strip()
    return re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.S | re.I).strip()


def normalized(value: Any) -> str:
    text = re.sub(r'\s+', ' ', canonical(value).lower())
    return f'({text})' if re.fullmatch(r'[a-z]', text) else text


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
                    'X-GitHub-Api-Version': '2022-11-28',
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
                'type': 'HTTPError',
                'status': exc.code,
                'headers': dict(exc.headers),
                'body': body,
            }
            if exc.code not in (408, 429, 500, 502, 503, 504):
                break
            time.sleep(int(exc.headers.get('Retry-After', '30')) + 5)
        except Exception as exc:
            last = {'type': type(exc).__name__, 'message': str(exc)}
            time.sleep(min(120, 12 * (attempt + 1)))
    return {'ok': False, 'error': last}


def make_batches(examples: list[dict[str, Any]], max_items: int = 40, max_chars: int = 100000):
    current: list[tuple[int, dict[str, Any]]] = []
    characters = 0
    for index, example in enumerate(examples):
        size = len(example['input'])
        if current and (len(current) >= max_items or characters + size > max_chars):
            yield current
            current, characters = [], 0
        current.append((index, example))
        characters += size
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
    for batch in make_batches(examples):
        pending = [item for item in batch if str(item[0]) not in predictions]
        if not pending:
            continue
        queue = [pending]
        while queue:
            subset = queue.pop(0)
            result = request_batch(model, task, subset)
            checkpoint['raw_batches'].append({
                'ids': [index for index, _ in subset],
                'result': result,
            })
            if result.get('ok'):
                predictions.update(result['answers'])
            elif len(subset) > 1:
                middle = len(subset) // 2
                queue.extend((subset[:middle], subset[middle:]))
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2, default=str))
        print(task, len(predictions), '/', len(examples), flush=True)
        time.sleep(5)
    return checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--shard', required=True, choices=sorted(SHARDS))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    specification = SHARDS[args.shard]
    model = specification['model']
    task_data: dict[str, list[dict[str, Any]]] = {}
    report: dict[str, Any] = {
        'protocol': (
            'Guaranteed-close jury using previously uncontended model buckets. Prompts contain only '
            'inputs and task instructions; all prediction files are sealed before scoring.'
        ),
        'shard': args.shard,
        'model': model,
        'tasks': {},
    }

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
            'prediction_sha256': hashlib.sha256(
                json.dumps(predictions, sort_keys=True).encode()
            ).hexdigest(),
            'raw_batches': checkpoint['raw_batches'],
        }
        (OUT / f'{task}.predictions.json').write_text(json.dumps(sealed, indent=2, default=str))

    for task in specification['tasks']:
        sealed = json.loads((OUT / f'{task}.predictions.json').read_text())
        examples = task_data[task]
        rows = []
        for index, example in enumerate(examples):
            prediction = sealed['predictions'].get(str(index))
            rows.append({
                'index': index,
                'prediction': prediction,
                'target': example['target'],
                'correct': prediction is not None and normalized(prediction) == normalized(example['target']),
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
