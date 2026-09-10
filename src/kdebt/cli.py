"""Four commands. No account, model API or repository code execution."""

import argparse
import json
import sqlite3
import sys

from . import __version__
from .repository import RepoError, Repository
from .service import concept_from_dict, scan
from .store import Store


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def parser():
    root = argparse.ArgumentParser(prog="kdebt", description="Find one code behavior worth understanding.")
    root.add_argument("--version", action="version", version=f"kdebt {__version__}")
    root.add_argument("--repo", default=".", help="repository path (default: current directory)")
    commands = root.add_subparsers(dest="command")
    init = commands.add_parser("init", help="set local responsibility scope")
    init.add_argument("--scope", action="append", help="repository-relative directory or file; repeatable")
    for command, help_text in (("scan", "rank supported code concepts"),
                               ("explain", "show code facts and ranking reasons"),
                               ("drill", "ask one code-grounded question")):
        child = commands.add_parser(command, help=help_text)
        child.add_argument("path", nargs="?", help="repository-relative file or directory")
        child.add_argument("--since", help="compare a Git revision with the current working tree")
        child.add_argument("--json", action="store_true", help="machine-readable output")
        if command == "scan":
            child.add_argument("--limit", type=positive, default=5)
        if command == "drill":
            child.add_argument("--id", help="choose the stable concept ID from scan --json")
            child.add_argument("--answer", help="record the user's answer without automatic grading")
            child.add_argument("--covered", action="append", default=[], metavar="FACT_ID",
                               help="fact explicitly self-checked by the user; repeatable")
            child.add_argument("--fingerprint", help="required with --answer; from the displayed drill")
    return root


def emit(value):
    print(json.dumps(value, ensure_ascii=True, indent=2))


def show_facts(item):
    for fact in item["facts"]:
        print(f"  [{fact['id']}] {fact['text']} ({item['path']}:{fact['line']})")
    print(f"  Boundary: {item['caveat']}")


def run(args):
    repo = Repository(args.repo)
    if args.command == "init":
        store = Store(repo.root)
        config_path = store.directory / "config.json"
        if config_path.exists():
            print("Already initialized. Edit .kdebt/config.json to change scope.")
            return 0
        scopes = [repo.normalize_path(s) for s in args.scope or ["."]]
        store.initialize()
        config_path.write_text(json.dumps({"scopes": scopes}, indent=2) + "\n", encoding="utf-8")
        print(f"Initialized {repo.root.name}. Responsibility scope: {', '.join(scopes)}")
        print("Answers stay in .kdebt/ and are ignored by Git. No understanding checks recorded yet.")
        return 0

    report = scan(repo, args.since, args.path)
    if args.command == "scan":
        if args.json:
            # JSON intentionally contains every candidate, independent of display limit.
            emit(report)
            return 0
        print(f"Knowledge Debt / {report['repository']}\n")
        print(f"Analyzed: {report['analyzed_files']} Python files; {report['supported_instances']} supported instances")
        print(f"Current self-checks: {report['states']['self_checked']} / {report['supported_instances']}")
        print(f"Changed since recorded answer: {report['states']['stale']}")
        if args.since:
            print(f"Scope: changes from {args.since} to working tree; removed instances: {len(report['removed'])}")
        print("\nCheck priority (not an understanding score)")
        for index, item in enumerate(report["concepts"][:args.limit], 1):
            print(f"{index}. {item['priority']:6} {item['path']}:{item['line']} / {item['kind']}")
            print(f"   {item['symbol']} | {item['state']}")
        if not report["concepts"]:
            print("No supported candidates in this scope. This does not establish understanding coverage.")
        print("\nNext: kdebt drill [path] -- one question, grounded in your source.")
    elif args.command == "explain":
        if args.json:
            emit(report)
            return 0
        for item in report["concepts"]:
            print(f"\n{item['path']}:{item['line']} / {item['symbol']} / {item['priority']}")
            for reason in item["reasons"]:
                print(f"  - {reason}")
            show_facts(item)
        if not report["concepts"]:
            print("No supported candidates. Try another path or omit --since.")
    else:
        if args.covered and args.answer is None:
            raise RepoError("--covered requires --answer")
        candidates = [c for c in report["concepts"] if not args.id or c["id"] == args.id]
        if not candidates:
            if args.id:
                raise RepoError("Concept ID not found in this scope; rescan before answering")
            if args.json:
                emit({"schema_version": 1, "drill": None, "warnings": report["warnings"]})
            else:
                print("No supported drill in this scope. Nothing has been graded.")
            return 0
        item = candidates[0]
        concept = concept_from_dict(item)
        if args.answer is not None:
            if not args.id or not args.fingerprint:
                raise RepoError("Recording requires --id and --fingerprint from the displayed drill")
            if args.fingerprint != concept.fingerprint:
                raise RepoError("Code changed since the question was displayed; request a fresh drill")
            Store(repo.root).save(concept, args.answer, args.covered, repo.head())
            result = {"schema_version": 1, "concept_id": concept.id,
                      "state": "self_checked" if args.covered else "answer_recorded",
                      "self_checked_facts": len(set(args.covered)), "total_facts": len(concept.facts),
                      "provenance": "user_self_report", "automatically_graded": False}
            if args.json:
                emit(result)
            else:
                print(f"Answer recorded. Self-checked facts: {len(set(args.covered))}/{len(concept.facts)}.")
                print("This is your self-report, not an automatic assessment of mastery.")
            return 0
        if args.json:
            emit({"schema_version": 1, "drill": item, "warnings": report["warnings"]})
            return 0
        print(f"Two-minute handoff / {item['path']}:{item['line']}\n")
        print(item["question"])
        if not sys.stdin.isatty():
            print("\nRun interactively to answer, or use --json for the integration contract.")
            return 0
        answer = input("\nYour answer (blank to skip): ").strip()
        if not answer:
            print("Skipped. No evidence recorded.")
            return 0
        print("\nCompare your answer with these source facts:")
        show_facts(item)
        print("Only mark facts your answer covered BEFORE reading this checklist.")
        covered = input("Fact IDs you self-checked (e.g. f1 f2; blank = answer only): ").split()
        # The user may edit code while the prompt is open. Revalidate the binding.
        fresh = scan(repo, path=item["path"])
        current = next((c for c in fresh["concepts"] if c["id"] == item["id"]), None)
        if not current or current["fingerprint"] != item["fingerprint"]:
            raise RepoError("Code changed while answering; request a fresh drill")
        Store(repo.root).save(concept, answer, covered, repo.head())
        print(f"\nRecorded {len(set(covered))}/{len(concept.facts)} self-checked source facts.")
        print("No automatic grade. Reasoning beyond these facts remains unverified.")
    for warning in report["warnings"]:
        print(f"Warning: {warning['path']}: {warning['reason']}", file=sys.stderr)
    return 0


def main(argv=None):
    arguments = parser()
    args = arguments.parse_args(argv)
    if args.command is None:
        args = arguments.parse_args(["--repo", args.repo, "scan"])
    try:
        return run(args)
    except (RepoError, OSError, sqlite3.Error, ValueError) as exc:
        if getattr(args, "json", False):
            emit({"schema_version": 1, "error": str(exc)})
        else:
            print(f"kdebt: {exc}", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled; no answer recorded.", file=sys.stderr)
        return 130
