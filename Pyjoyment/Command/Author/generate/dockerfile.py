"""
Pyjoyment.Command.Author.generate.dockerfile - Dockerfile generator command
===========================================================================
::

    Usage: APPLICATION generate dockerfile [OPTIONS]

      ./myapp.py generate dockerfile
      python -m MyApp generate dockerfile
      python -m MyApp generate dockerfile --user app
      python -m MyApp generate dockerfile --port 8080
      python -m MyApp generate dockerfile --graceful-timeout 8
      python -m MyApp generate dockerfile --healthcheck /
      python -m MyApp generate dockerfile --target lambda
      python -m MyApp generate dockerfile --compress public
      python -m MyApp generate dockerfile --apt-package brotli --apt-package zstd --compress public
      python -m MyApp generate dockerfile --apt-package brotli --compress public --compress-encoding br --compress-encoding gzip

    Options:
      -a, --apt-package <name>           Install a package of Debian in the
                                         image, can be repeated
      -c, --compress <path>              Write the variants of gzip, and of
                                         brotli and zstd if the image has them,
                                         of the static files of a directory in
                                         the image, can be repeated
      -C, --compress-pattern <glob>      Name of the files that --compress
                                         compresses, can be repeated, defaults to
                                         the formats of text
      -e, --compress-encoding <name>     Encoding of the variants that --compress
                                         writes, "br", "zstd" or "gzip", can be
                                         repeated, defaults to gzip and the ones
                                         that the image has
      -G, --graceful-timeout <seconds>   Graceful timeout of the workers of the
                                         server, defaults to the one of the
                                         server
      -H, --healthcheck <path>           Path that the HEALTHCHECK of the image
                                         requests, defaults to the liveness of
                                         the plugin Health, if the application
                                         has it
      -h, --help                         Show this summary of available options
      -p, --port <port>                  Port that the server listens on and the
                                         image exposes, defaults to 3000
      -t, --target <name>                Target of the image, "lambda" for an
                                         event function of AWS Lambda, defaults
                                         to a server
      -u, --user <name>                  Create a system user and run the
                                         application as it, defaults to the user
                                         of the image

:mod:`Pyjoyment.Command.Author.generate.dockerfile` generates ``Dockerfile``
and ``.dockerignore`` for applications.

The image is built in two stages. The first one installs the dependencies
with uv into ``.venv``: the ones of ``pyproject.toml``, which
:mod:`Pyjoyment.Command.Author.generate.pyproject` generates, locked with
``uv.lock`` if there is one, or the ones of the inline metadata of PEP 723 of
a :mod:`Pyjoyment.Lite` script that has it and no ``pyproject.toml``, locked
with its ``.lock`` file if there is one. Without either, the generator fails
with the commands that add them. The second one has Python, ``.venv`` and the
application only, and its command runs the pre-forking server without
uv, so that the signals of ``docker stop`` go straight to the server, which
stops gracefully on ``TERM``. The images of Python and of uv are those of the
versions that run the generator.

Docker and Cloud Run give a container 10 seconds to stop, less than the 25
seconds that :attr:`Pyjo.Server.Prefork.Pyjo_Server_Prefork.graceful_timeout`
gives a worker, so ``--graceful-timeout 8`` sets ``PYJO_GRACEFUL_TIMEOUT`` in
the image, which the command ``prefork`` takes for its option, and which the
environment of the container can change again. With Docker,
``docker stop -t 30``, or ``stop_grace_period: 30s`` of Docker Compose, lets
the workers finish their requests too.

The server listens on the port of the ``PORT`` environment variable, which
the image sets to the port of ``--port``, ``3000`` by default, and exposes,
and which ``docker build --build-arg PORT=8080`` changes too. A platform as
Knative, Cloud Run, Render, Koyeb or Heroku sets ``PORT`` for the container,
and the server listens on its port, as Knative ignores ``EXPOSE`` and sets
``PORT`` to the ``containerPort`` of the service, ``8080`` by default.

An application with :mod:`Pyjoyment.Plugin.Health` gets a ``HEALTHCHECK``
that requests its liveness, ``/livez`` by default, or the path of
``--healthcheck``, and an empty path leaves it out. Python makes the request
with :mod:`http.client`, as the image has no ``curl``, and Docker shows the
health of the container in ``docker ps``, and Docker Compose waits for it with
``depends_on`` and ``condition: service_healthy``. Kubernetes and Cloud Run
ignore it and have probes of their own.

With ``--apt-package``, the image has packages of Debian, which ``apt-get``
installs before the application is copied, so that the layer stays in the
cache of the build while the application changes: the libraries that a
dependency of the application loads, as ``libpq5``, or tools, as ``brotli``
and ``zstd``.

With ``--compress``, the image has the precompressed variants of the static
files of a directory, as ``public``, which :mod:`Pyjoyment.Static` serves to
the clients that take them: ``.gz`` of ``gzip -k -9 -n`` of the image, and
``.br`` of ``brotli -k -q 11`` and ``.zst`` of ``zstd -k -19`` if the image has
them, as ``--apt-package brotli --apt-package zstd`` installs them, each with
the mtime of its file. It compresses the formats of text, CSS, JavaScript,
JSON, source maps, SVG, HTML, plain text, XML, WebAssembly and fonts in
TrueType and OpenType, or the names of ``--compress-pattern``, as the formats
of images, video, audio, the WOFF fonts, PDF and archives are compressed
already, and leaves out the files smaller than
:attr:`~Pyjoyment.Renderer.Pyjoyment_Renderer.min_compress_size` of the
renderer.
With ``--compress-encoding``, it writes the variants of those encodings only,
as ``br`` and ``gzip`` for CloudFront, which forwards no other encoding of
``Accept-Encoding`` to the origin, and the build fails without their tools.

With ``--target lambda``, the image is the one of an event function of AWS
Lambda: its command runs the script of the application, or its package, which
is the runtime of the function itself, as :mod:`Pyjoyment.Command.lambda`
detects, with the runtime client of :mod:`Pyjo.Server.Lambda`, and it has no
port, no ``HEALTHCHECK`` and no graceful timeout of a server, whose options
are not for it. A function whose Function URL streams its responses has
``PYJO_LAMBDA_INVOKE_MODE=RESPONSE_STREAM`` in its environment, as
:attr:`Pyjo.Server.Lambda.Pyjo_Server_Lambda.invoke_mode` says.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

Ported from `Mojolicious::Command::Author::generate::dockerfile
<https://github.com/mojolicious/mojo/blob/v9.49/lib/Mojolicious/Command/Author/generate/dockerfile.pm>`_ of
Mojolicious 9.49.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.File
import Pyjoyment.Command

from Pyjo.Util import extract_usage, getopt

import json
import os
import re
import shlex
import shutil
import subprocess
import sys

from typing import Any


class Pyjoyment_Command_Author_generate_dockerfile(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.Author.generate.dockerfile` inherits all
    attributes and methods from :mod:`Pyjoyment.Command` and implements the
    following new ones.
    """

    # Not in Mojolicious: the formats of text, which compress well, as the formats of images, video, audio, the WOFF
    # fonts, PDF and archives are compressed already
    compress_patterns: tuple[str, ...] = (
        '*.css',
        '*.csv',
        '*.html',
        '*.js',
        '*.json',
        '*.map',
        '*.mjs',
        '*.otf',
        '*.svg',
        '*.ttf',
        '*.txt',
        '*.wasm',
        '*.xml',
    )
    """::

        patterns = dockerfile.compress_patterns
        dockerfile.compress_patterns = ('*.css', '*.js')

    Names of the files that ``--compress`` compresses without
    ``--compress-pattern``, the formats of text, which compress well.
    """

    description = 'Generate "Dockerfile"'
    """::

        description = dockerfile.description
        dockerfile.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = dockerfile.usage
        dockerfile.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> None:
        """::

            dockerfile.run(*sys.argv[1:])

        Run this command.
        """
        # Not in Mojolicious: the options
        arguments = list(args)
        if not (
            opts := getopt(
                arguments,
                {
                    'a|apt-package=s@': None,
                    'c|compress=s@': None,
                    'C|compress-pattern=s@': None,
                    'e|compress-encoding=s@': None,
                    'G|graceful-timeout=i': None,
                    'H|healthcheck=s': None,
                    'p|port=i': None,
                    't|target=s': None,
                    'u|user=s': None,
                },
            )
        ):
            raise Pyjo.Exception.new(self.usage)

        # Not in Mojolicious: the target of the image, an event function of AWS Lambda, which has no options of a server
        target: str | None = opts.target
        if target not in (None, 'lambda'):
            raise Pyjo.Exception.new(f'Unknown target: {target}')
        if target == 'lambda':
            for option in ('graceful_timeout', 'healthcheck', 'port'):
                if getattr(opts, option) is not None:
                    raise Pyjo.Exception.new(f'Option --{option.replace("_", "-")} is not for the target lambda')

        # Not in Mojolicious: the packages of Debian, as the tools that write the variants of the static files
        packages: list[str] = opts.apt_package or []

        # Not in Mojolicious: the variants of gzip, brotli and zstd of the static files, for the formats of text, as
        # Pyjoyment.Static serves them, and the files that the renderer would not compress either
        compress: list[str] = opts.compress or []
        patterns: list[str] = opts.compress_pattern or list(self.compress_patterns)
        if opts.compress_pattern and not compress:
            raise Pyjo.Exception.new('Option --compress-pattern needs --compress')
        encodings: list[str] = opts.compress_encoding or []
        if encodings and not compress:
            raise Pyjo.Exception.new('Option --compress-encoding needs --compress')
        if unknown := [e for e in encodings if e not in _COMPRESSORS]:
            raise Pyjo.Exception.new(f'Unknown encoding: {unknown[0]}')
        # The tools of the encodings of the option, which fail without them, or gzip and the tools that the image has
        if encodings:
            commands = [command for encoding, command in _COMPRESSORS.items() if encoding in encodings]
        else:
            optional = [c for e, c in _COMPRESSORS.items() if e != 'gzip']
            commands = [
                _COMPRESSORS['gzip'],
                *(f'if command -v {c.split()[0]} >/dev/null; then {c}; fi' for c in optional),
            ]

        name = self.app.moniker

        # Not in Mojolicious: the HEALTHCHECK of the liveness of Pyjoyment.Plugin.Health, with http.client, as the image
        # has no curl
        # Helpers of a plugin are found at run time, so the application is Any
        app: Any = self.app
        path: str | None = opts.healthcheck
        if path is None and target is None and app.renderer.get_helper('health.path') is not None:
            path = app.health.path('livez')
        port = "int(os.environ['PORT'])"
        code = f"c = http.client.HTTPConnection('127.0.0.1', {port}, timeout=2); c.request('GET', {path!r})"
        healthcheck = (
            json.dumps(
                ['python', '-c', f'import http.client, os, sys; {code}; sys.exit(c.getresponse().status != 200)']
            )
            if path
            else None
        )

        # Unlike Mojolicious: the script of Pyjoyment.Lite or the package of the application, which python runs, where
        # Mojo runs the script, and the dependencies of pyproject.toml, or of the inline metadata of PEP 723 of a script
        # without it
        exe = os.environ.get('PYJO_EXE')
        script = Pyjo.File.path(exe).to_rel(self.app.home).to_str() if exe else None
        cmd = ['python', script] if script else ['python', '-m', type(self.app).__module__]
        project = self.rel_file('pyproject.toml').is_file
        if not project and not (exe and _metadata(Pyjo.File.path(exe))):
            raise Pyjo.Exception.new(_no_dependencies(script))
        lock = 'uv.lock' if project else f'{script}.lock'
        values = {
            'apt_packages': ' '.join(shlex.quote(package) for package in packages),
            'compress': ' '.join(shlex.quote(path) for path in compress),
            'compress_commands': ' \\\n    && '.join(commands),
            'compress_names': ' -o '.join(f'-name {shlex.quote(pattern)}' for pattern in patterns),
            'compress_size': self.app.renderer.min_compress_size - 1,
            'cmd': json.dumps(cmd if target == 'lambda' else [*cmd, 'prefork']),
            'graceful_timeout': opts.graceful_timeout,
            'healthcheck': healthcheck,
            'lock': lock if self.rel_file(lock).is_file else None,
            'name': name,
            'port': opts.port or 3000,
            'python': f'{sys.version_info.major}.{sys.version_info.minor}',
            'script': None if project else script,
            'target': target,
            'user': opts.user,
            'uv': _uv(),
        }
        self.render_to_rel_file('dockerfile', 'Dockerfile', values)

        # Not in Mojolicious: .dockerignore, as the .venv of the host is not the one of the image
        self.render_to_rel_file('dockerignore', '.dockerignore')


# Not in Mojolicious: the commands that write the variants of the encodings of Pyjoyment.Static, in its order
_COMPRESSORS = {
    'br': 'brotli -k -f -q 11 "$@"',
    'zstd': 'zstd -q -k -f -19 "$@"',
    'gzip': 'gzip -k -f -9 -n "$@"',
}


# Not in Mojolicious: the error of an application without pyproject.toml, or of a script without it and without
# the inline metadata of PEP 723, with the commands that add them, instead of a build that fails without them
def _no_dependencies(script: str | None) -> str:
    if script is None:
        return 'No dependencies of the application: add a pyproject.toml with "generate pyproject"'
    add = f'uv add --script {shlex.quote(script)} Pyjoyment'
    return (
        f'No dependencies of the script {script}: add its inline metadata with "{add}", '
        'or a pyproject.toml with "generate pyproject"'
    )


# Not in Mojolicious: whether the script has the inline metadata of PEP 723
def _metadata(path: Pyjo.File.object) -> bool:
    try:
        return re.search(r'(?m)^# /// script\r?$', str(path.slurp('UTF-8') or '')) is not None
    except OSError:
        return False


# Not in Mojolicious: the version of uv, for its image
def _uv() -> str:
    if (uv := shutil.which('uv')) is None:
        return 'latest'
    try:
        output = subprocess.run([uv, '--version'], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return 'latest'
    return m[1] if (m := re.match(r'uv (\d+\.\d+\.\d+)', output)) else 'latest'


new = Pyjoyment_Command_Author_generate_dockerfile.new
object = Pyjoyment_Command_Author_generate_dockerfile

__DATA__ = r"""
@@ dockerfile
FROM python:<%= python %>-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:<%= uv %> /uv /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 UV_PYTHON_DOWNLOADS=0
WORKDIR /opt/<%= name %>
% if script:
ENV VIRTUAL_ENV=/opt/<%= name %>/.venv
COPY <%= ' '.join([script, *([lock] if lock else [])]) %> ./
RUN uv venv && uv sync --script <%= script %> --active<%= ' --locked' if lock else '' %>
% else:
COPY <%= ' '.join(['pyproject.toml', *([lock] if lock else [])]) %> ./
RUN uv sync --no-install-project<%= ' --locked' if lock else '' %>
% end

FROM python:<%= python %>-slim
WORKDIR /opt/<%= name %>
% if apt_packages:
RUN apt-get update \\
    && apt-get install --yes --no-install-recommends <%= apt_packages %> \\
    && rm -rf /var/lib/apt/lists/*
% end
COPY --from=builder /opt/<%= name %>/.venv .venv
COPY . .
ENV PATH="/opt/<%= name %>/.venv/bin:$PATH"
% if compress:
RUN find <%= compress %> -type f -size +<%= compress_size %>c \\
    \( <%= compress_names %> \) \\
    -exec sh -c '<%= compress_commands %>' sh {} +
% end
% if user:
RUN useradd --system <%= user %>
USER <%= user %>
% end
% if target != 'lambda':
ARG PORT=<%= port %>
ENV PORT=${PORT}
% if graceful_timeout is not None:
ENV PYJO_GRACEFUL_TIMEOUT=<%= graceful_timeout %>
% end
EXPOSE ${PORT}
% if healthcheck:
HEALTHCHECK --timeout=3s --start-period=30s --start-interval=1s CMD <%= healthcheck %>
% end
% end
CMD <%= cmd %>

@@ dockerignore
.git
.venv
__pycache__
"""
