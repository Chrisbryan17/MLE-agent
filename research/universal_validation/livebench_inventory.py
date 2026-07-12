#!/usr/bin/env python3
from __future__ import annotations

import collections
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

DATASET = 'livebench/reasoning'
BASE = 'https://datasets-server.huggingface.co'
OUT = Path('artifacts/livebench_inventory')
CACHE = Path('.livebench_cache')


def get_json(path, params, retries=8):
    url = BASE + path + '?' + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'hybrid-reasoning-validation/0.1'})
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read())
        except Exception as exc:
            last = exc
            time.sleep(min(30, 2 ** attempt))
    raise last


def download(url, path, retries=8):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'hybrid-reasoning-validation/0.1'})
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = get_json('/parquet', {'dataset': DATASET})
    entries = manifest.get('parquet_files', [])
    task_counts = collections.Counter()
    releases = collections.Counter()
    schemas = []
    hashes = {}
    row_shapes = {}
    total = 0
    for index, entry in enumerate(entries):
        local = CACHE / f'{index:03d}.parquet'
        download(entry['url'], local)
        hashes[local.name] = hashlib.sha256(local.read_bytes()).hexdigest()
        parquet = pq.ParquetFile(local)
        schemas.append(str(parquet.schema_arrow))
        for batch in parquet.iter_batches(batch_size=2048):
            for row in batch.to_pylist():
                total += 1
                task_counts[str(row.get('task'))] += 1
                releases[str(row.get('livebench_release_date') or row.get('release_date'))] += 1
                task = str(row.get('task'))
                if task not in row_shapes:
                    row_shapes[task] = {
                        key: {
                            'type': type(value).__name__,
                            'length': len(value) if hasattr(value, '__len__') else None,
                            'redacted': any(token in key.lower() for token in ('ground_truth', 'answer', 'target', 'label')),
                        }
                        for key, value in row.items()
                    }
    payload = {
        'dataset': DATASET,
        'repository_commit': '864b0d7203c66b429d93c43841df0a773f7738c7',
        'public_release_policy': 'Use the latest fully public release documented by the repository: 2024-11-25.',
        'parquet_files': len(entries),
        'rows': total,
        'task_counts': dict(task_counts),
        'release_counts': dict(releases),
        'row_shapes': row_shapes,
        'schemas': sorted(set(schemas)),
        'parquet_sha256': hashes,
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (OUT / 'inventory.json').write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps({'rows': total, 'tasks': dict(task_counts), 'releases': dict(releases)}, indent=2))


if __name__ == '__main__':
    main()
