"""Capture source inputs before analysis, without checking out or executing code."""

import hashlib

from .repository import RepoError

EXCLUDED = {".kdebt", ".venv", "venv", "__pycache__", "node_modules"}
MAX_TOTAL_BYTES = 20_000_000


def in_scope(path, scopes):
    return (path.endswith(".py") and not EXCLUDED.intersection(path.split("/"))
            and any(scope == "." or path == scope or path.startswith(scope + "/") for scope in scopes))


def selected_scopes(repo, path=None):
    scopes = [repo.normalize_path(s) for s in repo.config()["scopes"]]
    if path:
        requested = repo.normalize_path(path)
        if not any(s == "." or requested == s or requested.startswith(s + "/") for s in scopes):
            raise RepoError("Requested path is outside your configured responsibility scope")
        scopes = [requested]
    return sorted(set(scopes))


def capture(repo, scopes, revision=None):
    sources, warnings = {}, []
    if revision:
        paths = []
        for entry in repo.git("ls-tree", "-r", "-z", revision).split("\0"):
            if not entry:
                continue
            metadata, path = entry.split("\t", 1)
            mode, kind, _ = metadata.split()
            if in_scope(path, scopes):
                if kind != "blob" or mode not in ("100644", "100755"):
                    warnings.append({"path": path, "reason": "Non-regular Git source skipped"})
                else:
                    paths.append(path)
    else:
        paths = repo.files(scopes)
    total = 0
    for path in sorted(paths):
        try:
            if revision:
                source = repo.at_revision(revision, path)
                if source is None:
                    raise RepoError("Cannot read source object from the selected commit")
            else:
                target = repo.root / path
                if not target.exists() and not target.is_symlink():
                    continue  # deleted tracked file
                source = repo.read(path)
            total += len(source.encode("utf-8", "surrogatepass"))
            if total > MAX_TOTAL_BYTES:
                raise OverflowError("Brief source snapshot exceeds 20 MB; choose a narrower path")
            sources[path] = source
        except (OSError, UnicodeError, SyntaxError, RepoError) as exc:
            warnings.append({"path": path, "reason": str(exc)})
    return {"sources": sources, "warnings": warnings}


def snapshot_id(snapshot):
    result = hashlib.sha256()
    for path, source in sorted(snapshot["sources"].items()):
        for value in (path, source):
            encoded = value.encode("utf-8", "surrogatepass")
            result.update(len(encoded).to_bytes(8, "big"))
            result.update(encoded)
    return result.hexdigest()
