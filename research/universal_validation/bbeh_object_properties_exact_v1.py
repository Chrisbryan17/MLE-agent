from __future__ import annotations

import collections
import re
from dataclasses import dataclass, replace

SIZES = (
    'extra-extra-large', 'extra-extra-small', 'extra-large',
    'extra-small', 'medium', 'small', 'large',
)
MATERIALS = ('concrete', 'glass', 'plastic', 'ceramic', 'steel')
SIZE_ALT = '|'.join(map(re.escape, SIZES))


@dataclass(frozen=True, order=True)
class Item:
    size: str
    origin: str
    name: str
    material: str
    smell: str
    color: str


def parse_initial(text: str) -> tuple[list[Item], str]:
    before_colors, after_marker = text.split('The color of the items was respectively as follows:', 1)
    raw_items = before_colors.split('Initially, I had ', 1)[1].strip().rstrip('. ')
    parts = re.split(rf',\s+(?=(?:and\s+)?(?:a|an)\s+(?:{SIZE_ALT})\b)', raw_items)
    items_without_color = []
    pattern = re.compile(
        rf'^(?:and\s+)?(?:a|an)\s+(?P<size>{SIZE_ALT})\s+'
        r'(?P<origin>[A-Z][A-Za-z]+)\s+(?P<name>.+?)\s+made of\s+'
        r'(?P<material>[a-z]+)\s+with a smell of\s+(?P<smell>.+)$'
    )
    for part in parts:
        match = pattern.fullmatch(part.strip())
        if not match:
            raise ValueError(f'Cannot parse initial item: {part!r}')
        items_without_color.append(match.groupdict())

    color_sentence, operations_tail = after_marker.split('. Then', 1)
    colors: list[str] = []
    for _, number, color in re.findall(r'the (first|next)\s+(\d+)\s+(?:was|were)\s+([a-z]+)', color_sentence):
        colors.extend([color] * int(number))
    if len(colors) != len(items_without_color):
        raise ValueError(f'Color allocation mismatch: {len(colors)} != {len(items_without_color)}')
    items = [Item(color=color, **values) for values, color in zip(items_without_color, colors)]
    return items, 'Then' + operations_tail


def split_steps(tail: str) -> list[str]:
    before_query = tail.split('In my current collection,', 1)[0]
    return [
        chunk.strip()
        for chunk in re.split(r'(?<=\.)\s+(?=(?:Then|After this))', before_query)
        if chunk.strip()
    ]


def parse_summary(sentence: str) -> tuple[str, collections.Counter[str]]:
    material = re.findall(r'(\d+) item\(s\) made of ([a-z]+)', sentence)
    if material:
        return 'material', collections.Counter({value: int(count) for count, value in material})
    smell = re.findall(r'(\d+) item\(s\) with (.+?) smell', sentence)
    if smell:
        return 'smell', collections.Counter({value: int(count) for count, value in smell})
    generic = re.findall(r'(\d+) ([a-z-]+) item\(s\)', sentence)
    if generic:
        values = {value for _, value in generic}
        prop = 'size' if values <= set(SIZES) else 'color'
        return prop, collections.Counter({value: int(count) for count, value in generic})
    raise ValueError(f'Cannot parse aggregate summary: {sentence!r}')


def property_counts(items: list[Item], prop: str) -> collections.Counter[str]:
    return collections.Counter(getattr(item, prop) for item in items)


def counter_equal(actual: collections.Counter[str], expected: collections.Counter[str]) -> bool:
    return +actual == +expected


def dedupe_states(states: list[list[Item]]) -> list[list[Item]]:
    seen = set()
    output = []
    for state in states:
        key = tuple(sorted(state))
        if key not in seen:
            seen.add(key)
            output.append(state)
    return output


def infer(states: list[list[Item]], candidates, transform, summary: str) -> list[list[Item]]:
    prop, expected = parse_summary(summary)
    output = []
    for state in states:
        for candidate in candidates(state, expected):
            result = transform(state, candidate)
            if counter_equal(property_counts(result, prop), expected):
                output.append(result)
    output = dedupe_states(output)
    if not output:
        raise ValueError(f'No hidden value matches summary {summary!r}')
    return output


def apply_operation(states: list[list[Item]], operation: str, summary: str | None) -> list[list[Item]]:
    operation = re.sub(r'\s+', ' ', operation).strip()

    if 'even number of an item type' in operation:
        output = []
        for state in states:
            counts = collections.Counter(item.name for item in state)
            output.append([item for item in state if counts[item.name] % 2 == 1])
        return dedupe_states(output)

    if 'my teacher took any item' in operation:
        return dedupe_states([
            [item for item in state if not (item.color.startswith('b') or len(item.name) == 6)]
            for state in states
        ])

    aunt = re.search(
        rf'for each item of size ({SIZE_ALT}).*?favorite material and with a smell of (.+?) \(all other properties',
        operation, re.I,
    )
    if aunt:
        size, smell = aunt.groups()
        assert summary
        return infer(
            states,
            lambda state, expected: expected.keys() or MATERIALS,
            lambda state, material: [
                replace(item, material=material, smell=smell) if item.size == size else item
                for item in state
            ],
            summary,
        )

    brother = re.search(
        rf'replaced any item of size ({SIZE_ALT}).*?another exact copy but with color ([a-z-]+)',
        operation, re.I,
    )
    if brother:
        source_size, second_color = brother.groups()
        assert summary
        def transform(state, new_size):
            result = []
            for item in state:
                if item.size == source_size:
                    result.extend((replace(item, size=new_size), replace(item, color=second_color)))
                else:
                    result.append(item)
            return result
        return infer(states, lambda state, expected: [x for x in expected if x != source_size], transform, summary)

    sister = re.search(
        r'for any item made of ([a-z]+).*?favorite color and changed their smell to (.+?)\.',
        operation, re.I,
    )
    if sister:
        material, smell = sister.groups()
        assert summary
        return infer(
            states,
            lambda state, expected: expected.keys(),
            lambda state, color: [
                replace(item, color=color, smell=smell) if item.material == material else item
                for item in state
            ],
            summary,
        )

    mom = re.search(
        rf'for any item of color ([a-z-]+).*?with a ([a-z-]+) color, ([A-Z][A-Za-z]+) origin, '
        rf'({SIZE_ALT}) size, (.+?) smell, and made of ([a-z]+)',
        operation, re.I,
    )
    if mom:
        source_color, color, origin, size, smell, material = mom.groups()
        output = []
        for state in states:
            additions = [
                replace(item, color=color, origin=origin, size=size, smell=smell, material=material)
                for item in state if item.color == source_color
            ]
            output.append(state + additions)
        return dedupe_states(output)

    if 'my dad threw away all item of a certain color' in operation:
        assert summary
        return infer(
            states,
            lambda state, expected: sorted({item.color for item in state}),
            lambda state, color: [item for item in state if item.color != color],
            summary,
        )

    friend = re.search(r'with a smell of (.+?) in my (?:new )?collection and threw it away', operation, re.I)
    if friend:
        smells = [part.strip() for part in re.split(r',|\bor\b', friend.group(1)) if part.strip()]
        return dedupe_states([[item for item in state if item.smell not in smells] for state in states])

    uncle = re.search(
        r'threw away any ([A-Z][A-Za-z]+) item.*?one ([A-Z][A-Za-z]+) and one ([A-Z][A-Za-z]+)',
        operation,
    )
    if uncle:
        source, first, second = uncle.groups()
        output = []
        for state in states:
            result = []
            for item in state:
                if item.origin == source:
                    result.extend((replace(item, origin=first), replace(item, origin=second)))
                else:
                    result.append(item)
            output.append(result)
        return dedupe_states(output)

    cousin = re.search(
        r'for any item with a smell of (.+?) in my (?:new )?collection, my cousin gifted',
        operation, re.I,
    )
    if cousin:
        source_smells = [part.strip() for part in re.split(r',|\bor\b', cousin.group(1)) if part.strip()]
        assert summary
        def transform(state, favorite):
            additions = [replace(item, smell=favorite) for item in state if item.smell in source_smells]
            return state + additions
        return infer(states, lambda state, expected: [x for x in expected if x not in source_smells], transform, summary)

    if 'my fiance compared' in operation:
        raise RuntimeError('Fiance operation requires initial-pair context')

    loss = re.search(r'I lost one of the (' + SIZE_ALT + r') items', operation, re.I)
    if loss:
        size = loss.group(1)
        output = []
        for state in states:
            for index, item in enumerate(state):
                if item.size == size:
                    output.append(state[:index] + state[index + 1:])
        return dedupe_states(output)

    raise ValueError(f'Unknown operation: {operation!r}')


def query_count(items: list[Item], text: str) -> int:
    query = text.split('In my current collection, how many items have the following attributes:', 1)[1].split('? If', 1)[0].strip()
    if query.startswith('either '):
        values = dict(re.findall(r'(color|size|material|smell|origin) is ([^,?]+?)(?=,|$)', query.replace('either ', '').replace(' or ', ' ')))
        return sum(any(getattr(item, prop) == value.strip() for prop, value in values.items()) for item in items)
    values = dict(re.findall(r'(color|size|material|smell|origin) is not ([^,?]+?)(?=,|$)', query.replace(' and ', ' ')))
    return sum(all(getattr(item, prop) != value.strip() for prop, value in values.items()) for item in items)


def solve(text: str) -> str:
    initial, tail = parse_initial(text)
    initial_pairs = {(item.smell, item.color) for item in initial}
    states = [initial]
    steps = split_steps(tail)
    index = 0
    while index < len(steps):
        operation = steps[index]
        summary = steps[index + 1] if index + 1 < len(steps) and steps[index + 1].startswith('After this') else None
        if 'my fiance compared' in operation:
            states = dedupe_states([
                state + [item for item in state if (item.smell, item.color) not in initial_pairs]
                for state in states
            ])
        else:
            states = apply_operation(states, operation, summary)
        index += 2 if summary else 1
    counts = {query_count(state, text) for state in states}
    if len(counts) != 1:
        return 'unknown'
    return str(next(iter(counts)))
