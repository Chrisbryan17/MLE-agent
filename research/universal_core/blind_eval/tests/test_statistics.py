import pytest
from universal_core.blind_eval.statistics import wilson_interval
def test_known_interval():
    lo,hi=wilson_interval(50,100); assert lo==pytest.approx(.4038,abs=1e-4); assert hi==pytest.approx(.5962,abs=1e-4)
def test_empty(): assert wilson_interval(0,0)==(0.0,0.0)
def test_bad_counts():
    with pytest.raises(ValueError): wilson_interval(2,1)
