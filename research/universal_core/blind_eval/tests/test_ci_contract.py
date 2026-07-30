from pathlib import Path
from universal_core.blind_eval.constants import FROZEN_CORE_COMMIT
REPO_ROOT=Path(__file__).resolve().parents[4]
WORKFLOW=REPO_ROOT/".github/workflows/universal-core-blind-eval-v1.yml"
CHECKPOINT=Path(__file__).resolve().parents[1]/"checkpoints/2026-07-30/BLIND_EVAL_PROTOCOL_V1.md"

def test_workflow_contains_required_guards():
    text=WORKFLOW.read_text(encoding="utf-8")
    for token in ("python -m pytest research/universal_core/tests","python -m pytest research/universal_core/blind_eval/tests","python -m universal_core.archive_guard",FROZEN_CORE_COMMIT,"universal-core-blind-eval-v1-evidence","prohibited-mechanism-scan"):
        assert token in text

def test_checkpoint_preserves_claim_boundary():
    text=CHECKPOINT.read_text(encoding="utf-8").casefold(); assert "protocol mechanics" in text; assert "not an independent blind benchmark" in text; assert "no scientific accuracy result" in text
