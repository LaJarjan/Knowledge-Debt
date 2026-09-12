"""Repeatable synthetic scan timings; source fixtures are never executed.

Run after installing the package: python scripts/benchmark.py --files 100 500
Temporary repositories are removed by TemporaryDirectory on completion.
"""

import argparse
import json
import platform
import subprocess
import tempfile
import time
from pathlib import Path

from kdebt.repository import Repository
from kdebt.service import concept_from_dict, scan
from kdebt.store import Store

SOURCE = "import asyncio\nasync def work():\n    gate = asyncio.Semaphore(4)\n    async with gate:\n        return await request()\n"


def benchmark(count):
    with tempfile.TemporaryDirectory(prefix="kdebt-bench-") as directory:
        root = Path(directory)

        def git(*args):
            subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

        git("init", "-q")
        git("config", "user.name", "Benchmark")
        git("config", "user.email", "benchmark@example.com")
        git("config", "commit.gpgsign", "false")
        for index in range(count):
            (root / f"worker_{index:05}.py").write_text(SOURCE, encoding="utf-8")
        git("add", ".")
        git("commit", "-qm", "benchmark fixture")
        repo = Repository(str(root))
        started = time.perf_counter()
        full = scan(repo)
        full_time = time.perf_counter() - started
        store = Store(root)
        head = repo.head()
        for item in full["concepts"]:
            concept = concept_from_dict(item)
            store.save(concept, "Synthetic benchmark answer", ["f1"], head)
        started = time.perf_counter()
        scan(repo)
        stored_time = time.perf_counter() - started
        (root / "worker_00000.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(8)"))
        started = time.perf_counter()
        changed = scan(repo, "HEAD")
        diff_time = time.perf_counter() - started
        return {"files": count, "instances": full["supported_instances"],
                "full_scan_seconds": round(full_time, 3),
                "with_evidence_seconds": round(stored_time, 3),
                "one_file_diff_seconds": round(diff_time, 3),
                "diff_analyzed_files": changed["analyzed_files"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, nargs="+", default=[100, 500])
    args = parser.parse_args()
    if any(n < 1 or n > 10000 for n in args.files):
        parser.error("file counts must be between 1 and 10000")
    print(json.dumps({"python": platform.python_version(), "platform": platform.system()}), flush=True)
    for count in args.files:
        print(json.dumps(benchmark(count)), flush=True)
