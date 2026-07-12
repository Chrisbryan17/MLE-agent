#!/usr/bin/env python3
"""Fetch CLUTRR public Dataset Viewer metadata and representative rows."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://datasets-server.huggingface.co'
DATASET = 'CLUTRR/v1'


def get(path, params):
    url = BASE + path + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'User-Agent': 'SOL-research/0.1'})
    return json.loads(urllib.request.urlopen(request, timeout=120).read())


def main():
    out = Path('artifacts/clutrr_probe')
    out.mkdir(parents=True, exist_ok=True)
    splits = get('/splits', {'dataset': DATASET})
    (out / 'splits.json').write_text(json.dumps(splits, indent=2))
    rows = []
    seen = set()
    for item in splits.get('splits', []):
        config, split = item['config'], item['split']
        key = (config, split)
        if key in seen:
            continue
        seen.add(key)
        try:
            preview = get('/first-rows', {'dataset': DATASET, 'config': config, 'split': split})
            sample = {
                'config': config,
                'split': split,
                'features': preview.get('features'),
                'rows': preview.get('rows', [])[:5],
            }
            rows.append(sample)
        except Exception as exc:
            rows.append({'config': config, 'split': split, 'error': f'{type(exc).__name__}: {exc}'})
    (out / 'preview.json').write_text(json.dumps(rows, indent=2))
    print(json.dumps({'dataset': DATASET, 'split_count': len(seen), 'previews': len(rows)}, indent=2))


if __name__ == '__main__':
    main()
