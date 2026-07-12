#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

import bbeh_exact_robust as exact
import livebench_geometry_exact as geometry

DATASET='livebench/reasoning'
BASE='https://datasets-server.huggingface.co'
OUT=Path('artifacts/livebench_eval_v3')
CACHE=Path('.livebench_eval_v3_cache')
PUBLIC_CUTOFF='2024-11-25'
SUPPORTED={'web_of_lies_v2','spatial'}


def get_json(path,params,retries=8):
    url=BASE+path+'?'+urllib.parse.urlencode(params)
    last=None
    for attempt in range(retries):
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'hybrid-reasoning-validation/0.1'})
            with urllib.request.urlopen(request,timeout=180) as response:
                return json.loads(response.read())
        except Exception as exc:
            last=exc;time.sleep(min(30,2**attempt))
    raise last


def download(url,path,retries=8):
    if path.exists():return
    path.parent.mkdir(parents=True,exist_ok=True)
    last=None
    for attempt in range(retries):
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'hybrid-reasoning-validation/0.1'})
            with urllib.request.urlopen(request,timeout=300) as response,path.open('wb') as handle:
                while True:
                    block=response.read(1024*1024)
                    if not block:break
                    handle.write(block)
            return
        except Exception as exc:
            last=exc;path.unlink(missing_ok=True);time.sleep(min(30,2**attempt))
    raise last


def rows():
    manifest=get_json('/parquet',{'dataset':DATASET});output=[];hashes={}
    for index,entry in enumerate(manifest.get('parquet_files',[])):
        local=CACHE/f'{index:03d}.parquet';download(entry['url'],local)
        hashes[local.name]=hashlib.sha256(local.read_bytes()).hexdigest()
        parquet=pq.ParquetFile(local)
        for batch in parquet.iter_batches(batch_size=2048):output.extend(batch.to_pylist())
    return output,hashes


def normalized(value):
    if value is None:return None
    return ' '.join(str(value).strip().lower().replace('**','').split())


def solve(row):
    text=row['turns'][0] if isinstance(row.get('turns'),list) else str(row.get('turns',''))
    task=row.get('task')
    if task=='web_of_lies_v2':return exact.solve_web_of_lies(text),'web_of_lies_exact'
    if task=='spatial':return geometry.solve(text),'geometry_exact_v2'
    return None,'abstain_unsupported'


def main():
    OUT.mkdir(parents=True,exist_ok=True);dataset,hashes=rows();records=[]
    for index,row in enumerate(dataset):
        release=str(row.get('livebench_release_date') or row.get('release_date') or '')[:10]
        if release and release>PUBLIC_CUTOFF:continue
        prediction,cell=solve(row);target=row.get('ground_truth')
        records.append({'index':index,'question_id':row.get('question_id'),'task':row.get('task'),'release':release,'cell':cell,'prediction':prediction,'target':target,'correct':normalized(prediction)==normalized(target)})
    tasks={}
    for task in sorted({record['task'] for record in records}):
        subset=[record for record in records if record['task']==task];correct=sum(record['correct'] for record in subset);coverage=sum(record['prediction'] is not None for record in subset)
        tasks[task]={'n':len(subset),'correct':correct,'accuracy':correct/len(subset),'coverage':coverage/len(subset),'errors':[record for record in subset if not record['correct']]}
    n=len(records);correct=sum(record['correct'] for record in records);supported=[record for record in records if record['task'] in SUPPORTED];supported_correct=sum(record['correct'] for record in supported)
    payload={
        'protocol':'Second adaptive repair. The 48/50 v2 artifact remains primary evidence of the preceding frozen compiler. Zebra abstentions count wrong.',
        'pre_repair_artifact_sha256':'sha256:39fb67a872fb708e0a7f0d1cd2ec0004113fd16b776de9872f8bbf0407a95d17',
        'repository_commit':'864b0d7203c66b429d93c43841df0a773f7738c7','public_cutoff':PUBLIC_CUTOFF,'tasks':tasks,
        'aggregate':{'n':n,'correct':correct,'full_micro_accuracy':correct/n,'full_macro_accuracy':sum(value['accuracy'] for value in tasks.values())/len(tasks),'coverage':sum(record['prediction'] is not None for record in records)/n,'supported_n':len(supported),'supported_correct':supported_correct,'supported_accuracy':supported_correct/len(supported)},
        'parquet_sha256':hashes,
        'code_sha256':{'evaluator':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'geometry':hashlib.sha256(Path('livebench_geometry_exact.py').read_bytes()).hexdigest(),'logic':hashlib.sha256(Path('bbeh_exact_robust.py').read_bytes()).hexdigest()},
    }
    (OUT/'results.json').write_text(json.dumps(payload,indent=2,default=str));print(json.dumps(payload['aggregate'],indent=2))

if __name__=='__main__':main()
