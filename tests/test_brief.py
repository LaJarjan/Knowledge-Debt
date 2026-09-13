import json
import unittest
from pathlib import Path
from unittest.mock import patch

from kdebt.brief import build
from kdebt.repository import RepoError
from kdebt.service import scan
from test_kdebt import RepositoryFixture, SOURCE


class BriefTests(RepositoryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.commit()

    def read(self, result):
        return json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))

    def test_outputs_are_offline_and_no_understanding_is_written(self):
        result = build(self.repo, lang="zh")
        report = self.read(result)
        html = Path(result["html"]).read_text(encoding="utf-8")
        self.assertIn("代码写完了", html)
        self.assertIn("Content-Security-Policy", html)
        self.assertNotIn("<script", html)
        self.assertEqual(report["summary"]["changed_files"], 0)
        self.assertEqual(report["summary"]["current_behaviors"], 1)
        self.assertTrue(Path(result["markdown"]).exists())
        self.assertFalse((self.root / ".kdebt" / "evidence.sqlite3").exists())
        self.assertEqual(scan(self.repo)["states"]["unrecorded"], 1)
        relative = Path(result["html"]).relative_to(self.root).as_posix()
        self.assertIn(relative, self.git("check-ignore", relative).decode())

    def test_baseline_to_working_tree_has_before_after(self):
        (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(8)"))
        report = self.read(build(self.repo))
        card = report["cards"][0]
        self.assertEqual(card["change"], "changed")
        self.assertIn("4", card["before_facts"][1]["text"])
        self.assertIn("8", card["facts"][1]["text"])

    def test_committed_target_does_not_use_dirty_working_tree(self):
        base = self.repo.head()
        (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(8)"))
        self.commit()
        target = self.repo.head()
        (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(99)"))
        report = self.read(build(self.repo, base=base, head=target))
        self.assertEqual(report["target"], target)
        self.assertIn("8", report["cards"][0]["facts"][1]["text"])
        self.assertNotIn("99", report["cards"][0]["snippet"]["text"])

    def test_previous_guide_recheck_and_unchanged(self):
        first = build(self.repo)
        second = self.read(build(self.repo))
        self.assertEqual(second["cards"][0]["since_guide"], "unchanged")
        (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(8)"))
        third = self.read(build(self.repo))
        self.assertEqual(third["summary"]["needs_review"], 1)
        self.assertTrue(third["cards"][0]["prior_facts"])
        self.assertTrue(Path(first["html"]).exists())

    def test_formatting_retains_explanation(self):
        build(self.repo)
        (self.root / "worker.py").write_text("# header\n" + SOURCE)
        report = self.read(build(self.repo))
        self.assertEqual(report["cards"][0]["since_guide"], "unchanged")
        self.assertEqual(report["summary"]["changed_files"], 1)

    def test_removed_behavior(self):
        build(self.repo)
        (self.root / "worker.py").unlink()
        report = self.read(build(self.repo))
        self.assertEqual(len(report["removed"]), 1)
        self.assertEqual(len(report["removed_since_guide"]), 1)
        self.assertEqual(report["cards"], [])

    def test_parse_failure_is_not_removal(self):
        build(self.repo)
        (self.root / "worker.py").write_text("def broken(")
        report = self.read(build(self.repo))
        self.assertEqual(report["removed"], [])
        self.assertEqual(report["cards"][0]["since_guide"], "unverified")
        self.assertFalse(report["cards"][0]["verified"])
        (self.root / "worker.py").write_text(SOURCE)
        restored = self.read(build(self.repo))
        self.assertEqual(restored["cards"][0]["since_guide"], "restored")

    def test_working_tree_mutation_aborts_publish(self):
        from kdebt.brief_render import render_html

        def mutate(report):
            (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", "Semaphore(9)"))
            return render_html(report)

        with patch("kdebt.brief_render.render_html", side_effect=mutate):
            with self.assertRaisesRegex(RepoError, "changed during generation"):
                build(self.repo)
        self.assertFalse((self.root / ".kdebt").exists())

    def test_generated_source_is_escaped(self):
        (self.root / "worker.py").write_text(SOURCE.replace("Semaphore(4)", 'Semaphore("<script>alert(1)</script>")'))
        result = build(self.repo)
        html = Path(result["html"]).read_text(encoding="utf-8")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        markdown = Path(result["markdown"]).read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;", markdown)

    def test_scopes_have_independent_histories(self):
        (self.root / "other.py").write_text(SOURCE)
        build(self.repo, path="worker.py")
        other = self.read(build(self.repo, path="other.py"))
        self.assertIsNone(other["previous_snapshot"])

    def test_unsupported_changes_are_visible(self):
        (self.root / "plain.py").write_text("def add(a, b): return a + b")
        report = self.read(build(self.repo))
        plain = next(f for f in report["files"] if f["path"] == "plain.py")
        self.assertEqual(plain["supported_cards"], 0)

    def test_corrupt_history_does_not_overwrite(self):
        result = build(self.repo)
        pointer = Path(result["html"]).parent.parent / "latest.json"
        pointer.write_text('{"generation":"../../escape"}')
        with self.assertRaises(RepoError):
            build(self.repo)
        self.assertEqual(pointer.read_text(), '{"generation":"../../escape"}')

    def test_partial_generation_does_not_replace_latest(self):
        result = build(self.repo)
        pointer = Path(result["html"]).parent.parent / "latest.json"
        before = pointer.read_bytes()
        with patch("kdebt.brief.os.replace", side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError):
                build(self.repo)
        self.assertEqual(pointer.read_bytes(), before)

    def test_cli_json_contract(self):
        code, output = self.call("brief", "--base", "HEAD", "--lang", "zh", "--json")
        self.assertEqual(code, 0, output)
        result = json.loads(output)
        self.assertTrue(Path(result["html"]).exists())
        self.assertEqual(result["schema_version"], 2)

    def test_invalid_base_fails_without_artifacts(self):
        code, output = self.call("brief", "--base", "missing", "--json")
        self.assertEqual(code, 2)
        self.assertIn("error", json.loads(output))
        self.assertFalse((self.root / ".kdebt").exists())
