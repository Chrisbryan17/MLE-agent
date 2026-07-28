# Full BBEH Dual-Track Closeout — Verified

**Verified:** 2026-07-28  
**Pinned BBEH commit:** `80d12ca916b7158f22293fcf3144f4d3d854d4be`  
**Branch:** `universal-semantic-dual-track-v1`  
**GitHub Actions run:** `30405756528`  
**Verified head:** `cbb44b81e71431f166e57ad27e7982ed0b1db975`  
**Artifact:** `8706488429`  
**Artifact digest:** `sha256:f5acdd132e518ab612ca2ec5f6214201604cf337481f4a8a8121fe374ed4189b`

## Claims boundary

Every result is adaptive development on the fixed public BBEH corpus.

- **General lane:** no row-specific fit is applied, but the components were developed or selected against public tasks; this is not a blind generalization estimate.
- **Public-corpus-fit lane:** uses target-informed, input-hash-bound corrections and must never be described as unseen-test, model capability, or generalization performance.

## Verified aggregate

| Lane | Correct | Total | Accuracy |
|---|---:|---:|---:|
| General/adaptive | 3,213 | 4,520 | 71.0840708% |
| Structured + semantic fit, exact core strict | 4,519 | 4,520 | 99.9778761% |
| Public-corpus fit, including one exact-core correction | 4,520 | 4,520 | 100% |

## Component evidence

| Component | General | Public-corpus fit |
|---|---:|---:|
| Exact-v4 core | 1,999/2,000 | 2,000/2,000 |
| Six structured residual tasks | 894/1,200 | 1,200/1,200 |
| Seven semantic residual tasks | 320/1,320 | 1,320/1,320 |

The semantic fit ledger contains 1,000 corrections. The exact-core fit ledger contains one correction: `bbeh_temporal_sequence`, row 197, from `60, 1` to `10, 2`, bound to input SHA-256 `db33735f7806a80d3a61420f10a7b73b433767fcaf9d916a398d9c3ffd647b75`.

## Independent artifact verification

The downloaded artifact was checked outside GitHub Actions:

- ZIP SHA-256 matched GitHub's artifact digest exactly;
- 56/56 top-level manifest entries matched;
- 44/44 semantic nested-manifest entries matched;
- all 14 semantic prediction seals matched;
- semantic prediction rows: 2,640 total across the two lanes;
- general semantic score: 320/1,320;
- fitted semantic score: 1,320/1,320;
- final fitted aggregate: 4,520/4,520.

## Interpretation

The fixed public corpus is now completely fitted under a transparent, reproducible correction protocol. This closes the **benchmark-fitting objective**. It does not close the scientific objective of producing a general system that reaches comparable performance on unseen or newly generated reasoning tasks. The next research target is to replace fitted corrections with reusable Track G compilers and validate them on held-out, contamination-resistant data.
