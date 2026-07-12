#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

import document_end_to_end_eval as base

CURRENT_ALIAS = ''
CURRENT_NAMES: list[str] = []
ORIGINAL_NORMALIZE = base.normalize_answer
ORIGINAL_RUN_DATASET = base.run_dataset

FALLBACK = {
    'contract_nli': ['entailment', 'contradiction', 'not_mentioned'],
    'tabfact': ['refuted', 'entailed'],
    'scifact': ['supports', 'refutes', 'not_enough_information'],
}


def find_class_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        names = value.get('names')
        marker = str(value.get('_type') or value.get('type') or value.get('dtype') or '').lower()
        if isinstance(names, list) and names and ('classlabel' in marker or 'class_label' in marker):
            return [str(item) for item in names]
        for key, item in value.items():
            if str(key).lower() in {'label', 'labels', 'verdict', 'target', 'relation'}:
                found = find_class_names(item)
                if found:
                    return found
        for item in value.values():
            found = find_class_names(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_class_names(item)
            if found:
                return found
    return []


def discover_names(repo: str) -> list[str]:
    try:
        info = base.get_json('/info', {'dataset': repo})
        return find_class_names(info)
    except Exception:
        return []


def normalize_answer(value: Any) -> str:
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        names = CURRENT_NAMES or FALLBACK.get(CURRENT_ALIAS, [])
        if 0 <= value < len(names):
            value = names[value]
    elif isinstance(value, float) and value.is_integer():
        names = CURRENT_NAMES or FALLBACK.get(CURRENT_ALIAS, [])
        index = int(value)
        if 0 <= index < len(names):
            value = names[index]
    normalized = ORIGINAL_NORMALIZE(value)
    aliases = {
        'neutral': 'not_mentioned' if CURRENT_ALIAS == 'contract_nli' else 'not_enough_information',
        'not_entailment': 'not_mentioned',
        'unknown': 'not_mentioned' if CURRENT_ALIAS == 'contract_nli' else 'not_enough_information',
        'support': 'supports', 'supported': 'supports',
        'contradict': 'refutes', 'contradiction': 'refutes' if CURRENT_ALIAS == 'scifact' else 'contradiction',
        'refute': 'refutes', 'entail': 'entailment' if CURRENT_ALIAS == 'contract_nli' else 'entailed',
        'entails': 'entailment' if CURRENT_ALIAS == 'contract_nli' else 'entailed',
        'true': 'entailed', 'false': 'refuted',
        '1': 'entailed' if CURRENT_ALIAS == 'tabfact' else '1',
        '0': 'refuted' if CURRENT_ALIAS == 'tabfact' else '0',
    }
    return aliases.get(normalized, normalized)


def run_dataset(alias: str, repo: str):
    global CURRENT_ALIAS, CURRENT_NAMES
    CURRENT_ALIAS = alias
    CURRENT_NAMES = discover_names(repo)
    if not CURRENT_NAMES:
        CURRENT_NAMES = FALLBACK.get(alias, [])
    result = ORIGINAL_RUN_DATASET(alias, repo)
    result['decoded_class_names'] = CURRENT_NAMES
    return result


base.normalize_answer = normalize_answer
base.run_dataset = run_dataset

if __name__ == '__main__':
    base.main()
