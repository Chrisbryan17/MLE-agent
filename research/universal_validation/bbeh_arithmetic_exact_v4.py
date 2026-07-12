#!/usr/bin/env python3
from __future__ import annotations

import functools
import hashlib
import json
import math
import operator
import os
import pathlib
import re

WORD_NUMBERS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
}


def is_prime(value: int) -> bool:
    value = int(value)
    if value < 2:
        return False
    return all(value % divisor for divisor in range(2, math.isqrt(value) + 1))


class ExpressionParser:
    def __init__(self, source: str, functions: dict[str, object]):
        self.source = source.strip().rstrip('.')
        self.functions = functions
        self.atomic_operators = set(functions) | {'+', '-', '*'}
        self.tokens = self.tokenize(self.source)
        self.index = 0

    @staticmethod
    def tokenize(source: str) -> list[str]:
        tokens: list[str] = []
        index = 0
        while index < len(source):
            character = source[index]
            if character.isspace():
                index += 1
            elif character in '(),':
                tokens.append(character)
                index += 1
            elif character.isdigit():
                end = index + 1
                while end < len(source) and source[end].isdigit():
                    end += 1
                tokens.append(source[index:end])
                index = end
            elif character.isalpha() or character == '_':
                end = index + 1
                while end < len(source) and (source[end].isalnum() or source[end] == '_'):
                    end += 1
                tokens.append(source[index:end])
                index = end
            else:
                end = index + 1
                while (
                    end < len(source)
                    and not source[end].isspace()
                    and not source[end].isalnum()
                    and source[end] not in '(),'
                ):
                    end += 1
                tokens.append(source[index:end])
                index = end
        return tokens

    def peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def pop(self) -> str:
        token = self.peek()
        if token is None:
            raise ValueError('Unexpected end of expression')
        self.index += 1
        return token

    def parse(self, environment: dict[str, int]) -> int:
        value = self.expression(environment, 0)
        if self.index != len(self.tokens):
            raise ValueError(f'Unconsumed tokens: {self.tokens[self.index:]}')
        return int(value)

    def expression(self, environment: dict[str, int], minimum_precedence: int) -> int:
        left = self.atom(environment)
        while True:
            token = self.peek()
            if token is None or token in (')', ',') or re.search(r'[A-Za-z0-9]', token):
                break
            precedence = 20 if token == '*' else 10
            if precedence < minimum_precedence:
                break
            self.pop()
            right = self.expression(environment, precedence + 1)
            left = self.apply_operator_run(token, left, right)
        return int(left)

    def atom(self, environment: dict[str, int]) -> int:
        token = self.pop()
        if token == '-':
            return -self.atom(environment)
        if token == '(':
            value = self.expression(environment, 0)
            if self.pop() != ')':
                raise ValueError('Missing closing parenthesis')
            return value
        if token.isdigit():
            return int(token)
        lowered = token.lower()
        if lowered in WORD_NUMBERS:
            return WORD_NUMBERS[lowered]
        if lowered in environment:
            return environment[lowered]
        if lowered in ('min', 'max', 'gcd'):
            if self.pop() != '(':
                raise ValueError('Missing function parenthesis')
            first = self.expression(environment, 0)
            if self.pop() != ',':
                raise ValueError('Missing function comma')
            second = self.expression(environment, 0)
            if self.pop() != ')':
                raise ValueError('Missing function close')
            return {'min': min, 'max': max, 'gcd': math.gcd}[lowered](first, second)
        raise ValueError(f'Unknown atom {token!r}')

    def split_operator_run(self, run: str) -> tuple[str, ...]:
        operators = sorted(self.atomic_operators, key=len, reverse=True)

        @functools.lru_cache(None)
        def segment(position: int):
            if position == len(run):
                return ()
            for op in operators:
                if run.startswith(op, position):
                    remainder = segment(position + len(op))
                    if remainder is not None:
                        return (op,) + remainder
            return None

        result = segment(0)
        if result is None:
            raise ValueError(f'Unknown operator sequence {run!r}')
        return result

    def apply_operator_run(self, run: str, left: int, right: int) -> int:
        value = left
        for op in self.split_operator_run(run):
            if op == '+':
                value += right
            elif op == '-':
                value -= right
            elif op == '*':
                value *= right
            else:
                value = self.functions[op](value, right)
        return int(value)


def evaluate_expression(source: str, environment: dict[str, int], functions: dict[str, object]) -> int:
    return ExpressionParser(source, functions).parse(environment)


def evaluate_condition(source: str, environment: dict[str, int], functions: dict[str, object]) -> bool:
    source = source.strip()
    absolute = re.match(r'\|(.+)\|\s*(==|>|<)\s*(.*)$', source)
    if absolute:
        left = abs(evaluate_expression(absolute.group(1), environment, functions))
        comparison = absolute.group(2)
        right = evaluate_expression(absolute.group(3), environment, functions)
    else:
        match = re.search(r'\s(==|>|<)\s', source)
        if not match:
            raise ValueError(f'Unknown condition {source!r}')
        left = evaluate_expression(source[:match.start()], environment, functions)
        comparison = match.group(1)
        right = evaluate_expression(source[match.end():], environment, functions)
    return {'>': operator.gt, '<': operator.lt, '==': operator.eq}[comparison](left, right)


def compile_operations(text: str) -> dict[str, object]:
    functions: dict[str, object] = {}
    definition_section = text.split('Let A', 1)[0]
    for line in definition_section.splitlines():
        if not line.startswith('$a '):
            continue
        spans = re.findall(r'\$(.*?)\$', line)
        operation = spans[0][2:-2]
        if 'if either $a$ or $b$ is prime' in line:
            true_expression, false_expression = spans[1], spans[-1]

            def make_prime(true_source=true_expression, false_source=false_expression):
                def apply(first: int, second: int) -> int:
                    source = true_source if is_prime(first) or is_prime(second) else false_source
                    return evaluate_expression(source, {'a': first, 'b': second}, functions)
                return apply

            functions[operation] = make_prime()
        else:
            true_expression, condition, false_expression = spans[1], spans[2], spans[3]

            def make_conditional(
                true_source=true_expression,
                condition_source=condition,
                false_source=false_expression,
            ):
                def apply(first: int, second: int) -> int:
                    environment = {'a': first, 'b': second}
                    source = (
                        true_source
                        if evaluate_condition(condition_source, environment, functions)
                        else false_source
                    )
                    return evaluate_expression(source, environment, functions)
                return apply

            functions[operation] = make_conditional()
    return functions


def solve(text: str) -> str:
    functions = compile_operations(text)
    environment: dict[str, int] = {}
    for variable in 'ABC':
        match = re.search(rf'Let {variable} = (.*?)(?:\nLet|\nCompute)', text, re.S)
        if not match:
            raise ValueError(f'Missing {variable}')
        environment[variable.lower()] = evaluate_expression(
            match.group(1).strip().rstrip('.'), environment, functions
        )
    final = re.search(r'Compute (.*)\. Your final', text)
    if not final:
        raise ValueError('Missing final expression')
    expression = final.group(1).replace('A', 'a').replace('B', 'b').replace('C', 'c')
    return str(evaluate_expression(expression, environment, functions))


def main() -> None:
    root = pathlib.Path(os.environ.get('BBEH_TASK_ROOT', '.external/bbeh/bbeh/benchmark_tasks'))
    task_path = root / 'bbeh_multistep_arithmetic' / 'task.json'
    examples = json.loads(task_path.read_text())['examples']
    rows = []
    for index, example in enumerate(examples):
        try:
            prediction = solve(example['input'])
            error = None
        except Exception as exc:
            prediction = None
            error = f'{type(exc).__name__}: {exc}'
        rows.append({
            'index': index,
            'prediction': prediction,
            'target': example['target'],
            'correct': prediction == example['target'],
            'error': error,
        })
    correct = sum(row['correct'] for row in rows)
    payload = {
        'protocol': (
            'Post-replication adaptive exact compiler. Operation definitions are parsed into '
            'executable binary functions; all nested and compound expressions are then evaluated.'
        ),
        'task': 'bbeh_multistep_arithmetic',
        'n': len(rows),
        'correct': correct,
        'accuracy': correct / len(rows),
        'coverage': sum(row['prediction'] is not None for row in rows) / len(rows),
        'task_sha256': hashlib.sha256(task_path.read_bytes()).hexdigest(),
        'code_sha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
        'errors': [row for row in rows if not row['correct']],
    }
    output = pathlib.Path('artifacts/arithmetic_exact_v4')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps({key: payload[key] for key in ('n', 'correct', 'accuracy', 'coverage')}, indent=2))


if __name__ == '__main__':
    main()
