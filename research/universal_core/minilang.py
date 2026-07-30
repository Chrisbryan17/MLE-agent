from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import re

from .canonical import canonical_json_bytes, sha256_hex, to_canonical_data


class MiniLangValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ExecutionLimits:
    max_steps: int = 10_000
    max_loop_items: int = 1_000
    max_output_bytes: int = 1_000_000
    max_depth: int = 64

    def __post_init__(self) -> None:
        for name, value in (
            ("max_steps", self.max_steps),
            ("max_loop_items", self.max_loop_items),
            ("max_output_bytes", self.max_output_bytes),
            ("max_depth", self.max_depth),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")


_ALLOWED_FUNCTIONS = frozenset({
    "add", "subtract", "multiply", "divide", "mod",
    "equal", "less", "less_equal", "greater", "greater_equal",
    "and", "or", "not", "length", "contains", "lower", "split",
    "join", "sorted", "unique",
})
_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _require_keys(data: Mapping[str, Any], allowed: set[str], required: set[str]) -> None:
    unknown = set(data) - allowed
    missing = required - set(data)
    if unknown:
        raise MiniLangValidationError(f"unknown fields: {sorted(unknown)}")
    if missing:
        raise MiniLangValidationError(f"missing fields: {sorted(missing)}")


def _validate_name(name: Any) -> str:
    if not isinstance(name, str) or not _NAME_PATTERN.fullmatch(name):
        raise MiniLangValidationError(f"invalid variable name: {name!r}")
    return name


def _validate_expression(expression: Any, depth: int = 0) -> None:
    if depth > 64:
        raise MiniLangValidationError("expression nesting limit exceeded")
    if expression is None or isinstance(expression, bool | int | float | str):
        return
    if not isinstance(expression, Mapping):
        raise MiniLangValidationError("expression must be a scalar or mapping")
    if "literal" in expression:
        _require_keys(expression, {"literal"}, {"literal"})
        try:
            to_canonical_data(expression["literal"])
        except TypeError as exc:
            raise MiniLangValidationError("literal is not serializable") from exc
        return
    if "var" in expression:
        _require_keys(expression, {"var"}, {"var"})
        name = expression["var"]
        if name != "$input":
            _validate_name(name)
        return
    if "index" in expression:
        _require_keys(expression, {"index"}, {"index"})
        items = expression["index"]
        if not isinstance(items, list) or len(items) != 2:
            raise MiniLangValidationError("index expression requires [value, key]")
        _validate_expression(items[0], depth + 1)
        _validate_expression(items[1], depth + 1)
        return
    if "call" in expression:
        _require_keys(expression, {"call", "args"}, {"call", "args"})
        function = expression["call"]
        if function not in _ALLOWED_FUNCTIONS:
            raise MiniLangValidationError(f"unknown function: {function!r}")
        args = expression["args"]
        if not isinstance(args, list):
            raise MiniLangValidationError("function args must be a list")
        for argument in args:
            _validate_expression(argument, depth + 1)
        return
    raise MiniLangValidationError("expression uses an unsupported form")


def _validate_body(body: Any, depth: int = 0) -> None:
    if depth > 64:
        raise MiniLangValidationError("statement nesting limit exceeded")
    if not isinstance(body, list):
        raise MiniLangValidationError("program body must be a list")
    for statement in body:
        if not isinstance(statement, Mapping) or "op" not in statement:
            raise MiniLangValidationError("statement must be a mapping with op")
        operation = statement["op"]
        if operation in {"let", "set"}:
            _require_keys(statement, {"op", "name", "value"}, {"op", "name", "value"})
            _validate_name(statement["name"])
            _validate_expression(statement["value"], depth + 1)
        elif operation == "if":
            _require_keys(statement, {"op", "condition", "then", "else"}, {"op", "condition", "then"})
            _validate_expression(statement["condition"], depth + 1)
            _validate_body(statement["then"], depth + 1)
            _validate_body(statement.get("else", []), depth + 1)
        elif operation == "for_each":
            _require_keys(statement, {"op", "item", "in", "body"}, {"op", "item", "in", "body"})
            _validate_name(statement["item"])
            _validate_expression(statement["in"], depth + 1)
            _validate_body(statement["body"], depth + 1)
        elif operation == "return":
            _require_keys(statement, {"op", "value"}, {"op", "value"})
            _validate_expression(statement["value"], depth + 1)
        else:
            raise MiniLangValidationError(f"unsupported statement operation: {operation!r}")


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value


class _Runtime:
    def __init__(self, input_value: Any, limits: ExecutionLimits) -> None:
        self.environment: dict[str, Any] = {"$input": input_value}
        self.limits = limits
        self.steps = 0
        self.loop_items = 0

    def bump(self) -> None:
        self.steps += 1
        if self.steps > self.limits.max_steps:
            raise RuntimeError("MiniLang step budget exceeded")

    def compute(self, expression: Any, depth: int = 0) -> Any:
        self.bump()
        if depth > self.limits.max_depth:
            raise RuntimeError("MiniLang runtime depth exceeded")
        if expression is None or isinstance(expression, bool | int | float | str):
            return expression
        if "literal" in expression:
            return expression["literal"]
        if "var" in expression:
            name = expression["var"]
            if name not in self.environment:
                raise RuntimeError(f"unknown MiniLang variable: {name}")
            return self.environment[name]
        if "index" in expression:
            source = self.compute(expression["index"][0], depth + 1)
            key = self.compute(expression["index"][1], depth + 1)
            return source[key]
        if "call" in expression:
            arguments = [self.compute(argument, depth + 1) for argument in expression["args"]]
            return _call_function(str(expression["call"]), arguments)
        raise RuntimeError("invalid validated MiniLang expression")

    def execute_body(self, body: Sequence[Mapping[str, Any]], depth: int = 0) -> None:
        if depth > self.limits.max_depth:
            raise RuntimeError("MiniLang runtime depth exceeded")
        for statement in body:
            self.bump()
            operation = statement["op"]
            if operation == "let":
                name = statement["name"]
                if name in self.environment:
                    raise RuntimeError(f"MiniLang variable already exists: {name}")
                self.environment[name] = self.compute(statement["value"], depth + 1)
            elif operation == "set":
                name = statement["name"]
                if name not in self.environment or name == "$input":
                    raise RuntimeError(f"MiniLang variable cannot be set: {name}")
                self.environment[name] = self.compute(statement["value"], depth + 1)
            elif operation == "if":
                branch = statement["then"] if bool(self.compute(statement["condition"], depth + 1)) else statement.get("else", [])
                self.execute_body(branch, depth + 1)
            elif operation == "for_each":
                values = self.compute(statement["in"], depth + 1)
                if not isinstance(values, Sequence) or isinstance(values, str | bytes):
                    raise RuntimeError("MiniLang for_each input must be a sequence")
                name = statement["item"]
                sentinel = object()
                previous = self.environment.get(name, sentinel)
                try:
                    for item in values:
                        self.bump()
                        self.loop_items += 1
                        if self.loop_items > self.limits.max_loop_items:
                            raise RuntimeError("MiniLang loop item limit exceeded")
                        self.environment[name] = item
                        self.execute_body(statement["body"], depth + 1)
                finally:
                    if previous is sentinel:
                        self.environment.pop(name, None)
                    else:
                        self.environment[name] = previous
            elif operation == "return":
                raise _ReturnSignal(self.compute(statement["value"], depth + 1))
            else:
                raise RuntimeError("invalid validated MiniLang statement")


def _arity(name: str, arguments: list[Any], minimum: int, maximum: int | None = None) -> None:
    maximum = minimum if maximum is None else maximum
    if not minimum <= len(arguments) <= maximum:
        raise RuntimeError(f"MiniLang function {name} expects {minimum} to {maximum} arguments")


def _call_function(name: str, arguments: list[Any]) -> Any:
    if name == "add":
        _arity(name, arguments, 2)
        return arguments[0] + arguments[1]
    if name == "subtract":
        _arity(name, arguments, 2)
        return arguments[0] - arguments[1]
    if name == "multiply":
        _arity(name, arguments, 2)
        return arguments[0] * arguments[1]
    if name == "divide":
        _arity(name, arguments, 2)
        return arguments[0] / arguments[1]
    if name == "mod":
        _arity(name, arguments, 2)
        return arguments[0] % arguments[1]
    if name == "equal":
        _arity(name, arguments, 2)
        return arguments[0] == arguments[1]
    if name == "less":
        _arity(name, arguments, 2)
        return arguments[0] < arguments[1]
    if name == "less_equal":
        _arity(name, arguments, 2)
        return arguments[0] <= arguments[1]
    if name == "greater":
        _arity(name, arguments, 2)
        return arguments[0] > arguments[1]
    if name == "greater_equal":
        _arity(name, arguments, 2)
        return arguments[0] >= arguments[1]
    if name == "and":
        _arity(name, arguments, 2)
        return bool(arguments[0]) and bool(arguments[1])
    if name == "or":
        _arity(name, arguments, 2)
        return bool(arguments[0]) or bool(arguments[1])
    if name == "not":
        _arity(name, arguments, 1)
        return not bool(arguments[0])
    if name == "length":
        _arity(name, arguments, 1)
        return len(arguments[0])
    if name == "contains":
        _arity(name, arguments, 2)
        return arguments[1] in arguments[0]
    if name == "lower":
        _arity(name, arguments, 1)
        return str(arguments[0]).casefold()
    if name == "split":
        _arity(name, arguments, 1, 2)
        return str(arguments[0]).split(None if len(arguments) == 1 else str(arguments[1]))
    if name == "join":
        _arity(name, arguments, 2)
        return str(arguments[1]).join(str(item) for item in arguments[0])
    if name == "sorted":
        _arity(name, arguments, 1, 2)
        return sorted(arguments[0], reverse=bool(arguments[1]) if len(arguments) == 2 else False)
    if name == "unique":
        _arity(name, arguments, 1)
        result: list[Any] = []
        for item in arguments[0]:
            if item not in result:
                result.append(item)
        return result
    raise RuntimeError(f"unknown validated MiniLang function: {name}")


@dataclass(frozen=True)
class MiniLangProgram:
    body: tuple[Mapping[str, Any], ...]
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise MiniLangValidationError(f"unsupported MiniLang version: {self.version}")
        normalized = to_canonical_data(list(self.body))
        _validate_body(normalized)
        object.__setattr__(self, "body", tuple(normalized))

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "MiniLangProgram":
        if not isinstance(data, Mapping):
            raise MiniLangValidationError("MiniLang program must be a mapping")
        _require_keys(data, {"kind", "version", "body"}, {"kind", "version", "body"})
        if data["kind"] != "minilang":
            raise MiniLangValidationError("MiniLang program kind must be minilang")
        body = data["body"]
        if not isinstance(body, list):
            raise MiniLangValidationError("MiniLang body must be a list")
        return cls(tuple(body), int(data["version"]))

    def to_data(self) -> dict[str, Any]:
        return {"kind": "minilang", "version": self.version, "body": list(self.body)}

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json_bytes(self.to_data()))

    def run(self, input_value: Any, limits: ExecutionLimits | None = None) -> Any:
        limits = limits or ExecutionLimits()
        runtime = _Runtime(input_value, limits)
        try:
            runtime.execute_body(self.body)
        except _ReturnSignal as signal:
            output = signal.value
            if len(canonical_json_bytes(output)) > limits.max_output_bytes:
                raise RuntimeError("MiniLang output size limit exceeded")
            return output
        raise RuntimeError("MiniLang program did not return a value")
