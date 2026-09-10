# Knowledge Debt

**Your codebase changed. Take two minutes to catch up.**

Find a code behavior worth understanding, answer one question, and keep a local,
version-bound record of what you checked.

[中文说明](README.zh-CN.md) · [Design](docs/design.md) · [Agent integration](docs/agent-integration.md) · [Roadmap](docs/roadmap.md)

```text
$ kdebt scan examples

Knowledge Debt / Knowledge-Debt

Analyzed: 1 Python files; 3 supported instances
Current self-checks: 0 / 3
Changed since recorded answer: 0

Check priority (not an understanding score)
1. MEDIUM examples/worker.py:7 / concurrency
   fetch_batch | unrecorded
2. MEDIUM examples/worker.py:17 / retry
   retry_read | unrecorded
3. MEDIUM examples/worker.py:26 / cleanup
   consume | unrecorded

$ kdebt drill examples/worker.py

Two-minute handoff / examples/worker.py:7

In fetch_batch, what value is passed to asyncio.Semaphore,
and where is this object acquired and released? Does this
snippet establish a limit across separate calls to this function?
```

**Authorship is not understanding. Missing evidence is not proof of ignorance.**

Knowledge Debt helps you choose what to inspect. It does not detect AI authorship,
grade intelligence, or claim that you understand 72% of a repository.

## Try it

Requires Python 3.10+ and Git. Install from this repository; there is no assumed
PyPI release. The CLI has **zero third-party runtime dependencies**, makes no model
API calls, and does not execute the source it scans.

```bash
git clone https://github.com/LaJarjan/Knowledge-Debt.git
cd Knowledge-Debt
python -m pip install .
kdebt scan examples
kdebt drill examples/worker.py
```

Or install into an isolated CLI environment with `pipx install .` from the clone.

In your own Python Git repository:

```bash
kdebt init --scope src             # optional: defaults to the whole repository
kdebt scan                        # top 5 supported candidates
kdebt scan --since HEAD            # staged + unstaged + untracked changes
kdebt scan --since HEAD~3          # changes since a historical commit
kdebt explain src/worker.py        # reasons, source facts and limits
kdebt drill src/worker.py          # one question, then a self-check
```

`kdebt` with no command is `kdebt scan`. Use `kdebt --repo /path/to/repo scan`
from another directory. Scope and file arguments are relative to the repository
root, even when invoked from a subdirectory. Repeat `--scope` for multiple areas.

## What v0.1 actually does

- Reads Python files known to Git plus non-ignored untracked Python files.
- Recognizes three bounded **syntax candidates**: semaphore construction,
  retry-shaped loops, and cleanup calls in `finally`.
- Links every checklist fact to a source location and expression.
- Compares supported instances against a Git baseline with `--since`.
- Asks one code-specific question. You answer **before** seeing the fact checklist.
- Saves your answer and explicitly self-checked facts in local SQLite.
- Marks a record stale when its function's normalized syntax or tracked
  declaration context changes. Comments and formatting alone do not invalidate it.
- Provides JSON contracts for Agent Skills and future editor integrations.

### A self-check, not an automated grade

After answering, you see a few literal source facts and the limits of what they
establish. You choose which facts your original answer covered. A count such as
`2/3 self-checked source facts` is **your self-report**. Causal reasoning, runtime
behavior, and long-term retention remain unverified.

No lexical keyword matching pretends to understand your answer. An explanation
written by an agent must not be saved as your own evidence.

| State | Meaning |
| --- | --- |
| `unrecorded` | No answer here; your understanding is unknown |
| `answer_recorded` | An answer exists without an explicit fact self-check |
| `self_checked` | You checked at least one fact against this code fingerprint |
| `stale` | The source fingerprint changed after the latest answer |

### How candidates are ordered

| Priority | Rule |
| --- | --- |
| HIGH | A recorded answer is stale, or a concept changed/was added relative to `--since` without a current self-check |
| MEDIUM | No self-check exists and no explicit baseline change elevates it |
| LOW | At least one fact has a current self-check |

Ties sort by path, line and concept kind. These are deterministic review priorities,
not calibrated risk probabilities. A partial self-check lowering priority is an
explicit v0.1 simplification, not evidence of complete understanding.

## Boundaries

This is an **alpha with deliberately narrow recognition**, not a complete Python
semantic analyzer. It does not resolve arbitrary aliases, build a call graph,
detect all retries, prove cleanup, or infer why an author chose a limit. A method
named `Semaphore` could be a custom callable; candidates say so.

- Unsupported files and concepts do not count as understood.
- `--since` compares a baseline to the working tree, not just committed changes.
  Its counts describe that filtered scope, not your entire repository.
- The fingerprint is function-level and conservative, not a semantic equivalence
  proof. Changing module declarations can invalidate several functions. Cross-file
  dependency changes are not tracked yet.
- Moving or renaming a file/function creates a new instance. Removing or inserting
  same-kind candidates may change ordinal identity. No blame-based knowledge inference.
- Syntax errors, unsupported source encodings, symlinks and oversized source files
  are reported or skipped. Each source has a 1 MB limit; each Git command a 30s timeout.
- A shallow clone can only compare revisions it contains. Supply an available base.
- There is no AI detector, autonomous natural-language grading, telemetry, scheduled
  reminder, IDE extension or hosted service in v0.1.

## Local by default

`scan` and `explain` do not create state. `init` or recording a drill creates:

```text
.kdebt/
  .gitignore         # ignores everything in this directory
  config.json        # optional responsibility scopes
  evidence.sqlite3   # answers, checked fact IDs, timestamps, code fingerprints
```

This directory is Git-ignored, **not encrypted**. Do not force-add it or include it
in public archives. The CLI makes no network requests. If an external Agent reads
CLI JSON, that Agent's own data handling applies; JSON includes source expressions.

## Agent workflow

The repository includes [a portable Skill](skills/knowledge-debt/SKILL.md).
Keep the deterministic engine responsible for facts and storage; use your coding
assistant for the conversation. The Skill is a source artifact, not an automatically
installed integration. See [setup and the JSON contract](docs/agent-integration.md).

```bash
kdebt drill --since HEAD --json
```

## Contribute

The most useful contribution is a real code example where a question is valuable,
misleading, or missing. Include a minimal snippet and expected facts, without
private code. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

CI is configured to run tests on Linux, Windows and macOS with Python 3.10 and 3.13.

MIT licensed. Built around one question: **can you confidently take responsibility
for the code you just changed?**
