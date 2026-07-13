#!/usr/bin/env python3
from __future__ import annotations
import ast,json,pathlib,re,statistics,sys

CANON={
 'study minutes':'study_minutes','exercise minutes':'exercise_minutes','sleep minutes':'sleep_minutes',
 'bed time':'bed_time','number of messages':'num_messages','number of emails':'num_emails',
 'number of calls':'num_calls','number of calories burned':'calories_burned','weekday':'weekday',
 'number of calories consumed':'calories_consumed','number of meetings':'num_meetings',
 'coding minutes':'coding_minutes','number of tasks completed':'num_tasks_completed',
 'water intake':'water_intake_ml','phone screen time minutes':'phone_screen_time_minutes',
 'music listening minutes':'music_listening_minutes','number of steps':'num_steps',
}

def split_cells(line):return [x.strip() for x in line.strip().strip('|').split('|')]
def table_block(text):
 start=text.index('|');end=text.index('\n\nHowever,',start)
 lines=[x for x in text[start:end].splitlines() if x.strip().startswith('|')]
 header=split_cells(lines[0]);rows=[]
 for line in lines[1:]:
  cells=split_cells(line)
  if cells and all(set(c.replace(' ',''))<=set('-:') for c in cells):continue
  rows.append(cells)
 return header,rows
def parse_list(s):
 body=s.strip()[1:-1];return [x.strip() for x in body.split(',')] if body.strip() else []
def flat_tokens(text):
 marker='format as follows:';start=text.index('[',text.index(marker));end=text.index('].\n\nHowever,',start)
 return [x.strip() for x in text[start+1:end].split(',')]

def repair(text):
 m=re.search(r'I have a table with (\d+) rows \(including the header\) and (\d+) columns',text)
 nrows_total,ncols=map(int,m.groups());ndata=nrows_total-1
 desc=text.split('\n\nHowever,',1)[1].split(' Compute the absolute difference',1)[0]
 if 'row-major format' in text.split('However,',1)[0]:
  toks=flat_tokens(text);header=toks[:ncols];vals=toks[ncols:];rows=[];pos=0;zero='(0-indexed' in desc
  if 'after saving each row' in desc:
   for i in range(ndata):
    rows.append(vals[pos:pos+ncols]);pos+=ncols+i+1
  elif 'failed to save the null values' in desc:
   lm=re.search(r'locations \((?:0|1)-indexed -- table header included\):\s*(\[.*?\])\.',desc,re.S)
   locs=ast.literal_eval(lm.group(1));byrow={}
   for r,c in locs:
    ri=r-1 if zero else r-2;ci=c if zero else c-1;byrow.setdefault(ri,[]).append(ci)
   for i in range(ndata):
    miss=sorted(byrow.get(i,[]));take=ncols-len(miss);row=vals[pos:pos+take];pos+=take
    for c in miss:row.insert(c,'null')
    rows.append(row)
  else:raise ValueError('unknown row-major corruption')
  return header,[r[:ncols] for r in rows]
 if 'column-major format' in text.split('However,',1)[0]:
  toks=flat_tokens(text);zero='(0-indexed' in desc;columns=[];header=[];pos=0
  if 'after saving each column' in desc:
   for j in range(ncols):
    header.append(toks[pos]);pos+=1;columns.append(toks[pos:pos+ndata]);pos+=ndata+j
  elif 'failed to save the null values' in desc:
   lm=re.search(r'locations \((?:0|1)-indexed -- table header included\):\s*(\[.*?\])\.',desc,re.S)
   locs=ast.literal_eval(lm.group(1));bycol={}
   for r,c in locs:
    ri=r-1 if zero else r-2;ci=c if zero else c-1;bycol.setdefault(ci,[]).append(ri)
   for j in range(ncols):
    header.append(toks[pos]);pos+=1;miss=sorted(bycol.get(j,[]));take=ndata-len(miss);col=toks[pos:pos+take];pos+=take
    for r in miss:col.insert(r,'null')
    columns.append(col)
  else:raise ValueError('unknown column-major corruption')
  return header,[[columns[j][i] for j in range(ncols)] for i in range(ndata)]
 header,rows=table_block(text)
 if 'merged every two rows' in desc:
  out=[]
  for row in rows:
   first=[];second=[]
   for cell in row[:ncols]:
    parts=re.split(r'\s*&&\s*',cell,maxsplit=1);first.append(parts[0]);second.append(parts[1] if len(parts)>1 else 'null')
   out.append(first)
   if len(out)<ndata:out.append(second)
  rows=out[:ndata]
 elif 'values in the i-th row were rotated to the right i times' in desc:
  out=[]
  for i,row in enumerate(rows[:ndata],1):
   row=(row+['null']*ncols)[:ncols];k=i%ncols;out.append(row[k:]+row[:k])
  rows=out
 elif 'values in the i-th column were rotated down i times' in desc:
  matrix=[(r+['null']*ncols)[:ncols] for r in rows[:ndata]];out=[['null']*ncols for _ in range(ndata)]
  for j in range(ncols):
   col=[matrix[i][j] for i in range(ndata)];k=(j+1)%ndata;col=col[k:]+col[:k]
   for i,v in enumerate(col):out[i][j]=v
  rows=out
 elif 'mistakenly replaced some values with "ERROR"' in desc:
  lm=re.search(r'respectively as follows:\s*(\[.*?\])\.',desc,re.S);vals=parse_list(lm.group(1));it=iter(vals)
  rows=[(r+['null']*ncols)[:ncols] for r in rows[:ndata]]
  if 'column-order' in desc:
   for j in range(ncols):
    for i in range(ndata):
     if rows[i][j].strip()=='ERROR':rows[i][j]=next(it)
  else:
   for i in range(ndata):
    for j in range(ncols):
     if rows[i][j].strip()=='ERROR':rows[i][j]=next(it)
 else:raise ValueError('unknown markdown corruption: '+desc[:200])
 return (header+['']*ncols)[:ncols],[(r+['null']*ncols)[:ncols] for r in rows[:ndata]]

def value(x):
 x=x.strip().strip('.')
 if x.lower()=='null' or x=='':return None
 if re.fullmatch(r'\d{1,2}:\d{2}',x):
  h,m=map(int,x.split(':'));return h*60+m
 try:return float(x)
 except:return x

def compile_condition(s):
 s=s.strip().lower()
 m=re.fullmatch(r'the bed time was between (\d{1,2}:\d{2}) and (\d{1,2}:\d{2}) \(inclusive\)',s)
 if m:return ('between','bed_time',value(m.group(1)),value(m.group(2)))
 m=re.fullmatch(r'the weekday is ([a-z]+)',s)
 if m:return ('eq','weekday',m.group(1)[:3].title())
 for phrase,col in sorted(CANON.items(),key=lambda z:-len(z[0])):
  m=re.fullmatch(r'the '+re.escape(phrase)+r' was (greater|less) than (\d+(?:\.\d+)?)(?: ml)?',s)
  if m:return ('gt' if m.group(1)=='greater' else 'lt',col,float(m.group(2)))
 raise ValueError('condition '+s)
def cond_ok(row,idx,c):
 kind,col,*args=c;v=row[idx[col]]
 if v is None:return False
 if kind=='between':return args[0]<=v<=args[1]
 if kind=='eq':return v==args[0]
 return isinstance(v,(int,float)) and (v>args[0] if kind=='gt' else v<args[0])

def solve(text,debug=False):
 header,raw=repair(text);rows=[[value(x) for x in r] for r in raw];idx={c:i for i,c in enumerate(header)}
 if 'weekday' in idx:
  days=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];j=idx['weekday']
  scores=[sum(1 for i,r in enumerate(rows) if r[j] in days and r[j]==days[(i+off)%7]) for off in range(7)]
  off=max(range(7),key=lambda k:scores[k])
  for i,r in enumerate(rows):
   if r[j] is None:r[j]=days[(i+off)%7]
 qm=re.search(r'Compute the absolute difference between the (mean|median|sum|stdev) of column ([a-z_]+) and column ([a-z_]+), only looking at the days where (.*?)\. Round',text,re.S)
 if not qm:raise ValueError('query')
 agg,c1,c2,cs=qm.groups();parts=re.split(r'\s+and\s+',cs.strip())
 if len(parts)>2:
  parts=re.findall(r'(the bed time was between \d{1,2}:\d{2} and \d{1,2}:\d{2} \(inclusive\)|the weekday is [A-Za-z]+|the [a-z ]+ was (?:greater|less) than \d+(?:\.\d+)?(?: ml)?)',cs,re.I)
 conditions=[compile_condition(x) for x in parts];selected=[r for r in rows if all(cond_ok(r,idx,c) for c in conditions)]
 vals=[[r[idx[col]] for r in selected if isinstance(r[idx[col]],(int,float))] for col in (c1,c2)]
 if any(not v for v in vals):answer='0'
 else:
  def calc(v):
   if agg=='mean':return statistics.mean(v)
   if agg=='median':return statistics.median(v)
   if agg=='sum':return sum(v)
   return statistics.stdev(v) if len(v)>1 else 0.0
  ans=round(abs(calc(vals[0])-calc(vals[1])),2);answer='0' if ans==0 else str(float(ans)) if float(ans).is_integer() else str(ans)
 if debug:return answer,header,rows,selected,conditions,vals
 return answer
