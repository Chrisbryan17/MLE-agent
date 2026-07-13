#!/usr/bin/env python3
from __future__ import annotations
import base64,gzip,hashlib,importlib.util,json,os,pathlib,platform,re,resource,statistics,time
ROOT=pathlib.Path(os.environ.get('BBEH_TASK_ROOT','.external/bbeh/bbeh/benchmark_tasks'))
OUT=pathlib.Path('artifacts/time_arithmetic_exact')
HERE=pathlib.Path(__file__).resolve().parent
ENC=HERE/'bbeh_time_arithmetic_exact_v1.py.gz.b64'
SOLVER=HERE/'bbeh_time_arithmetic_exact_v1.py'

def load_solver():
    SOLVER.write_bytes(gzip.decompress(base64.b64decode(ENC.read_text().strip())))
    spec=importlib.util.spec_from_file_location('time_solver',SOLVER);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def typed_normalize(value):
    text=str(value).strip()
    # Clock precision is semantic: trailing :00 seconds are equivalent to omitted seconds.
    m=re.fullmatch(r'([^,]+),\s*(\d{2}):(\d{2})(?::(\d{2}))?',text)
    if m:return ('clock',m.group(1),int(m.group(2)),int(m.group(3)),int(m.group(4) or 0))
    return ('text',text)

def main():
    solver=load_solver();path=ROOT/'bbeh_time_arithmetic'/'task.json';examples=json.loads(path.read_text())['examples'];rows=[];times=[]
    for i,e in enumerate(examples):
        started=time.perf_counter()
        try:prediction=solver.solve_example(e['input']);error=None
        except Exception as exc:prediction=None;error=f'{type(exc).__name__}: {exc}'
        elapsed=time.perf_counter()-started;times.append(elapsed)
        rows.append({'index':i,'prediction':prediction,'target':e['target'],'strict_correct':prediction==e['target'],'typed_correct':prediction is not None and typed_normalize(prediction)==typed_normalize(e['target']),'latency_seconds':elapsed,'error':error})
    strict=sum(r['strict_correct'] for r in rows);typed=sum(r['typed_correct'] for r in rows);OUT.mkdir(parents=True,exist_ok=True)
    payload={'protocol':'Pinned full-task post-development evaluation. Every official example counts. Strict exact-string accuracy is reported separately from typed temporal-value equivalence, where omitted zero seconds equal :00.','pinned_bbeh_commit':'80d12ca916b7158f22293fcf3144f4d3d854d4be','environment':{'python':platform.python_version(),'platform':platform.platform()},'aggregate':{'n':len(rows),'strict_correct':strict,'strict_accuracy':strict/len(rows),'typed_correct':typed,'typed_accuracy':typed/len(rows),'coverage':sum(r['prediction'] is not None for r in rows)/len(rows),'median_ms':statistics.median(times)*1000,'p95_ms':sorted(times)[int(.95*(len(times)-1))]*1000,'throughput_per_second':len(rows)/sum(times),'peak_rss_kb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},'task_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'encoded_solver_sha256':hashlib.sha256(ENC.read_bytes()).hexdigest(),'decoded_solver_sha256':hashlib.sha256(SOLVER.read_bytes()).hexdigest(),'strict_errors':[r for r in rows if not r['strict_correct']],'typed_errors':[r for r in rows if not r['typed_correct']]}
    (OUT/'results.json').write_text(json.dumps(payload,indent=2));print(json.dumps(payload['aggregate'],indent=2));print(json.dumps(payload['strict_errors'],indent=2))
if __name__=='__main__':main()
