Contributing
============

Contributing to Pyjoyment.

There are many ways to contribute to :mod:`Pyjoyment`, this guide will show
you a few of them.

.. Left out from Mojolicious: "PERL FOUNDATION BOYCOTT", as it is a matter of the Mojolicious project

Reporting bugs
--------------

We use the `GitHub issue tracker <https://github.com/pyjoyment/Pyjoyment/issues>`_,
so you'll need to create a (free) GitHub account to be able to submit issues,
comments and pull requests.

First of all, make sure you are using the latest version of
:mod:`Pyjoyment`, it is quite likely that your bug has already been fixed. If
that doesn't help, take a look at the list of currently open issues, perhaps
it has already been reported by someone else and you can just add a comment
confirming it.

If it hasn't been reported yet, try to prepare a test case demonstrating the
bug, you are not expected to fix it yourself, but you'll have to make sure the
developers can replicate your problem. Sending in your whole application
generally does more harm than good, the ``t`` directory of the repository has
many good examples for how to do it right. Writing a test is usually the
hardest part of fixing a bug, so the better your test case the faster it can
be fixed. ;) And if Mojolicious behaves differently for the same input, tell
us how, as :mod:`Pyjoyment` is a port of it.

And don't forget to add a descriptive title and text, when you create a new
issue. If your issue does not contain enough information or is
unintelligible, it might get closed pretty quickly. But don't be
disheartened, if there's new activity it will get reopened just as quickly.

Reporting security issues
~~~~~~~~~~~~~~~~~~~~~~~~~

Please report security issues privately, with `the form of GitHub
<https://github.com/pyjoyment/Pyjoyment/security/advisories/new>`_ for
reporting a vulnerability, and give us a few days to develop and release a
proper fix. The `security policy
<https://github.com/pyjoyment/Pyjoyment/blob/main/SECURITY.md>`_ says what a
report contains, what happens next and what is in scope.

Resolving issues
----------------

There are many ways in which you can help us resolve existing issues on the
`GitHub issue tracker <https://github.com/pyjoyment/Pyjoyment/issues>`_.

Can you replicate the problem on your computer? Add a comment saying that
you're seeing the same. Perhaps you can provide additional information that
will make it easier for others to replicate the problem, maybe even
contribute a better test case.

And for all code contributions we very much appreciate additional testing and
code review, just add a comment to show your approval or to point out flaws
that need to be addressed.

Contributing documentation
--------------------------

One of the easiest ways to contribute to :mod:`Pyjoyment` is through
documentation improvements. The documentation is the docstrings of the
modules, which Sphinx turns into the API reference, and the guides, which
are ported from the guides of Mojolicious.

Pull requests with additions or changes to the documentation included in the
:mod:`Pyjoyment` distribution follow the same rules as code contributions.
Please don't send pull requests for overly simplistic changes, such as the
addition of a comma or semicolon.

Contributing code
-----------------

All code contributions should be sent as `GitHub pull requests
<https://docs.github.com/pull-requests>`_. But please try to avoid pull
requests with very simplistic changes, such as a single typo fix somewhere in
the documentation or comments.

An expressive title and detailed description are invaluable during the review
process, which usually ends when the maintainer has reviewed the changes.

All code changes should emulate the style of the surrounding code, include
tests that fail without them, and update relevant documentation. `AGENTS.md
<https://github.com/pyjoyment/Pyjoyment/blob/main/AGENTS.md>`_ in the
repository describes how the project works and why, how a module is ported
from Mojolicious, and how the tests, the linters and the documentation are
run, for people and coding agents alike.

AI-assisted contributions are welcome, but we expect all contributions to be
submitted by a human who takes full responsibility for them.

While the :mod:`Pyjoyment` distribution covers a wide range of features, we
are rather conservative when it comes to adding new ones. So if your
contribution is not a simple bug fix, it is **strongly recommended** that you
discuss it in advance in the `GitHub issue tracker
<https://github.com/pyjoyment/Pyjoyment/issues>`_, to avoid unnecessary work and
to increase its chances of getting accepted.

The following mission statement and rules are the foundation of all
:mod:`Pyjo` and :mod:`Pyjoyment` development. Please make sure that your
contribution aligns well with them before sending a pull request.

Mission statement
~~~~~~~~~~~~~~~~~

:mod:`Pyjo` is a web development toolkit, with all the basic tools and
helpers needed to write simple web applications and higher level web
frameworks, such as :mod:`Pyjoyment`.

All components should be reusable in other projects, and in a UNIXish way
only loosely coupled.

Especially for people new to Python it should be as easy as possible to
install :mod:`Pyjoyment` and get started. Writing web applications can be one
of the most fun ways to learn a language!

For developers of other web frameworks, it should be possible to reuse all
the infrastructure and just consider the higher levels of the
:mod:`Pyjoyment` distribution an example application.

:mod:`Pyjoyment` is a port of Mojolicious, in the spirit of Mojo more than of
strict PEP 8, so that what is known of Mojolicious is true of Pyjoyment, in
Python.

Rules
~~~~~

General rules for the project:

- Web development should be easy and fun, this is what we optimize for.
- The web is a moving target, to stay relevant we have to stay in motion too.
- Keep it simple, no magic unless absolutely necessary.
- The installation process should be as fast and painless as possible. (Less
  than a minute on most common hardware is a good rule of thumb)
- It's not a feature without a test and documentation.
- A feature is only needed when the majority of the user base benefits from
  it.
- A module is ported from Mojolicious, its tests first, which are the
  specification, and what differs from Mojolicious on purpose is marked in
  the code.
- Refactoring should be avoided if there are no substantial benefits.
- No dependencies at run time, where Mojolicious uses an optional module,
  the standard library of Python takes its place.
- Emulate the style of the existing code and documentation, but don't be
  afraid to adopt newer best practices if you can apply them consistently.
- Domain specific languages should be avoided in favor of Python-ish
  solutions.
- Documentation belongs to the guides, module docstrings are just an API
  reference.
- The main focus of the included documentation should be on examples, no
  walls of text. (An example for every one or two sentences is a good rule of
  thumb)
- Everything should be ordered alphabetically if possible, or at least be
  consistent if not.
- The main source code repository should always be kept in a stable state,
  use feature branches for actual development.
- Code has to be run through the linters and formatters of `Trunk
  <https://docs.trunk.io>`_ with the included configuration, and everything
  should look like it was written by a single person.
- Functions and methods should be as short as possible, no spaghetti code.
- Comments should be correctly capitalized, and funny if possible,
  punctuation is optional if it doesn't increase readability.
- No names outside of ``README.md``, ``docs/license.rst`` and ``pyproject.toml``.

.. Left out from Mojolicious: the rules of deprecations, of experimental features and of the code names of major
   releases, as Pyjoyment has no policy of deprecations yet and no code names

.. Left out from Mojolicious: "Voting Rules", as Pyjoyment has one maintainer and no core team

.. Left out from Mojolicious: "CODE OF CONDUCT" and "FORK POLICY", as they are matters of the Mojolicious project

More
----

You can continue with :doc:`index` now or take a look at the `Mojolicious
wiki <https://github.com/mojolicious/mojo/wiki>`_, which contains a lot more
documentation and examples by many different authors.

Ported from `Mojolicious::Guides::Contributing
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Guides/Contributing.pod>`_
of Mojolicious 9.49.
