from __future__ import annotations
import math
from statistics import NormalDist

def wilson_interval(successes:int,total:int,confidence:float=0.95)->tuple[float,float]:
    if successes<0 or total<0 or successes>total: raise ValueError("invalid binomial counts")
    if not 0<confidence<1: raise ValueError("confidence must be between zero and one")
    if total==0: return (0.0,0.0)
    z=NormalDist().inv_cdf((1+confidence)/2)
    p=successes/total
    denominator=1+z*z/total
    center=(p+z*z/(2*total))/denominator
    margin=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denominator
    return (max(0.0,center-margin),min(1.0,center+margin))
