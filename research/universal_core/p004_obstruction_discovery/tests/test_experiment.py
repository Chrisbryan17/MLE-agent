import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import experiment as x


class P004Contracts(unittest.TestCase):
    def test_field_rank_identifiable_controls(self):
        xs = [x.make_row(i, 0, 0, 0) for i in (0, 1)]
        self.assertEqual(x.rank_mod(xs), 2)
        for row in (x.make_row(0, 1, 0, 0), x.make_row(0, 0, 1, 0), x.make_row(0, 0, 0, 1)):
            xs.append(row)
        self.assertEqual(x.rank_mod(xs), 5)

    def test_modular_generator_and_schema(self):
        pub, labels = x.make_dataset(1, 25, split="holdout")
        self.assertEqual(set(x.FEATURES), {u["cause"] for u in labels})
        self.assertEqual(len(pub), 25)
        self.assertEqual(len(pub[0]["queries"]), 36)
        self.assertTrue(all(9 <= r["x"] <= 12 for t in pub for r in t["targets"]))
        self.assertTrue(all(q["x"] <= 8 for t in pub for q in t["queries"]))
        self.assertFalse(any("cause" in t or "params" in t for t in pub))

    def test_deterministic(self):
        self.assertEqual(x.make_dataset(18, 5, split="development"), x.make_dataset(18, 5, split="development"))

    def test_all_methods_same_query_budget(self):
        pub, labels = x.make_dataset(17, 2, split="holdout")
        requests = x.plan_requests(pub)
        for case in requests:
            self.assertIsNone(case["requests"]["passive"])
            self.assertIsNone(case["requests"]["flat"])
            self.assertTrue(all(0 <= v < 36 for k, v in case["requests"].items() if v is not None))

    def test_posterior_normalized(self):
        pub, _ = x.make_dataset(2, 1, split="development")
        cs, ws = x.posterior(pub[0]["demonstrations"])
        self.assertEqual(len(cs), 13 + 4 * 13 * 12)
        self.assertAlmostEqual(sum(ws), 1.0, places=12)
        self.assertTrue(all(w >= 0 for w in ws))

    def test_constant_alignment(self):
        obs = [{**x.make_row(i, 0, 0, 0), "y": (i + 2) % 13} for i in range(5)]
        cs, ws = x.posterior(obs)
        pred = x.predict_one(cs, ws, x.make_row(11, 0, 0, 0))
        self.assertEqual(pred, 0)

    def test_obstruction_rank_is_only_diagnostic(self):
        same = [x.make_row(1, 1, 1, 1) for _ in range(4)]
        self.assertEqual(x.rank_mod(same), 1)
        self.assertEqual(x.feature("entity", same[0]), x.feature("switch", same[0]))
        # Identical observations cannot uniquely identify these mechanisms.

    def test_one_shot_and_hash_gates(self):
        with tempfile.TemporaryDirectory() as d:
            from argparse import Namespace
            args = Namespace(directory=d, count=1, split="holdout")
            with patch.object(x, "SEEDS", (33,)):
                x.cmd_prepare(args)
                with self.assertRaises(FileExistsError):
                    x.cmd_prepare(args)
                x.cmd_plan(args)
                x.cmd_broker(args)
                x.cmd_predict(args)
                x.cmd_score(args)
                with self.assertRaises(FileExistsError):
                    x.cmd_score(args)
                predictions = x.read_json(Path(d) / "predictions.json")
                predictions[0]["methods"]["odmd"]["predictions"][0] = -2
                x.write_json(Path(d) / "predictions.json", predictions)
                (Path(d) / "score.json").unlink()
                with self.assertRaises(ValueError):
                    x.cmd_score(args)

    def test_prediction_without_private_labels(self):
        pub, hidden = x.make_dataset(2, 1, split="holdout")
        requests = x.plan_requests(pub)
        replies = x.issue_replies(pub, hidden, requests)
        pred = x.perform_prediction(pub, requests, replies)
        self.assertEqual(len(pred), 1)
        self.assertEqual(set(pred[0]["methods"]), set(x.METHODS))
        self.assertTrue(all(0 <= y < 13 for m in x.METHODS for y in pred[0]["methods"][m]["predictions"]))

    def test_query_replies_do_not_contain_target_labels(self):
        pub, hidden = x.make_dataset(2, 1, split="holdout")
        replies = x.issue_replies(pub, hidden, x.plan_requests(pub))
        self.assertEqual(set(replies[0]), {"id", "answers"})
        self.assertNotIn("cause", json.dumps(replies[0]))
        self.assertNotIn("targets", json.dumps(replies[0]))

    def test_prediction_score_no_oracle_row_reuse(self):
        public, private = x.make_dataset(3, 1, split="development")
        qs = x.plan_requests(public)
        rep = x.issue_replies(public, private, qs)
        pred = x.perform_prediction(public, qs, rep)
        report = x.score(public, private, qs, pred)
        self.assertEqual(report["cases"], 1)
        self.assertTrue(all(0 <= m["accuracy"] <= 1 for m in report["metrics"].values()))

    def test_one_cause_example_nonlinear_distinguishing(self):
        target = x.make_row(7, 0, 0, 0)
        self.assertNotEqual(x.result("quadratic", 2, 3, target), x.result("constant", 2, 0, target))


if __name__ == "__main__":
    unittest.main()
