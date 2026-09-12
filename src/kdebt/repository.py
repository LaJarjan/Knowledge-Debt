"""Read-only Git access with explicit scope and bounded source reads."""

import json
import subprocess
import tokenize
from pathlib import Path, PurePosixPath


class RepoError(Exception):
    pass


class Repository:
    def __init__(self, location: str = "."):
        self.root = Path(location).resolve()
        result = self.git("rev-parse", "--show-toplevel")
        self.root = Path(result.strip()).resolve()

    def git(self, *args: str, binary=False, allow_failure=False):
        try:
            result = subprocess.run(["git", "-C", str(self.root), *args],
                                    capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RepoError(f"Cannot run Git: {exc}") from exc
        if result.returncode and not allow_failure:
            raise RepoError(result.stderr.decode("utf-8", "replace").strip() or "Git command failed")
        if result.returncode:
            return None
        return result.stdout if binary else result.stdout.decode("utf-8", "surrogateescape")

    def revision(self, ref: str) -> str:
        # Resolve once and use the resulting hash for all subsequent object reads.
        return self.git("rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()

    def head(self) -> str | None:
        result = self.git("rev-parse", "--verify", "HEAD", allow_failure=True)
        return result.strip() if result else None

    def config(self) -> dict:
        path = self.root / ".kdebt" / "config.json"
        if not path.exists():
            return {"scopes": ["."]}
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
            scopes = config["scopes"]
            if not isinstance(scopes, list) or not scopes:
                raise ValueError("scopes must be a nonempty list")
            for scope in scopes:
                self.normalize_path(scope)
            return config
        except (ValueError, KeyError, TypeError) as exc:
            raise RepoError(f"Invalid .kdebt/config.json: {exc}") from exc

    def normalize_path(self, value: str) -> str:
        if not isinstance(value, str):
            raise RepoError("Scope must be a path string")
        path = (self.root / value).resolve()
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise RepoError("Paths must stay inside the repository") from exc

    def files(self, scopes: list[str]) -> list[str]:
        raw = self.git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
        normalized = [self.normalize_path(s) for s in scopes]
        return sorted({p for p in raw.split("\0") if p.endswith(".py")
                       and not any(x in PurePosixPath(p).parts for x in
                                   (".kdebt", ".venv", "venv", "__pycache__", "node_modules"))
                       and any(s == "." or p == s or p.startswith(s + "/") for s in normalized)})

    def read(self, path: str) -> str:
        target = self.root / path
        if target.is_symlink() or not target.resolve().is_relative_to(self.root):
            raise RepoError("Symlinked source is not analyzed")
        if target.stat().st_size > 1_000_000:
            raise RepoError("Source exceeds the 1 MB analysis limit")
        with tokenize.open(target) as stream:
            return stream.read()

    def changed_files(self, baseline):
        changed = self.git("diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                           "--name-only", "-z", baseline, "--")
        untracked = self.git("ls-files", "--others", "--exclude-standard", "-z")
        return set(changed.split("\0")) | set(untracked.split("\0"))

    def at_revision(self, revision: str, path: str) -> str | None:
        raw = self.git("show", f"{revision}:{path}", binary=True, allow_failure=True)
        if raw is None:
            return None
        if len(raw) > 1_000_000:
            raise RepoError("Baseline source exceeds the 1 MB analysis limit")
        import io
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        return raw.decode(encoding)
