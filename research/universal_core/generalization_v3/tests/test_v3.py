import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sys import path

path.insert(0, str(Path(__file__).resolve().parents[1]))
import experiment
from synthesis import (OPS, P, PROBES, canonical_programs, choose_active,
                       consensus, fit, learn_library, order_candidates, run, signature)
from semantics import Fact, evaluate_extraction, evidence_answer
from experiment import (generate, prepare, query_choices, release_feedback, predict, score, file_sha, BUDGET)


class SynthesisTests(unittest.TestCase):
    def test_transformations_are_pure_and_bounded(self):
        x = (0, 1, 2, 3)
        for op in OPS:
            out = run((op,), x)
            self.assertEqual(len(out), 4)
            self.assertTrue(all(0 <= k < P for k in out))
        self.assertEqual(x, (0, 1, 2, 3))
        with self.assertRaises(ValueError):
            run(("undefined",), x)
        with self.assertRaises(ValueError):
            run((), (1, 2, 3))

    def test_composition_order_matters(self):
        x = (0, 1, 2, 3)
        self.assertNotEqual(run(("roll", "inc_first"), x), run(("inc_first", "roll"), x))

    def test_program_behavior_deduplicated(self):
        p = canonical_programs(3)
        self.assertEqual(len(p), len({signature(x) for x in p}))
        self.assertTrue(any(len(x) == 3 for x in p))

    def test_active_query_maximizes_entropy(self):
        fitting = (("inc_first",), ("inc_last",))
        pool = ((0,0,0,0), (1,1,1,1))
        self.assertEqual(choose_active(fitting, pool), 0)
        self.assertEqual(choose_active((), pool), 0)

    def test_abstention_for_ties_and_no_hypothesis(self):
        self.assertEqual(consensus((), (0,0,0,0))["status"], "ABSTAIN")
        self.assertEqual(consensus((("inc_first",), ("inc_last",)), (0,0,0,0))["status"], "ABSTAIN")

    def test_library_uses_demonstrations_only(self):
        examples=[]
        for idx in range(5):
            pp=("inc_first", "roll")
            demos=[{"input": list(x), "output": list(run(pp,x))} for x in PROBES]
            examples.append({"id": "train-%d" % idx, "demos": demos})
        lib=learn_library(examples)
        self.assertEqual(lib.training_digest, __import__('synthesis').digest(examples))
        self.assertTrue(all(len(p)==2 for p in lib.macros))

    def test_heldout_compositional_signatures_not_in_training(self):
        with patch.object(experiment, "SEEDS", (3331, 3337, 3343)):
            public, gold, oracle = generate()
        self.assertEqual(len(public['train']),108)
        self.assertEqual(len(public['holdout']),180)
        self.assertEqual(set(gold),set(oracle))
        self.assertEqual(len(set(t['id'] for t in public['holdout'])),180)
        self.assertTrue(all(len(t['demos'])==1 for t in public['holdout']))

    def test_seal_refuses_overwrites_and_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            with patch.object(experiment, "SEEDS", (3331, 3337, 3343)):
                prepare(folder)
                with self.assertRaises(FileExistsError):
                    prepare(folder)
            with patch.object(experiment, "SEEDS", (3331, 3337, 3343)):
                q=query_choices(folder)
                with self.assertRaises(RuntimeError):
                    release_feedback(folder, expected_query_sha256='bad')
                f=release_feedback(folder,expected_query_sha256=q['query_digest'])
                with self.assertRaises(RuntimeError):
                    predict(folder,expected_query_sha256=q['query_digest'],expected_feedback_sha256='bad')
                p=predict(folder,expected_query_sha256=q['query_digest'],expected_feedback_sha256=f['feedback_sha256'])
                with self.assertRaises(RuntimeError):
                    score(folder,expected_prediction_sha256='bad')
                s=score(folder,expected_prediction_sha256=p['prediction_sha256'])
                self.assertEqual(s['holdout'],180)
                self.assertEqual(set(s['metrics']),{'no_query','random_query','active_query','active_no_macros','full_no_query','active_full'})
                self.assertTrue(all(sum(m['per_seed'][str(seed)]['n'] for seed in (3331,3337,3343))==180 for m in s['metrics'].values()))
                with self.assertRaises(FileExistsError):
                    score(folder,expected_prediction_sha256=p['prediction_sha256'])


class SemanticTests(unittest.TestCase):
    def test_provenance_types_quantifiers_and_temporal_scope(self):
        src={'d':'Asha approved invoice on 2026-09-01.'}
        base={'subject':'Asha','predicate':'approved','object':'invoice','subject_type':'person','object_type':'document',
              'polarity':'positive','quantifier':'exists','valid_from':'2026-09-01','valid_until':'2026-09-30',
              'source_id':'d','span_start':0,'span_end':22}
        f=Fact.from_mapping(base,src)
        self.assertIs(evidence_answer([f],'Asha','approved','invoice','2026-09-15'),True)
        self.assertIsNone(evidence_answer([f],'Asha','approved','invoice','2026-11-15'))
        for invalid in ({**base,'object_type':'banana'},{**base,'source_id':'missing'},
                        {**base,'quantifier':'sometimes'},{**base,'span_end':999},
                        {**base,'valid_from':'2026-10-01','valid_until':'2026-09-01'}):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                Fact.from_mapping(invalid,src)

    def test_negation_conflict_is_unknown_not_false(self):
        src={'d':'Example evidence source'}
        data={'subject':'S','predicate':'owns','object':'O','subject_type':'person','object_type':'document',
              'polarity':'negative','quantifier':'exists','valid_from':None,'valid_until':None,
              'source_id':'d','span_start':0,'span_end':7}
        neg=Fact.from_mapping(data,src)
        pos=Fact.from_mapping({**data,'polarity':'positive'},src)
        self.assertIs(evidence_answer([neg],'S','owns','O'),False)
        self.assertIsNone(evidence_answer([neg,pos],'S','owns','O'))
        self.assertEqual(evaluate_extraction([pos],[neg])['exact_document'],0)

if __name__=='__main__':unittest.main()

class TransportTests(unittest.TestCase):
    def test_exact_path_composition_and_flat_cycle(self):
        from transport import Edge, tree_estimate, robust_estimate, cycle_residuals, loss
        edges = [Edge(0, 1, 2), Edge(1, 2, 3), Edge(0, 2, 5)]
        self.assertEqual(tree_estimate(3, edges), (0, 2, 5))
        self.assertEqual(cycle_residuals(edges), {(0,1,2): 0})
        self.assertEqual(robust_estimate(3, edges), (0, 2, 5))
        self.assertEqual(loss((0,2,5), edges), 0)

    def test_corrupted_cycle_exposes_residual(self):
        from transport import Edge, cycle_residuals
        edges = [Edge(0,1,2), Edge(1,2,3), Edge(0,2,4)]
        self.assertNotEqual(cycle_residuals(edges)[0,1,2], 0)

    def test_disconnected_estimation_rejected(self):
        from transport import Edge, tree_estimate
        with self.assertRaisesRegex(ValueError,'disconnected'):
            tree_estimate(3,[Edge(0,1,2)])
