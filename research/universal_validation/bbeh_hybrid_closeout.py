#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
import urllib.request
import zipfile

REPO='Chrisbryan17/MLE-agent'
RUNS={'semantic':(29198729053,'universal-bbeh-semantic-jury'),'residual':(29199747387,'universal-bbeh-residual-jury')}
OUT=pathlib.Path('artifacts/bbeh_hybrid_closeout')
EXACT=pathlib.Path('artifacts/exact_closeout/results.json')

def api_json(path):
 request=urllib.request.Request('https://api.github.com'+path,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
 with urllib.request.urlopen(request,timeout=120) as response:return json.loads(response.read())
def download(url,path):
 request=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(request,timeout=300) as response,path.open('wb') as handle:
  while True:
   block=response.read(1024*1024)
   if not block:break
   handle.write(block)
def obtain(name,run_id,artifact_name,timeout=21600):
 deadline=time.time()+timeout
 while True:
  run=api_json(f'/repos/{REPO}/actions/runs/{run_id}');print(name,run.get('status'),run.get('conclusion'),flush=True)
  if run.get('status')=='completed':
   if run.get('conclusion')!='success':raise RuntimeError(f'{name} run concluded {run.get("conclusion")}')
   break
  if time.time()>deadline:raise TimeoutError(f'{name} run did not finish')
  time.sleep(60)
 artifacts=api_json(f'/repos/{REPO}/actions/runs/{run_id}/artifacts').get('artifacts',[]);match=next((item for item in artifacts if item['name']==artifact_name),None)
 if not match:raise RuntimeError(f'artifact {artifact_name} missing')
 archive=OUT/f'{name}.zip';download(match['archive_download_url'],archive);dest=OUT/name;dest.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(archive) as zf:zf.extractall(dest)
 candidates=list(dest.rglob('results.json'))
 if not candidates:raise RuntimeError(f'no results.json in {name}')
 result=json.loads(candidates[0].read_text())
 return result,{'run_id':run_id,'run_head_sha':run.get('head_sha'),'artifact_id':match['id'],'artifact_digest':match.get('digest'),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'results_path':str(candidates[0].relative_to(dest))}
def main():
 OUT.mkdir(parents=True,exist_ok=True);exact=json.loads(EXACT.read_text());sources={'exact':exact};provenance={'exact':{'results_sha256':hashlib.sha256(EXACT.read_bytes()).hexdigest()}}
 for name,(run_id,artifact_name) in RUNS.items():sources[name],provenance[name]=obtain(name,run_id,artifact_name)
 tasks={}
 for source,result in sources.items():
  for task,value in result['tasks'].items():
   if task in tasks:raise RuntimeError(f'duplicate task {task}')
   tasks[task]={'source':source,'n':int(value['n']),'correct':int(value['correct']),'accuracy':float(value['accuracy']),'coverage':float(value.get('coverage',1.0))}
 n=sum(value['n'] for value in tasks.values());correct=sum(value['correct'] for value in tasks.values())
 if len(tasks)!=23 or n!=4520:raise RuntimeError(f'expected 23 tasks/4520 examples, got {len(tasks)}/{n}')
 payload={'protocol':'Complete BBEH hybrid aggregate: ten exact cells plus two prediction-sealed o4-mini juries. Every one of the 4,520 official examples counts.','tasks':dict(sorted(tasks.items())),'aggregate':{'tasks':len(tasks),'n':n,'correct':correct,'micro_accuracy':correct/n,'macro_accuracy':sum(value['accuracy'] for value in tasks.values())/len(tasks),'coverage':sum(value['coverage']*value['n'] for value in tasks.values())/n,'exact_n':sum(value['n'] for value in tasks.values() if value['source']=='exact'),'exact_correct':sum(value['correct'] for value in tasks.values() if value['source']=='exact'),'jury_n':sum(value['n'] for value in tasks.values() if value['source']!='exact'),'jury_correct':sum(value['correct'] for value in tasks.values() if value['source']!='exact')},'provenance':provenance,'code_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
 (OUT/'results.json').write_text(json.dumps(payload,indent=2));print(json.dumps(payload['aggregate'],indent=2))
if __name__=='__main__':main()
