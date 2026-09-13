"""Build a shareable guide from synthetic example code, never private source.

Usage after installation: python scripts/demo_brief.py --output docs/demo --lang zh
"""

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from kdebt.brief import build
from kdebt.repository import Repository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="docs/demo")
    parser.add_argument("--lang", choices=("en", "zh"), default="en")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = (Path(__file__).resolve().parents[1] / "examples" / "worker.py").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="kdebt-guide-") as temporary:
        root = Path(temporary) / "handoff-demo"
        root.mkdir()

        def git(*arguments):
            subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True)

        git("init", "-q")
        git("config", "user.name", "Knowledge Debt Demo")
        git("config", "user.email", "demo@example.com")
        git("config", "commit.gpgsign", "false")
        before = source.split("\ndef consume(")[0].replace("Semaphore(4)", "Semaphore(2)").replace("range(3)", "range(2)")
        (root / "worker.py").write_text(before, encoding="utf-8")
        git("add", "worker.py")
        git("commit", "-qm", "Synthetic baseline")
        repo = Repository(str(root))
        build(repo, lang=args.lang)
        (root / "worker.py").write_text(source, encoding="utf-8")
        result = build(repo, lang=args.lang)
        shutil.copyfile(result["html"], output / "index.html")
        shutil.copyfile(result["markdown"], output / "guide.md")
        print(f"Synthetic handoff demo: {output / 'index.html'}")


if __name__ == "__main__":
    main()
