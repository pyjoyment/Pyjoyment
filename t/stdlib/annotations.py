from Pyjo.Test import *

import ast
import pathlib


# A module that ends with object = Pyjo_X cannot use object in its annotations: Python 3.14 evaluates them lazily
# (PEP 649), and so does pyright for a project on Python 3.14, as a distribution, when object is the class
def bare_objects(source):
    tree = ast.parse(source)
    if not any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'object' for target in node.targets)
        for node in tree.body
    ):
        return []

    annotations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
                if arg is not None and arg.annotation is not None:
                    annotations.append(arg.annotation)
            if node.returns is not None:
                annotations.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
        elif isinstance(node, ast.TypeAlias):
            annotations.append(node.value)

    lines = set()
    for annotation in annotations:
        for node in ast.walk(annotation):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                try:
                    quoted = ast.parse(node.value, mode='eval')
                except SyntaxError:
                    continue
                if any(isinstance(sub, ast.Name) and sub.id == 'object' for sub in ast.walk(quoted)):
                    lines.add(node.lineno)
            elif isinstance(node, ast.Name) and node.id == 'object':
                lines.add(node.lineno)
    return sorted(lines)


with subtest('The check'):
    source = """
import builtins

type Anything = builtins.object
type Alias = object


class C:
    def a(self, x: object, *args: 'list[object]') -> Anything: ...
    def b(self, cb: Callable[[], object]) -> 'Pyjo.Collection.object[C]': ...
    y: object


object = C
"""
    is_deeply_ok(bare_objects(source), [5, 9, 10, 11], 'object in annotations')
    is_deeply_ok(bare_objects(source.replace('object = C', '')), [], 'without the alias')

with subtest('No object in the annotations of a module with the alias'):
    root = pathlib.Path(__file__).parent.parent.parent
    found = [
        f'{path.relative_to(root)}:{line}'
        for package in ('Pyjo', 'Pyjoyment')
        for path in sorted((root / package).rglob('*.py'))
        for line in bare_objects(path.read_text(encoding='utf-8'))
    ]
    is_deeply_ok(found, [], 'builtins.object is Anything there')

done_testing()
