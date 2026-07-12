#!/usr/bin/env python3
"""SOL v2: domain-invariant semantic compiler overrides for the official benchmark."""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import re

import sol_benchmark as base


def ordinal_number(text: str):
    z = text.lower().replace('_', ' ').replace('-', ' ')
    for word, k in base.ORD.items():
        if re.search(rf'\b{word}\b', z):
            return k
    match = re.search(r'\b(\d+)(?:st|nd|rd|th)?\b', z)
    return int(match.group(1)) if match else None


def rank_index(text: str, n: int):
    z = re.sub(r'\s+', ' ', text.lower().replace('_', ' ').replace('-', ' ')).strip(' .')
    if 'leftmost' in z:
        return 0
    if 'rightmost' in z:
        return n - 1
    if re.search(r'\b(?:finished\s+)?first\b', z):
        return 0
    if re.search(r'\b(?:finished\s+)?last\b', z) and 'to last' not in z:
        return n - 1
    if 'newest' in z and not re.search(r'\b(?:second|third|fourth|fifth|sixth|seventh|\d+)\s+newest\b', z):
        return 0
    if 'oldest' in z and not re.search(r'\b(?:second|third|fourth|fifth|sixth|seventh|\d+)\s+oldest\b', z):
        return n - 1
    if 'most expensive' in z and not re.search(r'\b(?:second|third|fourth|fifth|sixth|seventh|\d+)\s+most expensive\b', z):
        return 0
    if 'cheapest' in z and not re.search(r'\b(?:second|third|fourth|fifth|sixth|seventh|\d+)\s+cheapest\b', z):
        return n - 1
    k = ordinal_number(z)
    if k is None:
        return None
    if 'from the right' in z or 'to last' in z or 'oldest' in z or 'cheapest' in z:
        return n - k
    if any(x in z for x in ('from the left', 'finished', 'newest', 'most expensive')):
        return k - 1
    return None


def parse_order_choice(choice: str, n: int):
    patterns = (
        r'^The\s+(.+?)\s+(?:is|are)\s+(?:the\s+)?(.+?)[.]?$',
        r'^(.+?)\s+finished\s+(.+?)[.]?$',
    )
    for pattern in patterns:
        match = re.match(pattern, choice.strip(), re.I)
        if match:
            idx = rank_index(choice, n)
            if idx is not None:
                return match.group(1).strip(), idx
    return None, None


def entities(choices):
    n = len(choices)
    result = []
    for choice in choices:
        entity, _ = parse_order_choice(choice, n)
        if entity and entity not in result:
            result.append(entity)
    return result


def mentions(sentence, entity_names):
    hits = []
    lower = sentence.lower()
    for entity in sorted(entity_names, key=len, reverse=True):
        match = re.search(r'(?<![A-Za-z0-9])' + re.escape(entity.lower()) + r'(?![A-Za-z0-9])', lower)
        if match:
            hits.append((match.start(), entity))
    return [entity for _, entity in sorted(hits)]


def order_compile(ex):
    choices = list(ex['target_scores'])
    entity_names = entities(choices)
    n = len(entity_names)
    precedence, fixed, unparsed = [], {}, []
    for sentence in re.split(r'(?<=[.!?])\s+', ex['input']):
        found = mentions(sentence, entity_names)
        if not found:
            continue
        if len(found) > 2 and re.search(r'\b(?:there (?:are|is|were)|sells|includes)\b', sentence, re.I):
            continue
        lower = sentence.lower()
        relation = any(
            phrase in lower
            for phrase in (
                'left of', 'right of', 'before', 'after', 'finished above', 'finished below',
                'newer than', 'older than', 'more expensive than', 'less expensive than',
            )
        )
        idx = rank_index(sentence, n)
        if idx is not None and not relation:
            fixed[found[0]] = idx
            continue
        if len(found) >= 2:
            a, b = found[:2]
            if any(x in lower for x in ('left of', 'before', 'finished above', 'newer than', 'more expensive than')):
                precedence.append((a, b))
                continue
            if any(x in lower for x in ('right of', 'after', 'finished below', 'older than', 'less expensive than')):
                precedence.append((b, a))
                continue
        unparsed.append(sentence)
    valid = []
    for ordering in itertools.permutations(entity_names):
        positions = {entity: i for i, entity in enumerate(ordering)}
        if all(positions[a] < positions[b] for a, b in precedence) and all(positions[e] == i for e, i in fixed.items()):
            valid.append(ordering)
    return choices, entity_names, precedence, fixed, unparsed, valid


def stable_choice(ex):
    choices = sorted(ex['target_scores'])
    digest = hashlib.sha256(ex['input'].encode()).digest()
    return choices[int.from_bytes(digest[:8], 'big') % len(choices)]


def solve_order(ex):
    choices, entity_names, precedence, fixed, unparsed, valid = order_compile(ex)
    parsed = [parse_order_choice(choice, len(entity_names)) for choice in choices]
    query_indices = {idx for _, idx in parsed if idx is not None}
    if not valid or len(query_indices) != 1:
        return None, {
            'cell': 'order', 'failure': 'no unique orbit/query', 'unparsed': unparsed,
            'entities': entity_names,
        }
    query_index = next(iter(query_indices))
    possible = {ordering[query_index] for ordering in valid}
    if len(possible) != 1:
        return None, {
            'cell': 'order', 'failure': 'ambiguous', 'orbits': len(valid),
            'possible': sorted(possible),
        }
    entity = next(iter(possible))
    answer = next((choice for choice, (candidate, _) in zip(choices, parsed) if candidate == entity), None)
    return answer, {
        'cell': 'finite-order-orbit', 'constraints': precedence, 'fixed': fixed,
        'orbits': len(valid), 'residual': 0,
    }


def ablate_order(ex):
    choices, entity_names, _, fixed, _, _ = order_compile(ex)
    parsed = [parse_order_choice(choice, len(entity_names)) for choice in choices]
    query_indices = {idx for _, idx in parsed if idx is not None}
    if len(query_indices) == 1:
        query_index = next(iter(query_indices))
        matches = [entity for entity, position in fixed.items() if position == query_index]
        if len(matches) == 1:
            answer = next((c for c, (entity, _) in zip(choices, parsed) if entity == matches[0]), None)
            if answer:
                return answer, {'cell': 'absolute-only'}
    return stable_choice(ex), {'cell': 'absolute-only'}


def initial_assignment(ex):
    choices = list(ex['target_scores'])
    assignment = {}
    verbs = r'(?:has|gets|is\s+playing|is\s+dancing\s+with|is\s+holding|is\s+wearing|holds)'
    for choice in choices:
        value = base.object_name(choice)
        match = re.search(
            rf'\b([A-Z][a-zA-Z\'-]*)\s+{verbs}\s+(?:(?:a|an|the)\s+)?{re.escape(value)}(?=\s*[,.;])',
            ex['input'], re.I,
        )
        if match:
            assignment[match.group(1)] = value
    return choices, assignment


def query_person(text, people):
    start = text.lower().rfind('at the end')
    tail = text[start:] if start >= 0 else text
    found = mentions(tail, people)
    return found[0] if found else None


def swap_sequence(text, people):
    canonical = {p.lower(): p for p in people}
    swaps = []
    for match in re.finditer(
        r'\b([A-Z][a-zA-Z\'-]*)\s+and\s+([A-Z][a-zA-Z\'-]*)\s+(?:swap|trade|switch)\b',
        text, re.I,
    ):
        a, b = match.group(1).lower(), match.group(2).lower()
        if a in canonical and b in canonical:
            swaps.append((canonical[a], canonical[b]))
    return swaps


def solve_shuffle(ex):
    choices, assignment = initial_assignment(ex)
    if len(assignment) != len(choices):
        return None, {'cell': 'permutation', 'failure': 'assignment', 'got': assignment}
    people = list(assignment)
    index = {person: i for i, person in enumerate(people)}
    state = [assignment[person] for person in people]
    permutation = list(range(len(people)))
    swaps = swap_sequence(ex['input'], people)
    for a, b in swaps:
        i, j = index[a], index[b]
        state[i], state[j] = state[j], state[i]
        permutation[i], permutation[j] = permutation[j], permutation[i]
    person = query_person(ex['input'], people)
    if person is None:
        return None, {'cell': 'permutation', 'failure': 'query'}
    value = state[index[person]]
    answer = next((choice for choice in choices if base.object_name(choice).lower() == value.lower()), None)
    return answer, {
        'cell': f'S_{len(people)} transport', 'swaps': swaps,
        'permutation': permutation, 'conserved': sorted(state) == sorted(assignment.values()),
        'residual': 0,
    }


def ablate_shuffle(ex):
    choices, assignment = initial_assignment(ex)
    people = list(assignment)
    swaps = swap_sequence(ex['input'], people)
    if swaps:
        a, b = swaps[-1]
        assignment[a], assignment[b] = assignment[b], assignment[a]
    person = query_person(ex['input'], people)
    value = assignment.get(person) if person else None
    if value:
        answer = next((choice for choice in choices if base.object_name(choice).lower() == value.lower()), None)
        if answer:
            return answer, {'cell': 'last-swap-only'}
    return stable_choice(ex), {'cell': 'last-swap-only'}


def infer_today(text):
    anchor = base.parse_date(text)
    premise = text.lower().split('what is', 1)[0]
    if not anchor:
        return None, 'no anchor'
    if 'day before yesterday' in premise:
        return anchor + dt.timedelta(2), 'day-before-yesterday+2'
    if 'day after tomorrow' in premise:
        return anchor - dt.timedelta(2), 'day-after-tomorrow-2'
    if 'yesterday was' in premise or re.search(r'\byesterday[, ]', premise):
        return anchor + dt.timedelta(1), 'yesterday+1'
    if re.search(r'\btomorrow (?:is|will be|was)', premise):
        return anchor - dt.timedelta(1), 'tomorrow-1'
    if re.search(r'\btoday\b|current date is|if today is|\bit is\s+\d{1,2}/\d{1,2}/\d{4}\s+today\b', premise):
        return anchor, 'today'
    match = re.search(r'which is (\d+) days? away from now', premise)
    if match:
        return anchor - dt.timedelta(int(match.group(1))), f'future-{match.group(1)}'
    match = re.search(r'which was (\d+) days? ago', premise)
    if match:
        return anchor + dt.timedelta(int(match.group(1))), f'past+{match.group(1)}'
    match = re.search(r'(\d+) days? from (?:today|now)', premise)
    if match:
        return anchor - dt.timedelta(int(match.group(1))), f'future-{match.group(1)}'
    return None, 'unsupported anchor'


def ablate_date(ex):
    choices = list(ex['target_scores'])
    anchor = base.parse_date(ex['input'])
    target = anchor.strftime('%m/%d/%Y') if anchor else ''
    answer = next((choice for choice in choices if choice.strip() == target), None)
    return (answer if answer else stable_choice(ex)), {'cell': 'anchor-only'}


base.entities = entities
base.mentions = mentions
base.order_compile = order_compile
base.solve_order = solve_order
base.ablate_order = ablate_order
base.initial_assignment = initial_assignment
base.solve_shuffle = solve_shuffle
base.ablate_shuffle = ablate_shuffle
base.infer_today = infer_today
base.ablate_date = ablate_date
for key in ('logical_3', 'logical_5', 'logical_7'):
    base.SOLVERS[key] = solve_order
    base.ABLATIONS[key] = ablate_order
for key in ('shuffle_3', 'shuffle_5', 'shuffle_7'):
    base.SOLVERS[key] = solve_shuffle
    base.ABLATIONS[key] = ablate_shuffle
base.ABLATIONS['date'] = ablate_date

if __name__ == '__main__':
    base.main()
