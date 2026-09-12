import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from kdebt.analyzer import extract
from kdebt.repository import Repository
from kdebt.service import concept_from_dict, scan
from kdebt.store import Store
from test_kdebt import RepositoryFixture, SOURCE


class BindingTests(unittest.TestCase):
    def test_import_aliases(self):
        for statement, name in (("import asyncio as aio", "aio.Semaphore"),
                                ("from asyncio import Semaphore as Gate", "Gate"),
                                ("from threading import BoundedSemaphore", "BoundedSemaphore")):
            with self.subTest(statement=statement):
                self.assertEqual(len(extract(f"{statement}\ndef work():\n    gate = {name}(4)", "x.py")), 1)

    def test_shadowed_names_abstain(self):
        cases = [
            "def work(asyncio):\n    return asyncio.Semaphore(4)",
            "def work():\n    asyncio = custom\n    return asyncio.Semaphore(4)",
            "def work():\n    def asyncio(): pass\n    return asyncio.Semaphore(4)",
            "asyncio.Semaphore = custom\ndef work():\n    return asyncio.Semaphore(4)",
            "def work():\n    if condition:\n        def asyncio(): pass\n    return asyncio.Semaphore(4)",
        ]
        for source in cases:
            with self.subTest(source=source):
                self.assertEqual(extract("import asyncio\n" + source, "x.py"), [])

    def test_custom_same_name_is_not_a_semaphore(self):
        source = "class Custom:\n    def Semaphore(self, n): return n\ndef work():\n    return Custom().Semaphore(4)"
        self.assertEqual(extract(source, "x.py"), [])

    def test_local_import_and_nested_inheritance(self):
        source = "def work():\n    from asyncio import Semaphore as Gate\n    def nested():\n        return Gate(4)"
        self.assertEqual(extract(source, "x.py")[0].symbol, "work.nested")

    def test_direct_guard_fact_matches_source(self):
        concept = extract(SOURCE, "x.py")[0]
        self.assertTrue(any("context manager uses the expression gate" in f.text for f in concept.facts))

    def test_nested_guard_is_not_claimed_as_direct_use(self):
        source = (Path(__file__).parents[1] / "examples" / "worker.py").read_text()
        concept = extract(source, "x.py")[0]
        self.assertTrue(any("No matching" in f.text for f in concept.facts))

    def test_multiple_cleanup_calls_are_all_in_checklist(self):
        source = "def work(a, b):\n    try:\n        run()\n    finally:\n        a.close()\n        b.release()"
        concept = extract(source, "x.py")[0]
        self.assertEqual(len(concept.facts), 3)

    def test_recognition_corpus(self):
        cases = json.loads((Path(__file__).parent / "cases" / "recognition.json").read_text(encoding="utf-8"))
        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertEqual([c.kind for c in extract(case["source"], "x.py")], case["expected"])


class FingerprintTests(unittest.TestCase):
    def compare(self, source, old, new, expected=True):
        before = extract(source, "x.py")[0]
        after = extract(source.replace(old, new), "x.py")[0]
        self.assertEqual(before.id, after.id)
        self.assertEqual(before.fingerprint != after.fingerprint, expected)

    def test_same_file_helper(self):
        self.compare("import asyncio\ndef helper(): return 4\ndef work():\n    gate = asyncio.Semaphore(helper())",
                     "return 4", "return 8")

    def test_transitive_helper(self):
        self.compare("import asyncio\ndef helper(): return value()\ndef value(): return 4\ndef work():\n    gate = asyncio.Semaphore(helper())",
                     "return 4", "return 8")

    def test_recursive_helper_terminates(self):
        self.compare("import asyncio\ndef helper(): return helper() or 4\ndef work():\n    gate = asyncio.Semaphore(helper())",
                     "or 4", "or 8")

    def test_class_base_and_decorator(self):
        source = "import asyncio\n@decorate\nclass Worker(BaseA):\n    def work(self):\n        gate = asyncio.Semaphore(4)"
        self.compare(source, "BaseA", "BaseB")
        self.compare(source, "@decorate", "@other")

    def test_same_class_helper(self):
        self.compare("import asyncio\nclass Worker:\n    def value(self): return 4\n    def work(self):\n        gate = asyncio.Semaphore(self.value())",
                     "return 4", "return 8")

    def test_unrelated_class_method_does_not_invalidate(self):
        self.compare("import asyncio\nclass Worker:\n    def value(self): return 4\n    def work(self):\n        gate = asyncio.Semaphore(4)",
                     "return 4", "return 8", False)


class EvidenceTests(RepositoryFixture, unittest.TestCase):
    def concept(self):
        return concept_from_dict(scan(self.repo)["concepts"][0])

    def test_partial_is_not_low_priority(self):
        concept = self.concept()
        Store(self.root).save(concept, "Four permits", ["f2"], None)
        report = scan(self.repo)
        self.assertEqual(report["states"]["partial"], 1)
        self.assertEqual(report["states"]["self_checked"], 0)
        self.assertEqual(report["concepts"][0]["priority"], "MEDIUM")

    def test_latest_answer_is_not_unioned_with_older_answers(self):
        concept = self.concept()
        store = Store(self.root)
        store.save(concept, "Complete", [f.id for f in concept.facts], None)
        self.assertEqual(store.state(concept), "self_checked")
        store.save(concept, "Now unsure", ["f1"], None)
        self.assertEqual(store.state(concept), "partial")
        store.save(concept, "Need to check", [], None)
        self.assertEqual(store.state(concept), "answer_recorded")

    def test_repeated_fact_ids_do_not_inflate_coverage(self):
        concept = self.concept()
        store = Store(self.root)
        store.save(concept, "One fact", ["f1"] * 10, None)
        self.assertEqual(store.state(concept), "partial")

    def test_old_fingerprint_is_stale_and_preserved(self):
        concept = self.concept()
        store = Store(self.root)
        store.save(concept, "Old answer", ["f1"], None)
        with closing(sqlite3.connect(store.path)) as db, db:
            db.execute("UPDATE evidence SET fingerprint = 'v0.1.0-fingerprint'")
        self.assertEqual(store.state(concept), "stale")
        self.assertEqual(store.latest(concept.id)["answer"], "Old answer")

    def test_scan_reads_database_once(self):
        Store(self.root).save(self.concept(), "An answer", [], None)
        (self.root / "another.py").write_text(SOURCE)
        with patch("kdebt.store.sqlite3.connect", wraps=sqlite3.connect) as connect:
            report = scan(self.repo)
        self.assertEqual(report["supported_instances"], 2)
        self.assertEqual(connect.call_count, 1)

    def test_oldest_checked_concept_rotates(self):
        (self.root / "another.py").write_text(SOURCE)
        store = Store(self.root)
        for item in scan(self.repo)["concepts"]:
            concept = concept_from_dict(item)
            store.save(concept, "Checked", [f.id for f in concept.facts], None)
        first = self.concept()
        store.save(first, "Checked again", [f.id for f in first.facts], None)
        self.assertNotEqual(self.concept().id, first.id)

    def test_corrupt_database_fails_without_modification(self):
        directory = self.root / ".kdebt"
        directory.mkdir()
        path = directory / "evidence.sqlite3"
        path.write_bytes(b"not a sqlite database")
        code, output = self.call("scan", "--json")
        self.assertEqual(code, 2)
        self.assertIn("Back up", json.loads(output)["error"])
        self.assertEqual(path.read_bytes(), b"not a sqlite database")

    def test_chinese_paths_and_subdirectory(self):
        directory = self.root / "中文目录"
        directory.mkdir()
        (directory / "任务.py").write_text(SOURCE, encoding="utf-8")
        repo = Repository(str(directory))
        self.assertEqual(repo.root, self.root.resolve())
        self.assertEqual(scan(repo, path="中文目录")["supported_instances"], 1)

    def test_interactive_skip_and_cancel_do_not_write(self):
        for outcome, expected in (("", 0), (KeyboardInterrupt(), 130), (EOFError(), 130)):
            with self.subTest(outcome=outcome), patch("sys.stdin.isatty", return_value=True):
                with patch("builtins.input", side_effect=[outcome]):
                    code, _ = self.call("drill")
            self.assertEqual(code, expected)
            self.assertFalse((self.root / ".kdebt").exists())

    def test_explanation_is_not_evidence(self):
        code, output = self.call("drill", "--show-facts")
        self.assertEqual(code, 0)
        self.assertIn("No understanding evidence recorded", output)
        self.assertFalse((self.root / ".kdebt").exists())

    def test_facts_only_keeps_analysis_warnings_visible(self):
        (self.root / "broken.py").write_text("def broken(")
        code, output = self.call("drill", "--show-facts")
        self.assertEqual(code, 0)
        self.assertIn("Warning: broken.py", output)
        self.assertFalse((self.root / ".kdebt").exists())

    def test_interactive_answer_rejects_changed_source(self):
        answers = iter(["Four permits", "f2"])

        def answer(prompt):
            result = next(answers)
            if result == "f2":
                (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(8)"))
            return result

        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=answer):
            code, output = self.call("drill")
        self.assertEqual(code, 2)
        self.assertIn("Code changed", output)
        self.assertFalse((self.root / ".kdebt").exists())

    def test_interactive_partial_answer(self):
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["Four permits", "f2"]):
            code, _ = self.call("drill")
        self.assertEqual(code, 0)
        self.assertEqual(scan(self.repo)["states"]["partial"], 1)

    def test_noninteractive_answer_requires_binding_even_without_candidates(self):
        (self.root / "worker.py").write_text("pass\n")
        code, output = self.call("drill", "--answer", "unbound", "--json")
        self.assertEqual(code, 2)
        self.assertIn("--fingerprint", json.loads(output)["error"])

    def test_baseline_skips_unchanged_source_reads(self):
        for index in range(10):
            (self.root / f"unchanged{index}.py").write_text(SOURCE)
        self.commit()
        (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(8)"))
        with patch.object(self.repo, "at_revision", wraps=self.repo.at_revision) as read:
            report = scan(self.repo, "HEAD")
        self.assertEqual(read.call_count, 1)
        self.assertEqual(report["supported_instances"], 1)

    def test_file_rename_is_removed_and_added(self):
        self.commit()
        self.git("mv", "worker.py", "renamed.py")
        report = scan(self.repo, "HEAD")
        self.assertEqual(len(report["removed"]), 1)
        self.assertEqual(report["concepts"][0]["change"], "added")

    def test_git_worktree(self):
        self.commit()
        worktree = self.root / "linked"
        self.git("worktree", "add", "--detach", str(worktree), "HEAD")
        report = scan(Repository(str(worktree)))
        self.assertEqual(report["supported_instances"], 1)

    def test_shallow_clone_missing_base_reports_error(self):
        self.commit()
        shallow = self.root / "shallow"
        self.git("clone", "--depth", "1", self.root.as_uri(), str(shallow))
        repo = Repository(str(shallow))
        self.assertEqual(scan(repo)["supported_instances"], 1)
        from kdebt.repository import RepoError
        with self.assertRaises(RepoError):
            scan(repo, "HEAD~1")
