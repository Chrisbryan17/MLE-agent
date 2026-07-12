#!/usr/bin/env python3
from __future__ import annotations
import calendar, datetime as dt, itertools, json, random, re, urllib.request
from pathlib import Path

BASE = 'https://raw.githubusercontent.com/google/BIG-bench/main/bigbench/benchmark_tasks'
URLS = {
    'logical_3': f'{BASE}/logical_deduction/three_objects/task.json',
    'logical_5': f'{BASE}/logical_deduction/five_objects/task.json',
    'logical_7': f'{BASE}/logical_deduction/seven_objects/task.json',
    'shuffle_3': f'{BASE}/tracking_shuffled_objects/three_objects/task.json',
    'shuffle_5': f'{BASE}/tracking_shuffled_objects/five_objects/task.json',
    'shuffle_7': f'{BASE}/tracking_shuffled_objects/seven_objects/task.json',
    'date': f'{BASE}/date_understanding/task.json',
}
ORD = {
    'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
    'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9,
}
MONTHS = {n.lower(): i for i, n in enumerate(calendar.month_name) if n}
MONTHS.update({n.lower(): i for i, n in enumerate(calendar.month_abbr) if n})


def norm(x):
    return re.sub(r'\s+', ' ', x.strip()).lower().rstrip(' .') if x else ''


def gold(ex):
    return next(k for k, v in ex['target_scores'].items() if float(v) == 1)


def load(name):
    p = Path('.cache') / f'{name}.json'
    p.parent.mkdir(exist_ok=True)
    if not p.exists():
        req = urllib.request.Request(URLS[name], headers={'User-Agent': 'SOL-research/0.1'})
        p.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return json.loads(p.read_text())['examples']


def posidx(s, n):
    z = s.lower()
    if 'leftmost' in z:
        return 0
    if 'rightmost' in z:
        return n - 1
    if 'middle' in z and n % 2:
        return n // 2
    for word, k in ORD.items():
        if re.search(rf'\b{word} from the left\b', z):
            return k - 1
        if re.search(rf'\b{word} from the right\b', z):
            return n - k
    return None


def entities(choices):
    out = []
    for c in choices:
        m = re.match(r'\s*The\s+(.+?)\s+is\s+', c, re.I)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def mentions(sentence, entity_names):
    hits = []
    lower = sentence.lower()
    for entity in sorted(entity_names, key=len, reverse=True):
        i = lower.find(entity.lower())
        if i >= 0:
            hits.append((i, entity))
    return [entity for _, entity in sorted(hits)]


def order_compile(ex):
    choices = list(ex['target_scores'])
    entity_names = entities(choices)
    n = len(entity_names)
    precedence = []
    fixed = {}
    unparsed = []
    for sentence in re.split(r'(?<=[.!?])\s+', ex['input']):
        if re.search(r'\bthere (?:are|is)\b', sentence, re.I):
            continue
        found = mentions(sentence, entity_names)
        if not found:
            continue
        p = posidx(sentence, n)
        if p is not None:
            fixed[found[0]] = p
            continue
        if len(found) >= 2:
            lower = sentence.lower()
            a, b = found[:2]
            if 'left of' in lower or 'before' in lower:
                precedence.append((a, b))
                continue
            if 'right of' in lower or 'after' in lower:
                precedence.append((b, a))
                continue
        unparsed.append(sentence)
    valid = []
    for ordering in itertools.permutations(entity_names):
        pos = {entity: i for i, entity in enumerate(ordering)}
        if all(pos[a] < pos[b] for a, b in precedence) and all(pos[e] == i for e, i in fixed.items()):
            valid.append(ordering)
    return choices, entity_names, precedence, fixed, unparsed, valid


def solve_order(ex):
    choices, entity_names, precedence, fixed, unparsed, valid = order_compile(ex)
    query_index = posidx(choices[0], len(entity_names))
    if not valid or query_index is None:
        return None, {'cell': 'order', 'failure': 'no orbit', 'unparsed': unparsed}
    possible = {ordering[query_index] for ordering in valid}
    if len(possible) != 1:
        return None, {
            'cell': 'order', 'failure': 'ambiguous', 'orbits': len(valid),
            'possible': sorted(possible),
        }
    entity = next(iter(possible))
    answer = next((c for c in choices if norm(c).startswith(norm(f'The {entity} is '))), None)
    return answer, {
        'cell': 'finite-order-orbit', 'constraints': precedence, 'fixed': fixed,
        'orbits': len(valid), 'residual': 0,
    }


def ablate_order(ex):
    choices, entity_names, _, fixed, _, _ = order_compile(ex)
    query_index = posidx(choices[0], len(entity_names))
    matches = [e for e, p in fixed.items() if p == query_index]
    answer = next(
        (c for c in choices if matches and norm(c).startswith(norm(f'The {matches[0]} is '))),
        choices[0],
    )
    return answer, {'cell': 'absolute-only'}


def object_name(choice):
    return re.sub(r'[.?!]+$', '', choice.strip())


def initial_assignment(ex):
    choices = list(ex['target_scores'])
    initial = ex['input'].split('As the game progresses', 1)[0]
    assignment = {}
    for choice in choices:
        obj = object_name(choice)
        match = re.search(
            rf'\b([A-Z][a-zA-Z\'-]*) has (?:a|an|the) {re.escape(obj)}\b',
            initial,
            re.I,
        )
        if match:
            assignment[match.group(1)] = obj
    return choices, assignment


def solve_shuffle(ex):
    choices, assignment = initial_assignment(ex)
    if len(assignment) != len(choices):
        return None, {'cell': 'permutation', 'failure': 'assignment', 'got': assignment}
    people = list(assignment)
    index = {p.lower(): i for i, p in enumerate(people)}
    state = [assignment[p] for p in people]
    permutation = list(range(len(people)))
    swaps = []
    for match in re.finditer(
        r'\b([A-Z][a-zA-Z\'-]*) and ([A-Z][a-zA-Z\'-]*) swap',
        ex['input'],
        re.I,
    ):
        a, b = match.group(1).lower(), match.group(2).lower()
        if a not in index or b not in index:
            continue
        i, j = index[a], index[b]
        state[i], state[j] = state[j], state[i]
        permutation[i], permutation[j] = permutation[j], permutation[i]
        swaps.append((people[i], people[j]))
    query = re.search(
        r'At the end of the game,\s*([A-Z][a-zA-Z\'-]*) has the\s*$',
        ex['input'].strip(),
        re.I,
    )
    if not query or query.group(1).lower() not in index:
        return None, {'cell': 'permutation', 'failure': 'query'}
    value = state[index[query.group(1).lower()]]
    answer = next((c for c in choices if object_name(c).lower() == value.lower()), None)
    return answer, {
        'cell': f'S_{len(people)} transport', 'swaps': swaps,
        'permutation': permutation, 'conserved': sorted(state) == sorted(assignment.values()),
        'residual': 0,
    }


def ablate_shuffle(ex):
    choices, assignment = initial_assignment(ex)
    people = list(assignment)
    index = {p.lower(): p for p in people}
    swaps = list(re.finditer(
        r'\b([A-Z][a-zA-Z\'-]*) and ([A-Z][a-zA-Z\'-]*) swap',
        ex['input'],
        re.I,
    ))
    if swaps:
        a, b = swaps[-1].group(1).lower(), swaps[-1].group(2).lower()
        if a in index and b in index:
            assignment[index[a]], assignment[index[b]] = assignment[index[b]], assignment[index[a]]
    query = re.search(
        r'At the end of the game,\s*([A-Z][a-zA-Z\'-]*) has the\s*$',
        ex['input'].strip(),
        re.I,
    )
    value = assignment.get(index.get(query.group(1).lower())) if query else None
    answer = next((c for c in choices if value and object_name(c).lower() == value.lower()), choices[0])
    return answer, {'cell': 'last-swap-only'}


def parse_date(text):
    pattern = r'\b(' + '|'.join(sorted(map(re.escape, MONTHS), key=len, reverse=True)) + r')\s+(\d{1,2}),\s*(\d{4})\b'
    match = re.search(pattern, text, re.I)
    if match:
        return dt.date(int(match.group(3)), MONTHS[match.group(1).lower()], int(match.group(2)))
    match = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', text)
    if match:
        return dt.date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
    return None


def add_months(date, k):
    absolute = date.year * 12 + date.month - 1 + k
    year, month0 = divmod(absolute, 12)
    month = month0 + 1
    return dt.date(year, month, min(date.day, calendar.monthrange(year, month)[1]))


def add_years(date, k):
    year = date.year + k
    return dt.date(year, date.month, min(date.day, calendar.monthrange(year, date.month)[1]))


def infer_today(text):
    anchor = parse_date(text)
    lower = text.lower()
    if not anchor:
        return None, 'no anchor'
    if 'yesterday was' in lower:
        return anchor + dt.timedelta(1), 'yesterday+1'
    if re.search(r'\btomorrow (?:is|will be|was)', lower):
        return anchor - dt.timedelta(1), 'tomorrow-1'
    if re.search(r'\btoday (?:is|was)|current date is', lower):
        return anchor, 'today'
    match = re.search(r'which is (\d+) days? away from now', lower)
    if match:
        return anchor - dt.timedelta(int(match.group(1))), f'future-{match.group(1)}'
    match = re.search(r'which was (\d+) days? ago', lower)
    if match:
        return anchor + dt.timedelta(int(match.group(1))), f'past+{match.group(1)}'
    return None, 'unsupported anchor'


def resolve_date_query(today, text):
    parts = text.lower().split('what is the date', 1)
    query = parts[1] if len(parts) == 2 else text.lower()
    if re.search(r'(?:one|a) week ago', query):
        return today - dt.timedelta(7), '-week'
    if re.search(r'(?:one|a) week (?:from|after)', query):
        return today + dt.timedelta(7), '+week'
    if re.search(r'(?:one|a) month ago|a month ago', query):
        return add_months(today, -1), '-month'
    if re.search(r'(?:one|a) month (?:from|after)', query):
        return add_months(today, 1), '+month'
    if 'one year ago' in query:
        return add_years(today, -1), '-year'
    if re.search(r'one year (?:from|after)', query):
        return add_years(today, 1), '+year'
    match = re.search(r'(\d+) days? ago', query)
    if match:
        return today - dt.timedelta(int(match.group(1))), f'-{match.group(1)}d'
    match = re.search(r'(\d+) days? (?:later|from (?:today|now)|in the future)', query)
    if match:
        return today + dt.timedelta(int(match.group(1))), f'+{match.group(1)}d'
    match = re.search(r'(\d+) hours? later', query)
    if match and int(match.group(1)) % 24 == 0:
        return today + dt.timedelta(int(match.group(1)) // 24), f'+{match.group(1)}h'
    if 'tomorrow' in query:
        return today + dt.timedelta(1), '+day'
    if 'yesterday' in query:
        return today - dt.timedelta(1), '-day'
    if 'today' in query:
        return today, 'today'
    return None, 'unsupported query'


def solve_date(ex):
    today, anchor_proof = infer_today(ex['input'])
    target, query_proof = resolve_date_query(today, ex['input']) if today else (None, '')
    if not target:
        return None, {'cell': 'calendar', 'failure': anchor_proof or query_proof}
    target_string = target.strftime('%m/%d/%Y')
    answer = next((c for c in ex['target_scores'] if c.strip() == target_string), None)
    return answer, {
        'cell': 'calendar-affine', 'today': today.isoformat(),
        'transport': query_proof, 'target': target_string, 'residual_days': 0,
    }


def ablate_date(ex):
    choices = list(ex['target_scores'])
    anchor = parse_date(ex['input'])
    target = anchor.strftime('%m/%d/%Y') if anchor else ''
    return next((c for c in choices if c.strip() == target), choices[0]), {'cell': 'anchor-only'}


SOLVERS = {
    'logical_3': solve_order, 'logical_5': solve_order, 'logical_7': solve_order,
    'shuffle_3': solve_shuffle, 'shuffle_5': solve_shuffle, 'shuffle_7': solve_shuffle,
    'date': solve_date,
}
ABLATIONS = {
    'logical_3': ablate_order, 'logical_5': ablate_order, 'logical_7': ablate_order,
    'shuffle_3': ablate_shuffle, 'shuffle_5': ablate_shuffle, 'shuffle_7': ablate_shuffle,
    'date': ablate_date,
}


def perturb(name, ex, rng):
    ex = {**ex, 'target_scores': dict(ex['target_scores'])}
    if name.startswith('logical'):
        entity_names = entities(ex['target_scores'])
        mapping = {e: f'object-{rng.randrange(10**8, 10**9)}' for e in entity_names}
        text = ex['input']
        scores = {}
        for old in sorted(mapping, key=len, reverse=True):
            text = re.sub(re.escape(old), mapping[old], text, flags=re.I)
        for choice, value in ex['target_scores'].items():
            new_choice = choice
            for old in sorted(mapping, key=len, reverse=True):
                new_choice = re.sub(re.escape(old), mapping[old], new_choice, flags=re.I)
            scores[new_choice] = value
        ex['input'] = text
        ex['target_scores'] = scores
    ex['input'] = re.sub(r'\s+', ' ', ex['input']).replace('. ', '.   ')
    return ex


def evaluate(examples, solver):
    correct = 0
    covered = 0
    errors = []
    predictions = []
    for i, ex in enumerate(examples):
        answer, proof = solver(ex)
        predictions.append(answer)
        is_correct = norm(answer) == norm(gold(ex))
        correct += int(is_correct)
        covered += int(answer is not None)
        if not is_correct and len(errors) < 40:
            errors.append({
                'i': i, 'input': ex['input'], 'gold': gold(ex),
                'pred': answer, 'proof': proof,
            })
    return {
        'n': len(examples), 'accuracy': correct / len(examples),
        'coverage': covered / len(examples), 'errors': errors,
        'predictions': predictions,
    }


def paired_bootstrap(golds, system, ablation, samples=5000):
    rng = random.Random(33)
    differences = [
        int(norm(s) == norm(g)) - int(norm(a) == norm(g))
        for g, s, a in zip(golds, system, ablation)
    ]
    draws = []
    for _ in range(samples):
        draws.append(sum(differences[rng.randrange(len(differences))] for _ in differences) / len(differences))
    draws.sort()
    return {
        'delta': sum(differences) / len(differences),
        'lo': draws[int(.025 * samples)],
        'hi': draws[int(.975 * samples)],
    }


def main():
    artifacts = Path('artifacts')
    artifacts.mkdir(exist_ok=True)
    report = {'name': 'Semantic Orbit Logic', 'training_examples': 0, 'tasks': {}}
    all_golds, all_system, all_ablation = [], [], []
    for name in URLS:
        examples = load(name)
        system = evaluate(examples, SOLVERS[name])
        ablation = evaluate(examples, ABLATIONS[name])
        rng = random.Random(20260712)
        metamorphic = evaluate([perturb(name, ex, rng) for ex in examples], SOLVERS[name])
        golds = [gold(ex) for ex in examples]
        report['tasks'][name] = {
            'sol': {k: v for k, v in system.items() if k != 'predictions'},
            'ablation': {k: v for k, v in ablation.items() if k != 'predictions'},
            'metamorphic': {k: v for k, v in metamorphic.items() if k != 'predictions'},
            'paired': paired_bootstrap(golds, system['predictions'], ablation['predictions']),
        }
        all_golds.extend(golds)
        all_system.extend(system['predictions'])
        all_ablation.extend(ablation['predictions'])
        print(name, system['accuracy'], ablation['accuracy'], system['coverage'], metamorphic['accuracy'])
    report['aggregate'] = {
        'n': len(all_golds),
        'sol_accuracy': sum(norm(x) == norm(g) for x, g in zip(all_system, all_golds)) / len(all_golds),
        'ablation_accuracy': sum(norm(x) == norm(g) for x, g in zip(all_ablation, all_golds)) / len(all_golds),
        'paired': paired_bootstrap(all_golds, all_system, all_ablation, 10000),
    }
    Path('artifacts/results.json').write_text(json.dumps(report, indent=2))
    rows = [
        '# SOL official BIG-bench results', '',
        '|Task|N|SOL|Ablation|Coverage|Metamorphic|',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for name, value in report['tasks'].items():
        rows.append(
            f"|{name}|{value['sol']['n']}|{value['sol']['accuracy']:.4f}|"
            f"{value['ablation']['accuracy']:.4f}|{value['sol']['coverage']:.4f}|"
            f"{value['metamorphic']['accuracy']:.4f}|"
        )
    aggregate = report['aggregate']
    rows += [
        '', f"**Micro accuracy:** {aggregate['sol_accuracy']:.4f}",
        f"**Ablation:** {aggregate['ablation_accuracy']:.4f}",
        f"**Paired delta:** {aggregate['paired']['delta']:.4f} "
        f"[{aggregate['paired']['lo']:.4f}, {aggregate['paired']['hi']:.4f}]",
        '', 'Parse failures and abstentions count as wrong. No benchmark examples are used for fitting.',
    ]
    Path('artifacts/RESULTS.md').write_text('\n'.join(rows) + '\n')
    print(json.dumps(report['aggregate'], indent=2))


if __name__ == '__main__':
    main()
