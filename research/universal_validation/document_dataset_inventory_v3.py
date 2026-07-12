#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

BASE='https://datasets-server.huggingface.co'
OUT=Path('artifacts/document_inventory_v3')
CACHE=Path('.document_cache_v3')
DATASETS={
    'contract_nli':'kiddothe2b/contract-nli',
    'finqa':'dreamerdeo/finqa',
    'scifact':'davidheineman/scifact-open',
    'tabfact':'table-benchmark/tabfact',
    'docred':'Despina/re-docred',
}
SENSITIVE=('label','answer','target','gold','verdict','relation')


def get_json(path,params,retries=8):
    url=BASE+path+'?'+urllib.parse.urlencode(params);last=None
    for attempt in range(retries):
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'hybrid-reasoning-validation/0.1'})
            with urllib.request.urlopen(request,timeout=180) as response:return json.loads(response.read())
        except Exception as exc:last=exc;time.sleep(min(30,2**attempt))
    raise last


def download(url,path,retries=8):
    if path.exists():return
    path.parent.mkdir(parents=True,exist_ok=True);last=None
    for attempt in range(retries):
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'hybrid-reasoning-validation/0.1'})
            with urllib.request.urlopen(request,timeout=300) as response,path.open('wb') as handle:
                while True:
                    block=response.read(1024*1024)
                    if not block:break
                    handle.write(block)
            return
        except Exception as exc:last=exc;path.unlink(missing_ok=True);time.sleep(min(30,2**attempt))
    raise last


def shape(value:Any):
    if isinstance(value,dict):return {'type':'dict','keys':sorted(value),'children':{key:shape(item) for key,item in list(value.items())[:20]}}
    if isinstance(value,list):return {'type':'list','length':len(value),'item':shape(value[0]) if value else None}
    if isinstance(value,str):return {'type':'str','length':len(value)}
    return {'type':type(value).__name__}


def redact(row):
    return {key:({'redacted':True,**shape(value)} if any(token in key.lower() for token in SENSITIVE) else shape(value)) for key,value in row.items()}


def inspect(alias,repo):
    result={'alias':alias,'repo':repo,'exports':[],'errors':[]}
    try:manifest=get_json('/parquet',{'dataset':repo})
    except Exception as exc:
        result['errors'].append(f'parquet_manifest: {type(exc).__name__}: {exc}');return result
    entries=manifest.get('parquet_files',[]);result['parquet_file_count']=len(entries);result['configs']=sorted({str(entry.get('config')) for entry in entries});result['splits']=sorted({str(entry.get('split')) for entry in entries})
    groups={}
    for entry in entries:groups.setdefault((entry.get('config'),entry.get('split')),[]).append(entry)
    for (config,split),files in sorted(groups.items(),key=lambda item:(str(item[0][0]),str(item[0][1]))):
        first=files[0];local=CACHE/alias/str(config)/str(split)/'000.parquet';item={'config':config,'split':split,'shards':len(files),'first_url':first['url']}
        try:
            download(first['url'],local);item['first_shard_sha256']=hashlib.sha256(local.read_bytes()).hexdigest();parquet=pq.ParquetFile(local);item['schema']=str(parquet.schema_arrow);item['first_shard_rows']=parquet.metadata.num_rows;batch=next(parquet.iter_batches(batch_size=1));item['row_shape']=redact(batch.to_pylist()[0])
        except Exception as exc:item['error']=f'{type(exc).__name__}: {exc}'
        result['exports'].append(item)
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True);reports=[inspect(alias,repo) for alias,repo in DATASETS.items()]
    payload={'protocol':'Frozen serviceable Parquet mirrors; label/relation-like values redacted from inventory. Mirror selection changes transport only, not benchmark family.','datasets':reports,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'inventory.json').write_text(json.dumps(payload,indent=2,default=str));print(json.dumps({report['alias']:{'repo':report['repo'],'files':report.get('parquet_file_count',0),'configs':report.get('configs'),'splits':report.get('splits'),'errors':report.get('errors')} for report in reports},indent=2))

if __name__=='__main__':main()
