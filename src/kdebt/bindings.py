"""Bounded lexical import resolution and same-file fingerprint dependencies."""

import ast

DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def local_nodes(node):
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (*DEFINITIONS, ast.Lambda)):
            continue
        yield from local_nodes(child)


def scope_imports(body, inherited=None, arguments=None):
    """Accept unique import bindings; abstain on shadowing or reassignment."""
    bindings = {}

    def bind(name, value=None):
        bindings.setdefault(name, []).append(value)

    if arguments:
        for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
            bind(argument.arg)
        for argument in (arguments.vararg, arguments.kwarg):
            if argument:
                bind(argument.arg)
    wildcard = False
    for statement in body:
        if isinstance(statement, DEFINITIONS):
            bind(statement.name)
            continue
        for node in local_nodes(statement):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, DEFINITIONS):
                    bind(child.name)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bind(alias.asname or alias.name.split(".")[0],
                         alias.name if alias.asname else alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        wildcard = True
                    else:
                        bind(alias.asname or alias.name,
                             f"{node.module}.{alias.name}" if not node.level and node.module else None)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                bind(node.id)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
                base = node.value
                while isinstance(base, ast.Attribute):
                    base = base.value
                if isinstance(base, ast.Name):
                    bind(base.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bind(node.name)
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                for name in node.names:
                    bind(name)
    result = dict(inherited or {})
    for name, values in bindings.items():
        result[name] = values[0] if len(values) == 1 else None
    if wildcard:
        return {name: None for name in result}
    return result


def resolve(node, imports):
    if isinstance(node, ast.Name):
        return imports.get(node.id)
    if isinstance(node, ast.Attribute):
        base = resolve(node.value, imports)
        return f"{base}.{node.attr}" if base else None
    return None


def dependencies(roots, definitions):
    """Transitively include referenced same-file definitions, conservatively.

    Local shadows may over-invalidate. External calls are not resolved.
    """
    pending = list(roots)
    seen = {id(node) for node in roots}
    included = []
    while pending:
        node = pending.pop()
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        names.update(n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute))
        for name in sorted(names):
            for target in definitions.get(name, []):
                if id(target) not in seen:
                    seen.add(id(target))
                    included.append(target)
                    pending.append(target)
    return "|".join(sorted(ast.dump(n, include_attributes=False) for n in included))
