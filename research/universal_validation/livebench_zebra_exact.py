#!/usr/bin/env python3
from __future__ import annotations

import re
import z3


def parse_problem(text):
    match=re.search(r'There are (\d+) people',text,re.I)
    if not match:
        raise ValueError('missing n')
    n=int(match.group(1))
    categories_match=re.search(r'Each person has a set of attributes:\s*(.*?)\.',text,re.S|re.I)
    categories=[item.strip() for item in categories_match.group(1).split(',')]
    values_match=re.search(r'The attributes have the following possible values:\s*(.*?)(?:\nEach person has|\nand exactly one person)',text,re.S|re.I)
    values_by_category={}
    for line in values_match.group(1).splitlines():
        line=line.strip().lstrip('-').strip()
        if ':' not in line:
            continue
        category,values=line.split(':',1)
        values_by_category[category.strip()]=[value.strip() for value in values.split(',')]
    categories=[next((key for key in values_by_category if key.lower()==category.lower()),category) for category in categories]
    value_to_category={value:category for category,values in values_by_category.items() for value in values}
    if 'You know the following about the people:' in text:
        block=text.split('You know the following about the people:',1)[1].split('Given this information',1)[0]
        question_block=text.split('Given this information, answer the following questions:',1)[1].split('Think step by step',1)[0]
    else:
        block=text.split('Given the following premises about the line of people:',1)[1].split('Answer the following question:',1)[0]
        question_block=text.split('Answer the following question:',1)[1].split('Return ',1)[0]
    clues=[]
    for line in block.splitlines():
        line=line.strip().lstrip('-').strip()
        if line and not line.lower().startswith('in the above'):
            clues.append(line)
    questions=[question.strip() for question in question_block.splitlines() if question.strip()]
    return n,categories,values_by_category,value_to_category,clues,questions


def occurrences(text,values):
    low=text.lower()
    spans=[]
    for value in sorted(values,key=len,reverse=True):
        pattern=r'(?<![\w-])'+re.escape(value.lower())+r'(?![\w-])'
        for match in re.finditer(pattern,low):
            spans.append((match.start(),match.end(),value))
    spans.sort()
    occupied=[]
    found=[]
    for start,end,value in spans:
        if any(not (end<=left or start>=right) for left,right in occupied):
            continue
        occupied.append((start,end))
        found.append((start,value))
    return [value for _,value in sorted(found)]


def between(value,left,right):
    return z3.Or(z3.And(left<value,value<right),z3.And(right<value,value<left))


def compile_atomic(clue,variables,n,all_values):
    low=clue.lower().strip().rstrip('.')
    values=occurrences(low,all_values)
    if 'on the far left or far right' in low:
        return z3.Or(variables[values[0]]==1,variables[values[0]]==n)
    if 'on the far left' in low:
        return variables[values[0]]==1
    if 'on the far right' in low:
        return variables[values[0]]==n
    if 'in the middle' in low:
        return variables[values[0]]==(n+1)//2
    position=re.search(r'in (?:the )?(\d+)(?:st|nd|rd|th)? position',low)
    if position and values:
        return variables[values[0]]==int(position.group(1))
    if 'in an even position' in low:
        return variables[values[0]]%2==0
    if 'in an odd position' in low:
        return variables[values[0]]%2==1
    if 'same parity positions' in low:
        return variables[values[0]]%2==variables[values[1]]%2
    if 'different parity positions' in low:
        return variables[values[0]]%2!=variables[values[1]]%2
    if 'immediately between' in low:
        return z3.And(z3.Abs(variables[values[0]]-variables[values[1]])==1,z3.Abs(variables[values[0]]-variables[values[2]])==1,variables[values[1]]!=variables[values[2]])
    if 'somewhere between' in low:
        return between(variables[values[0]],variables[values[1]],variables[values[2]])
    distance=re.search(r'(\d+) (?:people|persons?) (?:are )?between',low)
    if distance and len(values)>=2:
        return z3.Abs(variables[values[0]]-variables[values[1]])==int(distance.group(1))+1
    if 'immediate left or immediate right' in low:
        return z3.Abs(variables[values[0]]-variables[values[1]])==1
    if 'on the immediate left of' in low:
        return variables[values[0]]+1==variables[values[1]]
    if 'on the immediate right of' in low:
        return variables[values[0]]==variables[values[1]]+1
    distance=re.search(r'(\d+) places? to the left of',low)
    if distance:
        return variables[values[0]]+int(distance.group(1))==variables[values[1]]
    distance=re.search(r'(\d+) places? to the right of',low)
    if distance:
        return variables[values[0]]==variables[values[1]]+int(distance.group(1))
    if 'not anywhere to the left of' in low:
        return variables[values[0]]>=variables[values[1]]
    if 'not anywhere to the right of' in low:
        return variables[values[0]]<=variables[values[1]]
    if 'somewhere to the left of' in low:
        return variables[values[0]]<variables[values[1]]
    if 'somewhere to the right of' in low:
        return variables[values[0]]>variables[values[1]]
    negative_markers=('not the same as','does not own','doesn\'t own','does not eat','doesn\'t eat','cannot stand','avoids getting on','is not ','hates ','dislikes ','cannot play','does not drink','doesn\'t drink','does not watch','doesn\'t watch','does not play','doesn\'t play','does not like','doesn\'t like')
    if len(values)>=2 and any(marker in low for marker in negative_markers):
        return variables[values[0]]!=variables[values[1]]
    if len(values)>=2:
        return variables[values[0]]==variables[values[1]]
    raise ValueError(f'uncompiled atomic: {clue} values={values}')


def split_logical(clue):
    low=clue.lower()
    if ', but not both' in low:
        body=clue[:low.rfind(', but not both')]
        return 'xor',re.split(r'\s+or\s+',body,maxsplit=1,flags=re.I)
    if ' or both' in low:
        body=clue[:low.rfind(' or both')]
        return 'or',re.split(r'\s+or\s+',body,maxsplit=1,flags=re.I)
    return None,None


def compile_clue(clue,variables,n,all_values):
    kind,parts=split_logical(clue)
    if kind:
        first=compile_atomic(parts[0],variables,n,all_values)
        second=compile_atomic(parts[1],variables,n,all_values)
        return z3.Xor(first,second) if kind=='xor' else z3.Or(first,second)
    return compile_atomic(clue,variables,n,all_values)


def category_from_question(question,categories):
    low=question.lower().strip()
    requested=[
        (('what is the job','what job'),'Job'),
        (('what is the movie genre','what movie genre'),'Movie-Genre'),
        (('what is the music genre','what music genre','what kind of music'),'Music-Genre'),
        (('what is the nationality','what nationality'),'Nationality'),
        (('what is the sport','what sport'),'Sport'),
        (('what is the pet','what pet','what kind of pet'),'Pet'),
        (('what is the beverage','what beverage'),'Beverage'),
        (('what is the food','what food'),'Food'),
        (('what is the transport','what transport'),'Transport'),
        (('what is the hobby','what hobby'),'Hobby'),
    ]
    for prefixes,category in requested:
        if any(low.startswith(prefix) for prefix in prefixes):
            return next((item for item in categories if item.lower()==category.lower()),None)
    if ' drink' in low:
        return next((item for item in categories if item.lower()=='beverage'),None)
    if ' watch' in low or (' prefer' in low and any(item.lower()=='movie-genre' for item in categories)):
        return next((item for item in categories if item.lower()=='movie-genre'),None)
    if ' listen' in low or ' enjoy' in low:
        return next((item for item in categories if item.lower()=='music-genre'),None)
    if ' travel' in low or ' use' in low:
        return next((item for item in categories if item.lower()=='transport'),None)
    if ' eat' in low or ' food' in low:
        return next((item for item in categories if item.lower()=='food'),None)
    if ' play' in low:
        return next((item for item in categories if item.lower()=='sport'),None)
    if ' own' in low:
        return next((item for item in categories if item.lower()=='pet'),None)
    if ' do' in low or ' like' in low:
        return next((item for item in categories if item.lower()=='hobby'),None)
    return None


def solve(text,debug=False):
    n,categories,values_by_category,value_to_category,clues,questions=parse_problem(text)
    all_values=list(value_to_category)
    variables={value:z3.Int('p_'+re.sub(r'\W+','_',value)) for value in all_values}
    solver=z3.Solver()
    for value in all_values:
        solver.add(variables[value]>=1,variables[value]<=n)
    for values in values_by_category.values():
        solver.add(z3.Distinct([variables[value] for value in values]))
    failures=[]
    for clue in clues:
        try:
            solver.add(compile_clue(clue,variables,n,all_values))
        except Exception as exc:
            failures.append((clue,str(exc)))
    if failures:
        if debug:
            return {'failures':failures,'n':n,'clues':len(clues)}
        raise ValueError(failures)
    if solver.check()!=z3.sat:
        if debug:
            return {'unsat':True,'n':n,'clues':len(clues)}
        return None
    answers=[]
    for question in questions:
        low=question.lower()
        values=occurrences(question,all_values)
        if 'at what position' in low:
            if not values:
                raise ValueError('position question without value: '+question)
            expression=variables[values[0]]
            possible=[]
            for position in range(1,n+1):
                solver.push();solver.add(expression==position)
                if solver.check()==z3.sat:
                    possible.append(position)
                solver.pop()
            answers.append(str(possible[0]) if len(possible)==1 else None)
            continue
        category=category_from_question(question,categories)
        if category is None:
            raise ValueError('unknown question category: '+question)
        position_match=re.search(r'person in position\s+(\d+)|position\s+(\d+)|(?:the\s+)?(first|second|third|fourth|fifth)\s+(?:position|person)',low)
        if position_match:
            token=next(item for item in position_match.groups() if item)
            ordinal={'first':1,'second':2,'third':3,'fourth':4,'fifth':5}
            position=int(token) if token.isdigit() else ordinal[token]
            reference=z3.IntVal(position)
        else:
            if not values:
                raise ValueError('attribute question without reference value: '+question)
            reference=variables[values[0]]
        candidates=[]
        for candidate in values_by_category[category]:
            solver.push();solver.add(variables[candidate]==reference)
            if solver.check()==z3.sat:
                candidates.append(candidate)
            solver.pop()
        answers.append(candidates[0] if len(candidates)==1 else None)
    if debug:
        return {'answers':answers,'n':n,'clues':len(clues),'questions':questions}
    return ', '.join(answers) if all(answer is not None for answer in answers) else None
