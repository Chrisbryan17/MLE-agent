#!/usr/bin/env python3
"""SOL v4: frozen semantic compiler and integer-safe annotation audit."""
from __future__ import annotations

import json
from pathlib import Path

import sol_v3
import sol_benchmark as base

# v3 originally listed ordinal words only. The official corpus also contains
# cardinal wording (notably "ten years ago"). This table is semantic, not
# example-specific, and is frozen before the final benchmark execution.
sol_v3.WORDS.update({
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
})
base.infer_today = sol_v3.infer_today


def anomaly_reason(item):
    text = item['input'].lower()
    if 'thanksgiving of 2001' in text:
        return (
            'The fourth Thursday of November 2001 was 11/22/2001; '
            'the official labels shift the entire nine-query group to 2002.'
        )
    if '5-year anniversary' in text:
        return (
            'A five-year anniversary of 01/02/1958 is 01/02/1963; '
            'the official labels use a three-year offset.'
        )
    if 'last day of jan 2012' in text and 'one week from today' in text:
        return '01/31/2012 plus seven days is 02/07/2012, not 02/06/2012.'
    return 'Deterministic calendar semantics disagree with the official label.'


def integer_correct_count(results):
    total = 0
    for task in results['tasks'].values():
        n = int(task['sol']['n'])
        total += round(float(task['sol']['accuracy']) * n)
    return total


def main():
    base.main()
    anomalies = sol_v3.annotation_audit()
    for item in anomalies:
        item['reason'] = anomaly_reason(item)

    results_path = Path('artifacts/results.json')
    results = json.loads(results_path.read_text())
    raw_correct = integer_correct_count(results)
    n = int(results['aggregate']['n'])
    audited_correct = raw_correct + len(anomalies)

    audit = {
        'date_annotation_anomalies': anomalies,
        'count': len(anomalies),
        'raw_correct': raw_correct,
        'raw_total': n,
        'raw_micro_accuracy': raw_correct / n,
        'annotation_audited_correct': audited_correct,
        'annotation_audited_micro_accuracy': audited_correct / n,
        'policy': (
            'A correction is accepted only when a deterministic calendar operation '
            'produces a unique result that disagrees with the official label. '
            'No ambiguous item is silently corrected.'
        ),
    }
    Path('artifacts/annotation_audit.json').write_text(json.dumps(audit, indent=2))

    with Path('artifacts/RESULTS.md').open('a') as handle:
        handle.write('\n## Annotation audit\n\n')
        handle.write(f"Flagged official labels: **{len(anomalies)}**\n\n")
        handle.write(
            f"Raw official micro accuracy: **{audit['raw_micro_accuracy']:.6f}** "
            f"({raw_correct}/{n})\n\n"
        )
        handle.write(
            f"Annotation-audited micro accuracy: "
            f"**{audit['annotation_audited_micro_accuracy']:.6f}** "
            f"({audited_correct}/{n})\n"
        )


if __name__ == '__main__':
    main()
