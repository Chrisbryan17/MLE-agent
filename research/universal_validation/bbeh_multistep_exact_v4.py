from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable

NUMBER_WORDS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
    'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
}
BUILTIN_OPS = {'+', '-', '*'}
OP_CHARS = set('+-*~!&:#;@<>[]')


def is_prime(n: int) -> bool:
    n = int(n)
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


@dataclass(frozen=True)
class Token:
    kind: str
    value: str


def tokenize(text: str) -> list[Token]:
    text = text.replace('$', '')
    out: list[Token] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isdigit():
            j = i + 1
            while j < len(text) and text[j].isdigit():
                j += 1
            out.append(Token('INT', text[i:j]))
            i = j
            continue
        if ch.isalpha() or ch == '_':
            j = i + 1
            while j < len(text) and (text[j].isalnum() or text[j] == '_'):
                j += 1
            out.append(Token('NAME', text[i:j]))
            i = j
            continue
        if ch in OP_CHARS:
            j = i + 1
            while j < len(text) and text[j] in OP_CHARS:
                j += 1
            out.append(Token('OP', text[i:j]))
            i = j
            continue
        if ch == '(':
            out.append(Token('LPAREN', ch))
        elif ch == ')':
            out.append(Token('RPAREN', ch))
        elif ch == ',':
            out.append(Token('COMMA', ch))
        else:
            raise ValueError(f'Unexpected character {ch!r} in {text!r}')
        i += 1
    out.append(Token('EOF', ''))
    return out


class Evaluator:
    def __init__(self):
        self.custom: dict[str, Callable[[int, int], int]] = {}

    def split_opseq(self, sequence: str) -> list[str]:
        if sequence in BUILTIN_OPS or sequence in self.custom:
            return [sequence]
        atoms = sorted(set(self.custom) | BUILTIN_OPS, key=lambda x: (-len(x), x))
        result: list[str] = []
        i = 0
        while i < len(sequence):
            match = next((op for op in atoms if sequence.startswith(op, i)), None)
            if match is None:
                raise ValueError(f'Cannot segment operator sequence {sequence!r} at {i}; atoms={atoms}')
            result.append(match)
            i += len(match)
        return result

    def apply_atomic(self, op: str, left: int, right: int) -> int:
        if op == '+':
            return left + right
        if op == '-':
            return left - right
        if op == '*':
            return left * right
        return int(self.custom[op](left, right))

    def apply(self, sequence: str, left: int, right: int) -> int:
        value = left
        for op in self.split_opseq(sequence):
            value = self.apply_atomic(op, value, right)
        return int(value)

    def eval_expr(self, text: str, env: dict[str, int] | None = None) -> int:
        parser = Parser(tokenize(text), self, env or {})
        value = parser.parse_expr()
        parser.expect('EOF')
        return int(value)

    def eval_condition(self, text: str, env: dict[str, int]) -> bool:
        condition = text.strip().replace('$', '')
        if re.fullmatch(r'either\s+a\s+or\s+b\s+is\s+prime', condition, re.I):
            return is_prime(env['a']) or is_prime(env['b'])
        absolute = re.fullmatch(r'\|(.+?)\|\s+(==|>|<)\s+(.+)', condition)
        if absolute:
            left = abs(self.eval_expr(absolute.group(1), env))
            right = self.eval_expr(absolute.group(3), env)
            return {'==': left == right, '>': left > right, '<': left < right}[absolute.group(2)]
        comparison = re.fullmatch(r'(.+?)\s+(==|>|<)\s+(.+)', condition)
        if not comparison:
            raise ValueError(f'Unsupported condition {condition!r}')
        left = self.eval_expr(comparison.group(1), env)
        right = self.eval_expr(comparison.group(3), env)
        return {'==': left == right, '>': left > right, '<': left < right}[comparison.group(2)]


class Parser:
    def __init__(self, tokens: list[Token], evaluator: Evaluator, env: dict[str, int]):
        self.tokens = tokens
        self.i = 0
        self.evaluator = evaluator
        self.env = env

    def current(self) -> Token:
        return self.tokens[self.i]

    def take(self) -> Token:
        token = self.current()
        self.i += 1
        return token

    def expect(self, kind: str, value: str | None = None) -> Token:
        token = self.take()
        if token.kind != kind or (value is not None and token.value != value):
            raise ValueError(f'Expected {kind} {value}, got {token}')
        return token

    @staticmethod
    def precedence(opseq: str) -> int:
        if opseq == '*':
            return 30
        if opseq in ('+', '-'):
            return 20
        return 25

    def parse_expr(self, min_precedence: int = 0) -> int:
        token = self.take()
        if token.kind == 'INT':
            left = int(token.value)
        elif token.kind == 'NAME':
            name = token.value
            lowered = name.lower()
            if self.current().kind == 'LPAREN':
                self.take()
                first = self.parse_expr()
                self.expect('COMMA')
                second = self.parse_expr()
                self.expect('RPAREN')
                if lowered == 'min':
                    left = min(first, second)
                elif lowered == 'max':
                    left = max(first, second)
                elif lowered == 'gcd':
                    left = math.gcd(first, second)
                else:
                    raise ValueError(f'Unknown function {name}')
            elif lowered in NUMBER_WORDS:
                left = NUMBER_WORDS[lowered]
            elif name in self.env:
                left = int(self.env[name])
            elif lowered in self.env:
                left = int(self.env[lowered])
            else:
                raise ValueError(f'Unknown name {name!r}')
        elif token.kind == 'OP' and token.value == '-':
            left = -self.parse_expr(100)
        elif token.kind == 'LPAREN':
            left = self.parse_expr()
            self.expect('RPAREN')
        else:
            raise ValueError(f'Unexpected prefix token {token}')

        while self.current().kind == 'OP':
            opseq = self.current().value
            precedence = self.precedence(opseq)
            if precedence < min_precedence:
                break
            self.take()
            right = self.parse_expr(precedence + 1)
            left = self.evaluator.apply(opseq, left, right)
        return int(left)


def parse_definition(line: str, evaluator: Evaluator) -> tuple[str, Callable[[int, int], int]]:
    head = re.match(r'^\$a\s+(.+?)\s+b\$\s+equals\s+\$(.+?)\$\s+if\s+(.+)$', line.strip())
    if not head:
        raise ValueError(f'Cannot parse definition: {line}')
    op, then_expr, tail = head.groups()
    if tail.startswith('either '):
        match = re.fullmatch(
            r'either\s+\$a\$\s+or\s+\$b\$\s+is\s+prime\s+and\s+\$(.+?)\$\s+otherwise\.',
            tail,
        )
        if not match:
            raise ValueError(f'Cannot parse prime definition tail: {tail}')
        condition = 'either a or b is prime'
        else_expr = match.group(1)
    elif '; otherwise' in tail:
        match = re.fullmatch(r'\$(.+?)\$;\s+otherwise,\s+it\s+equals\s+\$(.+?)\$\.', tail)
        if not match:
            raise ValueError(f'Cannot parse semicolon definition tail: {tail}')
        condition, else_expr = match.groups()
    else:
        match = re.fullmatch(
            r'\$(.+?)\$\s+and\s+\$(.+?)\$\s+otherwise(?:,\s+where\s+gcd\s+stands\s+for\s+greatest\s+common\s+divisor)?\.',
            tail,
        )
        if not match:
            raise ValueError(f'Cannot parse and definition tail: {tail}')
        condition, else_expr = match.groups()

    def operation(a: int, b: int, _then=then_expr, _else=else_expr, _condition=condition) -> int:
        env = {'a': int(a), 'b': int(b)}
        branch = _then if evaluator.eval_condition(_condition, env) else _else
        return evaluator.eval_expr(branch, env)

    return op.strip(), operation


def solve(text: str) -> str | None:
    evaluator = Evaluator()
    for line in text.splitlines():
        if line.startswith('$a '):
            op, function = parse_definition(line, evaluator)
            evaluator.custom[op] = function

    values: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r'^Let\s+([ABC])\s*=\s*(.+?)\.?$', line.strip())
        if match:
            name, expression = match.groups()
            values[name] = evaluator.eval_expr(expression, values)
    if set(values) != {'A', 'B', 'C'}:
        return None
    return str(values['A'] + values['B'] - values['C'])
