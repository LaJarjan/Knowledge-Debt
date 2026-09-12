# Agent integration

The source Skill is [`skills/knowledge-debt/SKILL.md`](../skills/knowledge-debt/SKILL.md).
Install the CLI first, then add that skill directory using your Agent host's skill
installation mechanism. Hosts differ; this repository does not automatically edit
your Agent configuration or claim a universal slash command. You can also ask your
assistant to read that file and follow the workflow for the current repository.

Example request: “Use Knowledge Debt to ask me one question about my current changes.”

## Read a question

```bash
kdebt drill --since HEAD --json
```

Returns `schema_version: 2`, a `drill` object (or null) and warnings. The object
contains `id`, `fingerprint`, `path`, `symbol`, `question`, `facts`, `caveat`, priority
and evidence state. Ask the question before displaying the checklist. Point to the
source location. Translating the question is fine; inventing new required facts is not.

Use `kdebt scan --json` to see all candidates; JSON is not truncated by the terminal
display limit. `--since HEAD` includes staged, unstaged and untracked Python files.
Without a baseline, the tool scans the configured scope.

## Record a literal user answer

After showing the fact checklist and receiving the user's explicit self-check:

```bash
kdebt drill --id CONCEPT_ID --fingerprint FINGERPRINT --answer "USER ANSWER" --covered f1 --json
```

Repeat `--covered` for multiple fact IDs. Omit it to record an unassessed answer.
IDs and fingerprint must come from the displayed question; stale submissions fail.
Use structured subprocess argument arrays or correct shell quoting when passing
answers. Do not interpolate untrusted answers into shell code.

The result identifies `user_self_report` provenance and `automatically_graded: false`.
`partial` means only part of the checklist was checked; `self_checked` requires
all listed facts. Neither proves reasoning or mastery. Old answers are retained,
but the new analyzer fingerprint invalidates surviving v0.1.0 concept records.
Do not turn that into an automated grade. If the user asks for an explanation,
provide one, but do not save your explanation as their answer. Only the user may
confirm which facts their original answer covered.

## Errors and privacy

`kdebt drill PATH --show-facts` displays the source checklist without recording
evidence. Use it when the user wants to read the facts instead of answering.

- Exit 0: successful operation, including no supported candidates.
- Exit 2: invalid arguments, Git/config/state error or rejected evidence binding.
- Exit 130: interactive cancellation.

Application errors with `--json` return an error object. Argument-parser errors
use argparse's stderr output. Per-file analysis failures appear in `warnings`.
Do not silently replace invalid baselines or pretend skipped files were covered.

CLI JSON includes source expressions. Reading it into a hosted Agent sends that
context through the Agent's own data handling. The CLI itself is offline. Answers
are Git-ignored in the local repository and are not encrypted.
