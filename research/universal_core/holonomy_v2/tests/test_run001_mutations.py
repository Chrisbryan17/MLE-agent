from universal_core.holonomy_v2.blind_adapter import run_public_task_v2
from universal_core.holonomy_v2.engine import HolonomyEngine
from universal_core.holonomy_v2.tests.regression.run001.family_generator import generate_mutation
from universal_core.holonomy_v2.types import SearchConfig


def test_run001_mutation_gate() -> None:
    correct = attempted = rows = 0
    for seed in range(40):
        task = generate_mutation(seed)
        output = run_public_task_v2(task, HolonomyEngine(SearchConfig()))
        for prediction, target in zip(output["predictions"], task["targets"]):
            rows += 1
            if prediction["status"] == "ACCEPTED":
                attempted += 1
                correct += prediction["prediction"] == target
    assert rows == 400
    assert attempted / rows >= 0.95
    assert correct / rows >= 0.95
