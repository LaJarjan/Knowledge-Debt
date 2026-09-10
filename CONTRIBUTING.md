# Contributing

Start with a reproducible example: source snippet, expected source fact, and why
the resulting question matters to someone maintaining that code.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests create disposable Git repositories and do not contact a model service.
Keep new runtime dependencies justified; the alpha uses only the standard library.

Recognizer changes should include a meaningful positive case, a misleading or
unsupported case, and a version-invalidation test if evidence behavior changes.
Do not use keyword presence in an answer as proof of understanding. Every source
fact must have a location and a stated boundary where runtime inference is absent.

Keep private source, credentials and `.kdebt/` databases out of issues and pull
requests. Product proposals should explain the user moment they help, not just
the metric they add.
