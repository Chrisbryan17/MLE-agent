#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

DATASET = 'livebench/reasoning'
BASE = 'https://datasets-server.huggingface.co'
OUT = Path('artifacts/livebench_spatial_inputs')
CACHE = Path('.livebench_spatial_cache')
PUBLIC_CUTOFF = '2024-11-25'


def get_json(path, params, retries=8):
    url = BASE + path + '?' + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'hybrid-reasoning-validation/0.1'})
            with urllib.request.urlopen(req, timeout=180) as response:
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
            req = urllib.request.Request(url, headers={'User-Agent': 'hybrid-reasoning-validation/0.1'})
            with urllib.request.urlopen(req, timeout=300) as response, path.open('wb') as handle:
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
    rows = []
    hashes = {}
    for index, entry in enumerate(manifest.get('parquet_files', [])):
        local = CACHE / f'{index:03d}.parquet'
        download(entry['url'], local)
        hashes[local.name] = hashlib.sha256(local.read_bytes()).hexdigest()
        parquet = pq.ParquetFile(local)
        for batch in parquet.iter_batches(batch_size=2048):
            for row in batch.to_pylist():
                release = str(row.get('livebench_release_date') or row.get('release_date') or '')[:10]
                if row.get('task') != 'spatial' or (release and release > PUBLIC_CUTOFF):
                    continue
                turns = row.get('turns') or []
                rows.append({
                    'question_id': row.get('question_id'),
                    'release': release,
                    'input': turns[0] if turns else '',
                })
    payload = {
        'protocol': 'Unlabeled inputs only. Ground-truth field never serialized.',
        'dataset': DATASET,
        'repository_commit': '864b0d7203c66b429d93c43841df0a773f7738c7',
        'public_cutoff': PUBLIC_CUTOFF,
        'count': len(rows),
        'inputs': rows,
        'parquet_sha256': hashes,
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (OUT / 'inputs.json').write_text(json.dumps(payload, indent=2))
    print(json.dumps({'count': len(rows)}, indent=2))


if __name__ == '__main__':
    main()
