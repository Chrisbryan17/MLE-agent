#!/usr/bin/env python3
from __future__ import annotations
import collections,dataclasses,re
SIZES=['extra-extra-large','extra-extra-small','extra-large','extra-small','medium','large','small']
ORIGINS=['Afghan','Brazilian','British','Canadian','Chinese','French','German','Iranian','Italian','Japanese','Mexican','Polish','Portuguese','Russian','Spanish','Turkish']
MATERIALS=['concrete','glass','plastic','ceramic','steel']
SMELLS=['wet dog','baking bread','pine needles','burning wood','garlic','vinegar','rose','popcorn','coconut','gasoline','coffee','chocolate','citrus fruits','lavender','vanilla','leather','freshly cut grass']
COLORS=['beige','black','blue','brown','crimson','cyan','gold','gray','green','indigo','ivory','khaki','magenta','maroon','orange','pink','purple','red','silver','teal','turquoise','violet','white','yellow']
@dataclasses.dataclass(frozen=True,order=True)
class Item:
 size:str;origin:str;name:str;material:str;smell:str;color:str
 def replace(self,**kw):return dataclasses.replace(self,**kw)
def alt(xs):return '|'.join(map(re.escape,sorted(xs,key=len,reverse=True)))
ITEM_RE=re.compile(r'\b(?:an?|the)\s+('+alt(SIZES)+r')\s+('+alt(ORIGINS)+r')\s+(.+?)\s+made of\s+('+alt(MATERIALS)+r')\s+with a smell of\s+('+alt(SMELLS)+r')(?=,\s+(?:an?|the)\s+(?:'+alt(SIZES)+r')\b|\.\s*$)',re.I)
def initial_items(text):
 before=text.split('The color of the items was respectively as follows:',1)[0];raw=[]
 for m in ITEM_RE.finditer(before):raw.append((m.group(1).lower(),m.group(2).title(),m.group(3).strip(),m.group(4).lower(),m.group(5).lower()))
 cm=re.search(r'The color of the items was respectively as follows:\s*(.*?)(?=\.\s*Then)',text,re.S);colors=[]
 for n,c in re.findall(r'the (?:first|next) (\d+) (?:was|were) ([a-z]+)',cm.group(1),re.I):colors.extend([c.lower()]*int(n))
 if len(raw)!=len(colors):raise ValueError(f'initial parse {len(raw)} items {len(colors)} colors')
 return tuple(Item(*x,color) for x,color in zip(raw,colors))
def canon(items):return tuple(sorted(items))
def counts(items,attr):return collections.Counter(getattr(x,attr) for x in items)
def checkpoint(part):
 if 'After this' not in part:return None
 cp=part.split('After this',1)[1].split('. Then',1)[0];pairs=[];attr=None
 if 'made of' in cp:attr='material';pairs=[(int(n),v.lower()) for n,v in re.findall(r'(\d+) item\(s\) made of ([a-z]+)',cp)]
 elif 'smell' in cp:attr='smell';pairs=[(int(n),v.lower()) for n,v in re.findall(r'(\d+) item\(s\) with (.+?) smell',cp)]
 else:
  raw=[(int(n),v.lower()) for n,v in re.findall(r'(\d+) ([a-z-]+) item\(s\)',cp)]
  if raw:attr='size' if all(v in SIZES for _,v in raw) else 'color';pairs=raw
 if not attr or not pairs:raise ValueError('checkpoint parse')
 return attr,collections.Counter({v:n for n,v in pairs if n})
def matches(items,cp):
 if cp is None:return True
 attr,expected=cp;return collections.Counter({k:v for k,v in counts(items,attr).items() if v})==expected
def parts(text):
 after=text.split('The color of the items was respectively as follows:',1)[1];after=re.split(r'\.\s*Then,?\s+',after,maxsplit=1)[1]
 return re.split(r'\s+Then,?\s+',after)
def hidden(worlds,candidates,fn,cp):
 out={canon(fn(w,c)) for w in worlds for c in candidates if matches(canon(fn(w,c)),cp)}
 if not out:raise ValueError('no hidden candidate matched checkpoint')
 return out
def smell_list(op):
 m=re.search(r'smell of (.*?)(?: in my| in the| in collection)',op,re.I);out=[]
 if not m:return out
 for x in re.split(r',\s*|\s+or\s+',m.group(1)):
  x=re.sub(r'^or\s+','',x.strip(),flags=re.I).lower()
  if x in SMELLS:out.append(x)
 return out

def solve(text,debug=False):
 initial=initial_items(text);worlds={canon(initial)};initial_pairs={(x.smell,x.color) for x in initial};trace=[]
 for part in parts(text):
  op=part.split('After this',1)[0].strip().rstrip('. ');low=op.lower();cp=checkpoint(part)
  if low.startswith('for each item of size') and 'favorite material' in low:
   m=re.search(r'item of size ('+alt(SIZES)+r').*?smell of ('+alt(SMELLS)+r')',op,re.I);src,smell=m.group(1).lower(),m.group(2).lower()
   worlds=hidden(worlds,MATERIALS,lambda w,c:tuple(x.replace(material=c,smell=smell) if x.size==src else x for x in w),cp)
  elif low.startswith('for any item made of') and 'favorite color' in low:
   m=re.search(r'made of ('+alt(MATERIALS)+r').*?smell to ('+alt(SMELLS)+r')',op,re.I);mat,smell=m.group(1).lower(),m.group(2).lower()
   worlds=hidden(worlds,COLORS,lambda w,c:tuple(x.replace(color=c,smell=smell) if x.material==mat else x for x in w),cp)
  elif 'my mom gave me another one' in low:
   m=re.search(r'item of color ('+alt(COLORS)+r').*?with a ('+alt(COLORS)+r') color, ('+alt(ORIGINS)+r') origin, ('+alt(SIZES)+r') size, ('+alt(SMELLS)+r') smell, and made of ('+alt(MATERIALS)+r')',op,re.I)
   src,color,origin,size,smell,mat=m.groups();src=src.lower();color=color.lower();origin=origin.title();size=size.lower();smell=smell.lower();mat=mat.lower();new=set()
   for w in worlds:
    nw=canon(tuple(w)+tuple(x.replace(color=color,origin=origin,size=size,smell=smell,material=mat) for x in w if x.color==src))
    if matches(nw,cp):new.add(nw)
   worlds=new
  elif 'my dad threw away all item of a certain color' in low:worlds=hidden(worlds,COLORS,lambda w,c:tuple(x for x in w if x.color!=c),cp)
  elif 'even number of an item type' in low:
   new=set()
   for w in worlds:
    c=collections.Counter(x.name for x in w);nw=canon(tuple(x for x in w if c[x.name]%2==1))
    if matches(nw,cp):new.add(nw)
   worlds=new
  elif 'my brother replaced any item of size' in low:
   m=re.search(r'item of size ('+alt(SIZES)+r').*?color ('+alt(COLORS)+r')',op,re.I);src,color=m.group(1).lower(),m.group(2).lower()
   def fn(w,c):
    out=[]
    for x in w:out.extend((x.replace(size=c),x.replace(color=color))) if x.size==src else out.append(x)
    return tuple(out)
   worlds=hidden(worlds,[x for x in SIZES if x!=src],fn,cp)
  elif 'my uncle threw away any' in low:
   m=re.search(r'threw away any ('+alt(ORIGINS)+r') item.*?one ('+alt(ORIGINS)+r') and one ('+alt(ORIGINS)+r')',op,re.I);src,o1,o2=m.groups();src=src.title();o1=o1.title();o2=o2.title();new=set()
   for w in worlds:
    out=[]
    for x in w:out.extend((x.replace(origin=o1),x.replace(origin=o2))) if x.origin==src else out.append(x)
    nw=canon(out)
    if matches(nw,cp):new.add(nw)
   worlds=new
  elif 'my cousin gifted me another one' in low:
   ss=smell_list(op);worlds=hidden(worlds,[x for x in SMELLS if x not in ss],lambda w,c:tuple(w)+tuple(x.replace(smell=c) for x in w if x.smell in ss),cp)
  elif 'my friend took any item with a smell of' in low:
   ss=smell_list(op);worlds={canon(tuple(x for x in w if x.smell not in ss)) for w in worlds}
  elif 'my teacher took any item' in low:
   n=int(re.search(r'name had (\d+) characters',op,re.I).group(1));worlds={canon(tuple(x for x in w if not (x.color.startswith('b') or len(x.name.replace(' ',''))==n))) for w in worlds}
  elif 'my fiance compared' in low:worlds={canon(tuple(w)+tuple(x for x in w if (x.smell,x.color) not in initial_pairs)) for w in worlds}
  elif 'i lost one of the' in low:
   size=re.search(r'lost one of the ('+alt(SIZES)+r') items',op,re.I).group(1).lower();new=set()
   for w in worlds:
    for i,x in enumerate(w):
     if x.size==size:new.add(canon(w[:i]+w[i+1:]))
   worlds=new
  else:raise ValueError('unknown operation: '+op[:300])
  if not worlds:raise ValueError('all worlds eliminated')
  trace.append({'operation':op,'worlds':len(worlds),'sizes':sorted({len(w) for w in worlds})})
 qm=re.search(r'how many items have the following attributes: (.*?)\? If the exact',text,re.I|re.S);q=qm.group(1).lower()
 def qv(prefix,domain):
  m=re.search(prefix+' ('+alt(domain)+r')',q,re.I);return m.group(1).lower() if m else None
 color=qv(r'color is(?: not)?',COLORS);size=qv(r'size is(?: not)?',SIZES);mat=qv(r'material is(?: not)?',MATERIALS);smell=qv(r'smell is(?: not)?',SMELLS);origin=qv(r'origin is(?: not)?',ORIGINS);origin=origin.title() if origin else None
 negative='color is not' in q;answers=set()
 for w in worlds:
  if negative:answers.add(sum(x.color!=color and x.size!=size and x.material!=mat and x.smell!=smell and x.origin!=origin for x in w))
  else:answers.add(sum(x.color==color or x.size==size or x.material==mat or x.smell==smell or x.origin==origin for x in w))
 answer=str(next(iter(answers))) if len(answers)==1 else 'unknown'
 return (answer,trace,worlds) if debug else answer
