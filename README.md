# Knowledge Debt

**AI finished the code. Get a guide you can take responsibility with.**

Knowledge Debt turns a Python code change into a local handoff guide: source-linked
behaviors, maintenance considerations, before/after facts, and questions that still
need an answer. Generate it again to see which explanations need rechecking.

## New in v0.2: a code handoff you can read

```bash
kdebt brief --base HEAD                   # working tree vs HEAD
kdebt brief src/cache --base HEAD --lang zh
kdebt brief --base HEAD~2 --head HEAD      # two committed snapshots
```

Open the printed HTML path. Each run also writes Markdown and a structured
manifest, privately inside `.kdebt/briefs/`. No account, model API, web server,
or repository code execution. This is a **local facts edition**: maintenance
advice is labelled as general guidance, not a verified explanation of author intent.

![Code handoff guide — synthetic example](docs/demo/preview.png)

[Example HTML source](docs/demo/index.html) · [Example Markdown](docs/demo/guide.md) · [Guide usage and limits](docs/brief.md)

The example is generated from synthetic code. Download/open the HTML locally to
use the source disclosures; GitHub's file view shows source.

Subsequent runs distinguish unchanged explanations, new behaviors, behaviors
needing review, removals, and source that could not be revalidated. Reading does
not count as mastery. Optional understanding checks remain available:

[中文说明](README.zh-CN.md) · [Design](docs/design.md) · [Agent integration](docs/agent-integration.md) · [Roadmap](docs/roadmap.md)

```text
$ kdebt scan examples

Knowledge Debt / Knowledge-Debt

Analyzed: 1 Python files; 3 supported instances
Complete fact self-checks: 0 / 3
Partial fact self-checks: 0
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

In fetch_batch, where is this semaphore constructed and what
initial value is supplied? Identify matching with/acquire/release
syntax in this function's direct body. What remains unknown
about uses outside that body?
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
kdebt drill src/worker.py --show-facts  # read the checklist; record nothing
```

`kdebt` with no command is `kdebt scan`. Use `kdebt --repo /path/to/repo scan`
from another directory. Scope and file arguments are relative to the repository
root, even when invoked from a subdirectory. Repeat `--scope` for multiple areas.

## Understanding checks retained from v0.1.1

- Reads Python files known to Git plus non-ignored untracked Python files.
- Recognizes three bounded **syntax candidates**: imported asyncio/threading
  semaphore construction, counted retry-shaped loops, and cleanup calls in `finally`.
- Resolves common import aliases, abstains on shadowed/custom semaphore names,
  and requires a known delay inside a retry handler plus a try-body exit.
- Links every checklist fact to a source location and expression.
- Compares supported instances against a Git baseline with `--since`.
- Asks one code-specific question. You answer **before** seeing the fact checklist.
- Saves your answer and explicitly self-checked facts in local SQLite.
- Marks a record stale when its function, transitively referenced same-file
  definitions, or enclosing class/declaration context changes. Comments and
  formatting alone do not invalidate it.
- Provides JSON contracts for Agent Skills and future editor integrations.

### A self-check, not an automated grade

After answering, you see a few literal source facts and the limits of what they
establish. You choose which facts your original answer covered. A count such as
`2/4 self-checked source facts` is **your self-report**. Causal reasoning, runtime
behavior, and long-term retention remain unverified.

No lexical keyword matching pretends to understand your answer. An explanation
written by an agent must not be saved as your own evidence.

| State | Meaning |
| --- | --- |
| `unrecorded` | No answer here; your understanding is unknown |
| `answer_recorded` | An answer exists without an explicit fact self-check |
| `partial` | You checked some, but not all, facts for this fingerprint |
| `self_checked` | You checked every listed source fact; this is not proof of mastery |
| `stale` | The source fingerprint changed after the latest answer |

### How candidates are ordered

| Priority | Rule |
| --- | --- |
| HIGH | A recorded answer is stale, or a concept changed/was added relative to `--since` without a complete current fact self-check |
| MEDIUM | The checklist is incomplete and no explicit baseline change elevates it |
| LOW | All listed facts have a current self-check |

Ties prioritize never-recorded instances, then the oldest latest answer, then path,
line and kind. Repeated drills rotate as you record answers. These are deterministic
review priorities, not calibrated risk probabilities. Partial answers are not
silently combined into a complete self-check; the latest answer defines the state.

## Boundaries

This is an **alpha with deliberately narrow recognition**, not a complete Python
semantic analyzer. It resolves a bounded set of lexical imports, not runtime object
identity or monkey-patching. It does not build a complete call graph, detect all
retries, prove cleanup, or infer why an author chose a limit. Unknown/custom
semaphore names are skipped. Some genuine retries are deliberately not recognized.

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

`scan` and `explain` do not create state. `init`, recording a drill, or generating a
brief creates local state (a brief does not create an evidence database):

```text
.kdebt/
  .gitignore         # ignores everything in this directory
  config.json        # optional responsibility scopes
  evidence.sqlite3   # answers, checked fact IDs, timestamps, code fingerprints
  briefs/            # versioned guides and latest-generation pointers
```

This directory is Git-ignored, **not encrypted**. Do not force-add it or include it
in public archives. The CLI makes no network requests. If an external Agent reads
CLI JSON, that Agent's own data handling applies; JSON includes source expressions.
Generated briefs also contain source snippets; review them before sharing. Only
the synthetic files under `docs/demo/` are intentionally public examples.

## Agent workflow

v0.1.1 emits JSON `schema_version: 2` with a new `partial` state. Existing local
databases remain readable and answers are preserved. The analyzer fingerprint
version changed: surviving v0.1.0 instances require a new check rather than
silently applying old fact IDs to the expanded checklist.

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
The suite includes a 24-case synthetic recognition corpus and interactive drill
regressions. See [validation and benchmarking](docs/validation.md) for limits and
the remaining real-user evaluation work.

MIT licensed. Built around one question: **can you confidently take responsibility
for the code you just changed?**
