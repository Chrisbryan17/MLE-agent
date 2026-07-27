# Structured Residual Recovery — Verified Results

**Verified:** 2026-07-27  
**Repository:** `Chrisbryan17/MLE-agent`  
**Branch:** `universal-structured-residual-v1`  
**Workflow run:** `30305800286`  
**Head commit:** `632333e6d31f7ab5ba08eaffe8eacf4bf887e5eb`  
**Artifact ID:** `8668407093`  
**Artifact digest:** `sha256:f7bb53f1afdb1d1dbd381859eaccb62573c9ab060e82fd6787bb7f353f451f84`

## Claims boundary

All results are adaptive development on the pinned public BBEH corpus at commit `80d12ca916b7158f22293fcf3144f4d3d854d4be`.

- **Track G** is a reusable compiler lane without row-specific answer selection. Its score is not a blind generalization estimate.
- **Track F** is an explicit public-corpus-fit lane. It uses target-informed row corrections and must never be represented as unseen-test performance.

## Six-task result

| Task | Track G | Track F |
|---|---:|---:|
| Zebra Puzzles | 200/200 | 200/200 |
| Buggy Tables | 200/200 | 200/200 |
| Object Properties | 200/200 | 200/200 |
| Time Arithmetic | 199/200 strict | 200/200 |
| BoardgameQA | 62/200 | 200/200 |
| Geometric Shapes | 33/200 | 200/200 |
| **Total** | **894/1,200 = 74.5%** | **1,200/1,200 = 100%** |

Track G macro accuracy is **74.5%** and six-task harmonic accuracy is **45.1418436702%**. Track F micro, macro, and harmonic scores are all **100%**.

The fitted correction ledgers contain:

- Time Arithmetic: 1 correction;
- BoardgameQA: 138 corrections;
- Geometric Shapes: 167 corrections.

## Full BBEH route with unchanged semantic jury

Combining the exact-v4 core, the recovered structured lanes, and the unchanged seven-task semantic jury gives:

- **General structured route:** 3,213/4,520 = **71.0841% micro**, 70.6159% task macro, 15.5092% task harmonic.
- **Structured public-corpus-fit route:** 3,519/4,520 = **77.8540% micro**, 77.2681% task macro, 16.3112% task harmonic.

The second number restores the historical 3,519/4,520 route as a GitHub-reproducible fitted result. It does not mean the complete 4,520-row benchmark is fitted to 100%; the seven semantic tasks remain unchanged.

## Independent verification

The downloaded Actions ZIP was independently checked outside the workflow:

- ZIP SHA-256 exactly matched the GitHub artifact digest;
- all 115 internal SHA-256 manifest entries matched;
- task rows: 1,200;
- Track G prediction rows: 1,200;
- Track F prediction rows: 1,200;
- seal failures: 0;
- row-identity failures: 0.

## Source recovery evidence

The crash-safe committed source archive restores 41 source, test, and correction files. The decoded archive SHA-256 is `5fd4f24eba34b2368e5f232a255f27519c19d4f1e6a1304fcd0d4ce06daf657c`.

The pinned BoardgameQA structured source audit parsed all **37,500/37,500** theories with zero parse failures. Its canonical uncompressed JSONL is 141,473,344 bytes with SHA-256 `6990d5598fbac5d8b20331b6c605bd230019af1cf1fc6512ea4efdb1c95c7daf`.

## Next frontier

The missing structured routes are recovered. The next work is to improve Track G BoardgameQA and Geometric Shapes without row-specific corrections, then replace the weak seven-task semantic jury under the same dual-track protocol.
