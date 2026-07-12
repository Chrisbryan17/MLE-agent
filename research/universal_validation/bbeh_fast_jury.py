#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request
from typing import Any

ENDPOINT='https://models.github.ai/inference/chat/completions'
ROOT=pathlib.Path(os.environ.get('BBEH_ROOT','.external/bbeh'))
OUT=pathlib.Path('artifacts/bbeh_fast_jury')
SHARDS={
 'deepseek':{'model':'deepseek/DeepSeek-R1','tasks':('bbeh_boardgame_qa','bbeh_buggy_tables','bbeh_time_arithmetic','bbeh_zebra_puzzles')},
 'grok':{'model':'xai/grok-3','tasks':('bbeh_causal_understanding','bbeh_sportqa','bbeh_geometric_shapes')},
 'llama':{'model':'meta/Llama-4-Maverick-17B-128E-Instruct','tasks':('bbeh_disambiguation_qa','bbeh_movie_recommendation','bbeh_sarc_triples')},
 'mistral':{'model':'mistral-ai/Mistral-Medium-3','tasks':('bbeh_nycc','bbeh_linguini','bbeh_object_properties')},
}
INSTRUCTIONS={
 'bbeh_boardgame_qa':'Perform defeasible rule reasoning to a fixed point, respect stated priorities, and answer proved, disproved, or unknown exactly as requested.',
 'bbeh_buggy_tables':'Reconstruct corrupted table cells from row and column patterns and compute the requested result exactly.',
 'bbeh_time_arithmetic':'Solve both linked date/time stages exactly, substitute the first result into the second, and respect calendar and timezone details.',
 'bbeh_zebra_puzzles':'Solve the complete finite-domain logic puzzle using all-different, equality, order, adjacency, offsets, endpoints, and disjunctions.',
 'bbeh_causal_understanding':'Apply ordinary human causal judgment, distinguishing actual causes from background conditions and abnormal interventions.',
 'bbeh_sportqa':'Use sports rules, event structure, chronology, and physical plausibility.',
 'bbeh_geometric_shapes':'Parse the SVG or geometric construction, track all operations, and return the exact requested property or answer token.',
 'bbeh_disambiguation_qa':'Resolve references using syntax, discourse coherence, and commonsense.',
 'bbeh_movie_recommendation':'Choose the movie most similar in genre, themes, tone, audience, and narrative structure.',
 'bbeh_sarc_triples':'Identify the sarcastic sentence whose literal wording conflicts with context.',
 'bbeh_nycc':'Choose the funniest New Yorker-style caption: concise, scene-specific, surprising, and socially observant.',
 'bbeh_linguini':'Infer the hidden language from demonstrations, including morphology, case, agreement, and word order.',
 'bbeh_object_properties':'Track every object and property update in order, including set membership, either/neither, exceptions, and overwrites.',
}
SYSTEM='Solve every numbered item independently. Return only one valid JSON object mapping each numeric item id string to its exact final answer. No explanations, markdown, or omitted keys.'

def canonical(value:Any)->str:
 text=str(value).strip();return re.sub(r'^```(?:json)?\s*|\s*```$','',text,flags=re.S|re.I).strip()
def normalized(value:Any)->str:
 text=re.sub(r'\s+',' ',canonical(value).lower())
 return f'({text})' if re.fullmatch(r'[a-z]',text) else text
def extract_json(content:str)->dict[str,str]:
 cleaned=canonical(content)
 try:value=json.loads(cleaned)
 except json.JSONDecodeError:
  match=re.search(r'\{.*\}',cleaned,re.S)
  if not match:raise
  value=json.loads(match.group(0))
 if not isinstance(value,dict):raise TypeError('Expected JSON object')
 output={}
 for key,answer in value.items():
  match=re.search(r'\d+',str(key))
  if match:output[match.group(0)]=canonical(answer)
 return output

def prompt(task,items):
 parts=[INSTRUCTIONS[task],'','TEST ITEMS:','']
 for index,example in items:parts.extend((f'ITEM {index}:',example['input'],''))
 parts.append('Return only the JSON answer map.')
 return '\n'.join(parts)

def request_batch(model,task,items,retries=10):
 payload={'model':model,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':prompt(task,items)}]}
 last=None
 for attempt in range(retries):
  started=time.time()
  try:
   request=urllib.request.Request(ENDPOINT,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Content-Type':'application/json','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
   with urllib.request.urlopen(request,timeout=1200) as response:
    raw=response.read().decode(errors='replace');headers=dict(response.headers);status=response.status
   decoded=json.loads(raw);message=decoded['choices'][0]['message'];content=message.get('content') or message.get('reasoning_content') or ''
   answers=extract_json(content);missing=[str(i) for i,_ in items if str(i) not in answers]
   if missing:raise ValueError(f'Missing ids: {missing}')
   return {'ok':True,'answers':answers,'status':status,'headers':headers,'usage':decoded.get('usage'),'latency_seconds':time.time()-started,'raw_message':message}
  except urllib.error.HTTPError as exc:
   body=exc.read().decode(errors='replace');last={'type':'HTTPError','status':exc.code,'headers':dict(exc.headers),'body':body}
   if exc.code not in (408,429,500,502,503,504):break
   time.sleep(int(exc.headers.get('Retry-After','30'))+5)
  except Exception as exc:
   last={'type':type(exc).__name__,'message':str(exc)};time.sleep(min(180,15*(attempt+1)))
 return {'ok':False,'error':last}

def batches(examples,max_items=32,max_chars=90000):
 current=[];chars=0
 for index,example in enumerate(examples):
  size=len(example['input'])
  if current and (len(current)>=max_items or chars+size>max_chars):yield current;current=[];chars=0
  current.append((index,example));chars+=size
 if current:yield current

def solve_task(model,task,examples):
 checkpoint_path=OUT/f'{task}.checkpoint.json'
 checkpoint=json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {'task':task,'model':model,'predictions':{},'raw_batches':[]}
 predictions=checkpoint['predictions']
 for batch in batches(examples):
  pending=[item for item in batch if str(item[0]) not in predictions]
  if not pending:continue
  queue=[pending]
  while queue:
   subset=queue.pop(0);result=request_batch(model,task,subset);checkpoint['raw_batches'].append({'ids':[i for i,_ in subset],'result':result})
   if result.get('ok'):predictions.update(result['answers'])
   elif len(subset)>1:
    middle=len(subset)//2;queue.extend((subset[:middle],subset[middle:]))
  checkpoint_path.write_text(json.dumps(checkpoint,indent=2,default=str));print(task,len(predictions),'/',len(examples),flush=True);time.sleep(8)
 return checkpoint

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--shard',required=True,choices=sorted(SHARDS));args=parser.parse_args()
 OUT.mkdir(parents=True,exist_ok=True);spec=SHARDS[args.shard];model=spec['model'];task_data={}
 report={'protocol':'Four-model fast jury. Inputs only in prompts; every task prediction file is sealed before any target is scored.','shard':args.shard,'model':model,'tasks':{}}
 for task in spec['tasks']:
  path=ROOT/'bbeh'/'benchmark_tasks'/task/'task.json';examples=json.loads(path.read_text())['examples'];task_data[task]=examples;checkpoint=solve_task(model,task,examples);predictions=checkpoint['predictions']
  sealed={'task':task,'model':model,'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'predictions':predictions,'prediction_sha256':hashlib.sha256(json.dumps(predictions,sort_keys=True).encode()).hexdigest(),'raw_batches':checkpoint['raw_batches']}
  (OUT/f'{task}.predictions.json').write_text(json.dumps(sealed,indent=2,default=str))
 for task in spec['tasks']:
  sealed=json.loads((OUT/f'{task}.predictions.json').read_text());examples=task_data[task];rows=[]
  for index,example in enumerate(examples):
   prediction=sealed['predictions'].get(str(index));rows.append({'index':index,'prediction':prediction,'target':example['target'],'correct':prediction is not None and normalized(prediction)==normalized(example['target'])})
  correct=sum(row['correct'] for row in rows);report['tasks'][task]={'n':len(rows),'correct':correct,'accuracy':correct/len(rows),'coverage':sum(row['prediction'] is not None for row in rows)/len(rows),'prediction_sha256':sealed['prediction_sha256'],'errors':[row for row in rows if not row['correct']]}
 n=sum(v['n'] for v in report['tasks'].values());correct=sum(v['correct'] for v in report['tasks'].values());report['aggregate']={'tasks':len(report['tasks']),'n':n,'correct':correct,'micro_accuracy':correct/n,'macro_accuracy':sum(v['accuracy'] for v in report['tasks'].values())/len(report['tasks']),'coverage':sum(v['coverage']*v['n'] for v in report['tasks'].values())/n};report['code_sha256']=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest();(OUT/f'{args.shard}.results.json').write_text(json.dumps(report,indent=2,default=str));print(json.dumps(report['aggregate'],indent=2))
if __name__=='__main__':main()
