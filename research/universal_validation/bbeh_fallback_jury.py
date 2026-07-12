#!/usr/bin/env python3
from __future__ import annotations

import bbeh_jury_recovery as base

base.SHARDS['fallback'] = {
    'model': 'openai/o3',
    'tasks': (
        'bbeh_hyperbaton',
        'bbeh_multistep_arithmetic',
        'bbeh_object_counting',
        'bbeh_shuffled_objects',
        'bbeh_web_of_lies',
        'bbeh_word_sorting',
    ),
}

base.INSTRUCTIONS.update({
    'bbeh_hyperbaton': (
        'Infer the adjective-order system from the demonstrations and choose the option that obeys '
        'the induced ordering. Return exactly the requested option or letter.'
    ),
    'bbeh_multistep_arithmetic': (
        'Infer every custom operator definition, including conditions and helper functions, then '
        'evaluate the nested expression exactly. Return only the requested final answer.'
    ),
    'bbeh_object_counting': (
        'Track quantities and ownership precisely. Identify the requested semantic categories and '
        'apply the requested sum, difference, or comparison exactly.'
    ),
    'bbeh_shuffled_objects': (
        'Compile all named actions and swaps, including repeated actions and no-ops, execute them in '
        'order, and return the exact requested option.'
    ),
    'bbeh_web_of_lies': (
        'Translate every truth/lie statement into Boolean constraints, solve all consistent worlds, '
        'and answer each queried person as yes, no, or unknown exactly as requested.'
    ),
    'bbeh_word_sorting': (
        'For direct tasks, apply the custom alphabet exactly. For trace-audit tasks, recompute the '
        'sorting process and identify the first incorrect thought, or No if every thought is valid.'
    ),
})

if __name__ == '__main__':
    base.main()
