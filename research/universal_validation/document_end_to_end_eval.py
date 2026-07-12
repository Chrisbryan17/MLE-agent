#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import random
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any

import pyarrow.parquet as pq

BASE = 'https://datasets-server.huggingface.co'
ENDPOINT = 'https://models.github.ai/inference/chat/completions'
MODEL = os.environ.get('DOCUMENT_JURY_MODEL', 'openai/o4-mini')
SAMPLE_SIZE = int(os.environ.get('DOCUMENT_SAMPLE_SIZE', '100'))
OUT = pathlib.Path('artifacts/document_end_to_end')
CACHE = pathlib.Path('.document_eval_cache')

DATASETS = {
    'contract_nli': 'kiddothe2b/contract-nli',
    'finqa': 'dreamerdeo/finqa',
    'scifact': 'davidheineman/scifact-open',
    'tabfact': 'table-benchmark/tabfact',
    'redocred': 'Despina/re-docred',
}

SYSTEM = (
    'You are an evidence-grounded document reasoning engine. Solve each numbered item '
    'independently. Return only one JSON object mapping each item id to an object with '
    'two keys: "answer" and "evidence". Evidence must be a short exact quote copied '
    'from the supplied context. Never invent a quote and never omit an item.'
)


def get_json(path: str, params: dict[str, Any], retries: int = 8) -> dict[str, Any]:
    url = BASE + path + '?' + urllib.parse.urlencode(params)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'world-graph-validation/0.1'})
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read())
        except Exception as exc:
            last = exc
            time.sleep(min(30, 2 ** attempt))
    assert last is not None
    raise last


def download(url: str, path: pathlib.Path, retries: int = 8) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'world-graph-validation/0.1'})
            with urllib.request.urlopen(request, timeout=300) as response, path.open('wb') as handle:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    handle.write(block)
            return
        except Exception as exc:
            last = exc
            path.unlink(missing_ok=True)
            time.sleep(min(30, 2 ** attempt))
    assert last is not None
    raise last


def parquet_rows(alias: str, repo: str) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    manifest = get_json('/parquet', {'dataset': repo})
    entries = manifest.get('parquet_files', [])
    if not entries:
        raise RuntimeError(f'No Parquet exports for {repo}')
    preferred_order = ('test', 'validation', 'dev', 'train')
    available = sorted({str(entry.get('split')) for entry in entries})
    chosen = next((split for split in preferred_order if split in available), available[0])
    selected = [entry for entry in entries if str(entry.get('split')) == chosen]
    rows: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    descriptors: list[dict[str, Any]] = []
    for index, entry in enumerate(selected):
        local = CACHE / alias / chosen / f'{index:03d}.parquet'
        download(entry['url'], local)
        digest = hashlib.sha256(local.read_bytes()).hexdigest()
        hashes[str(local.relative_to(CACHE))] = digest
        parquet = pq.ParquetFile(local)
        descriptors.append({
            'config': entry.get('config'), 'split': chosen, 'url': entry['url'],
            'rows': parquet.metadata.num_rows, 'sha256': digest,
        })
        for batch in parquet.iter_batches(batch_size=2048):
            rows.extend(batch.to_pylist())
    return rows, hashes, descriptors


def scalar_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, default=str)


def find_field(row: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
    lower = {key.lower(): key for key in row}
    for candidate in candidates:
        if candidate in lower:
            return lower[candidate]
    for key in row:
        lowered = key.lower()
        if any(candidate in lowered for candidate in candidates):
            return key
    return None


def stable_id(alias: str, index: int, row: dict[str, Any]) -> str:
    identifier = find_field(row, ('id', 'uid', 'question_id', 'claim_id', 'title'))
    raw = scalar_text(row.get(identifier)) if identifier else str(index)
    return hashlib.sha256(f'{alias}|{raw}|{index}'.encode()).hexdigest()


def label_field(alias: str, row: dict[str, Any]) -> str | None:
    preferred = {
        'contract_nli': ('label',),
        'finqa': ('answers', 'answer'),
        'scifact': ('label', 'verdict', 'answer'),
        'tabfact': ('label', 'answer'),
        'redocred': ('relation', 'label', 'target'),
    }[alias]
    return find_field(row, preferred)


def context_and_query(alias: str, row: dict[str, Any]) -> tuple[str, str]:
    if alias == 'contract_nli':
        context_key = find_field(row, ('premise', 'contract', 'document', 'text'))
        query_key = find_field(row, ('hypothesis', 'query', 'question'))
        return scalar_text(row.get(context_key)), scalar_text(row.get(query_key))
    if alias == 'finqa':
        question_key = find_field(row, ('question', 'query'))
        chunks = []
        for candidate in ('pre_text', 'post_text', 'table', 'context', 'text'):
            key = find_field(row, (candidate,))
            if key and row.get(key) not in (None, '', []):
                chunks.append(f'{key}: {scalar_text(row[key])}')
        return '\n'.join(chunks), scalar_text(row.get(question_key))
    if alias == 'scifact':
        claim_key = find_field(row, ('claim', 'query', 'question'))
        chunks = []
        for candidate in ('abstract', 'evidence', 'context', 'text', 'document'):
            key = find_field(row, (candidate,))
            if key and row.get(key) not in (None, '', []):
                chunks.append(scalar_text(row[key]))
        return '\n'.join(chunks), scalar_text(row.get(claim_key))
    if alias == 'tabfact':
        statement_key = find_field(row, ('statement', 'claim', 'query', 'question'))
        table_key = find_field(row, ('table', 'context', 'text'))
        return scalar_text(row.get(table_key)), scalar_text(row.get(statement_key))
    # Re-DocRED sentence-level mirror.
    text_key = find_field(row, ('sentence', 'text', 'context', 'document'))
    head_key = find_field(row, ('head', 'subject', 'entity1', 'h'))
    tail_key = find_field(row, ('tail', 'object', 'entity2', 't'))
    query = f'What relation holds from {scalar_text(row.get(head_key))} to {scalar_text(row.get(tail_key))}?'
    return scalar_text(row.get(text_key)), query


def task_instruction(alias: str) -> str:
    return {
        'contract_nli': (
            'Classify the hypothesis relative to the contract as entailment, contradiction, '
            'or not_mentioned. Use the exact answer token.'
        ),
        'finqa': (
            'Answer the financial question exactly. Perform any required arithmetic over the '
            'table and report. Return only the final answer value, preserving percent signs.'
        ),
        'scifact': (
            'Classify the scientific claim as supports, refutes, or not_enough_information '
            'relative to the supplied scientific evidence.'
        ),
        'tabfact': 'Classify the statement relative to the table as entailed or refuted.',
        'redocred': (
            'Return the most specific relation name expressed by the sentence from the first '
            'entity to the second entity. Use no explanation in the answer field.'
        ),
    }[alias]


def build_prompt(alias: str, items: list[dict[str, Any]]) -> str:
    parts = [task_instruction(alias), '', 'ITEMS:']
    for item in items:
        context = item['context'][:90000]
        parts.extend((
            '', f"ITEM {item['item_id']}:",
            'CONTEXT:', context,
            'QUERY:', item['query'],
        ))
    parts.append('\nReturn only the JSON object.')
    return '\n'.join(parts)


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
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        match = re.search(r'\d+', str(key))
        if match:
            normalized[match.group(0)] = item
    return normalized


def request_batch(alias: str, items: list[dict[str, Any]], retries: int = 10) -> dict[str, Any]:
    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': build_prompt(alias, items)},
        ],
    }
    last: Any = None
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
            missing = [item['item_id'] for item in items if item['item_id'] not in answers]
            if missing:
                raise ValueError(f'Missing item ids: {missing}')
            return {
                'ok': True, 'answers': answers, 'status': status, 'headers': headers,
                'usage': decoded.get('usage'), 'latency_seconds': time.time() - started,
                'raw_message': message,
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors='replace')
            last = {'type': 'HTTPError', 'status': exc.code, 'body': body, 'headers': dict(exc.headers)}
            if exc.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(int(exc.headers.get('Retry-After', '30')) + 5)
        except Exception as exc:
            last = {'type': type(exc).__name__, 'message': str(exc)}
            time.sleep(min(180, 20 * (attempt + 1)))
    return {'ok': False, 'error': last}


def make_batches(alias: str, items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    maximum = 1 if alias == 'contract_nli' else 3
    max_chars = 95000
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    chars = 0
    for item in items:
        size = len(item['context']) + len(item['query'])
        if current and (len(current) >= maximum or chars + size > max_chars):
            batches.append(current)
            current = []
            chars = 0
        current.append(item)
        chars += size
    if current:
        batches.append(current)
    return batches


def normalize_answer(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get('answer', '')
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    text = scalar_text(value).strip().lower()
    text = text.replace('not mentioned', 'not_mentioned').replace('not enough information', 'not_enough_information')
    text = text.replace('entails', 'entailment').replace('entailed', 'entailment')
    text = text.replace('contradicts', 'contradiction').replace('contradicted', 'contradiction')
    text = text.replace('supported', 'supports').replace('refuted', 'refutes')
    text = re.sub(r'\s+', ' ', text)
    return text.strip(' ."\'')


def evidence_valid(context: str, prediction: Any) -> bool:
    if not isinstance(prediction, dict):
        return False
    evidence = prediction.get('evidence')
    if isinstance(evidence, list):
        quotes = [scalar_text(item).strip() for item in evidence]
    else:
        quotes = [scalar_text(evidence).strip()]
    quotes = [quote for quote in quotes if quote]
    if not quotes:
        return False
    lowered = context.lower()
    return all(quote.lower() in lowered for quote in quotes)


def deterministic_sample(alias: str, rows: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    ranked = sorted(
        enumerate(rows),
        key=lambda pair: hashlib.sha256(stable_id(alias, pair[0], pair[1]).encode()).hexdigest(),
    )
    return ranked[: min(SAMPLE_SIZE, len(ranked))]


def bootstrap_ci(correct: list[int], draws: int = 5000) -> tuple[float, float]:
    if not correct:
        return (0.0, 0.0)
    rng = random.Random(20260712)
    values = []
    n = len(correct)
    for _ in range(draws):
        values.append(sum(correct[rng.randrange(n)] for _ in range(n)) / n)
    values.sort()
    return values[int(0.025 * draws)], values[int(0.975 * draws)]


def run_dataset(alias: str, repo: str) -> dict[str, Any]:
    rows, hashes, descriptors = parquet_rows(alias, repo)
    labels = []
    for row in rows:
        key = label_field(alias, row)
        if key is not None:
            labels.append(normalize_answer(row.get(key)))
    majority = Counter(labels).most_common(1)[0][0] if labels else ''
    full_baseline_correct = sum(label == majority for label in labels)

    selected = deterministic_sample(alias, rows)
    items = []
    gold_by_id: dict[str, Any] = {}
    source_index: dict[str, dict[str, Any]] = {}
    for item_number, (row_index, row) in enumerate(selected):
        context, query = context_and_query(alias, row)
        item_id = str(item_number)
        items.append({'item_id': item_id, 'context': context, 'query': query})
        key = label_field(alias, row)
        gold_by_id[item_id] = row.get(key) if key else None
        source_index[item_id] = {'row_index': row_index, 'stable_id': stable_id(alias, row_index, row)}

    unlabeled = {
        'alias': alias, 'repo': repo, 'sample_size': len(items),
        'items': items, 'source_index': source_index, 'parquet_sha256': hashes,
    }
    sample_path = OUT / f'{alias}.unlabeled.json'
    sample_path.write_text(json.dumps(unlabeled, indent=2, default=str))
    sample_hash = hashlib.sha256(sample_path.read_bytes()).hexdigest()

    predictions: dict[str, Any] = {}
    raw_batches: list[dict[str, Any]] = []
    for batch in make_batches(alias, items):
        queue = [batch]
        while queue:
            subset = queue.pop(0)
            result = request_batch(alias, subset)
            raw_batches.append({'ids': [item['item_id'] for item in subset], 'result': result})
            if result.get('ok'):
                predictions.update(result['answers'])
            elif len(subset) > 1:
                midpoint = len(subset) // 2
                queue.extend((subset[:midpoint], subset[midpoint:]))
        checkpoint = {
            'alias': alias, 'model': MODEL, 'sample_sha256': sample_hash,
            'predictions': predictions, 'raw_batches': raw_batches,
        }
        (OUT / f'{alias}.checkpoint.json').write_text(json.dumps(checkpoint, indent=2, default=str))
        print(alias, len(predictions), '/', len(items), flush=True)
        time.sleep(35)

    sealed = {
        'alias': alias, 'model': MODEL, 'sample_sha256': sample_hash,
        'predictions': predictions,
        'prediction_sha256': hashlib.sha256(json.dumps(predictions, sort_keys=True).encode()).hexdigest(),
        'raw_batches': raw_batches,
    }
    (OUT / f'{alias}.predictions.json').write_text(json.dumps(sealed, indent=2, default=str))

    rows_scored = []
    for item in items:
        item_id = item['item_id']
        prediction = predictions.get(item_id)
        predicted_answer = normalize_answer(prediction)
        gold = normalize_answer(gold_by_id[item_id])
        answer_correct = predicted_answer == gold
        valid_evidence = evidence_valid(item['context'], prediction)
        rows_scored.append({
            'item_id': item_id, 'stable_id': source_index[item_id]['stable_id'],
            'prediction': prediction, 'gold': gold_by_id[item_id],
            'answer_correct': answer_correct, 'evidence_valid': valid_evidence,
            'joint_correct': answer_correct and valid_evidence,
        })
    answer_vector = [int(row['answer_correct']) for row in rows_scored]
    evidence_vector = [int(row['evidence_valid']) for row in rows_scored]
    joint_vector = [int(row['joint_correct']) for row in rows_scored]
    lo, hi = bootstrap_ci(answer_vector)
    return {
        'alias': alias, 'repo': repo, 'full_split_rows': len(rows),
        'full_majority_baseline': {
            'label': majority, 'correct': full_baseline_correct,
            'accuracy': full_baseline_correct / len(labels) if labels else 0.0,
        },
        'sample': {
            'n': len(rows_scored), 'answer_correct': sum(answer_vector),
            'answer_accuracy': statistics.mean(answer_vector) if answer_vector else 0.0,
            'answer_accuracy_ci95': [lo, hi],
            'evidence_valid': sum(evidence_vector),
            'evidence_valid_rate': statistics.mean(evidence_vector) if evidence_vector else 0.0,
            'joint_correct': sum(joint_vector),
            'joint_accuracy': statistics.mean(joint_vector) if joint_vector else 0.0,
            'coverage': len(predictions) / len(items) if items else 0.0,
        },
        'parquet_files': descriptors, 'sample_sha256': sample_hash,
        'prediction_sha256': sealed['prediction_sha256'],
        'errors': [row for row in rows_scored if not row['joint_correct']],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        'protocol': (
            'Full held-out split majority/coverage audit plus a deterministic 100-example '
            'end-to-end answer-and-evidence evaluation per domain. Unlabeled samples and '
            'predictions are hashed before labels are scored.'
        ),
        'model': MODEL, 'sample_size_per_domain': SAMPLE_SIZE,
        'datasets': {},
    }
    for alias, repo in DATASETS.items():
        report['datasets'][alias] = run_dataset(alias, repo)
        (OUT / 'partial_results.json').write_text(json.dumps(report, indent=2, default=str))
    samples = [item['sample'] for item in report['datasets'].values()]
    total_n = sum(item['n'] for item in samples)
    report['aggregate'] = {
        'n': total_n,
        'answer_correct': sum(item['answer_correct'] for item in samples),
        'answer_accuracy': sum(item['answer_correct'] for item in samples) / total_n,
        'joint_correct': sum(item['joint_correct'] for item in samples),
        'joint_accuracy': sum(item['joint_correct'] for item in samples) / total_n,
        'macro_answer_accuracy': statistics.mean(item['answer_accuracy'] for item in samples),
        'macro_joint_accuracy': statistics.mean(item['joint_accuracy'] for item in samples),
    }
    (OUT / 'results.json').write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report['aggregate'], indent=2))


if __name__ == '__main__':
    main()
