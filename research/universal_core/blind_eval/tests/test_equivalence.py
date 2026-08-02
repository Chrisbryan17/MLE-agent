import pytest
from universal_core.blind_eval.contracts import EquivalenceKind,EquivalenceRule
from universal_core.blind_eval.equivalence import answers_equivalent
@pytest.mark.parametrize(("rule","left","right"),[(EquivalenceRule(),{"x":1},{"x":1}),(EquivalenceRule(EquivalenceKind.CASEFOLD_STRING),"Alert","alert"),(EquivalenceRule(EquivalenceKind.UNORDERED_SEQUENCE),[3,1,2],[2,3,1]),(EquivalenceRule(EquivalenceKind.RATIONAL_NUMBER),"2/4","1/2"),(EquivalenceRule(EquivalenceKind.NUMERIC_TOLERANCE,1e-6),1.0,1.0000005),(EquivalenceRule(EquivalenceKind.GRAPH_EDGE_SET),[["a","b"],["b","c"]],[["b","c"],["a","b"]])])
def test_equivalence(rule,left,right): assert answers_equivalent(left,right,rule)
def test_exact_is_type_sensitive(): assert not answers_equivalent(1,"1",EquivalenceRule())
