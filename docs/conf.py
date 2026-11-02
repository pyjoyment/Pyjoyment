# Sphinx configuration: https://www.sphinx-doc.org/en/master/usage/configuration.html

import functools
import importlib.util
import inspect
import os
import re
import subprocess
import sys
import tomllib


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# The modules are documented from the source tree, not from an installed package
sys.path.insert(0, ROOT)

with open(os.path.join(ROOT, 'pyproject.toml'), 'rb') as f:
    PROJECT = tomllib.load(f)['project']

project = PROJECT['name']
author = ', '.join(a['name'] for a in PROJECT['authors'])
copyright = f'2014-2026, {author}'
version = release = PROJECT['version']

# The diagrams of the guides, which mermaid.js renders in the browser
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.linkcode', 'sphinxcontrib.mermaid']

# The trees of files and processes are treeView-beta, which mermaid.js has since 11.16, newer than the one that
# sphinxcontrib-mermaid loads by default
mermaid_version = '11.17.2'

# A tree has the width of its text, as the text of the page, not the width of the page, and a sequence names its
# participants once, above it
mermaid_init_config = {
    'startOnLoad': False,
    'treeView': {'useMaxWidth': False},
    'sequence': {'mirrorActors': False},
}

# A diagram has its own size, where sphinxcontrib-mermaid makes each one 500 pixels high
html_static_path = ['_static']
html_css_files = ['mermaid.css']

# The commit that the links to the source point to: the one that Read the Docs builds, or the one of the checkout
COMMIT = (
    os.environ.get('READTHEDOCS_GIT_COMMIT_HASH')
    or subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    or 'main'
)

SOURCE = f'https://github.com/pyjoyment/Pyjoyment/blob/{COMMIT}'


# The link [source] of a class, a function or a method goes to the lines of its source on GitHub; an object without
# source of its own, as a constant or a descriptor that a loop makes, has none
def linkcode_resolve(domain, info):
    if domain != 'py' or not info['module']:
        return None
    obj = sys.modules.get(info['module'])
    for part in info['fullname'].split('.'):
        obj = getattr(obj, part, None)
    if isinstance(obj, property):
        obj = obj.fget
    elif isinstance(obj, functools.cached_property):
        obj = obj.func
    try:
        obj = inspect.unwrap(obj)
        path = inspect.getsourcefile(obj)
        lines, start = inspect.getsourcelines(obj)
    except (TypeError, OSError, ValueError):
        return None
    if not path or not os.path.abspath(path).startswith(ROOT + os.sep):
        return None
    file = os.path.relpath(path, ROOT).replace(os.sep, '/')
    return f'{SOURCE}/{file}#L{start}-L{start + len(lines) - 1}'


# A function or a method under a second name, as `raise_` of `throw`, is an alias
# that the documentation of the first one names, so it is not documented twice:
# its own name is public and finds the same object. So is a class under a second
# name, as `object` and `Path` of `Pyjo_Path`, which each module has; as targets
# named `object`, those aliases would also make the `object` type in annotations
# ambiguous.
def skip_alias(app, what, name, obj, skip, options):
    canonical = getattr(obj, '__name__', name)
    if isinstance(obj, type):
        return True if canonical != name else None
    if canonical == name or canonical.startswith('_'):
        return None
    found = sys.modules.get(getattr(obj, '__module__', None) or '')
    for part in getattr(obj, '__qualname__', '').split('.'):
        found = getattr(found, part, None)
    return True if found is obj else None


# The attribute `__weakref__` that Python makes for a class without `__slots__`
# is not an API of the class, but `:special-members:` without a list documents it
def skip_weakref(app, what, name, obj, skip, options):
    return True if name == '__weakref__' else None


# The link "Page source" goes to the file on GitHub: the module of a page of the
# API, whose source only names it, or the page itself, rendered, where the theme
# links to its text in _sources
def source_link(app, pagename, templatename, context, doctree):
    if not context.get('sourcename'):
        return
    path = app.env.doc2path(pagename)
    automodule = re.search(r'^\.\. automodule:: (\S+)', path.read_text('UTF-8'), re.M)
    if automodule:
        path = importlib.util.find_spec(automodule.group(1)).origin
    url = f'{SOURCE}/{os.path.relpath(path, ROOT).replace(os.sep, "/")}'
    pathto, sources = context['pathto'], '_sources/' + context['sourcename']
    context['pathto'] = lambda uri, *args, **kwargs: url if uri == sources else pathto(uri, *args, **kwargs)


def setup(app):
    app.connect('autodoc-skip-member', skip_alias)
    app.connect('autodoc-skip-member', skip_weakref)
    app.connect('html-page-context', source_link)


# The table of contents lists the pages, not the classes and functions that
# autodoc documents on them.
toc_object_entries = False

exclude_patterns = ['_build']

html_theme = 'alabaster'
html_theme_options = {
    'github_user': 'pyjoyment',
    'github_repo': 'Pyjoyment',
    'show_powered_by': False,
    # The sans-serif font of the system, where Alabaster has Georgia
    'font_family': "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    'head_font_family': "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
}
