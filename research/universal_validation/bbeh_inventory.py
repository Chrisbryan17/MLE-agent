#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get('BBEH_ROOT', '.external/bbeh'))
OUT = Path('artifacts/bbeh_inventory')


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def summarize(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {'type': 'dict', 'keys': sorted(value.keys())}
    if isinstance(value, list):
        return {'type': 'list', 'length': len(value), 'item_type': type(value[0]).__name__ if value else None}
    return {'type': type(value).__name__, 'repr': repr(value)[:300]}


def extract_records(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list) and all(isinstance(x, dict) for x in obj):
        return obj
    if isinstance(obj, dict):
        for key in ('examples', 'data', 'instances', 'samples', 'questions'):
            value = obj.get(key)
            if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                return value
    return []


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = []
    key_counts = Counter()
    total_records = 0
    task_candidates = []
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.json', '.jsonl'}:
            continue
        relative = str(path.relative_to(ROOT))
        entry: dict[str, Any] = {
            'path': relative,
            'bytes': path.stat().st_size,
            'sha256': sha256(path),
        }
        try:
            if path.suffix.lower() == '.jsonl':
                records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
                obj: Any = records
            else:
                obj = json.loads(path.read_text(encoding='utf-8'))
            records = extract_records(obj)
            entry['root'] = summarize(obj)
            entry['records'] = len(records)
            total_records += len(records)
            if records:
                schema = Counter(tuple(sorted(record.keys())) for record in records)
                entry['schemas'] = [
                    {'keys': list(keys), 'count': count}
                    for keys, count in schema.most_common()
                ]
                entry['sample'] = records[0]
                for record in records:
                    key_counts.update(record.keys())
                task_candidates.append(relative)
        except Exception as exc:
            entry['parse_error'] = f'{type(exc).__name__}: {exc}'
        files.append(entry)

    payload = {
        'root': str(ROOT),
        'file_count': len(files),
        'total_records_detected': total_records,
        'task_candidate_files': task_candidates,
        'record_key_frequency': dict(key_counts.most_common()),
        'files': files,
        'abstention_baseline': {
            'predictions': 0,
            'coverage': 0.0,
            'policy': 'Every missing prediction counts incorrect.',
        },
    }
    (OUT / 'inventory.json').write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    lines = [
        '# BBEH frozen inventory', '',
        f'- Parsed JSON/JSONL files: **{len(files)}**',
        f'- Detected records: **{total_records}**',
        f'- Candidate task files: **{len(task_candidates)}**',
        '', '## Candidate task files', '',
    ]
    lines.extend(f'- `{name}`' for name in task_candidates)
    (OUT / 'INVENTORY.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({
        'file_count': len(files),
        'total_records': total_records,
        'task_candidates': len(task_candidates),
    }, indent=2))


if __name__ == '__main__':
    main()
