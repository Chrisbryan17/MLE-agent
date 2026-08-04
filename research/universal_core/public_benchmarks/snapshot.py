"""Fetch, normalize, and verify immutable public benchmark snapshots."""

from __future__ import annotations

import argparse
import base64
import collections
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile
from typing import Any, Iterable

PACKAGE_DIR = pathlib.Path(__file__).resolve().parent
LOCK_PATH = PACKAGE_DIR / "sources.lock.json"
DEFAULT_VENDOR = PACKAGE_DIR / "vendor"
MANIFEST_NAME = "SNAPSHOT_MANIFEST.json"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], *, cwd: pathlib.Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def clone_at(repository: str, commit: str, destination: pathlib.Path) -> None:
    run(["git", "clone", "--filter=blob:none", "--no-checkout", repository, str(destination)])
    run(["git", "checkout", "--detach", commit], cwd=destination)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=destination, text=True).strip()
    if actual != commit:
        raise RuntimeError(f"checkout mismatch: expected {commit}, got {actual}")


def json_default(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"__bytes_base64__": base64.b64encode(value).decode("ascii")}
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "tolist"):
        return value.tolist()
    raise TypeError(f"unsupported JSON value: {type(value)!r}")


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=json_default) + "\n")


def write_jsonl(path: pathlib.Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=json_default) + "\n")
            count += 1
    return count


def valid_grid(grid: Any) -> bool:
    if not isinstance(grid, list) or not grid or not all(isinstance(row, list) and row for row in grid):
        return False
    width = len(grid[0])
    return (
        1 <= len(grid) <= 30
        and 1 <= width <= 30
        and all(len(row) == width for row in grid)
        and all(type(cell) is int and 0 <= cell <= 9 for row in grid for cell in row)
    )


def verify_arc(target: pathlib.Path, lock: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"commit": lock["commit"], "splits": {}}
    for split, expected in (
        ("training", lock["expected_training_tasks"]),
        ("evaluation", lock["expected_evaluation_tasks"]),
    ):
        paths = sorted((target / "data" / split).glob("*.json"))
        if len(paths) != expected:
            raise RuntimeError(f"ARC {split}: expected {expected} tasks, found {len(paths)}")
        pairs = 0
        test_inputs = 0
        for path in paths:
            task = json.loads(path.read_text(encoding="utf-8"))
            if set(task) != {"train", "test"}:
                raise RuntimeError(f"ARC malformed keys in {path}")
            for section in ("train", "test"):
                if not isinstance(task[section], list) or not task[section]:
                    raise RuntimeError(f"ARC empty {section} in {path}")
                for pair in task[section]:
                    if "input" not in pair or not valid_grid(pair["input"]):
                        raise RuntimeError(f"ARC invalid input grid in {path}")
                    if "output" in pair and not valid_grid(pair["output"]):
                        raise RuntimeError(f"ARC invalid output grid in {path}")
                    pairs += 1
                    if section == "test":
                        test_inputs += 1
        result["splits"][split] = {"tasks": len(paths), "pairs": pairs, "test_inputs": test_inputs}
    return result


def fetch_arc(lock: dict[str, Any], work: pathlib.Path, vendor: pathlib.Path) -> dict[str, Any]:
    source = work / "arc-agi-2"
    clone_at(lock["repository"], lock["commit"], source)
    target = vendor / "arc_agi_2"
    shutil.copytree(source / "data", target / "data")
    for name in ("LICENSE", "readme.md", "changelog.md"):
        if (source / name).exists():
            shutil.copy2(source / name, target / name)
    return verify_arc(target, lock)


def locate_bbeh_sets(source: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    task_roots = [path for path in source.rglob("benchmark_tasks*") if path.is_dir()]
    scored: list[tuple[int, pathlib.Path]] = []
    for root in task_roots:
        count = 0
        for path in root.rglob("task.json"):
            try:
                count += len(json.loads(path.read_text(encoding="utf-8"))["examples"])
            except (KeyError, json.JSONDecodeError, TypeError):
                continue
        if count:
            scored.append((count, root))
    by_count = {count: root for count, root in scored}
    if 4520 not in by_count or 460 not in by_count:
        raise RuntimeError(f"unable to locate BBEH full/mini roots; observed {sorted(by_count)}")
    return by_count[4520], by_count[460]


def count_bbeh(root: pathlib.Path) -> tuple[int, int, list[str]]:
    tasks = 0
    examples = 0
    names: list[str] = []
    for path in sorted(root.rglob("task.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("examples")
        if not isinstance(rows, list):
            raise RuntimeError(f"BBEH missing examples list in {path}")
        for row in rows:
            if not isinstance(row, dict) or "input" not in row or "target" not in row:
                raise RuntimeError(f"BBEH malformed example in {path}")
        tasks += 1
        examples += len(rows)
        names.append(path.parent.name)
    return tasks, examples, names


def verify_bbeh(target: pathlib.Path, lock: dict[str, Any]) -> dict[str, Any]:
    full_tasks, full_examples, full_names = count_bbeh(target / "full")
    mini_tasks, mini_examples, mini_names = count_bbeh(target / "mini")
    if full_examples != lock["expected_full_examples"]:
        raise RuntimeError(f"BBEH full: expected {lock['expected_full_examples']}, found {full_examples}")
    if mini_examples != lock["expected_mini_examples"]:
        raise RuntimeError(f"BBEH mini: expected {lock['expected_mini_examples']}, found {mini_examples}")
    return {
        "commit": lock["commit"],
        "full": {"tasks": full_tasks, "examples": full_examples, "task_names": full_names},
        "mini": {"tasks": mini_tasks, "examples": mini_examples, "task_names": mini_names},
    }


def fetch_bbeh(lock: dict[str, Any], work: pathlib.Path, vendor: pathlib.Path) -> dict[str, Any]:
    source = work / "bbeh"
    clone_at(lock["repository"], lock["commit"], source)
    full_root, mini_root = locate_bbeh_sets(source)
    target = vendor / "bbeh"
    shutil.copytree(full_root, target / "full")
    shutil.copytree(mini_root, target / "mini")
    for name in ("LICENSE", "README.md", "leaderboard.md"):
        if (source / name).exists():
            shutil.copy2(source / name, target / name)
    if (source / "bbeh" / "evaluate.py").exists():
        shutil.copy2(source / "bbeh" / "evaluate.py", target / "evaluate.py")
    return verify_bbeh(target, lock)


def fetch_livebench(lock: dict[str, Any], work: pathlib.Path, vendor: pathlib.Path) -> dict[str, Any]:
    try:
        from datasets import load_dataset
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise RuntimeError("install datasets and huggingface_hub before fetching LiveBench") from exc

    source = work / "livebench-harness"
    clone_at(lock["repository"], lock["commit"], source)
    target = vendor / "livebench"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("LICENSE", "README.md", "changelog.md", "pyproject.toml"):
        if (source / name).exists():
            shutil.copy2(source / name, target / name)

    api = HfApi()
    repositories: dict[str, Any] = {}
    for repo_id in lock["dataset_repositories"]:
        category = repo_id.split("/", 1)[1]
        revision = api.dataset_info(repo_id=repo_id).sha
        dataset = load_dataset(repo_id, split="test", revision=revision)
        rows = [dict(row) for row in dataset]
        rows.sort(key=lambda row: str(row.get("question_id", "")))
        count = write_jsonl(target / "questions" / f"{category}.jsonl", rows)
        release_counts = collections.Counter(str(row.get("livebench_release_date", "")) for row in rows)
        repositories[repo_id] = {
            "revision": revision,
            "rows": count,
            "release_counts": dict(sorted(release_counts.items())),
            "features": sorted(dataset.features.keys()),
        }
    write_json(target / "DATASET_REVISIONS.json", repositories)
    return verify_livebench(target, lock)


def verify_livebench(target: pathlib.Path, lock: dict[str, Any]) -> dict[str, Any]:
    revisions_path = target / "DATASET_REVISIONS.json"
    if not revisions_path.exists():
        raise RuntimeError("LiveBench DATASET_REVISIONS.json is missing")
    revisions = json.loads(revisions_path.read_text(encoding="utf-8"))
    expected_repositories = set(lock["dataset_repositories"])
    if set(revisions) != expected_repositories:
        raise RuntimeError("LiveBench dataset repository set mismatch")
    result: dict[str, Any] = {
        "commit": lock["commit"],
        "release_ceiling": lock["public_release_ceiling"],
        "datasets": {},
    }
    seen_ids: set[str] = set()
    for repo_id in sorted(expected_repositories):
        category = repo_id.split("/", 1)[1]
        path = target / "questions" / f"{category}.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        if not rows:
            raise RuntimeError(f"LiveBench {category} is empty")
        releases: collections.Counter[str] = collections.Counter()
        tasks: collections.Counter[str] = collections.Counter()
        for row in rows:
            required = {"question_id", "category", "task", "turns", "ground_truth"}
            if not required.issubset(row):
                raise RuntimeError(f"LiveBench {category} row missing required keys")
            qid = str(row["question_id"])
            if qid in seen_ids:
                raise RuntimeError(f"duplicate LiveBench question_id across categories: {qid}")
            seen_ids.add(qid)
            releases[str(row.get("livebench_release_date", ""))] += 1
            tasks[str(row["task"])] += 1
        recorded = revisions[repo_id]
        if recorded["rows"] != len(rows):
            raise RuntimeError(f"LiveBench row-count mismatch for {repo_id}")
        result["datasets"][repo_id] = {
            "revision": recorded["revision"],
            "rows": len(rows),
            "tasks": dict(sorted(tasks.items())),
            "release_counts": dict(sorted(releases.items())),
        }
    result["total_rows"] = len(seen_ids)
    return result


def file_inventory(vendor: pathlib.Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for path in sorted(path for path in vendor.rglob("*") if path.is_file() and path.name != MANIFEST_NAME):
        inventory.append({
            "path": path.relative_to(vendor).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return inventory


def load_lock() -> dict[str, Any]:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def build_manifest(vendor: pathlib.Path, lock: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    inventory = file_inventory(vendor)
    payload = {
        "schema_version": 1,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "frozen_core": lock["frozen_core"],
        "benchmarks": results,
        "inventory": inventory,
        "totals": {
            "files": len(inventory),
            "bytes": sum(item["bytes"] for item in inventory),
        },
    }
    payload["inventory_digest"] = hashlib.sha256(canonical_json(inventory).encode("utf-8")).hexdigest()
    return payload


def fetch_all(vendor: pathlib.Path) -> dict[str, Any]:
    lock = load_lock()
    if (vendor / MANIFEST_NAME).exists():
        raise RuntimeError("snapshot already exists; delete it explicitly before creating a different snapshot")
    if vendor.exists():
        shutil.rmtree(vendor)
    vendor.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="public-benchmarks-") as temp:
        work = pathlib.Path(temp)
        results = {
            "arc_agi_2": fetch_arc(lock["benchmarks"]["arc_agi_2"], work, vendor),
            "bbeh": fetch_bbeh(lock["benchmarks"]["bbeh"], work, vendor),
            "livebench": fetch_livebench(lock["benchmarks"]["livebench"], work, vendor),
        }
    manifest = build_manifest(vendor, lock, results)
    write_json(vendor / MANIFEST_NAME, manifest)
    return manifest


def verify_all(vendor: pathlib.Path) -> dict[str, Any]:
    lock = load_lock()
    manifest_path = vendor / MANIFEST_NAME
    if not manifest_path.exists():
        raise RuntimeError(f"missing {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = {
        "arc_agi_2": verify_arc(vendor / "arc_agi_2", lock["benchmarks"]["arc_agi_2"]),
        "bbeh": verify_bbeh(vendor / "bbeh", lock["benchmarks"]["bbeh"]),
        "livebench": verify_livebench(vendor / "livebench", lock["benchmarks"]["livebench"]),
    }
    inventory = file_inventory(vendor)
    digest = hashlib.sha256(canonical_json(inventory).encode("utf-8")).hexdigest()
    if inventory != manifest["inventory"]:
        raise RuntimeError("snapshot file inventory does not match manifest")
    if digest != manifest["inventory_digest"]:
        raise RuntimeError("snapshot inventory digest does not match manifest")
    if results != manifest["benchmarks"]:
        raise RuntimeError("benchmark statistics do not match manifest")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("fetch", "verify"))
    parser.add_argument("--vendor", type=pathlib.Path, default=DEFAULT_VENDOR)
    args = parser.parse_args()
    manifest = fetch_all(args.vendor) if args.command == "fetch" else verify_all(args.vendor)
    print(json.dumps({
        "inventory_digest": manifest["inventory_digest"],
        "files": manifest["totals"]["files"],
        "bytes": manifest["totals"]["bytes"],
        "benchmarks": manifest["benchmarks"],
    }, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
