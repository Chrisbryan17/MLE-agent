# Clean Replication: Pilot 003

Run tests (development-only seeds) from this directory: `python -m unittest discover -s tests -v`.

Stage names and commands are identical to the [Pilot 002 README](README.md), with **a fresh `evidence/pilot-003` directory**. Commit dataset SHA-256 commitments *before* generating queries, commit query SHA-256 *before* releasing the oracle's responses, and commit prediction SHA-256 before scoring.

Do not use the old Pilot 002 holdout as a tuning corpus, and do not claim broader generality based on a synthetic known-operator suite. `CLEAN_REPLICATION.md` defines the new frozen evaluation.
