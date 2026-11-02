Installation
============

Pyjoyment is installed from `PyPI <https://pypi.org/project/Pyjoyment/>`_: ::

    pip install Pyjoyment

or, in a project managed with `uv <https://docs.astral.sh/uv/>`_: ::

    uv add Pyjoyment

A new project or script comes from its generator, which uv runs without
installing Pyjoyment first: ::

    uvx --from Pyjoyment pyjo generate app MyApp
    uvx --from Pyjoyment pyjo generate lite-app myapp.py

The development version is installed from the Git repository: ::

    pip install git+https://github.com/pyjoyment/Pyjoyment

The skills for coding agents that write applications with Pyjoyment are a
plugin of `Claude Code <https://code.claude.com/docs/en/plugins>`_, whose
``SKILL.md`` files other agents read too: ::

    /plugin install pyjoyment --marketplace pyjoyment/Pyjoyment

or from the shell, as the extensions of the editors have no ``/plugin``: ::

    claude plugin install pyjoyment --marketplace pyjoyment/Pyjoyment
