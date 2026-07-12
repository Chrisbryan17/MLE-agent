#!/usr/bin/env python3
"""CLUTRR evaluator using official Hugging Face Parquet exports.

This changes only data transport, not the frozen composition protocol in
clutrr_eval.py. It avoids Dataset Viewer row-endpoint rate limits.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

import clutrr_eval as evaluator

DATASET = evaluator.DATASET
BASE = evaluator.BASE


def get_json(path, params, retries=8):
    url = BASE + path + '?' + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'SOL-research/0.1'})
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read())
        except Exception as exc:
            last = exc
            time.sleep(min(30, 2 ** attempt))
    raise last


def parquet_manifest():
    cache = Path('.clutrr_cache/parquet_manifest.json')
    cache.parent.mkdir(exist_ok=True)
    if not cache.exists():
        cache.write_text(json.dumps(get_json('/parquet', {'dataset': DATASET}), indent=2))
    return json.loads(cache.read_text())


def download(url, path, retries=8):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'SOL-research/0.1'})
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
    raise last


def load_split(config, split):
    rows_cache = Path('.clutrr_cache') / f'{config}__{split}.jsonl'
    if rows_cache.exists():
        return [json.loads(line) for line in rows_cache.read_text().splitlines() if line]

    manifest = parquet_manifest()
    entries = [
        item for item in manifest.get('parquet_files', [])
        if item.get('config') == config and item.get('split') == split
    ]
    if not entries:
        raise RuntimeError(f'No Parquet exports found for {config}/{split}')

    rows = []
    for index, item in enumerate(entries):
        local = Path('.clutrr_cache/parquet') / config / split / f'{index:03d}.parquet'
        download(item['url'], local)
        parquet_file = pq.ParquetFile(local)
        for batch in parquet_file.iter_batches(batch_size=8192):
            rows.extend(batch.to_pylist())

    with rows_cache.open('w') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=str) + '\n')
    return rows


evaluator.load_split = load_split

if __name__ == '__main__':
    evaluator.main()
