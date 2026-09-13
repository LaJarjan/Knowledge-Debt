# Roadmap

## v0.2.0 — Reading-first handoff guides

- [x] `brief` for Git baseline → working tree or explicit commit target.
- [x] Standalone HTML, Markdown, source facts and before/after disclosures.
- [x] Private versioned guides with recheck and unverified states.
- [x] English/Chinese presentation and a synthetic public example.
- [ ] Optional model explanations with explicit claim provenance.
- [ ] Real-maintainer comparison against a one-off AI summary.

## v0.1.1 — Existing understanding checks

- [x] Four commands: init, scan, explain, drill.
- [x] Git baseline → working-tree concept comparison.
- [x] Three bounded Python syntax candidate families.
- [x] Source-linked questions and explicit self-check records.
- [x] Function/context fingerprint invalidation.
- [x] JSON interface and portable Agent Skill source.
- [x] English and Chinese onboarding, automated test suite and CI configuration.
- [x] Same-file dependency and class-header fingerprint invalidation.
- [x] Common import aliases, shadowing abstention and narrower retry recognition.
- [x] Partial/complete self-check states, drill rotation and facts-only viewing.
- [x] 24-case synthetic corpus, interactive regressions and scale benchmark script.
- [x] One evidence read per scan and unchanged-file filtering for baseline scans.

## Validate before adding integrations

Recruit 8–12 maintainers using their own Python repositories. For each session,
record whether top candidates were worth checking, whether any factual statement
was misleading, whether the drill surfaced an overlooked behavior, and whether
the maintainer voluntarily uses it on the next change. An initial working target
is at least 3 useful recommendations in a top-5 list, not an industry benchmark.

Keep private answers local. Collect only volunteered, redacted product feedback.
Do not claim learning gains from a higher score on a question whose answer was
just shown; test transfer with a different behavior-prediction question later.

## Next, driven by observed failures

- Expand lexical resolution only with new counterexamples and clear boundaries.
- Cover context-manager cleanup and more realistic retry control flow.
- Improve identity under moves and repeated same-kind instances.
- Track relevant cross-file dependencies, with conservative invalidation.
- Offer evidence history/export locally and evaluate the current drill rotation.
- Consider optional claim matching with source citations, abstention and a
  measured evaluation set. Keep machine assessments distinct from self-reports.

## Distribution after repeat use

Choose between a deeper Agent integration and an IDE side panel based on where
users return. Reuse the core engine. Add a PR view for public change questions only
if users want it; personal answers and scores remain private by default.

No calendar promises for IDE, MCP, agent-history ingestion, hosted dashboards or
automated grading. Useful questions come first.
