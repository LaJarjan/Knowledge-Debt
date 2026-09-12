# Changelog

## 0.1.1

- Invalidate evidence after referenced same-file helpers, class bases or decorators change.
- Resolve common semaphore import aliases and skip unknown, custom or shadowed bindings.
- Restrict retry recognition to counted loops with an exit and known delay in a handler.
- Exclude uncalled nested cleanup bodies and list all recognized cleanup calls.
- Expand semaphore checklists with construction scope and matching direct-body uses.
- Keep partial self-checks pending; rotate tied candidates by latest answer age.
- Add `drill --show-facts` without writing evidence.
- Load latest evidence in one query and skip unchanged files in baseline scans.
- Add regression tests, a 24-case recognition corpus and a repeatable scale benchmark.

Compatibility: JSON schema is now 2 and includes `partial`. Existing SQLite rows
are preserved. A new analyzer fingerprint salt intentionally makes surviving
old records stale; request a fresh drill before recording new coverage. The
`self_checked` state now requires every listed source fact, not merely one fact.

## 0.1.0

Initial local CLI, Git/AST analysis, source-grounded drill, SQLite self-reports,
portable Skill source, documentation and cross-platform CI.
