# Validation and evaluation

## Automated checks

```bash
python -m unittest discover -s tests -v
python scripts/benchmark.py --files 100 500
```

The test suite covers source facts, conservative lexical import resolution,
transitive same-file dependencies, unchanged formatting, class headers, partial
self-checks, old records, corrupted databases, interactive cancellation, changes
while answering, facts-only viewing, answer rotation, Unicode paths, renames,
shallow clones and Git worktrees.

`tests/cases/recognition.json` contains 24 hand-authored **synthetic** positive and
negative examples. These validate recognition boundaries, not production accuracy
or learning outcomes. They are regression fixtures, not an independent benchmark.

## Local performance observation

One run on Windows with Python 3.12.14 produced:

| Synthetic Python files | Full scan | Scan with one stored answer per file | One-file diff |
| --- | --- | --- | --- |
| 100 | 2.069 s | 0.210 s | 0.512 s |
| 500 | 0.896 s | 0.672 s | 0.466 s |

Each file contains one short semaphore example. Each diff scan analyzed one file.
Times exclude repository generation and answer seeding. These are single runs,
with warm caches and concurrent test activity; the 100-file cold run is slower
than the 500-file run. Do not infer scaling laws or a speedup percentage from this
table. Run the script repeatedly on representative repositories before setting
performance targets. The script executes Git only, never the fixture source.

The implementation reduces two concrete costs: one database query per scan instead
of a connection per concept, and source/blob reads only for Git-changed paths in
baseline mode. A regression asserts one baseline blob read when one of eleven
tracked files changes.

## Human evaluation still required

Recruit maintainers of real Python repositories. Ask each to assess a small set
of returned questions without revealing the expected assessment. Record:

1. Is this behavior relevant to the change they are about to maintain?
2. Can the question be answered using the provided context?
3. Does the checklist address the question, with uncertainty stated correctly?
4. Is there another reasonable answer or an essential missing dependency?
5. Does the drill finish in roughly two minutes and reveal anything overlooked?
6. Does the maintainer voluntarily use it on their next change?

An Agent integration also needs host-level testing: explanation-only requests,
refusal/skip, explicit fact confirmation, and attempts to save the Agent's own
answer. CLI tests cannot establish that an arbitrary Agent follows the Skill.
Neither real-user usefulness nor Agent compliance is claimed as validated yet.
