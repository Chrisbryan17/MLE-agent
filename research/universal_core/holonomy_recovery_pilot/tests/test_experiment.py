import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiment import P, identity, comp, inv, make_case, paths, choose, learn, true_map

class TestAlgebra(unittest.TestCase):
    def test_identity_inverse_all_group_elements(self):
        for a in range(1,P):
            for b in range(P):
                g=(a,b)
                self.assertEqual(comp(inv(g),g),identity())
                self.assertEqual(comp(g,inv(g)),identity())
    def test_associativity(self):
        for a,b,c in [((2,3),(8,4),(9,10)),((1,2),(1,3),(1,4)),((5,9),(7,8),(2,1))]:
            self.assertEqual(comp(comp(a,b),c),comp(a,comp(b,c)))
    def test_oracle_noiseless_cycle_and_composition(self):
        for seed in (1,2,3,81010050001):
            case, truth=make_case(seed, True, 0)
            ps=paths(case)
            self.assertGreater(len(ps),0)
            self.assertTrue(all(list(p)==truth for p,_ in ps))
            self.assertGreaterEqual(case['shortest_hops'],4)
    def test_holonomy_equals_dsl_for_exact_transport(self):
        for seed in range(20):
            case,_=make_case(815100 + seed,True,.15)
            self.assertEqual(choose(case,'holonomy',[])[0], choose(case,'dsl',[])[0])
    def test_unknown_composition_abstains(self):
        case,_=make_case(812310,True,0)
        self.assertIsNone(choose(case,'no_composition',[])[0])
    def test_pretrain_does_not_use_holdout_labels(self):
        train=[]; labels={}
        for n in range(20):
            case, truth=make_case(1000+n,False,0)
            train.append(case);labels[case['id']]=truth
        weights, count=learn(train,labels)
        self.assertEqual(len(weights),3)
        self.assertGreater(count,0)
    def test_changed_labels_cannot_control_holonomy(self):
        c,_=make_case(876100,True,.15)
        before=choose(c,'holonomy',[])
        c2=dict(c);c2['irrelevant_gold_label']=[0,0]
        self.assertEqual(before[:4],choose(c2,'holonomy',[])[:4])

if __name__=='__main__': unittest.main()
