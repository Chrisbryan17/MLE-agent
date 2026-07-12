#!/usr/bin/env python3
from __future__ import annotations

import ast
import collections
import dataclasses
import itertools
import json
import math
import operator
import re
from pathlib import Path
from typing import Any, Callable, Iterable

from sympy import And, Equivalent, Not, Or, Symbol
from sympy.logic.inference import satisfiable


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------

OPTION_MARKER_RE = re.compile(r"(?<![A-Za-z0-9_])\(([A-Z])\)\s+")
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10,
}


def options(text: str) -> dict[str, str]:
    """Parse multiple-choice options independently of line wrapping.

    BBEH usually prints one option per line, but semantics do not depend on
    newlines.  We identify standalone option markers and slice to the next
    marker.  Markers are restricted to single uppercase letters and a word
    boundary on the left, which excludes parentheses inside expressions.
    """
    # Prefer the explicit options section when present so parenthesized labels
    # in demonstrations or prose cannot be mistaken for answer choices.
    section = text.split("Options:", 1)[1] if "Options:" in text else text
    markers = list(OPTION_MARKER_RE.finditer(section))
    result: dict[str, str] = {}
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(section)
        result[marker.group(1)] = section[start:end].strip()
    return result


def normalize_answer(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip()


# ---------------------------------------------------------------------------
# Boolean Expressions
# ---------------------------------------------------------------------------

TRUE_CAPITALS = {
    ("afghanistan", "kabul"), ("armenia", "yerevan"),
    ("azerbaijan", "baku"), ("belarus", "minsk"),
    ("cameroon", "yaounde"), ("canada", "ottawa"),
    ("colombia", "bogota"), ("denmark", "copenhagen"),
    ("gambia", "banjul"), ("germany", "berlin"),
    ("india", "new delhi"), ("iran", "tehran"),
    ("iraq", "baghdad"), ("jordan", "amman"),
    ("malaysia", "kuala lumpur"), ("nepal", "kathmandu"),
    ("norway", "oslo"), ("turkey", "ankara"),
    ("uae", "abu dhabi"), ("the nigeria", "abuja"),
}

CAPITAL_RE = re.compile(r"The capital of (.+?) is (.+?)\.")


def _capital_replace(match: re.Match[str]) -> str:
    pair = (match.group(1).strip().lower(), match.group(2).strip().lower())
    return "True" if pair in TRUE_CAPITALS else "False"


def _pythonize_boolean(expr: str) -> str:
    # Whitespace is not semantic. Canonicalize it before matching natural-
    # language atoms such as capital-city claims and comparison phrases.
    expr = re.sub(r"\s+", " ", expr).strip()
    expr = CAPITAL_RE.sub(_capital_replace, expr)
    replacements = [
        (r"\bis greater than or equal to\b", ">="),
        (r"\bis less than or equal to\b", "<="),
        (r"\bis greater than\b", ">"),
        (r"\bis less than\b", "<"),
    ]
    for pattern, replacement in replacements:
        expr = re.sub(pattern, replacement, expr)
    expr = expr.replace(".", "")
    return expr


def solve_boolean_expressions(text: str) -> str | None:
    for letter, expr in options(text).items():
        candidate = _pythonize_boolean(expr)
        try:
            value = eval(candidate, {"__builtins__": {}}, {"max": max, "min": min})
        except Exception:
            continue
        if value is True:
            return f"({letter})"
    return None


# ---------------------------------------------------------------------------
# Dyck-language trace auditor
# ---------------------------------------------------------------------------

OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}", "<": ">"}
CLOSE_TO_OPEN = {v: k for k, v in OPEN_TO_CLOSE.items()}


def _stack_text(stack: list[str]) -> str:
    return " ".join(stack) if stack else "empty"


def solve_dyck_languages(text: str) -> str:
    m = re.search(r"Input:\s*(.*?)\nThought 1:", text, re.S)
    if not m:
        return "No"
    tokens = re.findall(r"[()\[\]{}<>]", m.group(1))
    thoughts = {
        int(n): body.strip()
        for n, body in re.findall(r"Thought\s+(\d+):\s*(.*?)(?=\nThought\s+\d+:|\nQ:|\Z)", text, re.S)
    }
    stack: list[str] = []
    token_thought = 3
    for token in tokens:
        if token in OPEN_TO_CLOSE:
            stack.append(token)
        else:
            if stack and stack[-1] == CLOSE_TO_OPEN[token]:
                stack.pop()
        body = thoughts.get(token_thought, "")
        claim = re.search(r"^\s*([()\[\]{}<>])\s*;\s*stack:\s*(.*)$", body)
        if not claim or claim.group(1) != token:
            return str(token_thought)
        claimed = re.sub(r"\s+", " ", claim.group(2).strip())
        if claimed != _stack_text(stack):
            return str(token_thought)
        token_thought += 1
    expected_closings = " ".join(OPEN_TO_CLOSE[ch] for ch in reversed(stack))
    for n in sorted(k for k in thoughts if k >= token_thought):
        body = thoughts[n]
        low = body.lower()
        if "final stack" in low:
            if "empty" in low:
                claimed = "empty"
            else:
                quoted = re.search(r'final stack is\s*["\'](.*?)["\']', body, re.I)
                claimed = re.sub(r"\s+", " ", quoted.group(1).strip()) if quoted else None
            if claimed is not None and claimed != _stack_text(stack):
                return str(n)
        if "we will need to pop" in low:
            quoted = re.findall(r'["\']([()\[\]{}<>])["\']', body)
            if quoted and quoted != list(reversed(stack)):
                return str(n)
        if re.search(r"so,?\s+we need", low):
            tail = body.split("need", 1)[-1]
            tail = re.split(r"so the answer is", tail, maxsplit=1, flags=re.I)[0]
            claimed = " ".join(re.findall(r"[()\[\]{}<>]", tail))
            if claimed and claimed != expected_closings:
                return str(n)
        if "so the answer is" in low:
            tail = body.lower().split("so the answer is", 1)[-1]
            claimed = " ".join(re.findall(r"[()\[\]{}<>]", tail))
            if claimed != expected_closings:
                return str(n)
    return "No"


# ---------------------------------------------------------------------------
# Hyperbaton
# ---------------------------------------------------------------------------

CATEGORY_WORDS: dict[str, set[str]] = {
    "opinion": {"awful", "beautiful", "good", "lovely", "mysterious", "nice", "normal", "obnoxious", "repulsive", "ridiculous", "silly", "terrible", "wonderful"},
    "size": {"big", "enormous", "extra-large", "extra-small", "huge", "large", "little", "massive", "medium-size", "midsize", "normal-size", "small", "tiny"},
    "age": {"ancient", "archaic", "brand-new", "new", "old", "old-fashioned"},
    "shape": {"circular", "prismlike", "pyramidal", "rectangular", "spherical", "square", "triangular"},
    "color": {"beige", "black", "blue", "brown", "crimson", "cyan", "gold", "gray", "green", "indigo", "magenta", "maroon", "orange", "pink", "aqua", "purple", "red", "silver", "teal", "turquoise", "violet", "white", "yellow"},
    "origin": {"afghan", "american", "bangladeshi", "brazilian", "british", "canadian", "chinese", "congolese", "egyptian", "ethiopian", "filipino", "french", "german", "indian", "indonesian", "iranian", "italian", "japanese", "mexican", "nigerian", "pakistani", "polish", "portuguese", "russian", "spanish", "thai", "turkish", "vietnamese"},
    "material": {"cardboard", "ceramic", "cloth", "concrete", "fiberglass", "glass", "iron", "leather", "paper", "plastic", "rubber", "steel", "wood", "wool"},
    "purpose": {"drinking", "driving", "eating", "exercise", "hiking", "smoking", "snorkeling", "typing", "walking", "whittling"},
}
WORD_CATEGORY = {word: cat for cat, words in CATEGORY_WORDS.items() for word in words}


def _category_sequence(phrase: str) -> list[str]:
    tokens = re.findall(r"[a-z]+(?:-[a-z]+)?", phrase.lower())
    return [WORD_CATEGORY[t] for t in tokens if t in WORD_CATEGORY]


def _transitive_closure(edges: set[tuple[str, str]]) -> set[tuple[str, str]]:
    reach=set(edges)
    changed=True
    while changed:
        changed=False
        for a,b in list(reach):
            for c,d in list(reach):
                if b==c and (a,d) not in reach:
                    reach.add((a,d));changed=True
    return reach


def solve_hyperbaton(text: str) -> str | None:
    before=text.split("In this variant of English",1)[0]
    demos=re.findall(r"\(\d+\)\s*(.*?)(?=\s*\(\d+\)|\Z)",before,re.S)
    edges=set()
    for demo in demos:
        cats=_category_sequence(demo)
        for a,b in zip(cats,cats[1:]):edges.add((a,b))
    reach=_transitive_closure(edges)
    opts=options(text)
    for letter,phrase in opts.items():
        cats=_category_sequence(phrase)
        if len(cats)<2:continue
        if all((a,b) in reach for i,a in enumerate(cats) for b in cats[i+1:]):
            return f"({letter})"
    return None


# ---------------------------------------------------------------------------
# Multistep arithmetic language
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class OpDef:
    symbol: str
    params: tuple[str, ...]
    expression: str


def _eval_expr(expr: str, env: dict[str, int]) -> int:
    node=ast.parse(expr,mode="eval")
    allowed=(ast.Expression,ast.BinOp,ast.UnaryOp,ast.Constant,ast.Name,ast.Add,ast.Sub,ast.Mult,ast.FloorDiv,ast.Div,ast.Mod,ast.Pow,ast.USub,ast.UAdd)
    if not all(isinstance(n,allowed) for n in ast.walk(node)):raise ValueError
    value=eval(compile(node,"<expr>","eval"),{"__builtins__":{}},env)
    return int(value)


def solve_multistep_arithmetic(text: str) -> str | None:
    defs={}
    for line in text.splitlines():
        m=re.match(r"\s*Let\s+([a-z])\s*([+*#@%&^~!?]+)\s*([a-z])\s*=\s*(.+?)(?:\.|$)",line)
        if m:defs[m.group(2)]=(m.group(1),m.group(3),m.group(4).replace("$",""))
    q=re.search(r"(?:Compute|What is)\s+(.+?)(?:\?|$)",text,re.I|re.S)
    if not q:return None
    expr=q.group(1).strip().replace("$","")
    # Repeatedly reduce fully parenthesized custom operations.
    pat=re.compile(r"\((-?\d+)\s*([+*#@%&^~!?]+)\s*(-?\d+)\)")
    for _ in range(1000):
        m=pat.search(expr)
        if not m:break
        a,op,b=int(m.group(1)),m.group(2),int(m.group(3))
        if op in defs:
            x,y,body=defs[op];value=_eval_expr(body,{x:a,y:b})
        else:value=_eval_expr(f"{a}{op}{b}",{})
        expr=expr[:m.start()]+str(value)+expr[m.end():]
    try:value=_eval_expr(expr,{})
    except Exception:return None
    return str(value)


# ---------------------------------------------------------------------------
# Object counting
# ---------------------------------------------------------------------------

ITEM_WORDS=set('apple apples banana bananas orange oranges pear pears peach peaches plum plums grape grapes strawberry strawberries blueberry blueberries raspberry raspberries blackberry blackberries watermelon watermelons lemon lemons lime limes mango mangoes pineapple pineapples kiwi kiwis papaya papayas coconut coconuts avocado avocados cherry cherries fig figs date dates apricot apricots nectarine nectarines pomegranate pomegranates guava guavas lychee lychees dragonfruit dragonfruits guitar guitars piano pianos violin violins cello cellos flute flutes trumpet trumpets trombone trombones saxophone saxophones clarinet clarinets oboe oboes bassoon bassoons harp harps drum drums banjo banjos ukulele ukuleles accordion accordions harmonica harmonicas xylophone xylophones tambourine tambourines maraca maracas mandolin mandolins sitar sitars tuba tubas horn horns keyboard keyboards'.split())

def solve_object_counting(text:str)->str|None:
    q=text.split('Question:',1)[-1]
    count=0
    for num,item in re.findall(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+([a-z]+)",q,re.I):
        if item.lower() in ITEM_WORDS:count+=int(num) if num.isdigit() else NUMBER_WORDS[num.lower()]
    return str(count)


# ---------------------------------------------------------------------------
# Shuffled objects
# ---------------------------------------------------------------------------

def solve_shuffled_objects(text:str)->str|None:
    init=re.search(r"Initially,(.*?)(?=As the game progresses|Then|After)",text,re.S|re.I)
    source=init.group(1) if init else text
    assignments={}
    for m in re.finditer(r"\b([A-Z][a-zA-Z'-]*) (?:has|holds|is holding|is wearing|is playing|is dancing with) (?:a |an |the )?([^,.;]+)",source):assignments[m.group(1)]=m.group(2).strip()
    people=list(assignments)
    for a,b in re.findall(r"\b([A-Z][a-zA-Z'-]*) and ([A-Z][a-zA-Z'-]*) (?:swap|trade|switch)",text,re.I):
        ca=next((p for p in people if p.lower()==a.lower()),None);cb=next((p for p in people if p.lower()==b.lower()),None)
        if ca and cb:assignments[ca],assignments[cb]=assignments[cb],assignments[ca]
    q=re.search(r"At the end.*?([A-Z][a-zA-Z'-]*) (?:has|holds|is holding|is wearing|is playing|is dancing with) (?:the )?\s*$",text.strip(),re.I)
    if not q:return None
    person=next((p for p in people if p.lower()==q.group(1).lower()),None)
    return assignments.get(person)


# ---------------------------------------------------------------------------
# Web of lies — exact Boolean CSP
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class BoolConstraint:
    scope:tuple[str,...]
    allowed:set[tuple[bool,...]]

def _allowed_for(scope,fn):
    return BoolConstraint(tuple(scope),{bits for bits in itertools.product([False,True],repeat=len(scope)) if fn(dict(zip(scope,bits)))})

def _component_for_query(q,constraints):
    names={q};changed=True
    while changed:
        changed=False
        for c in constraints:
            if names.intersection(c.scope) and not set(c.scope)<=names:names.update(c.scope);changed=True
    return names,[c for c in constraints if set(c.scope)<=names]

def _csp_satisfiable(constraints,fixed):
    names=sorted(set(fixed)|{n for c in constraints for n in c.scope})
    for bits in itertools.product([False,True],repeat=max(0,len(names)-len(fixed))):
        a=dict(fixed);a.update(dict(zip([n for n in names if n not in fixed],bits)))
        if all(tuple(a[n] for n in c.scope) in c.allowed for c in constraints):return True
    return False

def solve_web_of_lies(text: str) -> str | None:
    location_to_person={loc.strip():person for person,loc in re.findall(r"\b([A-Z][A-Za-z]+) is at the ([a-z ]+?)(?=\.|,)",text)}
    def entity(raw):
        raw=raw.strip();m=re.fullmatch(r"the person at the ([a-z ]+)",raw,re.I)
        return location_to_person.get(m.group(1).strip(),f"@{m.group(1).strip()}") if m else raw
    constraints=[]
    def atom(s,t,neg):return _allowed_for(tuple(dict.fromkeys([s,t])),lambda a:a[s]==((not a[t]) if neg else a[t]))
    def cardinal(s,names,counts):return _allowed_for(tuple(dict.fromkeys([s]+names)),lambda a:a[s]==(sum(bool(a[n]) for n in names) in counts))
    def equiv(s,a,b):return _allowed_for(tuple(dict.fromkeys([s,a,b])),lambda x:x[s]==(x[a]==x[b]))
    def parse(speaker,content):
        speaker=entity(speaker);content=content.strip().rstrip('.')
        content=re.sub(r"the person at the [a-z ]+?(?=\s+(?:tells|lies)|$|,)",lambda m:entity(m.group(0)),content,flags=re.I)
        m=re.fullmatch(r"([A-Z][A-Za-z]+) tells the truth",content)
        if m:return atom(speaker,m.group(1),False)
        m=re.fullmatch(r"([A-Z][A-Za-z]+) lies",content)
        if m:return atom(speaker,m.group(1),True)
        m=re.search(r"both\s+([A-Z][A-Za-z]+) and ([A-Z][A-Za-z]+) lie or both tell the truth",content,re.I)
        if m:return equiv(speaker,m.group(1),m.group(2))
        m=re.search(r"(?:of\s+)?([A-Z][A-Za-z]+),\s*([A-Z][A-Za-z]+) and ([A-Z][A-Za-z]+)",content)
        if m:
            names=list(m.groups());low=content.lower()
            if ("all three" in low and "only one" in low) or ("all three" in low and "exactly one" in low):return cardinal(speaker,names,{1,3})
            if "exactly two" in low and "none" in low:return cardinal(speaker,names,{0,2})
            if "all three" in low and "two of them" in low:return cardinal(speaker,names,{0,2})
            if "all three" in low and "lie" in low and ("only one" in low or "exactly one" in low):return cardinal(speaker,names,{0,1})
            if ("only one" in low or "exactly one" in low) and "lies" in low:return cardinal(speaker,names,{2})
            if "exactly one" in low or "only one" in low:return cardinal(speaker,names,{1})
            if "exactly two" in low:return cardinal(speaker,names,{2})
            if "all three" in low and "tell the truth" in low:return cardinal(speaker,names,{3})
            if "all three" in low and "lie" in low:return cardinal(speaker,names,{0})
            if "two of them tell the truth" in low:return cardinal(speaker,names,{2})
        return None
    declarative=re.split(r"\b(?:Does|Do)\b",text,maxsplit=1)[0]
    for sentence in re.split(r"(?<=\.)\s*",declarative):
        sentence=sentence.strip()
        m=re.fullmatch(r"(.+?) tells the truth\.",sentence,re.I)
        if m and 'says' not in sentence.lower():
            n=entity(m.group(1));constraints.append(_allowed_for((n,),lambda a,n=n:a[n]));continue
        m=re.fullmatch(r"(.+?) lies\.",sentence,re.I)
        if m and 'says' not in sentence.lower():
            n=entity(m.group(1));constraints.append(_allowed_for((n,),lambda a,n=n:not a[n]));continue
        m=re.fullmatch(r"(.+?) says (.+)\.",sentence,re.I)
        if m:
            c=parse(m.group(1),m.group(2))
            if c:constraints.append(c)
    query=[]
    for loc in re.findall(r"Does the person at the ([a-z ]+?) tell the truth\?",text,re.I):query.append(entity(f"the person at the {loc}"))
    if not query:
        m=re.search(r"\bDo\s+(.+?)\s+tell the truth\?",text,re.I|re.S)
        if m:query=re.findall(r"[A-Z][A-Za-z]+",m.group(1))
    if len(query)!=3:return None
    ans=[]
    for q in query:
        _,cc=_component_for_query(q,constraints);t=_csp_satisfiable(cc,{q:True});f=_csp_satisfiable(cc,{q:False})
        ans.append('yes' if t and not f else 'no' if f and not t else 'unknown')
    return ', '.join(ans)


# ---------------------------------------------------------------------------
# Word sorting
# ---------------------------------------------------------------------------

def _alphabet_rank(description:str):
    alphabet=list('abcdefghijklmnopqrstuvwxyz');low=description.lower()
    m=re.search(r"alphabet order\s*\[([^]]+)\]",low)
    if m:
        chars=re.findall(r"\b[a-z]\b",m.group(1))
        if len(chars)==26 and len(set(chars))==26:alphabet=chars
    m=re.search(r"except that ([a-z]) and ([a-z]) are the first two letters",low)
    if m:
        for ch in m.groups():alphabet.remove(ch)
        alphabet=[m.group(1),m.group(2)]+alphabet
    m=re.search(r"except that ([a-z]) is the first letter",low)
    if m:alphabet.remove(m.group(1));alphabet.insert(0,m.group(1))
    m=re.search(r"except that ([a-z]) and ([a-z]) are the last two letters",low)
    if m:
        for ch in m.groups():alphabet.remove(ch)
        alphabet.extend(m.groups())
    else:
        m=re.search(r"except that ([a-z]) is the last letter",low)
        if m:alphabet.remove(m.group(1));alphabet.append(m.group(1))
    for a,b in re.findall(r"([a-z]) and ([a-z]) (?:are )?swapped",low):
        ia,ib=alphabet.index(a),alphabet.index(b);alphabet[ia],alphabet[ib]=alphabet[ib],alphabet[ia]
    return {ch:i for i,ch in enumerate(alphabet)}

def solve_word_sorting(text:str)->str|None:
    if 'Consider a new alphabet' in text:
        m=re.search(r"Sort the following words.*?:\s*(.*)$",text,re.S)
        if not m:return None
        words=[w.strip() for w in m.group(1).split(',')];rank=_alphabet_rank(text)
        return ', '.join(sorted(words,key=lambda w:tuple(rank.get(ch,99) for ch in w.lower())))
    # Trace-audit variant: recompute expected alphabetical order and locate first wrong thought.
    m=re.search(r"Input:\s*(.*?)\nThought 1:",text,re.S)
    if not m:return None
    words=[w.strip() for w in m.group(1).split(',')]
    expected=sorted(words,key=str.lower)
    thoughts={int(n):b.strip() for n,b in re.findall(r"Thought\s+(\d+):\s*(.*?)(?=\nThought\s+\d+:|\nQ:|\Z)",text,re.S)}
    for n,b in sorted(thoughts.items()):
        if 'answer is' in b.lower():
            claimed=[x.strip() for x in b.split('answer is',1)[-1].strip(' .[]').split(',')]
            if claimed!=expected:return str(n)
    return 'No'

SOLVERS:dict[str,Callable[[str],str|None]]={
 'bbeh_boolean_expressions':solve_boolean_expressions,
 'bbeh_dyck_languages':solve_dyck_languages,
 'bbeh_hyperbaton':solve_hyperbaton,
 'bbeh_multistep_arithmetic':solve_multistep_arithmetic,
 'bbeh_object_counting':solve_object_counting,
 'bbeh_shuffled_objects':solve_shuffled_objects,
 'bbeh_web_of_lies':solve_web_of_lies,
 'bbeh_word_sorting':solve_word_sorting,
}

def predict(task,text):
 fn=SOLVERS.get(task);return fn(text) if fn else None
