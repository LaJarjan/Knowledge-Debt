# Versioned code handoff guides

`brief` is the reading-first entry point introduced in v0.2.0. Existing scan,
explain and drill commands remain available. Generating or reading a guide never
records an answer, a completed check or a mastery score.

## Commands

```bash
kdebt brief --base HEAD
kdebt brief src/cache --base HEAD --lang zh
kdebt brief --base HEAD~2 --head HEAD --json
```

- `--base` defaults to HEAD and must resolve to an available commit. An unborn
  repository needs an initial commit; missing shallow-clone history is an error.
- Without `--head`, the target includes staged, unstaged and non-ignored untracked
  Python source in the configured responsibility scope.
- With `--head`, both inputs are immutable commit objects. No checkout is performed.
- A positional path narrows configured scope, relative to the repository root.
  `--repo` goes before `brief`, as with the other commands.
- `--lang en|zh` localizes the page chrome and maintenance guidance. Source facts,
  analyzer caveats and drill questions keep their literal English text.
- `--json` returns schema 2 artifact paths, snapshot ID, summary and warnings.

The output consists of standalone `index.html`, `guide.md` and `brief.json` files.
No browser is automatically opened. HTML uses embedded CSS, native disclosure
controls and anchors. It contains no JavaScript, remote fonts or CDN dependencies.

## Read a guide

The overview shows changed Python files, supported current behaviors, and behavior
fingerprints that changed since the last guide. Cards distinguish:

1. Source facts, with locations and captured expressions.
2. General maintenance guidance, not inferred business intent.
3. Unknowns that require more context.
4. Optional questions and existing self-report states.

Before/after facts compare against the specified baseline. A separate disclosure
shows previous-guide facts when that guide needs review. These are two different
comparisons; changing the baseline does not erase the history of the target.

The local evidence map groups facts visually. **It is not a call graph or execution
trace.** The same three bounded recognizers as scan are used. Unsupported Python
changes remain visible in the file list without invented explanations. Non-Python
files are outside this analysis scope.

## Source and history binding

Briefs capture sources before analysis. For working trees they re-read the scope
and check HEAD before publishing, rejecting detected concurrent edits. There is
no filesystem transaction or lock: an artifact represents captured source, not a
promise that a mutable checkout still matches it after generation.

Each guide has a content snapshot hash; cards retain analyzer function/dependency
fingerprints. Comments can change the snapshot hash without invalidating a card.
Same-file dependency tracking is conservative. Cross-file dependency changes,
runtime monkey-patching and arbitrary aliases are not resolved.

History is local per normalized scope and target mode (working tree or commit).
Changing language uses the same history. Switching commit targets compares the
new target with the previous committed-target guide in that scope.

| Status since previous guide | Meaning |
| --- | --- |
| first | No prior guide in this scope/mode |
| new | A supported behavior was not present in the previous guide |
| unchanged | Its analyzer fingerprint remains the same |
| needs_review | The relevant fingerprint changed |
| unverified | Source failed to read or parse; old source is retained and labelled |
| restored | An unverified card is analyzable again |
| removed | A prior behavior is absent and its file did not fail analysis |

An unreadable file is never treated as a confirmed removal. Omitted/unsupported
code is never counted as understood. Reading a guide is not tracked as learning.

## Local storage

```text
.kdebt/briefs/<scope-and-mode-id>/
  latest.json
  <generation-id>/
    index.html
    guide.md
    brief.json
```

Generations are written to unique directories. After all artifacts exist, the
latest pointer is replaced atomically. An interrupted generation leaves the prior
pointer intact but may leave an orphan directory. Concurrent generators may both
complete and the last pointer replacement wins. History is not an automatic
filesystem watcher or encrypted archive. It is never uploaded by the CLI.

The source snapshot has a 20 MB aggregate limit, each source file a 1 MB limit,
and a guide supports at most 200 current behavior cards. Narrow the path for larger
repositories. Snippets are bounded; fact expressions remain available in source
disclosures. Git commands retain the existing 30-second timeout.

The output includes source code. Review it before sharing. Files under `.kdebt/`
are Git-ignored; do not force-add them. Only synthetic sample artifacts belong in
this project's public `docs/demo/` directory.

## Deliberately deferred

This release implements the local facts edition, not an LLM provider or automatic
claim verifier. Rich model explanations, full execution diagrams, host-level Agent
evaluation and real-maintainer usefulness studies are still future work. The HTML
renderer cannot turn limited AST facts into proof of runtime behavior.
