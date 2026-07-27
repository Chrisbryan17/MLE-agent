# Resume Instructions

Start from `STATE.md` and `SCOREBOARD.json`.

Do not continue from chat memory. Verify the current branch and Actions artifacts first.

The next implementation target is BoardgameQA. Use test-driven development and preserve a strict protocol:

- write a failing grammar/derivation test;
- confirm it fails for the intended reason;
- implement one grammar or inference family;
- rerun all tests;
- audit all 200 inputs without reading targets;
- generate predictions without targets;
- seal prediction bytes with SHA-256;
- score once;
- preserve the first score;
- version any target-informed repair separately.

Do not claim the historical 1,200/1,200 six-task result as repository-reproducible until BoardgameQA and Geometric Shapes sources are committed and the combined workflow succeeds.
