#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
from scipy.sparse import hstack
from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import NearestNeighbors

BASE = 'https://datasets-server.huggingface.co'
OUT = Path('artifacts/document_closeout')
CACHE = Path('.document_closeout_cache')
DATASETS = {
    'contract_nli': 'kiddothe2b/contract-nli',
    'finqa': 'dreamerdeo/finqa',
    'scifact': 'davidheineman/scifact-open',
    'tabfact': 'table-benchmark/tabfact',
    'docred': 'Despina/re-docred',
}


def get_json(path: str, params: dict[str, Any], retries: int = 8) -> dict[str, Any]:
    url = BASE + path + '?' + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'hybrid-reasoning-closeout/1.0'})
            with urllib.request.urlopen(req, timeout=180) as response:
                return json.loads(response.read())
        except Exception as exc:
            last = exc
            time.sleep(min(30, 2 ** attempt))
    raise last


def download(url: str, path: Path, retries: int = 8) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'hybrid-reasoning-closeout/1.0'})
            with urllib.request.urlopen(req, timeout=600) as response, path.open('wb') as handle:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    handle.write(block)
            return
        except Exception as exc:
            last = exc
            path.unlink(missing_ok=True)
            time.sleep(min(60, 2 ** attempt))
    raise last


def parquet_entries(repo: str) -> list[dict[str, Any]]:
    return get_json('/parquet', {'dataset': repo}).get('parquet_files', [])


def load_split(alias: str, repo: str, split: str, config: str | None = None):
    entries = [e for e in parquet_entries(repo) if e.get('split') == split and (config is None or e.get('config') == config)]
    if not entries:
        raise RuntimeError(f'No parquet entries for {alias}/{config}/{split}')
    rows = []
    hashes = {}
    for i, entry in enumerate(entries):
        local = CACHE / alias / str(entry.get('config')) / split / f'{i:03d}.parquet'
        download(entry['url'], local)
        hashes[str(local.relative_to(CACHE))] = hashlib.sha256(local.read_bytes()).hexdigest()
        pf = pq.ParquetFile(local)
        for batch in pf.iter_batches(batch_size=4096):
            rows.extend(batch.to_pylist())
    return rows, hashes


def tokenize(text: str) -> set[str]:
    return set(re.findall(r'[a-z0-9]+', text.lower()))


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?;])\s+|\n+', text) if s.strip()]


def select_evidence(premise: str, query: str, k: int = 6):
    q = tokenize(query)
    ranked = []
    for i, sentence in enumerate(sentences(premise)):
        s = tokenize(sentence)
        overlap = len(q & s)
        coverage = overlap / max(1, len(q))
        score = overlap + 3.0 * coverage + 0.05 * min(len(sentence), 500) / 500
        ranked.append((score, i, sentence))
    ranked.sort(reverse=True)
    chosen = sorted(ranked[:k], key=lambda item: item[1])
    return ' '.join(item[2] for item in chosen), [item[1] for item in chosen]


def class_report(y_true, y_pred):
    return {
        'n': len(y_true),
        'accuracy': float(accuracy_score(y_true, y_pred)),
        'macro_f1': float(f1_score(y_true, y_pred, average='macro', zero_division=0)),
        'micro_f1': float(f1_score(y_true, y_pred, average='micro', zero_division=0)),
        'coverage': 1.0,
    }


def make_hashing(ngram=(1, 2), n_features=2**19, analyzer='word'):
    return HashingVectorizer(n_features=n_features, alternate_sign=False, norm='l2', lowercase=True, analyzer=analyzer, ngram_range=ngram, token_pattern=r'(?u)\b\w+\b' if analyzer == 'word' else None)


def fit_sgd_text(train_texts, train_labels, test_texts, seed=20260712):
    word = make_hashing((1, 2), 2**19, 'word')
    char = make_hashing((3, 5), 2**18, 'char_wb')
    x_train = hstack([word.transform(train_texts), char.transform(train_texts)], format='csr')
    x_test = hstack([word.transform(test_texts), char.transform(test_texts)], format='csr')
    clf = SGDClassifier(loss='log_loss', alpha=2e-6, max_iter=40, tol=1e-4, random_state=seed, class_weight='balanced')
    clf.fit(x_train, train_labels)
    return clf.predict(x_test).tolist()


def eval_contract_nli():
    repo = DATASETS['contract_nli']
    results = {'dataset': repo, 'configs': {}, 'protocol': 'Train-only hashed word+character classifier over hypothesis plus top lexical evidence sentences.'}
    hashes = {}
    all_true, all_pred, evidence_rows = [], [], []
    for config in ('contractnli_a', 'contractnli_b'):
        train, h1 = load_split('contract_nli', repo, 'train', config)
        test, h2 = load_split('contract_nli', repo, 'test', config)
        hashes.update(h1); hashes.update(h2)
        train_texts = []
        for row in train:
            evidence, _ = select_evidence(row['premise'], row['hypothesis'])
            train_texts.append(f"HYPOTHESIS: {row['hypothesis']}\nEVIDENCE: {evidence}")
        test_texts = []
        for idx, row in enumerate(test):
            evidence, spans = select_evidence(row['premise'], row['hypothesis'])
            test_texts.append(f"HYPOTHESIS: {row['hypothesis']}\nEVIDENCE: {evidence}")
            if idx < 100:
                evidence_rows.append({'config': config, 'index': idx, 'sentence_indices': spans})
        y_true = [int(row['label']) for row in test]
        y_pred = [int(x) for x in fit_sgd_text(train_texts, [int(row['label']) for row in train], test_texts)]
        results['configs'][config] = class_report(y_true, y_pred)
        all_true.extend(y_true); all_pred.extend(y_pred)
    results['aggregate'] = class_report(all_true, all_pred)
    results['evidence_sample'] = evidence_rows
    results['parquet_sha256'] = hashes
    return results


def normalize_answer(value: Any) -> str:
    text = str(value).strip().lower().replace(',', '').replace('$', '')
    text = re.sub(r'\s+', ' ', text)
    if text.endswith('%'):
        try:
            return f"{float(text[:-1]):.4f}%"
        except ValueError:
            pass
    try:
        number = float(text)
        if abs(number - round(number)) < 1e-9:
            return str(int(round(number)))
        return f'{number:.4f}'.rstrip('0').rstrip('.')
    except ValueError:
        return text


def number_value(text: str):
    cleaned = text.strip().replace(',', '').replace('$', '').replace('%', '')
    cleaned = re.sub(r'^\((.*)\)$', r'-\1', cleaned)
    return float(cleaned) if re.fullmatch(r'[-+]?\d+(?:\.\d+)?', cleaned) else None


def flatten_finqa(row):
    table = row.get('table') or []
    headers = [str(x) for x in table[0]] if table else []
    cells = []
    for r_idx, line in enumerate(table[1:], start=1):
        row_label = str(line[0]) if line else ''
        for c_idx, cell in enumerate(line[1:], start=1):
            value = number_value(str(cell))
            if value is None:
                continue
            header = headers[c_idx] if c_idx < len(headers) else ''
            cells.append({'value': value, 'raw': str(cell), 'row': row_label, 'col': header, 'r': r_idx, 'c': c_idx})
    return cells


def finqa_rank_cells(row):
    cells = flatten_finqa(row)
    q = tokenize(row['question'])
    for cell in cells:
        cell['score'] = len(q & tokenize(cell['row'] + ' ' + cell['col'])) + 2.0 * len(q & tokenize(cell['row'])) + 1.5 * len(q & tokenize(cell['col']))
    return sorted(cells, key=lambda cell: (cell['score'], -cell['r'], -cell['c']), reverse=True)


def format_numeric(value: float, percent=False):
    candidates = []
    for decimals in (0, 1, 2, 3, 4):
        rounded = round(value, decimals)
        text = str(int(rounded)) if abs(rounded - int(round(rounded))) < 1e-9 else f'{rounded:.{decimals}f}'.rstrip('0').rstrip('.')
        candidates.append(text + ('%' if percent else ''))
    return list(dict.fromkeys(candidates))


def infer_finqa_candidates(row):
    ranked = finqa_rank_cells(row)
    q = row['question'].lower()
    values = [cell['value'] for cell in ranked[:8]]
    candidates = []
    if ranked:
        candidates.extend([ranked[i]['raw'] for i in range(min(5, len(ranked)))])
        candidates.extend(format_numeric(ranked[0]['value']))
    pairs = [(values[i], values[j]) for i in range(min(5, len(values))) for j in range(i + 1, min(6, len(values)))]
    if any(key in q for key in ('difference', 'increase', 'decrease', 'change')):
        for a, b in pairs:
            candidates += format_numeric(a - b) + format_numeric(b - a) + format_numeric(abs(a - b))
            if b != 0: candidates += format_numeric((a - b) / abs(b) * 100, True)
            if a != 0: candidates += format_numeric((b - a) / abs(a) * 100, True)
    if any(key in q for key in ('ratio', 'percentage', 'percent', 'as a proportion', 'what portion')):
        for a, b in pairs:
            if b != 0: candidates += format_numeric(a / b * 100, True) + format_numeric(a / b)
            if a != 0: candidates += format_numeric(b / a * 100, True) + format_numeric(b / a)
    if any(key in q for key in ('total', 'sum', 'combined', 'altogether')):
        for a, b in pairs: candidates += format_numeric(a + b)
    if 'average' in q or 'mean' in q:
        for a, b in pairs: candidates += format_numeric((a + b) / 2)
    if any(key in q for key in ('product', 'multiplied', 'times')):
        for a, b in pairs: candidates += format_numeric(a * b)
    if any(key in q for key in ('per ', 'divided', 'quotient')):
        for a, b in pairs:
            if b != 0: candidates += format_numeric(a / b)
            if a != 0: candidates += format_numeric(b / a)
    return list(dict.fromkeys(normalize_answer(x) for x in candidates if str(x).strip())), ranked[:5]


def eval_finqa():
    repo = DATASETS['finqa']
    train, h1 = load_split('finqa', repo, 'train')
    test, h2 = load_split('finqa', repo, 'test')
    tfidf = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2, max_features=120000)
    matrix = tfidf.fit_transform([row['question'] for row in train])
    nn = NearestNeighbors(n_neighbors=1, metric='cosine', algorithm='brute').fit(matrix)
    distances, indices = nn.kneighbors(tfidf.transform([row['question'] for row in test]))
    exact = numeric = covered = 0
    evidence_sample = []
    for i, row in enumerate(test):
        candidates, evidence = infer_finqa_candidates(row)
        gold = normalize_answer(row['answer'])
        if distances[i][0] <= 0.12:
            prediction = normalize_answer(train[int(indices[i][0])]['answer'])
            source = 'near_duplicate_train_question'
        else:
            prediction = candidates[0] if candidates else ''
            source = 'table_numeric_compiler'
        covered += int(bool(prediction)); exact += int(prediction == gold)
        try:
            p = float(prediction.rstrip('%')); g = float(gold.rstrip('%'))
            numeric += int(abs(p - g) <= max(1e-3, 0.01 * abs(g)))
        except ValueError:
            numeric += int(prediction == gold)
        if i < 100:
            evidence_sample.append({'index': i, 'source': source, 'prediction': prediction, 'gold': gold, 'evidence_cells': evidence})
    return {'dataset': repo, 'protocol': 'End-to-end deterministic table/text numeric compiler with train-only near-duplicate fallback; no gold evidence used for prediction.', 'aggregate': {'n': len(test), 'exact_match': exact / len(test), 'numeric_tolerance_accuracy': numeric / len(test), 'coverage': covered / len(test)}, 'evidence_sample': evidence_sample, 'parquet_sha256': {**h1, **h2}}


def eval_tabfact():
    repo = DATASETS['tabfact']
    train, h1 = load_split('tabfact', repo, 'train')
    test, h2 = load_split('tabfact', repo, 'test')
    def text(row):
        table = str(row.get('table') or '')[:7000]
        return f"TITLE: {row.get('table_title') or ''}\nSTATEMENT: {row.get('question') or ''}\nTABLE: {table}"
    y_true = [str(row['answer']) for row in test]
    y_pred = [str(x) for x in fit_sgd_text([text(row) for row in train], [str(row['answer']) for row in train], [text(row) for row in test])]
    return {'dataset': repo, 'protocol': 'Full-test table+statement hashed word/character classifier trained only on official train split.', 'aggregate': class_report(y_true, y_pred), 'parquet_sha256': {**h1, **h2}}


def docred_context(row):
    text = str(row.get('text') or '')
    e1, e2 = str(row.get('entity1') or ''), str(row.get('entity2') or '')
    selected = [sentence for sentence in sentences(text) if e1.lower() in sentence.lower() or e2.lower() in sentence.lower()]
    context = ' '.join(selected[:6]) if selected else text[:4000]
    return f"E1={e1} TYPE1={row.get('entity1Type')} E2={e2} TYPE2={row.get('entity2Type')} CONTEXT={context}"


def eval_docred():
    repo = DATASETS['docred']
    train, h1 = load_split('docred', repo, 'train')
    test, h2 = load_split('docred', repo, 'test')
    y_train = [str(row['relation']) for row in train]
    y_true = [str(row['relation']) for row in test]
    y_pred = [str(x) for x in fit_sgd_text([docred_context(row) for row in train], y_train, [docred_context(row) for row in test], 20260713)]
    report = class_report(y_true, y_pred); report['relation_classes'] = len(set(y_train))
    return {'dataset': repo, 'protocol': 'Pair-conditioned end-to-end document relation classification using supplied entity mentions/types and document text; official train/test split.', 'aggregate': report, 'parquet_sha256': {**h1, **h2}}


def flatten_scifact(rows):
    pairs = []
    for row in rows:
        evidence = row.get('evidence') or {}
        if not isinstance(evidence, dict): continue
        for doc_id, item in evidence.items():
            if not isinstance(item, dict): continue
            label, provenance = item.get('label'), item.get('provenance')
            if label is None or provenance is None: continue
            if isinstance(provenance, (dict, list)): provenance = json.dumps(provenance, ensure_ascii=False)
            pairs.append({'claim_id': str(row.get('id')), 'claim': str(row.get('claim') or ''), 'provenance': str(provenance), 'label': str(label), 'doc_id': str(doc_id)})
    return pairs


def eval_scifact():
    repo = DATASETS['scifact']
    rows, hashes = load_split('scifact', repo, 'claims')
    pairs = flatten_scifact(rows)
    labels = sorted(set(pair['label'] for pair in pairs))
    if len(labels) < 2:
        return {'dataset': repo, 'protocol': 'Grouped cross-validation unavailable.', 'aggregate': {'n': len(pairs), 'error': 'fewer than two labels'}, 'parquet_sha256': hashes}
    texts = [f"CLAIM: {pair['claim']}\nEVIDENCE: {pair['provenance']}" for pair in pairs]
    y = np.array([pair['label'] for pair in pairs]); groups = np.array([pair['claim_id'] for pair in pairs])
    folds = min(5, len(set(groups.tolist()))); predictions = np.empty(len(pairs), dtype=object)
    for fold, (train_idx, test_idx) in enumerate(GroupKFold(n_splits=folds).split(texts, y, groups), start=1):
        pred = fit_sgd_text([texts[i] for i in train_idx], y[train_idx].tolist(), [texts[i] for i in test_idx], 20260712 + fold)
        predictions[test_idx] = pred
    return {'dataset': repo, 'protocol': f'{folds}-fold grouped end-to-end claim/evidence classification; groups are claim IDs, preventing claim leakage. Mirror has no canonical train/test split.', 'aggregate': class_report(y.tolist(), predictions.tolist()), 'pairs': len(pairs), 'claims': len(set(groups.tolist())), 'parquet_sha256': hashes}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.time()
    results = {'protocol': 'Complete full-split document validation. All trainable systems use training labels only; FinQA prediction does not use gold evidence; SciFact uses grouped CV because its mirror exposes one claims split.', 'datasets': {}}
    for name, evaluator in [('contract_nli', eval_contract_nli), ('finqa', eval_finqa), ('scifact', eval_scifact), ('tabfact', eval_tabfact), ('docred', eval_docred)]:
        task_start = time.time()
        try:
            value = evaluator(); value['elapsed_seconds'] = time.time() - task_start; results['datasets'][name] = value
            print(name, json.dumps(value.get('aggregate', {}), sort_keys=True), flush=True)
        except Exception as exc:
            results['datasets'][name] = {'error': f'{type(exc).__name__}: {exc}', 'elapsed_seconds': time.time() - task_start}
            print(name, results['datasets'][name]['error'], flush=True)
    results['elapsed_seconds'] = time.time() - started
    results['code_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (OUT / 'results.json').write_text(json.dumps(results, indent=2, default=str))
    (OUT / 'SUMMARY.json').write_text(json.dumps({name: value.get('aggregate', {'error': value.get('error')}) for name, value in results['datasets'].items()}, indent=2, default=str))

if __name__ == '__main__':
    main()
