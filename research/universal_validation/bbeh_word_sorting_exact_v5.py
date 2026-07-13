#!/usr/bin/env python3
from __future__ import annotations
import collections,json,pathlib,re,sys
ORD={'first':0,'second':1,'third':2,'fourth':3,'fifth':4,'sixth':5,'seventh':6,'eighth':7,'ninth':8,'tenth':9,'eleventh':10,'twelfth':11}

def direct(text):
    alpha=list('abcdefghijklmnopqrstuvwxyz');low=text.lower()
    m=re.search(r'alphabet order\s*\[([^]]+)\]',low)
    if m:
        chars=re.findall(r'\b[a-z]\b',m.group(1));
        if len(chars)==26:alpha=chars
    m=re.search(r'except that ([a-z]) and ([a-z]) are the first two letters',low)
    if m:
        for c in m.groups():alpha.remove(c)
        alpha=list(m.groups())+alpha
    else:
        m=re.search(r'except that ([a-z]) is the first letter',low)
        if m:alpha.remove(m.group(1));alpha.insert(0,m.group(1))
    m=re.search(r'except that ([a-z]) and ([a-z]) are the last two letters',low)
    if m:
        for c in m.groups():alpha.remove(c)
        alpha.extend(m.groups())
    else:
        m=re.search(r'except that ([a-z]) is the last letter',low)
        if m:alpha.remove(m.group(1));alpha.append(m.group(1))
    for a,b in re.findall(r'([a-z]) and ([a-z]) (?:are )?swapped(?: in the order)?',low):
        ia,ib=alpha.index(a),alpha.index(b);alpha[ia],alpha[ib]=alpha[ib],alpha[ia]
    rank={c:i for i,c in enumerate(alpha)}
    m=re.search(r'separate them with comma:\s*(.*)$',text,re.S|re.I)
    if not m:return None
    words=[x.strip() for x in m.group(1).strip().split(',')]
    return ', '.join(sorted(words,key=lambda w:tuple(rank.get(c,99) for c in w.lower())))

def edit(a,b):
    if a==b:return 0
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        cur=[i]
        for j,y in enumerate(b,1):cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=cur
    return prev[-1]

def make_canon(original):
    vocab=list(dict.fromkeys(original))
    def canon(w):
        if w in vocab:return w
        ranked=sorted((edit(w.lower(),x.lower()),x) for x in vocab)
        if ranked and ranked[0][0]<=4 and (len(ranked)==1 or ranked[0][0]<ranked[1][0]):return ranked[0][1]
        return w
    return canon

def qwords(s):return re.findall(r'"([^"]+)"',s)
def parse_blocks(expr,canon):
    blocks=[]
    for part in expr.split('<'):
        ws=[canon(w) for w in qwords(part)]
        if ws:blocks.append(ws)
    return blocks

def same_group(a,b):return collections.Counter(a)==collections.Counter(b)
def state_equal(claim,expected):
    return len(claim)==len(expected) and all(same_group(a,b[0]) for a,b in zip(claim,expected))

def initial_state(words):
    groups=[]
    for key in sorted(set(w[0].lower() for w in words)):
        groups.append(([w for w in words if w[0].lower()==key],1))
    return groups

def next_unresolved(state):
    for i,(g,depth) in enumerate(state):
        if len(g)>1:return i,g,depth
    return None,None,None

def split_group(group,pos):
    buckets={}
    for w in group:
        clean=''.join(ch for ch in w.lower() if ch.isalpha())
        key=clean[pos] if len(clean)>pos else ''
        buckets.setdefault(key,[]).append(w)
    return [(buckets[k],pos+1) for k in sorted(buckets)]

def audit(text):
    m=re.search(r'List:\s*(.*?)\nThought 1:',text,re.S)
    if not m:return None
    original=m.group(1).strip().split();canon=make_canon(original)
    thoughts={int(n):b.strip() for n,b in re.findall(r'Thought\s+(\d+):\s*(.*?)(?=\nThought\s+\d+:|\nQ: Is there|\Z)',text,re.S)}
    state=None;pending=None;first_rank_by_letter={}
    for n in sorted(thoughts):
        body=thoughts[n];low=body.lower()
        pos=None
        for word,k in ORD.items():
            if f'{word} letter' in low:pos=k;break
        claims=re.findall(r'"([^"]+)"\s*:\s*"([a-z])"\s*\((\d+)\)',body)
        if n==1:
            for w,c,r in claims:first_rank_by_letter.setdefault(c.lower(),int(r))
            continue
        if state is None:
            if not body.startswith('We now have:'):return str(n)
            segment=body.split(':',1)[1].strip().rstrip('.')
            claim=parse_blocks(segment,canon);expected=initial_state(original)
            if not state_equal(claim,expected):return str(n)
            for part in segment.split('<'):
                ws=[canon(w) for w in qwords(part)]
                rm=re.search(r'\((\d+)\)',part)
                if ws and rm and int(rm.group(1)) != first_rank_by_letter.get(ws[0][0].lower(), int(rm.group(1))):return str(n)
            state=expected;continue
        if "sort this subpart" in low:
            idx,group,expected_pos=next_unresolved(state)
            if group is None:return str(n)
            sm=re.search(r'subpart\s+(\[.*?\])\s+by looking',body,re.S)
            if not sm:return str(n)
            selected=[canon(w) for w in qwords(sm.group(1))]
            if not same_group(selected,group) or pos!=expected_pos:return str(n)
            claim_map={canon(w):(c.lower(),int(r)) for w,c,r in claims}
            def letters(word):return ''.join(ch for ch in word.lower() if ch.isalpha())
            claim_error=False
            for word in group:
                clean=letters(word)
                if word not in claim_map or len(clean)<=expected_pos:
                    claim_error=True;continue
                c,r=claim_map[word]
                if clean[expected_pos]!=c or ord(c)-96!=r:claim_error=True
            claimed_buckets={}
            for word in group:
                c=claim_map.get(word,('',0))[0]
                claimed_buckets.setdefault(c,[]).append(word)
            claimed_split=[(claimed_buckets[k],expected_pos+1) for k in sorted(claimed_buckets)]
            pending=(idx,group,expected_pos,n,claim_error,claimed_split)
            continue
        if body.startswith('We now have:'):
            if pending is None:return str(n)
            idx,group,pos,sort_thought,claim_error,claimed_split=pending
            local_text=body.split(':',1)[1]
            local_text=local_text.split('for the subpart',1)[0].strip().rstrip('.')
            local_claim=parse_blocks(local_text,canon)
            local_expected=split_group(group,pos)
            if claim_error:
                if state_equal(local_claim,claimed_split):return str(sort_thought)
                return str(n)
            if not state_equal(local_claim,local_expected):return str(n)
            expected=state[:idx]+local_expected+state[idx+1:]
            if 'Hence, we have' in body:
                segment=body.split('Hence, we have',1)[1].strip().rstrip('.')
                claim=parse_blocks(segment,canon)
                if not claim:return str(n)
                flat_claim=[w for block in claim for w in block]
                if len(flat_claim)==len(original):
                    if not state_equal(claim,expected):return str(n)
                else:
                    flat_expected=[w for block,_ in expected for w in block]
                    found=False
                    for start in range(len(flat_expected)-len(flat_claim)+1):
                        if flat_expected[start:start+len(flat_claim)]==flat_claim:
                            found=True;break
                    if not found:return str(n)
            state=expected;pending=None;continue
        if 'answer is' in low:
            if any(len(g)>1 for g,_ in state):return str(n)
            tail=re.split(r'answer is',body,flags=re.I,maxsplit=1)[1]
            claimed=[canon(x) for x in re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",tail)[:len(original)]]
            expected=[w for g,_ in state for w in g]
            if claimed!=expected:return str(n)
            continue
    return 'No'

def solve(text):return direct(text) if text.lstrip().startswith('Consider a new alphabet') else audit(text)

def main(path):
    ex=json.loads(pathlib.Path(path).read_text())['examples'];errs=[]
    for i,e in enumerate(ex):
        try:p=solve(e['input']);err=None
        except Exception as exc:p=None;err=f'{type(exc).__name__}: {exc}'
        if p!=e['target']:errs.append((i,p,e['target'],err))
    print('correct',len(ex)-len(errs),'/',len(ex))
    for x in errs[:50]:print(x)
if __name__=='__main__':main(sys.argv[1])
