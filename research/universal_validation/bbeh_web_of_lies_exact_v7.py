#!/usr/bin/env python3
from __future__ import annotations
import json,pathlib,re,sys,time,z3
LOC_RE=r'the person at the ([a-z ]+?)'

def clean_entity(raw:str)->str:
 raw=raw.strip().rstrip('.,?')
 m=re.fullmatch(LOC_RE,raw,re.I)
 return '@'+m.group(1).strip().lower() if m else raw

def names3(content:str):
 m=re.search(r'(?:of\s+)?([A-Z][A-Za-z]+),\s*([A-Z][A-Za-z]+)\s+and\s+([A-Z][A-Za-z]+)',content)
 return list(m.groups()) if m else None

def count_is(xs,k):return z3.Sum([z3.If(x,1,0) for x in xs])==k

def proposition(content,var):
 content=content.strip().rstrip('.')
 low=content.lower()
 ns=names3(content)
 if ns:
  xs=[var(n) for n in ns]
  if 'only one of' in low and re.search(r'\blies\b',low):return count_is(xs,2)
  if 'all three' in low and ('tell the truth' in low or 'tells the truth' in low) and 'only one' in low:
   return z3.Or(count_is(xs,3),count_is(xs,1))
  if ('exactly one' in low or 'only one' in low) and ('tell the truth' in low or 'tells the truth' in low):
   return z3.Or(count_is(xs,1),count_is(xs,3)) if 'or all three' in low else count_is(xs,1)
  if 'exactly two' in low and ('tell the truth' in low or 'tells the truth' in low):
   return z3.Or(count_is(xs,2),count_is(xs,0)) if 'or none' in low else count_is(xs,2)
  if 'all three' in low and 'lie' in low and 'two of them tell the truth' in low:return z3.Or(count_is(xs,0),count_is(xs,2))
  if 'all tell the truth' in low or ('all three' in low and 'tell the truth' in low):return count_is(xs,3)
  if 'all three' in low and 'lie' in low:return count_is(xs,0)
  if 'two of them tell the truth' in low:return count_is(xs,2)
  return None
 m=re.fullmatch(r'([A-Z][A-Za-z]+|the person at the [a-z ]+?)\s+(tells the truth|lies)',content,re.I)
 if not m:return None
 target=clean_entity(m.group(1));return var(target) if m.group(2).lower()=='tells the truth' else z3.Not(var(target))

def solve(text:str)->str:
 text=re.sub(r'\.(?=[A-Z])','. ',text)
 variables={}
 def var(name):
  key=clean_entity(name)
  if key not in variables:variables[key]=z3.Bool('v'+str(len(variables)))
  return variables[key]
 solver=z3.Solver()
 declarative=re.split(r'\bDoes\b|\bDo\b',text,maxsplit=1)[0]
 declarative=re.sub(r'^In this question, assume each person either always tells the truth or always lies\.\s*','',declarative)
 for sentence in re.split(r'(?<=\.)\s+',declarative):
  sentence=sentence.strip()
  if not sentence:continue
  if re.fullmatch(r'[A-Z][A-Za-z]+ is at the [a-z ]+\.',sentence):continue
  low=sentence.lower()
  if low.endswith(' tells the truth.') and ' says ' not in low:
   subject=clean_entity(sentence[:-len(' tells the truth.')]);solver.add(var(subject));continue
  if low.endswith(' lies.') and ' says ' not in low:
   subject=clean_entity(sentence[:-len(' lies.')]);solver.add(z3.Not(var(subject)));continue
  if ' says ' in sentence:
   speaker_raw,content=sentence.split(' says ',1);p=proposition(content,var)
   if p is not None:solver.add(var(clean_entity(speaker_raw))==p)
 queries=[clean_entity(m.group(1)) for m in re.finditer(r'Does\s+(the person at the [a-z ]+?)\s+tell the truth\?',text,re.I)]
 if not queries:
  m=re.search(r'\bDo\s+(.+?)\s+tell the truth\?',text,re.S|re.I)
  if m:queries=re.findall(r'[A-Z][A-Za-z]+',m.group(1))
 if len(queries)!=3:raise ValueError(f'query parse {queries}')
 out=[]
 for q in queries:
  v=var(q);solver.push();solver.add(v);yes=solver.check()==z3.sat;solver.pop();solver.push();solver.add(z3.Not(v));no=solver.check()==z3.sat;solver.pop()
  out.append('yes' if yes and not no else 'no' if no and not yes else 'unknown')
 return ', '.join(out)

def main(path):
 ex=json.loads(pathlib.Path(path).read_text())['examples'];errs=[];st=time.time()
 for i,e in enumerate(ex):
  try:p=solve(e['input']);err=None
  except Exception as exc:p=None;err=f'{type(exc).__name__}: {exc}'
  if p!=e['target']:errs.append((i,p,e['target'],err))
 print('correct',len(ex)-len(errs),'/',len(ex),'elapsed',time.time()-st)
 for x in errs[:100]:print(x)
if __name__=='__main__':main(sys.argv[1])
