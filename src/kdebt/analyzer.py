"""Conservative syntax recognizers, never an interpreter of repository code.

Facts describe source structure. They do not assert runtime behavior of arbitrary
Python objects, establish author intent, or infer a user's knowledge.
"""

import ast
import hashlib

from .models import Concept, Fact


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def expression(node: ast.AST) -> str:
    return ast.unparse(node)


def local_nodes(node: ast.AST):
    """Walk one lexical body without attributing nested functions to its owner."""
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield from local_nodes(child)


def extract(source: str, path: str) -> list[Concept]:
    tree = ast.parse(source, filename=path)
    # Global declarations can affect functions; conservatively invalidate their
    # evidence on such changes. Unrelated function edits do not invalidate it.
    declarations = [n for n in tree.body if not isinstance(
        n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    context = "|".join(ast.dump(n, include_attributes=False) for n in declarations)
    concepts: list[Concept] = []

    def visit(body, prefix="", parent_context=""):
        for node in body:
            if isinstance(node, ast.ClassDef):
                members = [n for n in node.body if not isinstance(
                    n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
                class_context = ast.dump(ast.Module(body=members, type_ignores=[]))
                visit(node.body, prefix + node.name + ".", parent_context + class_context)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = prefix + node.name
                fingerprint = digest(context + parent_context + ast.dump(node, include_attributes=False))
                nodes = list(local_nodes(node))
                counters: dict[str, int] = {}

                def add(kind, anchor, question, rows, caveat):
                    index = counters.get(kind, 0)
                    counters[kind] = index + 1
                    concepts.append(Concept(
                        id=digest(f"{path}:{symbol}:{kind}:{index}"), path=path,
                        symbol=symbol, kind=kind, line=anchor.lineno,
                        end_line=anchor.end_lineno, fingerprint=fingerprint,
                        question=question,
                        facts=tuple(Fact(f"f{i + 1}", text, item.lineno, expression(item))
                                    for i, (text, item) in enumerate(rows)),
                        caveat=caveat,
                    ))

                for candidate in nodes:
                    if isinstance(candidate, ast.Call) and isinstance(candidate.func, (ast.Name, ast.Attribute)):
                        callee = expression(candidate.func)
                        if callee.split(".")[-1] in ("Semaphore", "BoundedSemaphore"):
                            value = expression(candidate.args[0]) if candidate.args else next(
                                (expression(k.value) for k in candidate.keywords if k.arg == "value"),
                                "the callable's default")
                            add("concurrency", candidate,
                                f"In {symbol}, what value is passed to {callee}, and where is this "
                                "object acquired and released? Does this snippet establish a limit "
                                "across separate calls to this function?",
                                [(f"The function contains a call to {callee}.", candidate),
                                 (f"Its initial value argument is {value}.", candidate)],
                                "Name-based candidate only: resolve the callable and object lifetime. "
                                "A constructor call alone does not prove that requests are guarded.")

                    if isinstance(candidate, (ast.For, ast.AsyncFor)):
                        nested = list(local_nodes(candidate))
                        handlers = [n for n in nested if isinstance(n, ast.ExceptHandler)]
                        delays = [n for n in nested if isinstance(n, ast.Call)
                                  and isinstance(n.func, (ast.Name, ast.Attribute))
                                  and expression(n.func).split(".")[-1] == "sleep"]
                        if handlers and delays:
                            caught = ", ".join(expression(h.type) if h.type else "all exceptions"
                                               for h in handlers)
                            add("retry", candidate,
                                f"Trace the retry-shaped loop in {symbol}: which exceptions are "
                                "handled, what delay is requested, and what happens after the last "
                                "iteration? What would you need to check before retrying a write?",
                                [(f"The loop iterates over {expression(candidate.iter)}.", candidate.iter),
                                 (f"The loop contains handlers for {caught}.", handlers[0]),
                                 (f"The loop contains the delay call {expression(delays[0])}.", delays[0])],
                                "Structural candidate: loop iterations are not necessarily request attempts. "
                                "Inspect control flow; idempotency and external side effects are not proven.")

                    if isinstance(candidate, ast.Try) and candidate.finalbody:
                        cleanup = [n for statement in candidate.finalbody for n in local_nodes(statement)
                                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                   and n.func.attr in ("close", "aclose", "release")]
                        if cleanup:
                            call = cleanup[0]
                            add("cleanup", candidate,
                                f"In {symbol}, what cleanup is inside finally? Trace a normal return "
                                "and an exception through this region. Could another statement or "
                                "condition prevent the cleanup call from completing?",
                                [("This try statement has a finally suite.", candidate),
                                 (f"That suite contains {expression(call)}.", call)],
                                "Containing a cleanup call does not prove that cleanup always completes. "
                                "Conditions, earlier exceptions, cancellation and process exit matter.")

                # Nested functions are separate instances, while outer semantics
                # remain dependencies of those nested functions.
                visit(node.body, symbol + ".", parent_context + ast.dump(node, include_attributes=False))

    visit(tree.body)
    return concepts
