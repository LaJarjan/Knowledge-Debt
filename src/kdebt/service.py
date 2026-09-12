"""Deterministic ranking and reports, independent of terminal presentation."""

from .analyzer import extract
from .repository import RepoError
from .store import Store


def scan(repo, since=None, path=None):
    scopes = repo.config()["scopes"]
    if path:
        requested = repo.normalize_path(path)
        normalized = [repo.normalize_path(s) for s in scopes]
        if not any(s == "." or requested == s or requested.startswith(s + "/") for s in normalized):
            raise RepoError("Requested path is outside your configured responsibility scope")
        scopes = [requested]
    baseline = repo.revision(since) if since else None
    store = Store(repo.root)
    records = store.latest_all()
    items, warnings, removed = [], [], []
    analyzed = 0
    files = repo.files(scopes)
    # Include deleted tracked files when calculating a baseline diff.
    if baseline:
        old_files = repo.git("ls-tree", "-r", "--name-only", "-z", baseline).split("\0")
        normalized = [repo.normalize_path(s) for s in scopes]
        files = sorted(set(files) | {p for p in old_files if p.endswith(".py")
                       and any(s == "." or p == s or p.startswith(s + "/") for s in normalized)
                       and not any(part in p.split("/") for part in (".venv", "venv", ".kdebt", "node_modules"))})
        touched = repo.changed_files(baseline)
        files = [file for file in files if file in touched]
    for file in files:
        try:
            source = repo.read(file) if (repo.root / file).exists() else None
            current = extract(source, file) if source is not None else []
            previous = []
            if baseline:
                old = repo.at_revision(baseline, file)
                previous = extract(old, file) if old is not None else []
            analyzed += source is not None
            old_map = {c.id: c for c in previous}
            current_map = {c.id: c for c in current}
            for old_concept in previous:
                if old_concept.id not in current_map:
                    removed.append(old_concept.to_dict())
            for concept in current:
                prior = old_map.get(concept.id)
                change = ("added" if prior is None else "changed" if prior.fingerprint != concept.fingerprint
                          else "unchanged") if baseline else "not_compared"
                if baseline and change == "unchanged":
                    continue
                record = records.get(concept.id)
                state = store.state_from_record(concept, record)
                reasons = []
                if change in ("added", "changed"):
                    reasons.append(f"Supported concept {change} relative to {since}.")
                if state == "stale":
                    reasons.append("Code fingerprint changed since your last recorded answer.")
                elif state == "unrecorded":
                    reasons.append("No answer recorded here; your understanding is unknown.")
                elif state == "answer_recorded":
                    reasons.append("An answer exists, without a self-check against the source facts.")
                elif state == "partial":
                    reasons.append("Only part of the source checklist was self-checked; this is still worth reviewing.")
                else:
                    reasons.append("You self-checked all source facts for this fingerprint; reasoning remains unverified.")
                priority = ("HIGH" if state == "stale" or (change in ("added", "changed") and state != "self_checked")
                            else "LOW" if state == "self_checked" else "MEDIUM")
                item = concept.to_dict()
                item.update(state=state, priority=priority, reasons=reasons, change=change,
                            last_recorded_id=record["id"] if record else None)
                items.append(item)
        except (SyntaxError, UnicodeError, OSError, RepoError) as exc:
            warnings.append({"path": file, "reason": str(exc)})
    items.sort(key=lambda c: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[c["priority"]],
                             c["last_recorded_id"] or 0, c["path"], c["line"], c["kind"]))
    states = {state: sum(c["state"] == state for c in items)
              for state in ("unrecorded", "answer_recorded", "partial", "self_checked", "stale")}
    return {"schema_version": 2, "repository": repo.root.name, "head": repo.head(),
            "baseline": baseline, "scopes": scopes, "analyzed_files": analyzed,
            "candidate_files": len(files), "supported_instances": len(items),
            "states": states, "concepts": items, "removed": removed, "warnings": warnings,
            "measurement": "Check priority and version-bound self-reports, not a probability of understanding.",
            "comparison": "baseline to working tree (including staged, unstaged and untracked source)" if baseline else None}


def concept_from_dict(item):
    from .models import Concept, Fact
    return Concept(**{key: item[key] for key in Concept.__dataclass_fields__ if key != "facts"},
                   facts=tuple(Fact(**fact) for fact in item["facts"]))
