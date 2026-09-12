import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from kdebt.analyzer import extract
from kdebt.cli import main
from kdebt.repository import Repository, RepoError
from kdebt.service import scan, concept_from_dict
from kdebt.store import Store


SOURCE = '''import asyncio

async def fetch():
    gate = asyncio.Semaphore(4)
    async with gate:
        await request()

def unrelated():
    return 1
'''


class AnalyzerTests(unittest.TestCase):
    def test_facts_have_real_source_locations(self):
        concept = extract(SOURCE, "worker.py")[0]
        self.assertEqual(concept.kind, "concurrency")
        self.assertEqual(concept.line, 4)
        self.assertIn("4", concept.facts[1].text)
        self.assertIn("alone does not prove", concept.caveat)

    def test_comments_and_formatting_keep_evidence(self):
        original = extract(SOURCE, "worker.py")[0]
        formatted = extract("# comment\n" + SOURCE.replace("Semaphore(4)", "Semaphore( 4 )"), "worker.py")[0]
        self.assertEqual(original.id, formatted.id)
        self.assertEqual(original.fingerprint, formatted.fingerprint)

    def test_unrelated_edit_preserves_evidence_but_limit_change_does_not(self):
        original = extract(SOURCE, "worker.py")[0]
        unrelated = extract(SOURCE.replace("return 1", "return 2"), "worker.py")[0]
        changed = extract(SOURCE.replace("Semaphore(4)", "Semaphore(8)"), "worker.py")[0]
        self.assertEqual(original.fingerprint, unrelated.fingerprint)
        self.assertEqual(original.id, changed.id)
        self.assertNotEqual(original.fingerprint, changed.fingerprint)

    def test_global_change_invalidates(self):
        original = extract("LIMIT = 4\n" + SOURCE, "worker.py")[0]
        changed = extract("LIMIT = 8\n" + SOURCE, "worker.py")[0]
        self.assertNotEqual(original.fingerprint, changed.fingerprint)

    def test_nested_constructor_not_attributed_to_outer(self):
        source = "from asyncio import Semaphore\ndef outer():\n    def inner():\n        gate = Semaphore(2)\n"
        concepts = extract(source, "a.py")
        self.assertEqual([c.symbol for c in concepts], ["outer.inner"])

    def test_retry_cleanup_and_unsupported(self):
        source = (Path(__file__).resolve().parents[1] / "examples" / "worker.py").read_text()
        concepts = extract(source, "worker.py")
        self.assertEqual({c.kind for c in concepts}, {"concurrency", "retry", "cleanup"})
        self.assertEqual(extract("def add(a, b): return a + b", "a.py"), [])


class RepositoryFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        (self.root / "worker.py").write_text(SOURCE, encoding="utf-8")
        self.repo = Repository(str(self.root))

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")

    def call(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(["--repo", str(self.root), *args])
        return code, out.getvalue()


class RepositoryTests(RepositoryFixture, unittest.TestCase):
    def test_unborn_repo_and_no_state_mutation_on_scan(self):
        report = scan(self.repo)
        self.assertIsNone(report["head"])
        self.assertEqual(report["states"]["unrecorded"], 1)
        self.assertFalse((self.root / ".kdebt").exists())

    def test_gitignored_source_not_scanned(self):
        (self.root / ".gitignore").write_text("secret.py\n")
        (self.root / "secret.py").write_text(SOURCE)
        self.assertEqual(scan(self.repo)["analyzed_files"], 1)

    def test_bad_python_reported_without_hiding_good_file(self):
        (self.root / "bad.py").write_text("def broken(")
        report = scan(self.repo)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertEqual(report["supported_instances"], 1)

    def test_baseline_detects_changes_untracked_and_removal(self):
        self.commit()
        self.assertEqual(scan(self.repo, "HEAD")["supported_instances"], 0)
        (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(8)"))
        report = scan(self.repo, "HEAD")
        self.assertEqual(report["concepts"][0]["change"], "changed")
        self.assertEqual(report["concepts"][0]["priority"], "HIGH")
        (self.root / "new.py").write_text(SOURCE)
        self.assertEqual(scan(self.repo, "HEAD")["supported_instances"], 2)
        (self.root / "worker.py").unlink()
        self.assertEqual(len(scan(self.repo, "HEAD")["removed"]), 1)

    def test_answers_are_private_and_stale_after_change(self):
        concept = concept_from_dict(scan(self.repo)["concepts"][0])
        store = Store(self.root)
        store.save(concept, "Four permits per local object", [fact.id for fact in concept.facts], None)
        self.assertEqual(store.state(concept), "self_checked")
        ignored = self.git("check-ignore", ".kdebt/evidence.sqlite3").decode()
        self.assertIn("evidence.sqlite3", ignored)
        (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(8)"))
        self.assertEqual(scan(self.repo)["states"]["stale"], 1)

    def test_answer_without_check_is_not_coverage(self):
        concept = concept_from_dict(scan(self.repo)["concepts"][0])
        store = Store(self.root)
        store.save(concept, "I need to inspect the scope", [], None)
        self.assertEqual(store.state(concept), "answer_recorded")

    def test_cli_json_round_trip_and_stale_submission(self):
        code, output = self.call("drill", "--json")
        self.assertEqual(code, 0)
        item = json.loads(output)["drill"]
        submission = ["drill", "--id", item["id"], "--fingerprint", item["fingerprint"],
                      "--answer", "Four permits", "--covered", "f2", "--json"]
        code, output = self.call(*submission)
        self.assertEqual(code, 0, output)
        self.assertFalse(json.loads(output)["automatically_graded"])
        (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(8)"))
        code, output = self.call(*submission)
        self.assertEqual(code, 2)
        self.assertIn("changed", json.loads(output)["error"])

    def test_scope_and_traversal(self):
        (self.root / "app").mkdir()
        (self.root / "app" / "worker.py").write_text(SOURCE)
        code, _ = self.call("init", "--scope", "app")
        self.assertEqual(code, 0)
        self.assertEqual(scan(self.repo)["analyzed_files"], 1)
        with self.assertRaises(RepoError):
            scan(self.repo, path="../outside")
        with self.assertRaises(RepoError):
            scan(self.repo, path="worker.py")

    def test_invalid_ref_and_fact_id(self):
        code, _ = self.call("scan", "--since", "missing-revision", "--json")
        self.assertEqual(code, 2)
        concept = concept_from_dict(scan(self.repo)["concepts"][0])
        with self.assertRaises(RepoError):
            Store(self.root).save(concept, "answer", ["f99"], None)

    def test_no_repository_code_execution(self):
        marker = self.root / "executed"
        (self.root / "worker.py").write_text(f"open({str(marker)!r}, 'w').write('bad')\n" + SOURCE)
        self.assertEqual(scan(self.repo)["supported_instances"], 1)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
