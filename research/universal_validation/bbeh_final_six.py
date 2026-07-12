#!/usr/bin/env python3
from __future__ import annotations

import bbeh_guaranteed_jury as base

base.SHARDS['finalsix'] = {
    'model': 'openai/gpt-4o-mini',
    'tasks': (
        'bbeh_boardgame_qa',
        'bbeh_buggy_tables',
        'bbeh_time_arithmetic',
        'bbeh_zebra_puzzles',
        'bbeh_geometric_shapes',
        'bbeh_linguini',
    ),
}

if __name__ == '__main__':
    base.main()
