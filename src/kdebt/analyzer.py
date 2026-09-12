"""Source-grounded syntax checks; never execute repository code or infer mastery."""

import ast
import hashlib

from .bindings import DEFINITIONS, dependencies, local_nodes, resolve, scope_imports
from .models import Concept, Fact

SEMAPHORES = {f"{module}.{name}" for module in ("asyncio", "threading")
              for name in ("Semaphore", "BoundedSemaphore")}
DELAYS = {"asyncio.sleep", "time.sleep"}
ANALYSIS_VERSION = "facts-v2"


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def expression(node):
    return ast.unparse(node)


def semaphore_rows(candidate, function, nodes):
    """Describe direct-body uses without pretending to resolve object identity."""
    value = expression(candidate.args[0]) if candidate.args else next(
        (expression(k.value) for k in candidate.keywords if k.arg == "value"),
        "the callable's default")
    rows = [(f"The function contains a call to {expression(candidate.func)}.", candidate),
            (f"Its initial value argument is {value}.", candidate),
            (f"The constructor expression is inside {function.name}, not at module scope.", candidate)]
    binding = next((n for n in nodes if isinstance(n, (ast.Assign, ast.AnnAssign))
                    and n.value is candidate), None)
    target = None
    if isinstance(binding, ast.Assign) and len(binding.targets) == 1:
        target = expression(binding.targets[0])
    elif isinstance(binding, ast.AnnAssign):
        target = expression(binding.target)
    uses = []
    if target:
        for node in nodes:
            if isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if expression(item.context_expr) == target:
                        uses.append((f"A direct-body context manager uses the expression {target}.", node))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if expression(node.func.value) == target and node.func.attr in ("acquire", "release"):
                    uses.append((f"The direct body contains {expression(node)}.", node))
    rows.extend(uses)
    if not uses:
        rows.append(("No matching with/acquire/release syntax was identified in this function's direct body; "
                     "nested functions and other methods are not followed for uses.", candidate))
    return rows


def retry_rows(loop, imports):
    if not (isinstance(loop.iter, ast.Call) and isinstance(loop.iter.func, ast.Name)
            and loop.iter.func.id == "range" and "range" not in imports):
        return None
    loop_targets = {n.id for n in ast.walk(loop.target) if isinstance(n, ast.Name)}
    for attempt in loop.body:
        if not isinstance(attempt, ast.Try):
            continue
        exits = [n for n in attempt.body if isinstance(n, (ast.Return, ast.Break))]
        calls = [n for statement in attempt.body if not isinstance(statement, DEFINITIONS)
                 for n in local_nodes(statement) if isinstance(n, ast.Call)]
        if not exits or not calls:
            continue
        if any(n.id in loop_targets for call in calls for n in ast.walk(call)
               if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)):
            continue
        handlers, delays = [], []
        for handler in attempt.handlers:
            found = [n for statement in handler.body if not isinstance(statement, DEFINITIONS)
                     for n in local_nodes(statement)
                     if isinstance(n, ast.Call) and resolve(n.func, imports) in DELAYS]
            if found:
                handlers.append(handler)
                delays.extend(found)
        if handlers:
            caught = ", ".join(expression(h.type) if h.type else "all exceptions" for h in handlers)
            return [(f"The loop iterates over {expression(loop.iter)}.", loop.iter),
                    (f"Delay-containing handlers catch {caught}.", handlers[0]),
                    (f"A handler contains the delay call {expression(delays[0])}.", delays[0]),
                    (f"The try body contains the exit {expression(exits[0])}.", exits[0])]
    return None


def extract(source, path):
    tree = ast.parse(source, filename=path)
    declarations = [n for n in tree.body if not isinstance(n, DEFINITIONS)]
    context = "|".join(ast.dump(n, include_attributes=False) for n in declarations)
    definitions = {}
    for node in tree.body:
        if isinstance(node, DEFINITIONS):
            definitions.setdefault(node.name, []).append(node)
    imports = scope_imports(tree.body)
    concepts = []

    def visit(body, prefix="", parent_context="", inherited=None, extra_definitions=None):
        for node in body:
            if isinstance(node, ast.ClassDef):
                members = [n for n in node.body if not isinstance(n, DEFINITIONS)]
                header = [*node.bases, *node.keywords, *node.decorator_list, *members]
                class_context = "|".join(ast.dump(n, include_attributes=False) for n in header)
                class_context += dependencies(header, definitions)
                methods = {key: list(value) for key, value in (extra_definitions or {}).items()}
                for member in node.body:
                    if isinstance(member, DEFINITIONS):
                        methods.setdefault(member.name, []).append(member)
                visit(node.body, prefix + node.name + ".", parent_context + class_context, inherited, methods)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = prefix + node.name
                known = {key: list(value) for key, value in definitions.items()}
                for key, value in (extra_definitions or {}).items():
                    known.setdefault(key, []).extend(value)
                fingerprint = digest(ANALYSIS_VERSION + context + parent_context
                                     + ast.dump(node, include_attributes=False) + dependencies([node], known))
                resolved = scope_imports(node.body, inherited, node.args)
                nodes = list(local_nodes(node))
                counters = {}

                def add(kind, anchor, question, rows, caveat):
                    index = counters.get(kind, 0)
                    counters[kind] = index + 1
                    concepts.append(Concept(
                        id=digest(f"{path}:{symbol}:{kind}:{index}"), path=path,
                        symbol=symbol, kind=kind, line=anchor.lineno,
                        end_line=anchor.end_lineno, fingerprint=fingerprint,
                        question=question,
                        facts=tuple(Fact(f"f{i + 1}", text, item.lineno, expression(item))
                                    for i, (text, item) in enumerate(rows)), caveat=caveat))

                for candidate in nodes:
                    if isinstance(candidate, ast.Call) and resolve(candidate.func, resolved) in SEMAPHORES:
                        add("concurrency", candidate,
                            f"In {symbol}, where is this semaphore constructed and what initial value is supplied? "
                            "Identify matching with/acquire/release syntax in this function's direct body. "
                            "What remains unknown about uses outside that body?",
                            semaphore_rows(candidate, node, nodes),
                            "The import resolves lexically to asyncio/threading. Matching expressions do not "
                            "prove object identity or runtime control flow. A constructor call alone does not prove "
                            "requests are guarded; nested closures, other methods and monkey-patching are not resolved.")
                    if isinstance(candidate, ast.For):
                        rows = retry_rows(candidate, resolved)
                        if rows:
                            add("retry", candidate,
                                f"In {symbol}, identify the counted loop, the exceptions whose handlers contain "
                                "a delay, the delay expression and the try-body exit. Does that alone prove "
                                "the operation is safe to repeat?",
                                rows, "Counted retry-shaped syntax, not a control-flow proof. Iterations are not "
                                "necessarily attempts; external effects and idempotency remain unverified.")
                    if isinstance(candidate, ast.Try) and candidate.finalbody:
                        cleanup = [n for statement in candidate.finalbody if not isinstance(statement, DEFINITIONS)
                                   for n in local_nodes(statement)
                                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                   and n.func.attr in ("close", "aclose", "release")]
                        if cleanup:
                            add("cleanup", candidate,
                                f"In {symbol}, identify the cleanup calls inside finally. Does their presence "
                                "alone establish that cleanup completes on every exit?",
                                [("This try statement has a finally suite.", candidate)] +
                                [(f"That suite contains {expression(call)}.", call) for call in cleanup],
                                "Containing a cleanup call does not prove that cleanup always completes. "
                                "Conditions, earlier exceptions, cancellation and process exit matter.")
                visit(node.body, symbol + ".", parent_context + ast.dump(node, include_attributes=False),
                      resolved, extra_definitions)

    visit(tree.body, inherited=imports)
    return concepts
