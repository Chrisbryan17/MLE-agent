#!/usr/bin/env python3
from __future__ import annotations
import json, math, pathlib, re, sys
from dataclasses import dataclass
from typing import Callable

NUMBER_WORDS={'zero':0,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
BASIC={'+','-','*'}

def is_prime(n:int)->bool:
    if n<2:return False
    if n%2==0:return n==2
    d=3
    while d*d<=n:
        if n%d==0:return False
        d+=2
    return True

def normalize(s:str)->str:
    s=s.replace('$','')
    s=re.sub(r'\b('+'|'.join(NUMBER_WORDS)+r')\b',lambda m:str(NUMBER_WORDS[m.group(1).lower()]),s,flags=re.I)
    return re.sub(r'\s+',' ',s).strip()

TOKEN_RE=re.compile(r'\d+|[A-Za-z]+|[(),]|[^\w\s(),]+')

def tokenize(s:str)->list[str]:
    return TOKEN_RE.findall(normalize(s))

@dataclass
class Parser:
    toks:list[str]
    env:dict[str,int]
    ops:dict[str,Callable[[int,int],int]]
    i:int=0
    def peek(self):return self.toks[self.i] if self.i<len(self.toks) else None
    def take(self):
        t=self.peek()
        if t is None: raise ValueError('unexpected EOF')
        self.i+=1;return t
    def primary(self)->int:
        t=self.take()
        if t=='-': return -self.primary()
        if t=='+': return self.primary()
        if t=='(':
            v=self.expr(0)
            if self.take()!=')':raise ValueError('expected )')
            return v
        if t.isdigit():return int(t)
        if re.fullmatch(r'[A-Za-z]+',t):
            if self.peek()=='(':
                self.take();a=self.expr(0)
                if self.take()!=',':raise ValueError('expected comma')
                b=self.expr(0)
                if self.take()!=')':raise ValueError('expected )')
                if t.lower()=='gcd':return math.gcd(a,b)
                if t.lower()=='min':return min(a,b)
                if t.lower()=='max':return max(a,b)
                raise ValueError('unknown function '+t)
            if t in self.env:return self.env[t]
            if t.lower() in self.env:return self.env[t.lower()]
            raise ValueError('unknown identifier '+t)
        raise ValueError('bad primary '+t)
    def segment(self,token:str)->list[str]:
        atoms=sorted(set(self.ops)|BASIC,key=len,reverse=True)
        memo={len(token):[]}
        for pos in range(len(token)-1,-1,-1):
            for atom in atoms:
                if token.startswith(atom,pos) and pos+len(atom) in memo:
                    memo[pos]=[atom]+memo[pos+len(atom)];break
        if 0 not in memo:raise ValueError(f'cannot segment operator {token!r}; atoms={atoms}')
        return memo[0]
    def precedence(self,token:str)->int:
        parts=self.segment(token)
        return 30 if len(parts)==1 and parts[0]=='*' else 20
    def apply_atom(self,atom:str,a:int,b:int)->int:
        if atom=='+':return a+b
        if atom=='-':return a-b
        if atom=='*':return a*b
        return int(self.ops[atom](a,b))
    def apply_token(self,token:str,a:int,b:int)->int:
        value=a
        for atom in self.segment(token):value=self.apply_atom(atom,value,b)
        return value
    def expr(self,min_prec=0)->int:
        left=self.primary()
        while self.peek() is not None and self.peek() not in {')',','}:
            token=self.peek()
            if re.fullmatch(r'[A-Za-z0-9]+',token):break
            try:prec=self.precedence(token)
            except Exception:break
            if prec<min_prec:break
            self.take();right=self.expr(prec+1);left=self.apply_token(token,left,right)
        return left

def eval_expr(s:str,env:dict[str,int],ops:dict[str,Callable[[int,int],int]])->int:
    p=Parser(tokenize(s),env,ops);v=p.expr(0)
    if p.i!=len(p.toks):raise ValueError(f'unconsumed {p.toks[p.i:]} in {s}')
    return int(v)

def eval_condition(cond:str,a:int,b:int,ops)->bool:
    cond=normalize(cond)
    if re.fullmatch(r'either a or b is prime',cond,re.I):return is_prime(a) or is_prime(b)
    m=re.fullmatch(r'(.+)\s+(==|>|<)\s+(.+)',cond)
    if not m:raise ValueError('unknown condition '+cond)
    lhs=m.group(1).strip();rhs=eval_expr(m.group(3).strip(),{'a':a,'b':b},ops)
    if lhs.startswith('|') and lhs.endswith('|'):val=abs(eval_expr(lhs[1:-1],{'a':a,'b':b},ops))
    else:val=eval_expr(lhs,{'a':a,'b':b},ops)
    return val==rhs if m.group(2)=='==' else val>rhs if m.group(2)=='>' else val<rhs

def parse_definition(line:str,ops):
    s=normalize(line).rstrip('.')
    s=re.sub(r', where gcd stands for greatest common divisor$','',s,flags=re.I)
    m=re.match(r'a\s+(\S+)\s+b\s+equals\s+(.+)$',s,re.I)
    if not m:raise ValueError('bad definition '+line)
    op,rhs=m.group(1),m.group(2)
    if '; otherwise,' in rhs:
        first,rest=rhs.split(' if ',1);cond,second=re.split(r'; otherwise,\s+it equals\s+',rest,maxsplit=1)
    else:
        first,rest=rhs.split(' if ',1);cond,second=re.split(r'\s+and\s+',rest,maxsplit=1);second=re.sub(r'\s+otherwise$','',second)
    first,cond,second=map(str.strip,(first,cond,second))
    def fn(a,b,first=first,cond=cond,second=second):
        branch=first if eval_condition(cond,a,b,ops) else second
        return eval_expr(branch,{'a':a,'b':b},ops)
    ops[op]=fn

def solve(text:str)->str:
    ops={}
    for line in text.splitlines():
        if line.startswith('$a '):parse_definition(line,ops)
    values={}
    for name,expr in re.findall(r'Let\s+([ABC])\s*=\s*(.+?)(?:\.|$)',text,re.M):
        values[name]=eval_expr(expr.strip(),values,ops)
    m=re.search(r'Compute\s+(.+?)\. Your final answer',text,re.S)
    if not m:raise ValueError('missing compute')
    return str(eval_expr(m.group(1).strip(),values,ops))

def main(path):
    exs=json.loads(pathlib.Path(path).read_text())['examples'];errs=[]
    for i,e in enumerate(exs):
        try:p=solve(e['input']);err=None
        except Exception as exc:p=None;err=f'{type(exc).__name__}: {exc}'
        if p!=str(e['target']).strip():errs.append((i,p,e['target'],err))
    print('correct',len(exs)-len(errs),'/',len(exs))
    for x in errs[:20]:print(x)
if __name__=='__main__':main(sys.argv[1])
