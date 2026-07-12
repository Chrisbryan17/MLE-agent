#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Optional

VECTORS={
 'right':(1,0),'left':(-1,0),
 'up-right':(1,-1),'down-left':(-1,1),
 'up-left':(0,-1),'down-right':(0,1),
 'up':(0,-1),'down':(0,1),
}
NUM={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}

def clean_obj(s:str)->str:
 s=s.strip().strip(' .')
 s=re.sub(r'^(?:a|an|the)\s+','',s,flags=re.I)
 return s

def split_items(s:str):
 s=re.sub(r'\b(?:and|or)\b',',',s)
 return [clean_obj(x) for x in s.split(',') if clean_obj(x)]

def solve_tree(text:str)->Optional[str]:
 parent:dict[str,set[str]]={}
 def add_parent(child:str,p:str):parent.setdefault(child.lower(),set()).add(p.lower())
 for m in re.finditer(r'\b([a-z][a-z ]*?) has (?:no grandchildren but has )?(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) children[:;]\s*(.*?)(?=\.)',text,re.I):
  p=clean_obj(m.group(1)).lower()
  for c in split_items(m.group(2)):add_parent(c,p)
 for m in re.finditer(r'\b([a-z][a-z ]*?) has (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) grandchildren:\s*(.*?)(?=\.)',text,re.I):
  gp=clean_obj(m.group(1)).lower();body=m.group(2)
  for gm in re.finditer(r'(.+?)\(whose parent is ([^)]+)\)',body,re.I):
   segment=re.sub(r'^\s*(?:and\s+)?','',gm.group(1));p=clean_obj(gm.group(2)).lower();add_parent(p,gp)
   for c in split_items(segment):add_parent(c,p)
 q=re.search(r'What is the cousin of the (.+?)\?',text,re.I)
 if not q:return None
 target=clean_obj(q.group(1)).lower();cousins=set()
 for p0 in parent.get(target,set()):
  for gp in parent.get(p0,set()):
   sibling_parents={node for node,ps in parent.items() if gp in ps and node!=p0}
   cousins.update(node for node,ps in parent.items() if ps & sibling_parents)
 cousins.discard(target)
 return ', '.join(sorted(cousins)) if cousins else 'unknown'

class Tracker:
 def __init__(self):
  self.var_solution={};self.current=(None,(0,0));self.obs={};self.coord_obj={}
 def resolve(self,pos):
  var,off=pos
  if var is None:return off
  if var in self.var_solution:
   b=self.var_solution[var];return (b[0]+off[0],b[1]+off[1])
  return None
 def move(self,d,n=1):
  var,(x,y)=self.current;dx,dy=VECTORS[d];self.current=(var,(x+dx*n,y+dy*n))
  if var in self.var_solution:self.current=(None,self.resolve(self.current))
 def jump(self,var):
  self.current=(None,self.var_solution[var]) if var in self.var_solution else (var,(0,0))
 def observe(self,obj):
  obj=clean_obj(obj);pos=self.current;self.obs.setdefault(obj,[]).append(pos);absolute=self.resolve(pos)
  if absolute is not None:self.coord_obj[absolute]=obj
  for other in self.obs[obj]:
   a=self.resolve(other);b=self.resolve(pos)
   if a is not None and b is None:
    var,off=pos;self.var_solution[var]=(a[0]-off[0],a[1]-off[1])
   elif b is not None and a is None:
    var,off=other;self.var_solution[var]=(b[0]-off[0],b[1]-off[1])
  for name,positions in self.obs.items():
   for pp in positions:
    aa=self.resolve(pp)
    if aa is not None:self.coord_obj[aa]=name
  if self.current[0] in self.var_solution:self.current=(None,self.resolve(self.current))
 def answer(self):
  pos=self.resolve(self.current);return self.coord_obj.get(pos,'unknown') if pos is not None else 'unknown'

def solve_circular(text:str)->Optional[str]:
 m=re.search(r'circular (?:path|grid) consisting of (\d+) connected dots',text,re.I)
 if not m:return None
 n=int(m.group(1))
 listed=re.search(r'where you find (?:a|an|the)?\s*(.*?)\. Moving in a clockwise direction from .*?, the elements on the path are (.*?)\. Starting from (.*?), you move around the ring by (.*?)\. What will',text,re.I|re.S)
 if listed:
  first=clean_obj(listed.group(1));s=listed.group(2).replace(', and ', ',').replace(' and ',',')
  objects=[first]+[clean_obj(x) for x in s.split(',') if clean_obj(x)];start_obj=clean_obj(listed.group(3))
  if len(objects)!=n or start_obj not in objects:return None
  idx=objects.index(start_obj)
  for steps,direction in re.findall(r'(\d+) steps? in a (counter-clockwise|clockwise) direction',listed.group(4),re.I):idx=(idx+(int(steps) if direction.lower()=='clockwise' else -int(steps)))%n
  return objects[idx]
 initial=re.search(r'Initially,.*?where you find\s+(?:a|an|the)?\s*(.*?)\.',text,re.I|re.S)
 if not initial:return None
 idx=0;seen={0:clean_obj(initial.group(1))};tail=re.split(r'What will you find\?',text[initial.end():],maxsplit=1,flags=re.I)[0]
 for mm in re.finditer(r'move around the ring by (\d+) steps? in a (counter-clockwise|clockwise) direction(?:, where you find\s+(?:a|an|the)?\s*(.*?))?\.',tail,re.I|re.S):
  steps=int(mm.group(1));idx=(idx+(steps if mm.group(2).lower()=='clockwise' else -steps))%n
  if mm.group(3):seen[idx]=clean_obj(mm.group(3))
 return seen.get(idx,'unknown')

def parse_observation(tail:str)->Optional[str]:
 m=re.search(r'(?:and see|where you (?:see|find))\s+(.+)$',tail,re.I);return clean_obj(m.group(1)) if m else None

def solve_lattice(text:str)->Optional[str]:
 tr=Tracker();m=re.search(r'(?:initially|initially at|You are initially).*?where you (?:see|find)\s+(.+?)\.',text,re.I|re.S)
 if not m:return None
 tr.observe(m.group(1));narrative=re.split(r'What will you find\?',text[m.end():],maxsplit=1,flags=re.I)[0]
 for clause in [c.strip() for c in re.split(r'(?<=\.)\s*',narrative) if c.strip()]:
  low=clause.lower()
  if 'jump to a random vertex' in low:
   vm=re.search(r'random vertex\s+([A-Z])',clause);tr.jump(vm.group(1) if vm else 'V');om=re.search(r'where you see\s+(.+?)\.',clause,re.I)
   if om:tr.observe(om.group(1))
   continue
  if 'jump back to the random vertex' in low:
   vm=re.search(r'random vertex\s+([A-Z])',clause);tr.jump(vm.group(1) if vm else 'V');seqm=re.search(r'following moves:\s*(.*?)\.',clause,re.I|re.S)
   if seqm:
    for d in re.findall(r'up-right|up-left|down-right|down-left|right|left|up|down',seqm.group(1),re.I):tr.move(d.lower(),1)
   continue
  if "don't move" in low or 'do not move' in low:continue
  mm=re.search(r'(?:you )?move\s+(up-right|up-left|down-right|down-left|right|left|up|down)\s+(?:for|by)\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+steps?',clause,re.I)
  if mm:
   n=int(mm.group(2)) if mm.group(2).isdigit() else NUM[mm.group(2).lower()];tr.move(mm.group(1).lower(),n);obj=parse_observation(clause.rstrip('.'))
   if obj:tr.observe(obj)
 return tr.answer()

def solve(text:str)->Optional[str]:
 if 'tree structure' in text:return solve_tree(text)
 if 'circular path' in text or 'circular grid' in text:return solve_circular(text)
 return solve_lattice(text)
