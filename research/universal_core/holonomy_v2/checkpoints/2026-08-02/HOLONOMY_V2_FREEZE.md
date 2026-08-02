# Holonomy V2 Freeze Record

Date: 2026-08-02

The V2 identity is the commit containing this record. The exact commit is written by CI to `artifacts/head.txt` and bound to the uploaded evidence artifact.

## Pre-freeze evidence

Verified implementation head: `ba3c73cb3dfab6ff297cb8e83c48e1b9a2ca0533`

Hosted workflow run: `30760091235`

Hosted job: `91528941973`

Hosted artifact: `8837181246`

Artifact SHA-256: `31e6470cfbe5f9635e9b46227d620cce4c6ad5fbc36c107e7f33e5219a4bccca`

## Gate state

- V1 tests passed.
- Protocol tests passed.
- V2 tests passed.
- Family regression: 600 of 600 attempted and correct.
- Mutation regression: 400 of 400 attempted and correct.
- Two gate replays matched.
- Archive identity passed.
- Production and authored-text checks passed.
- Independent artifact hash review passed.

## Boundary

Run 001 is development regression only.

No new capability claim is attached to this freeze. Fresh evidence begins with Run 002, whose private task rules and targets are created only after this identity is final.

Any code change after this record requires a new freeze and a newly created private challenge.
