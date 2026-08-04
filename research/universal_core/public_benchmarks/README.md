# Public benchmark snapshot

This directory keeps external public benchmark inputs separate from the frozen
Holonomy V2.1 source identity. The benchmark branch starts from frozen commit
`1d7c489bcdbff755d638b35ad47ce62bd4fe829d`; no file under `holonomy_v2` is
modified here.

The one-shot snapshot imports:

- ARC-AGI-2: all 1,000 public training tasks and 120 public evaluation tasks.
- BBEH: the official 4,520-example full set and 460-example mini set.
- LiveBench: every row currently public in the six official Hugging Face category
  repositories, normalized to deterministic JSON Lines. Each Hugging Face
  repository revision is recorded in `vendor/livebench/DATASET_REVISIONS.json`.

`sources.lock.json` pins the upstream GitHub commits. The generated
`vendor/SNAPSHOT_MANIFEST.json` records every file size and SHA-256 digest,
benchmark counts, task distributions, LiveBench releases, and the frozen core
identity.

To verify an existing snapshot:

```bash
python -m research.universal_core.public_benchmarks.snapshot verify
```

Creating a different snapshot requires explicitly deleting the existing vendor
snapshot. This is intentional: the first imported data identity should not move
silently.

The benchmark data retain their upstream licenses. ARC-AGI-2 is Apache-2.0.
BBEH software is Apache-2.0 and its other materials are CC-BY-4.0. LiveBench's
upstream license is copied into its snapshot directory.
