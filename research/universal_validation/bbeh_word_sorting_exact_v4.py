from __future__ import annotations

import re
from word_sort_state_auditor_v3 import predict as audit_trace


def alphabet_rank(text: str) -> dict[str, int]:
    alphabet = list('abcdefghijklmnopqrstuvwxyz')
    lower = text.lower()
    explicit = re.search(r'alphabet order\s*\[([^]]+)\]', lower)
    if explicit:
        chars = re.findall(r'\b[a-z]\b', explicit.group(1))
        if len(chars) != 26 or len(set(chars)) != 26:
            raise ValueError('Malformed explicit alphabet')
        alphabet = chars
    else:
        first_two = re.search(r'except that ([a-z]) and ([a-z]) are the first two letters', lower)
        last_two = re.search(r'except that ([a-z]) and ([a-z]) are the last two letters', lower)
        first_one = re.search(r'except that ([a-z]) is the first letter', lower)
        last_one = re.search(r'except that ([a-z]) is the last letter', lower)
        swapped = re.search(r'except that ([a-z]) and ([a-z]) are swapped', lower)
        if first_two:
            a, b = first_two.groups()
            alphabet.remove(a); alphabet.remove(b)
            alphabet = [a, b] + alphabet
        elif last_two:
            a, b = last_two.groups()
            alphabet.remove(a); alphabet.remove(b)
            alphabet += [a, b]
        elif first_one:
            a = first_one.group(1)
            alphabet.remove(a); alphabet.insert(0, a)
        elif last_one:
            a = last_one.group(1)
            alphabet.remove(a); alphabet.append(a)
        elif swapped:
            a, b = swapped.groups()
            ia, ib = alphabet.index(a), alphabet.index(b)
            alphabet[ia], alphabet[ib] = alphabet[ib], alphabet[ia]
        else:
            raise ValueError('Unknown alphabet transformation')
    return {char: index for index, char in enumerate(alphabet)}


def solve_direct(text: str) -> str | None:
    match = re.search(r'Sort the following words.*?:\s*(.*)$', text, re.S | re.I)
    if not match:
        return None
    words = [word.strip() for word in match.group(1).strip().split(',')]
    rank = alphabet_rank(text)
    ordered = sorted(words, key=lambda word: tuple(rank[char] for char in word.lower()))
    return ', '.join(ordered)


def solve(text: str) -> str | None:
    if text.lstrip().startswith('Consider a new alphabet'):
        return solve_direct(text)
    return audit_trace(text)
