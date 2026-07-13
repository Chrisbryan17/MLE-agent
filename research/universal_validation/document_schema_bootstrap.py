#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,pathlib,urllib.parse,urllib.request
import pyarrow.parquet as pq
BASE='https://datasets-server.huggingface.co'
DATASETS={'contract_nli':'kiddothe2b/contract-nli','finqa':'dreamerdeo/finqa','scifact':'davidheineman/scifact-open','tabfact':'table-benchmark/tabfact','redocred':'Despina/re-docred'}
OUT=pathlib.Path('artifacts/document_schema_bootstrap'); CACHE=pathlib.Path('.document_schema_cache')
def get(repo):
 u=BASE+'/parquet?'+urllib.parse.urlencode({'dataset':repo}); return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'urc-schema/1'}),timeout=180).read())['parquet_files']
def trunc(v,n=3000):
 s=json.dumps(v,ensure_ascii=False,default=str); return s if len(s)<=n else s[:n]+'…'
def main():
 OUT.mkdir(parents=True,exist_ok=True); report={}
 for alias,repo in DATASETS.items():
  entries=get(repo); splits={str(e.get('split')) for e in entries}; preferred=next((x for x in ('test','validation','dev','train','claims') if x in splits),sorted(splits)[0]); chosen=[e for e in entries if str(e.get('split'))==preferred][0]
  path=CACHE/f'{alias}.parquet'; path.parent.mkdir(parents=True,exist_ok=True)
  if not path.exists(): urllib.request.urlretrieve(chosen['url'],path)
  pf=pq.ParquetFile(path); rows=[]
  for batch in pf.iter_batches(batch_size=3): rows=batch.to_pylist(); break
  samples=[]
  for r in rows:
   value=trunc(r); samples.append(json.loads(value) if not value.endswith('…') else value)
  report[alias]={'repo':repo,'config':chosen.get('config'),'split':preferred,'rows':pf.metadata.num_rows,'schema':str(pf.schema_arrow),'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'samples':samples}
 (OUT/'schema_samples.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str)+'\n')
 print(json.dumps({k:{'split':v['split'],'rows':v['rows']} for k,v in report.items()},indent=2))
if __name__=='__main__':main()
