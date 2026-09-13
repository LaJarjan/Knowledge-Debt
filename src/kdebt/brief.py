"""Versioned code handoff guides. Generating a guide never records understanding."""

import json
import os
import uuid
from datetime import datetime, timezone

from .analyzer import extract, digest
from .repository import RepoError
from .snapshot import capture, selected_scopes, snapshot_id
from .store import Store

FORMAT_VERSION = 1


def analyze(snapshot):
    cards, warnings = {}, list(snapshot["warnings"])
    for path, source in snapshot["sources"].items():
        try:
            for concept in extract(source, path):
                item = concept.to_dict()
                # Embed a bounded, line-numbered source slice from this snapshot.
                start = max(1, concept.line - 2)
                end = min(len(source.splitlines()), max(concept.end_line + 2, concept.line + 8), start + 100)
                item["snippet"] = {"start": start, "text": "\n".join(source.splitlines()[start - 1:end]),
                                   "truncated": concept.end_line > end}
                item["verified"] = True
                cards[concept.id] = item
        except (SyntaxError, ValueError, RecursionError) as exc:
            warnings.append({"path": path, "reason": str(exc)})
    return cards, warnings


def safe_directory(root, parts):
    directory = root
    for part in parts:
        directory = directory / part
        if directory.is_symlink():
            raise RepoError("Brief storage must not contain symbolic links")
        directory.mkdir(exist_ok=True)
    return directory


def read_previous(directory):
    pointer = directory / "latest.json"
    if pointer.is_symlink():
        raise RepoError("Brief pointer must not be a symbolic link")
    if not pointer.exists():
        return None
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
        name = data["generation"]
        if not isinstance(name, str) or len(name) != 32 or any(c not in "0123456789abcdef" for c in name):
            raise ValueError("Invalid generation")
        folder = directory / name
        manifest = folder / "brief.json"
        if folder.is_symlink() or manifest.is_symlink():
            raise ValueError("Symlinked manifest")
        result = json.loads(manifest.read_text(encoding="utf-8"))
        if result["brief_format"] != FORMAT_VERSION or not isinstance(result["cards"], list) or not isinstance(result["snapshot"], str):
            raise ValueError("Unsupported brief format")
        for card in result["cards"]:
            if (not isinstance(card["id"], str) or len(card["id"]) != 24
                    or any(c not in "0123456789abcdef" for c in card["id"])
                    or card["kind"] not in ("concurrency", "retry", "cleanup")
                    or not isinstance(card["fingerprint"], str)
                    or not all(isinstance(card[k], str) for k in ("path", "symbol", "question", "caveat"))
                    or not isinstance(card["snippet"]["start"], int)
                    or not isinstance(card["snippet"]["text"], str)
                    or not isinstance(card["line"], int)):
                raise ValueError("Invalid card")
            for fact in card["facts"]:
                if (not isinstance(fact["id"], str) or not fact["id"].startswith("f")
                        or not fact["id"][1:].isdigit() or not isinstance(fact["line"], int)
                        or not all(isinstance(fact[k], str) for k in ("text", "source"))):
                    raise ValueError("Invalid source fact")
        # Carry forward only the source contract, never old presentation fields.
        keys = ("id", "path", "symbol", "kind", "line", "end_line", "fingerprint", "question", "facts", "caveat", "snippet", "verified")
        result["cards"] = [{key: card[key] for key in keys if key in card} for card in result["cards"]]
        return result
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RepoError("Cannot read previous brief. Back up .kdebt/briefs before recovery; history was not replaced.") from exc


def build(repo, base="HEAD", head=None, path=None, lang="en"):
    from .brief_render import render_html, render_markdown

    if lang not in ("en", "zh"):
        raise RepoError("Brief language must be en or zh")
    scopes = selected_scopes(repo, path)
    baseline = repo.revision(base)
    target = repo.revision(head) if head else None
    working_head = repo.head()
    try:
        before = capture(repo, scopes, baseline)
        after = capture(repo, scopes, target)
    except OverflowError as exc:
        raise RepoError(str(exc)) from exc
    old_cards, old_warnings = analyze(before)
    current, warnings = analyze(after)
    if len(current) > 200:
        raise RepoError("More than 200 supported behaviors; select a narrower path for a readable brief")
    failed_now = {w["path"] for w in warnings}
    failed_before = {w["path"] for w in old_warnings}

    # No database initialization or answer writes. Read existing self-reports only.
    records = Store(repo.root).latest_all()
    family = digest(json.dumps({"scopes": scopes, "mode": "commit" if target else "working-tree"}, sort_keys=True))
    # Defer creation until inputs have been parsed. Histories are local per scope
    # and target mode; changing the baseline does not erase the previous target.
    state_root = repo.root / ".kdebt"
    if state_root.is_symlink():
        raise RepoError("Knowledge Debt state must not be symlinked")
    history = state_root / "briefs" / family
    for candidate in (state_root / "briefs", history):
        if candidate.is_symlink():
            raise RepoError("Brief storage must not contain symbolic links")
    previous = read_previous(history) if history.exists() else None
    prior = {c["id"]: c for c in previous["cards"]} if previous else {}

    cards = []
    for key, item in current.items():
        old = old_cards.get(key)
        last = prior.get(key)
        change = ("unknown" if item["path"] in failed_before else "added" if not old else
                  "unchanged" if old["fingerprint"] == item["fingerprint"] else "changed")
        since_guide = ("first" if not previous else "new" if not last else
                       "restored" if not last.get("verified", True) else
                       "unchanged" if last["fingerprint"] == item["fingerprint"] else "needs_review")
        from .service import concept_from_dict
        item.update(change=change, since_guide=since_guide,
                    evidence_state=Store.state_from_record(concept_from_dict(item), records.get(key)),
                    before_facts=old["facts"] if old else [],
                    before_snippet=old["snippet"] if old else None,
                    prior_facts=last["facts"] if last and since_guide in ("needs_review", "restored") else [],
                    prior_snippet=last["snippet"] if last and since_guide in ("needs_review", "restored") else None)
        cards.append(item)
    # Never interpret a parse/read failure as a removed behavior.
    for key, last in prior.items():
        if key not in current and last["path"] in failed_now:
            retained = dict(last)
            retained.update(verified=False, change="unknown", since_guide="unverified", evidence_state="unverified")
            cards.append(retained)
    removed = [dict(c, since_guide="removed", change="removed") for key, c in old_cards.items()
               if key not in current and c["path"] not in failed_now]
    removed_since_guide = [c for key, c in prior.items() if key not in current and c["path"] not in failed_now]
    cards.sort(key=lambda c: (0 if c["since_guide"] in ("needs_review", "unverified") else
                             1 if c["change"] in ("added", "changed") else 2, c["path"], c["line"]))
    files = []
    for filename in sorted(set(before["sources"]) | set(after["sources"]) | failed_now | failed_before):
        a, b = before["sources"].get(filename), after["sources"].get(filename)
        change = ("unknown" if filename in failed_now | failed_before else
                  "added" if a is None else "removed" if b is None else "unchanged" if a == b else "changed")
        if change != "unchanged":
            files.append({"path": filename, "change": change,
                          "supported_cards": sum(c["path"] == filename and c["verified"] for c in cards)})
    report = {"brief_format": FORMAT_VERSION, "generator": "local-source-facts",
              "repository": repo.root.name, "generated_at": datetime.now(timezone.utc).isoformat(),
              "language": lang, "scopes": scopes, "baseline": baseline,
              "target": target or "working-tree", "working_head": working_head,
              "snapshot": snapshot_id(after), "previous_snapshot": previous["snapshot"] if previous else None,
              "cards": cards, "removed": removed, "removed_since_guide": removed_since_guide,
              "files": files, "warnings": warnings,
              "baseline_warnings": old_warnings,
              "summary": {"changed_files": len(files), "current_behaviors": len(current),
                          "changed_behaviors": sum(c["change"] in ("added", "changed") for c in cards),
                          "needs_review": sum(c["since_guide"] == "needs_review" for c in cards),
                          "unverified": sum(c["since_guide"] == "unverified" for c in cards)}}
    html, markdown = render_html(report), render_markdown(report)
    if not target:
        try:
            fresh = capture(repo, scopes)
        except OverflowError as exc:
            raise RepoError("Source changed during generation; rerun brief") from exc
        if fresh != after or repo.head() != working_head or selected_scopes(repo, path) != scopes:
            raise RepoError("Source or scope changed during generation; rerun brief. No guide was published.")

    state_root = safe_directory(repo.root, [".kdebt"])
    ignore = state_root / ".gitignore"
    if ignore.is_symlink():
        raise RepoError("Knowledge Debt ignore file must not be symlinked")
    ignore.write_text("*\n", encoding="utf-8")
    history = safe_directory(repo.root, [".kdebt", "briefs", family])
    generation = uuid.uuid4().hex
    destination = history / generation
    destination.mkdir()  # unique, never overwrite another guide
    (destination / "index.html").write_text(html, encoding="utf-8")
    (destination / "guide.md").write_text(markdown, encoding="utf-8")
    (destination / "brief.json").write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    # Publish only a complete generation. An interrupted write leaves the prior
    # pointer intact; orphan generations can be removed manually after backup.
    temporary = history / (generation + ".tmp")
    temporary.write_text(json.dumps({"generation": generation}), encoding="utf-8")
    os.replace(temporary, history / "latest.json")
    return {"schema_version": 2, "summary": report["summary"], "snapshot": report["snapshot"],
            "html": str(destination / "index.html"), "markdown": str(destination / "guide.md"),
            "manifest": str(destination / "brief.json"), "warnings": warnings + old_warnings}
