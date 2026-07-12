#!/usr/bin/env python3
"""SOL-BBH frontier harness.

Fair-use policy:
- Downloads the official public BBH JSON files only for evaluation.
- Solvers are written from task semantics, not from target memorization.
- Unsupported tasks abstain and score zero.
- Reports macro and micro accuracy, coverage, errors, and hashes.

This system is a benchmark-specialist reasoning system, not a foundation model.
A second validation lane on BBEH/metamorphic variants is required before any
scientific claim of general reasoning.
"""
from __future__ import annotations

import ast
import hashlib
import itertools
import json
import operator
import re
import sys
import urllib.request
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOL_DIR = HERE.parent / "sol"
sys.path.insert(0, str(SOL_DIR))

import sol_v4  # noqa: F401; installs the frozen calendar compiler
import sol_v2
import sol_benchmark as sol_base

BBH_BASE = "https://raw.githubusercontent.com/suzgunmirac/BIG-Bench-Hard/main/bbh"
TASKS = [
    "boolean_expressions",
    "causal_judgement",
    "date_understanding",
    "disambiguation_qa",
    "dyck_languages",
    "formal_fallacies",
    "geometric_shapes",
    "hyperbaton",
    "logical_deduction_five_objects",
    "logical_deduction_seven_objects",
    "logical_deduction_three_objects",
    "movie_recommendation",
    "multistep_arithmetic_two",
    "navigate",
    "object_counting",
    "penguins_in_a_table",
    "reasoning_about_colored_objects",
    "ruin_names",
    "salient_translation_error_detection",
    "snarks",
    "sports_understanding",
    "temporal_sequences",
    "tracking_shuffled_objects_five_objects",
    "tracking_shuffled_objects_seven_objects",
    "tracking_shuffled_objects_three_objects",
    "web_of_lies",
    "word_sorting",
]

NUMBER_WORDS = {
    "zero": 0,
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

FRUITS = {
    "apple", "banana", "blackberry", "grape", "nectarine", "orange",
    "peach", "plum", "raspberry", "strawberry",
}
VEGETABLES = {
    "broccoli", "cabbage", "carrot", "cauliflower", "celery", "garlic",
    "lettuce", "onion", "potato", "yam",
}
ANIMALS = {
    "bear", "cat", "chicken", "cow", "dog", "donkey", "duck", "fish",
    "frog", "goat", "mouse", "pig", "rabbit", "snail", "snake",
}
INSTRUMENTS = {
    "accordion", "clarinet", "drum", "flute", "piano", "trombone",
    "trumpet", "violin",
}


def normalize(value):
    if value is None:
        return None
    return re.sub(r"\s+", " ", str(value).strip())


def download_task(task):
    cache = HERE / ".bbh_cache" / f"{task}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        request = urllib.request.Request(
            f"{BBH_BASE}/{task}.json", headers={"User-Agent": "SOL-BBH/0.1"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            cache.write_bytes(response.read())
    return json.loads(cache.read_text())


def split_options(text):
    if "\nOptions:\n" not in text:
        return text, []
    prompt, block = text.rsplit("\nOptions:\n", 1)
    options = []
    for raw in block.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        match = re.match(r"^\(([A-Z])\)\s*(.+)$", raw)
        if match:
            options.append((f"({match.group(1)})", match.group(2).strip()))
        elif raw.startswith("-"):
            value = raw[1:].strip()
            options.append((value, value))
    return prompt, options


def option_label(answer_text, options):
    target = normalize(answer_text)
    for label, text in options:
        if normalize(text) == target:
            return label
    return None


def choice_example(text):
    prompt, options = split_options(text)
    return prompt, options, {
        "input": prompt,
        "target_scores": {option_text: 0 for _, option_text in options},
    }


# ---------------------------------------------------------------------------
# Exact cells
# ---------------------------------------------------------------------------


def solve_boolean(text):
    expression = text.strip()
    expression = re.sub(r"\s+is\s*$", "", expression)
    tree = ast.parse(expression, mode="eval")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not evaluate(node.operand)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            return all(evaluate(value) for value in node.values)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            return any(evaluate(value) for value in node.values)
        raise ValueError(f"Unsupported Boolean AST: {ast.dump(node)}")

    return str(evaluate(tree))


def solve_dyck(text):
    sequence = text.split("Input:", 1)[1]
    tokens = re.findall(r"[\[\](){}<>]", sequence)
    close = {"(": ")", "[": "]", "{": "}", "<": ">"}
    reverse = {value: key for key, value in close.items()}
    stack = []
    for token in tokens:
        if token in close:
            stack.append(token)
        elif stack and stack[-1] == reverse[token]:
            stack.pop()
        else:
            raise ValueError(f"Invalid Dyck prefix at {token!r}")
    return " ".join(close[token] for token in reversed(stack))


def solve_arithmetic(text):
    expression = re.sub(r"\s*=\s*$", "", text.strip())
    tree = ast.parse(expression, mode="eval")
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return Fraction(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in operations:
            return operations[type(node.op)](evaluate(node.operand))
        raise ValueError(f"Unsupported arithmetic AST: {ast.dump(node)}")

    result = evaluate(tree)
    if result.denominator == 1:
        return str(result.numerator)
    return str(float(result))


def solve_navigate(text):
    prompt, _ = split_options(text)
    body = prompt.split("starting point?", 1)[1]
    instructions = [item.strip() for item in body.split(".") if item.strip()]
    absolute = any(item.lower() == "always face forward" for item in instructions)
    x = y = 0
    heading = 0  # north, east, south, west
    vectors = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    for instruction in instructions:
        lower = instruction.lower()
        if lower == "always face forward":
            continue
        if lower == "turn left":
            heading = (heading - 1) % 4
            continue
        if lower == "turn right":
            heading = (heading + 1) % 4
            continue
        if lower == "turn around":
            heading = (heading + 2) % 4
            continue
        match = re.match(r"take (\d+) step(?:s)?(?: (forward|backward|left|right))?$", lower)
        if not match:
            raise ValueError(f"Unparsed navigation instruction: {instruction}")
        distance = int(match.group(1))
        direction = match.group(2)
        if absolute and direction:
            vector = {
                "forward": (0, 1),
                "backward": (0, -1),
                "left": (-1, 0),
                "right": (1, 0),
            }[direction]
        else:
            relative = {None: 0, "forward": 0, "right": 1, "backward": 2, "left": -1}[direction]
            vector = vectors[(heading + relative) % 4]
        x += vector[0] * distance
        y += vector[1] * distance
    return "Yes" if (x, y) == (0, 0) else "No"


def solve_word_sorting(text):
    words = text.split("List:", 1)[1].strip().split()
    return " ".join(sorted(words))


def solve_web_of_lies(text):
    prompt = text.removeprefix("Question: ")
    statements = [sentence.strip() for sentence in prompt.split(".") if sentence.strip()]
    truth = {}
    for statement in statements[:-1]:
        direct = re.match(r"^(\w+) (tells the truth|lies)$", statement)
        if direct:
            truth[direct.group(1)] = direct.group(2) == "tells the truth"
            continue
        reported = re.match(r"^(\w+) says (\w+) (tells the truth|lies)$", statement)
        if not reported:
            raise ValueError(f"Unparsed web statement: {statement}")
        speaker, subject, claim = reported.groups()
        proposition = truth[subject] if claim == "tells the truth" else not truth[subject]
        truth[speaker] = proposition
    query = re.match(r"^Does (\w+) tell the truth\?$", statements[-1])
    if not query:
        raise ValueError(f"Unparsed web query: {statements[-1]}")
    return "Yes" if truth[query.group(1)] else "No"


def singularize(noun):
    noun = noun.strip().lower().replace("heads of ", "").replace("head of ", "")
    noun = noun.replace("stalks of ", "").replace("stalk of ", "")
    noun = noun.replace("lettuce heads", "lettuce").replace("lettuce head", "lettuce")
    if noun.endswith("ies"):
        return noun[:-3] + "y"
    if noun.endswith("oes"):
        return noun[:-2]
    if noun.endswith("s") and not noun.endswith("ss"):
        return noun[:-1]
    return noun


def possession_items(text):
    inventory = text.split("I have ", 1)[1].split(". How many", 1)[0]
    inventory = inventory.replace(", and ", ", ").replace(" and ", ", ")
    result = []
    for phrase in [part.strip(" ,") for part in inventory.split(",") if part.strip(" ,")]:
        match = re.match(r"^(a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s+(.+)$", phrase)
        if not match:
            raise ValueError(f"Unparsed inventory phrase: {phrase}")
        result.append((NUMBER_WORDS[match.group(1)], singularize(match.group(2))))
    return result


def solve_object_counting(text):
    items = possession_items(text)
    category = re.search(r"How many (.+?) do I have\?", text).group(1).lower()
    if category == "objects":
        allowed = None
    elif category == "fruits":
        allowed = FRUITS
    elif category == "vegetables":
        allowed = VEGETABLES
    elif category == "animals":
        allowed = ANIMALS
    elif category == "musical instruments":
        allowed = INSTRUMENTS
    else:
        raise ValueError(f"Unknown counting category: {category}")
    return str(sum(count for count, noun in items if allowed is None or noun in allowed))


def to_hour(token):
    match = re.fullmatch(r"(\d{1,2})(am|pm)", token.lower())
    hour = int(match.group(1)) % 12
    return hour + (12 if match.group(2) == "pm" else 0)


def solve_temporal_sequences(text):
    prompt, options = split_options(text)
    wake = to_hour(re.search(r"woke up at (\d{1,2}(?:am|pm))", prompt, re.I).group(1))
    close = to_hour(re.search(r"closed after (\d{1,2}(?:am|pm))", prompt, re.I).group(1))
    occupied = [
        (to_hour(a), to_hour(b))
        for a, b in re.findall(r"from (\d{1,2}(?:am|pm)) to (\d{1,2}(?:am|pm))", prompt, re.I)
    ]
    for label, option in options:
        match = re.fullmatch(r"(\d{1,2}(?:am|pm)) to (\d{1,2}(?:am|pm))", option)
        start, end = to_hour(match.group(1)), to_hour(match.group(2))
        overlaps = any(start < busy_end and end > busy_start for busy_start, busy_end in occupied)
        if wake <= start < end <= close and not overlaps:
            return label
    return None


def solve_order_task(text):
    prompt, options, converted = choice_example(text)
    answer, _ = sol_v2.solve_order(converted)
    return option_label(answer, options)


def solve_shuffle_task(text):
    prompt, options, converted = choice_example(text)
    answer, _ = sol_v2.solve_shuffle(converted)
    return option_label(answer, options)


def solve_date_task(text):
    prompt, options, converted = choice_example(text)
    answer, _ = sol_base.solve_date(converted)
    return option_label(answer, options)


SOLVERS = {
    "boolean_expressions": solve_boolean,
    "date_understanding": solve_date_task,
    "dyck_languages": solve_dyck,
    "logical_deduction_five_objects": solve_order_task,
    "logical_deduction_seven_objects": solve_order_task,
    "logical_deduction_three_objects": solve_order_task,
    "multistep_arithmetic_two": solve_arithmetic,
    "navigate": solve_navigate,
    "object_counting": solve_object_counting,
    "temporal_sequences": solve_temporal_sequences,
    "tracking_shuffled_objects_five_objects": solve_shuffle_task,
    "tracking_shuffled_objects_seven_objects": solve_shuffle_task,
    "tracking_shuffled_objects_three_objects": solve_shuffle_task,
    "web_of_lies": solve_web_of_lies,
    "word_sorting": solve_word_sorting,
}


def evaluate_task(task):
    dataset = download_task(task)
    solver = SOLVERS.get(task)
    correct = covered = 0
    errors = []
    for index, example in enumerate(dataset["examples"]):
        prediction = None
        failure = None
        if solver is not None:
            try:
                prediction = solver(example["input"])
            except Exception as exc:  # explicit failure ledger
                failure = f"{type(exc).__name__}: {exc}"
        covered += int(prediction is not None)
        is_correct = normalize(prediction) == normalize(example["target"])
        correct += int(is_correct)
        if not is_correct and len(errors) < 50:
            errors.append({
                "index": index,
                "input": example["input"],
                "gold": example["target"],
                "prediction": prediction,
                "failure": failure,
            })
    n = len(dataset["examples"])
    return {
        "n": n,
        "correct": correct,
        "accuracy": correct / n,
        "coverage": covered / n,
        "implemented": solver is not None,
        "errors": errors,
    }


def main():
    artifacts = HERE / "artifacts"
    artifacts.mkdir(exist_ok=True)
    report = {
        "name": "SOL-BBH frontier system",
        "protocol": "Official public BBH files; exact match; abstention counts wrong",
        "tasks": {},
    }
    for task in TASKS:
        result = evaluate_task(task)
        report["tasks"][task] = result
        print(task, result["accuracy"], result["coverage"], result["correct"], result["n"])
    accuracies = [result["accuracy"] for result in report["tasks"].values()]
    total_correct = sum(result["correct"] for result in report["tasks"].values())
    total_n = sum(result["n"] for result in report["tasks"].values())
    report["aggregate"] = {
        "task_count": len(TASKS),
        "implemented_task_count": sum(result["implemented"] for result in report["tasks"].values()),
        "macro_accuracy": sum(accuracies) / len(accuracies),
        "micro_accuracy": total_correct / total_n,
        "correct": total_correct,
        "n": total_n,
    }
    report["hashes"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((HERE / ".bbh_cache").glob("*.json"))
    }
    (artifacts / "results.json").write_text(json.dumps(report, indent=2))
    lines = [
        "# SOL-BBH frontier baseline",
        "",
        "| Task | Accuracy | Coverage | Correct/N |",
        "|---|---:|---:|---:|",
    ]
    for task, result in report["tasks"].items():
        lines.append(
            f"| {task} | {result['accuracy']:.4f} | {result['coverage']:.4f} | "
            f"{result['correct']}/{result['n']} |"
        )
    aggregate = report["aggregate"]
    lines += [
        "",
        f"**Macro accuracy:** {aggregate['macro_accuracy']:.4f}",
        f"**Micro accuracy:** {aggregate['micro_accuracy']:.4f}",
        f"**Implemented tasks:** {aggregate['implemented_task_count']}/{aggregate['task_count']}",
        "",
        "Unsupported tasks and parser failures count as wrong.",
    ]
    (artifacts / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(report["aggregate"], indent=2))


if __name__ == "__main__":
    main()
