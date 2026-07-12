#!/usr/bin/env python3
from __future__ import annotations
import re
from dataclasses import dataclass,field

DAYS=['Monday','Tuesday','Wednesday','Thursday','Friday']

def tm(s:str)->int:
 s=s.strip().lower().replace(' ','');ampm=None
 if s.endswith('am') or s.endswith('pm'):ampm=s[-2:];s=s[:-2]
 if ':' in s:h,m=map(int,s.split(':'))
 else:h,m=int(s),0
 if ampm=='pm' and h!=12:h+=12
 if ampm=='am' and h==12:h=0
 return h*60+m

def merge(ints):
 ints=sorted((max(0,a),min(24*60,b)) for a,b in ints if b>a);out=[]
 for a,b in ints:
  if out and a<=out[-1][1]:out[-1]=(out[-1][0],max(out[-1][1],b))
  else:out.append((a,b))
 return out

def subtract(base,blocked):
 out=[]
 for a,b in base:
  cur=a
  for x,y in merge(blocked):
   if y<=cur or x>=b:continue
   if x>cur:out.append((cur,min(x,b)))
   cur=max(cur,y)
   if cur>=b:break
  if cur<b:out.append((cur,b))
 return merge(out)

def add_interval(ints,new):return merge(list(ints)+[new])
def overlap_minutes(ints,a,b):return sum(max(0,min(b,y)-max(a,x)) for x,y in ints)

@dataclass
class Person:
 name:str
 offset:int=0
 start:int=9*60
 end:int=17*60
 booked:dict=field(default_factory=dict)
 free_only:dict=field(default_factory=dict)
 clear_small:int|None=None
 clear_morning:tuple|None=None
 lunch:dict=field(default_factory=dict)
 miss:int=0
 miss_last:int=0
 end_before:int|None=None
 min_days:dict=field(default_factory=dict)
 max_days:dict=field(default_factory=dict)
 buffer_before:int=0
 buffer_after:int=0

def parse_intervals(desc,start=540,end=1020):
 out=[]
 for a,b in re.findall(r'from\s+(\d{1,2}(?::\d{2})?)\s+to\s+(\d{1,2}(?::\d{2})?)',desc,re.I):out.append((tm(a),tm(b)))
 for x in re.findall(r'anytime before\s+(\d{1,2}(?::\d{2})?)',desc,re.I):out.append((start,tm(x)))
 for x in re.findall(r'anytime after\s+(\d{1,2}(?::\d{2})?)',desc,re.I):out.append((tm(x),end))
 return merge(out)

def parse(text:str):
 intro=text.split('\n',1)[0];names_part=re.search(r'^(.*?) work from',intro,re.I).group(1);names=[x.strip() for x in re.split(r',|\band\b',names_part) if x.strip()];people={n:Person(n) for n in names}
 for name in names:
  m=re.search(rf"The schedule for {re.escape(name)}'s week.*?is as follows:\s*(.*?)(?=\n\n\nThe schedule for|\n\n\n?[A-Z][a-z]+ (?:can|prefers|is|needs|asks|feels)|\n\nLet X)",text,re.S)
  if not m:continue
  block=m.group(1)
  for day in DAYS:
   dm=re.search(rf'{day}:\s*(.*)',block)
   if not dm:continue
   desc=dm.group(1).strip()
   if desc.lower().startswith('booked'):people[name].booked[day]=parse_intervals(desc)
   elif desc.lower().startswith('free only'):people[name].free_only[day]=parse_intervals(desc)
 before=text.split('Let X',1)[0]
 for line in before.splitlines():
  line=line.strip()
  if not line:continue
  pm=next((people[n] for n in names if line.startswith(n+' ')),None)
  if not pm:continue
  low=line.lower()
  if re.search(r'timezone that is one hour ahead',low):pm.offset=60
  m=re.search(r'clear any meeting of (\d+) minutes or less',low)
  if m:pm.clear_small=int(m.group(1))
  m=re.search(r'clear their morning schedule from (\d{1,2}(?::\d{2})?) to (\d{1,2}(?::\d{2})?)',low)
  if m:pm.clear_morning=(tm(m.group(1)),tm(m.group(2)))
  m=re.search(r'needs a break for lunch on (\w+) from (\d{1,2}(?::\d{2})?) to (\d{1,2}(?::\d{2})?)',low)
  if m:pm.lunch[m.group(1).title()]=(tm(m.group(2)),tm(m.group(3)))
  m=re.search(r'flexible to miss the last \(at most\) (\d+) minutes',low)
  if m:pm.miss_last=int(m.group(1))
  elif (m:=re.search(r'flexible to miss \(at most\) (\d+) minutes',low)):pm.miss=int(m.group(1))
  m=re.search(r'fine to stay until (\d{1,2}(?::\d{2})?)pm',low)
  if m:pm.end=tm(m.group(1)+'pm')
  m=re.search(r'requires the meeting to end before (\d{1,2}(?::\d{2})?)pm',low)
  if m:pm.end_before=tm(m.group(1)+'pm')
  m=re.search(r'at least (\d+) minutes of free time before',low)
  if m:pm.buffer_before=int(m.group(1))
  m=re.search(r'at least (\d+) minutes of free time after',low)
  if m:pm.buffer_after=int(m.group(1))
  m=re.search(r'prefers long meetings on tuesdays and fridays.*?at least (\d+) minutes',low)
  if m:
   for d in ['Tuesday','Friday']:pm.min_days[d]=int(m.group(1))
  m=re.search(r'prefers short meetings on mondays and thursdays.*?at most (\d+) hour',low)
  if m:
   for d in ['Monday','Thursday']:pm.max_days[d]=int(m.group(1))*60
 return people

def local_avail(p:Person,day:str):
 work=[(p.start,p.end)]
 if day in p.free_only:avail=[(max(p.start,a),min(p.end,b)) for a,b in p.free_only[day]]
 else:
  blocked=p.booked.get(day,[])
  if p.clear_small is not None:blocked=[z for z in blocked if z[1]-z[0]>p.clear_small]
  avail=subtract(work,blocked)
 if p.clear_morning:avail=add_interval(avail,p.clear_morning)
 if day in p.lunch:avail=subtract(avail,[p.lunch[day]])
 if p.end_before is not None:avail=[(a,min(b,p.end_before)) for a,b in avail if a<p.end_before]
 return merge([(a-p.offset,b-p.offset) for a,b in avail])

def acceptable(p,day,s,e,avail):
 dur=e-s
 if day in p.min_days and dur<p.min_days[day]:return False
 if day in p.max_days and dur>p.max_days[day]:return False
 if p.buffer_before and overlap_minutes(avail,s-p.buffer_before,s)<p.buffer_before:return False
 if p.buffer_after and overlap_minutes(avail,e,e+p.buffer_after)<p.buffer_after:return False
 covered=overlap_minutes(avail,s,e)
 if p.miss_last:
  required=max(0,dur-p.miss_last);return overlap_minutes(avail,s,s+required)>=required
 if p.miss:return dur-covered<=p.miss
 return covered>=dur

def solve(text:str):
 people=parse(text);best=-1;count=0
 for day in DAYS:
  av={n:local_avail(p,day) for n,p in people.items()}
  for s in range(7*60,19*60+1,30):
   for e in range(s+5,20*60+1,5):
    if all(acceptable(p,day,s,e,av[n]) for n,p in people.items()):
     dur=e-s
     if dur>best:best=dur;count=1
     elif dur==best:count+=1
 return f'{best}, {count}' if best>=0 else None
