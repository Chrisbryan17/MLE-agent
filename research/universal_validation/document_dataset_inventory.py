#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from datasets import get_dataset_config_names, get_dataset_split_names, load_dataset, load_dataset_builder

OUT = Path('artifacts/document_inventory')
DATASETS = {
    'contract_nli': 'kiddothe2b/contract-nli',
    'finqa': 'ibm-research/finqa',
    'scifact': 'allenai/scifact',
    'tabfact': 'wenhu/tab_fact',
    'docred': 'thunlp/docred',
}
SENSITIVE = ('label', 'answer', 'target', 'gold', 'verdict')


def shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {'type': 'dict', 'keys': sorted(value), 'children': {k: shape(v) for k, v in list(value.items())[:20]}}
    if isinstance(value, list):
        return {'type': 'list', 'length': len(value), 'item': shape(value[0]) if value else None}
    if isinstance(value, str):
        return {'type': 'str', 'length': len(value)}
    return {'type': type(value).__name__}


def redact_row(row: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in row.items():
        if any(token in key.lower() for token in SENSITIVE):
            result[key] = {'redacted': True, **shape(value)}
        else:
            result[key] = shape(value)
    return result


def inspect_dataset(alias: str, repo: str) -> dict[str, Any]:
    result: dict[str, Any] = {'alias': alias, 'repo': repo, 'configs': [], 'errors': []}
    try:
        configs = get_dataset_config_names(repo)
    except Exception as exc:
        configs = [None]
        result['errors'].append(f'config_names: {type(exc).__name__}: {exc}')
    if not configs:
        configs = [None]
    for config in configs:
        entry: dict[str, Any] = {'config': config}
        try:
            builder = load_dataset_builder(repo, config)
            entry['features'] = str(builder.info.features)
            entry['description_length'] = len(builder.info.description or '')
            entry['splits_metadata'] = {
                name: {
                    'num_examples': split.num_examples,
                    'num_bytes': split.num_bytes,
                }
                for name, split in (builder.info.splits or {}).items()
            }
        except Exception as exc:
            entry['builder_error'] = f'{type(exc).__name__}: {exc}'
        try:
            splits = get_dataset_split_names(repo, config)
            entry['splits'] = splits
        except Exception as exc:
            splits = list(entry.get('splits_metadata', {}))
            entry['split_error'] = f'{type(exc).__name__}: {exc}'
        entry['row_shapes'] = {}
        for split in splits[:5]:
            try:
                stream = load_dataset(repo, config, split=split, streaming=True)
                row = next(iter(stream))
                entry['row_shapes'][split] = redact_row(row)
            except Exception as exc:
                entry['row_shapes'][split] = {'error': f'{type(exc).__name__}: {exc}'}
        result['configs'].append(entry)
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reports = [inspect_dataset(alias, repo) for alias, repo in DATASETS.items()]
    payload = {
        'protocol': 'Schema/split inventory only. Label-like values are redacted.',
        'datasets': reports,
        'environment': {'python': sys.version, 'platform': platform.platform()},
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (OUT / 'inventory.json').write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps({
        report['alias']: {
            'configs': len(report['configs']),
            'errors': report['errors'],
        }
        for report in reports
    }, indent=2))


if __name__ == '__main__':
    main()
