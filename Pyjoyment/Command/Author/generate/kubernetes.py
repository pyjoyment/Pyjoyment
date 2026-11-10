"""
Pyjoyment.Command.Author.generate.kubernetes - Kubernetes generator command
===========================================================================
::

    Usage: APPLICATION generate kubernetes [OPTIONS] [-- SERVER OPTIONS]

      ./myapp.py generate kubernetes
      python -m MyApp generate kubernetes
      python -m MyApp generate kubernetes --image ghcr.io/me/myapp:1.0
      python -m MyApp generate kubernetes --host-path
      python -m MyApp generate kubernetes --graceful-timeout 25
      python -m MyApp generate kubernetes --shutdown-delay 10
      python -m MyApp generate kubernetes --no-dev
      python -m MyApp generate kubernetes --server prefork -- --workers 2

    Options:
          --dev                          Install the dependency group "dev" of
                                         the project in the pod of "dev", which
                                         --no-dev leaves out, defaults to
                                         installing it
      -G, --graceful-timeout <seconds>   Graceful timeout of the workers of the
                                         server of "prod", defaults to the one of
                                         the server
      -h, --help                         Show this summary of available options
          --host-path                    Mount the directory of the project in
                                         the pod of "dev", in the place of a
                                         ConfigMap
      -i, --image <name>                 Image of "prod", the one of "generate
                                         dockerfile", defaults to the name of the
                                         application
      -p, --port <port>                  Port that the server listens on,
                                         defaults to 3000
      -S, --shutdown-delay <seconds>     Time that the server of "prod" keeps
                                         serving after TERM, defaults to 5
      -s, --server <name>                Server of "dev", "daemon", "prefork" or
                                         "reload", defaults to "reload" with
                                         --host-path or "daemon"

:mod:`Pyjoyment.Command.Author.generate.kubernetes` generates the manifests
of an application for Kubernetes, as Kustomize has them, in ``kubernetes``: a
base, with a Deployment and a Service of the name of the application, and two
overlays, ``dev`` and ``prod``, which ``kubectl apply -k`` applies. ::

    kubernetes/
      base/
        kustomization.yaml
        deployment.yaml
        probes.yaml
        service.yaml
      dev/
        kustomization.yaml
        deployment.yaml
        files/
      prod/
        kustomization.yaml
        deployment.yaml

The server listens on the port of the ``PORT`` environment variable, ``3000``
by default, as in the image of
:mod:`Pyjoyment.Command.Author.generate.dockerfile`, which the Service exposes
on the port ``80``. The probes of Kubernetes of an application with
:mod:`Pyjoyment.Plugin.Health` request it: the startup and the liveness its
liveness, ``/livez`` by default, and the readiness its readiness,
``/readyz``, which fails while the server stops gracefully, so that the
Service sends no more requests to the pod before its end. The probes of an
application without it connect to the port, which the server listens on once
it has started. The probes are a patch of their own, ``base/probes.yaml``, as
the application gets the plugin or loses it.

The overlay ``prod`` runs the image of ``--image``, which
:mod:`Pyjoyment.Command.Author.generate.dockerfile` builds, with the
pre-forking server of the image, in the operating mode ``production``.
Kubernetes takes a pod that it stops out of the endpoints of its Service at
the same time as it sends it ``TERM``, so the server keeps serving for the 5
seconds of ``--shutdown-delay``, which sets ``PYJO_SHUTDOWN_DELAY``, until the
proxies of the cluster know it, and ``terminationGracePeriodSeconds`` is 5
seconds above the delay and the 25 seconds that
:attr:`Pyjo.Server.Prefork.Pyjo_Server_Prefork.graceful_timeout` gives a
worker, or ``--graceful-timeout``, which sets ``PYJO_GRACEFUL_TIMEOUT``, so
that the server stops by itself before the kill of Kubernetes. Without
``--image``, the image is the one of the name of the application, as
``docker build -t myapp .`` tags it, which a cluster of Docker Desktop or
OrbStack takes from Docker.

The overlay ``dev`` runs the application in the image of uv with Python, of
the version that runs the generator, which installs the dependencies of the
application when the pod starts, as the image of
:mod:`Pyjoyment.Command.Author.generate.dockerfile` does when it is built, the
ones of ``pyproject.toml`` or of the inline metadata of PEP 723 of a script,
without which the generator fails with the commands that add them, in
an ``emptyDir``, with the dependency group ``dev`` of a project, which
``--no-dev`` leaves out, and runs it in the operating mode ``development``,
without building an image, with the server of ``--server``: the command
``daemon``, ``prefork``, or ``pyjo-reload`` of :mod:`Pyjo.Server.Reload`,
with the options after ``--``. The application is a ConfigMap that ``configMapGenerator`` of Kustomize makes of a
copy of it in ``kubernetes/dev/files``, which the pod copies, as the files of a
ConfigMap are read-only. The application is the files of the current
directory, without hidden ones, ``__pycache__``, ``dist`` and ``kubernetes``,
as for :mod:`Pyjoyment.Command.Author.generate.lambda_zip`, and a ConfigMap
holds 1 MiB at most. A new ConfigMap of a changed application has a new name,
which rolls the Deployment out. ``kubernetes/dev/files`` is a build of the
application, as ``dist`` of
:mod:`Pyjoyment.Command.Author.generate.lambda_zip`, which goes into
``.gitignore``.

With ``--host-path``, the pod of ``dev`` mounts the directory of the project
in the place of the ConfigMap, as a cluster that sees the disk of the
machine, as the one of Docker Desktop or OrbStack, or of kind with
``extraMounts``, mounts it, and the server is ``pyjo-reload``, which restarts
the application when a file of it changes, where a ConfigMap changes with a
new pod and the server is ``daemon``.

The files of ``base`` and ``prod``, which are to be edited, are written once,
and the ones of ``dev`` and ``base/probes.yaml`` anew each time, as the
application changes, which a patch of its own in the place of the one of
``base/probes.yaml`` in ``base/kustomization.yaml`` keeps from changing the
probes.

This is a core command, that means it is always enabled and its code a good
example for learning to build new commands, you're welcome to fork it.

See :mod:`Pyjoyment.Commands` for a list of commands that are available by
default.

See also
--------

:mod:`Pyjoyment`, https://mojolicious.org.

It has no counterpart in Mojolicious.

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
import sys

from typing import Any


# The data of a ConfigMap, at most
_LIMIT = 1024 * 1024


class Pyjoyment_Command_Author_generate_kubernetes(Pyjoyment.Command.object):
    """
    :mod:`Pyjoyment.Command.Author.generate.kubernetes` inherits all
    attributes and methods from :mod:`Pyjoyment.Command` and implements the
    following new ones.
    """

    description = 'Generate the manifests of Kubernetes'
    """::

        description = kubernetes.description
        kubernetes.description = 'Foo'

    Short description of this command, used for the command list.
    """

    usage = extract_usage()
    """::

        usage = kubernetes.usage
        kubernetes.usage = 'Foo'

    Usage information for this command, used for the help screen.
    """

    def run(self, *args: str) -> None:
        """::

            kubernetes.run(*sys.argv[1:])

        Run this command.
        """
        arguments = list(args)
        spec = {'dev!': None, 'G|graceful-timeout=i': None, 'host-path': None, 'i|image=s': None, 'p|port=i': None}
        if not (opts := getopt(arguments, {**spec, 'S|shutdown-delay=i': None, 's|server=s': None})):
            raise Pyjo.Exception.new(self.usage)

        # The server of dev, which reloads the application of the directory of the project, where its files change,
        # and the arguments after "--" for it
        server: str = opts.server or ('reload' if opts.host_path else 'daemon')
        if server not in ('daemon', 'prefork', 'reload'):
            raise Pyjo.Exception.new(f'Unknown server: {server}')

        # The name of the resources, which Kubernetes takes in lower case, with "-" in the place of "_", and the one of
        # the image, as "docker build -t" tags it
        moniker = self.app.moniker
        name = re.sub(r'[^a-z0-9]+', '-', moniker.lower()).strip('-') or 'app'

        # The probes of Pyjoyment.Plugin.Health, or of the port without it; helpers of a plugin are found at run time, so
        # the application is Any
        app: Any = self.app
        health = app.renderer.get_helper('health.path') is not None
        probes = {'livez': app.health.path('livez'), 'readyz': app.health.path('readyz')} if health else None

        # The script of Pyjoyment.Lite or the package of the application, and the dependencies of pyproject.toml, or of
        # the inline metadata of PEP 723 of a script without it, as generate dockerfile has them
        exe = os.environ.get('PYJO_EXE')
        script = Pyjo.File.path(exe).to_rel(self.app.home).to_str().replace(os.sep, '/') if exe else None
        package = type(self.app).__module__
        project = self.rel_file('pyproject.toml').is_file
        if not project and not (exe and _metadata(Pyjo.File.path(exe))):
            raise Pyjo.Exception.new(_no_dependencies(script))
        lock = 'uv.lock' if project else f'{script}.lock'
        port = opts.port or 3000

        base = {'moniker': moniker, 'name': name, 'port': port, 'probes': probes}
        self.render_to_rel_file('base_kustomization', 'kubernetes/base/kustomization.yaml', base)
        self.render_to_rel_file('base_deployment', 'kubernetes/base/deployment.yaml', base)
        self.render_to_rel_file('base_service', 'kubernetes/base/service.yaml', base)
        # The probes anew each time, as the application gets or loses the plugin Health
        self._write(self.rel_file('kubernetes/base/probes.yaml'), self.render_data('base_probes', base))

        graceful: int | None = opts.graceful_timeout
        delay: int = 5 if opts.shutdown_delay is None else opts.shutdown_delay
        prod = {'delay': delay, 'graceful_timeout': graceful, 'image': opts.image, 'moniker': moniker, 'name': name}
        self.render_to_rel_file('prod_kustomization', 'kubernetes/prod/kustomization.yaml', prod)
        self.render_to_rel_file('prod_deployment', 'kubernetes/prod/deployment.yaml', prod)

        # The command of dev: the dependencies in the emptyDir, with the group "dev" of a project unless --no-dev, and
        # the server, with "python -m", which puts the application in the path, as the image of generate dockerfile
        # does; pyjo-reload watches the package of an application too, as it watches the script, "lib" and "templates"
        # by default
        locked = ' --locked' if self.rel_file(lock).is_file else ''
        if project:
            sync = f'uv sync --no-install-project{locked}{" --no-dev" if opts.dev is False else ""}'
        else:
            sync = f'uv venv --allow-existing /uv/venv && uv sync --script {shlex.quote(str(script))} --active{locked}'
        python = '/uv/venv/bin/python'
        if server == 'reload':
            watch = [] if script else ['-w', package, '-w', 'templates']
            cmd = [python, '-m', 'Pyjo.Server.Reload', *watch, *arguments, script or f'{package}/__main__.py']
        else:
            cmd = [python, *([script] if script else ['-m', package]), server, *arguments]
        command = f'{sync} && exec {shlex.join(cmd)}'

        # The application in a ConfigMap of a copy of its files, or the directory of the project
        files: list[tuple[str, str, str]] = []
        dev = self.rel_file('kubernetes/dev')
        copy = dev.child('files')
        if copy.is_dir:
            copy.remove_tree()
        if not opts.host_path:
            size = 0
            keys: set[str] = set()
            for file in Pyjo.File.path().list_tree().each():
                path = file.to_rel(Pyjo.File.path()).to_str().replace(os.sep, '/')
                if path.split('/')[0] in ('dist', 'kubernetes') or '__pycache__' in path.split('/'):
                    continue
                if (size := size + os.path.getsize(file)) > _LIMIT:
                    raise Pyjo.Exception.new(f'The application is larger than a ConfigMap holds: {_LIMIT} bytes')
                key = _key(path, keys)
                files.append((key, json.dumps(f'{key}=files/{path}'), json.dumps(path)))
                destination = copy.child(*path.split('/'))
                destination.dirname().make_path()
                shutil.copyfile(file.to_str(), destination.to_str())

        dev.make_path()
        values = {
            'command': json.dumps(['sh', '-c', command]),
            'files': files,
            'host_path': json.dumps(Pyjo.File.path().to_abs().to_str()) if opts.host_path else None,
            'image': f'ghcr.io/astral-sh/uv:python{sys.version_info.major}.{sys.version_info.minor}-trixie-slim',
            'name': name,
            'project': project,
        }
        for file in ('kustomization', 'deployment'):
            self._write(dev.child(f'{file}.yaml'), self.render_data(f'dev_{file}', values))

    # A file that the generator writes anew each time, where write_file keeps one that exists
    def _write(self, file: Pyjo.File.object, data: str) -> None:
        file.spew(data)
        self._loud(f'  [write] {file}')


# The error of an application without pyproject.toml, or of a script without it and without the inline
# metadata of PEP 723, with the commands that add them, instead of a build that fails without its dependencies
def _no_dependencies(script: str | None) -> str:
    if script is None:
        return 'No dependencies of the application: add a pyproject.toml with "generate pyproject"'
    add = f'uv add --script {shlex.quote(script)} Pyjoyment'
    return (
        f'No dependencies of the script {script}: add its inline metadata with "{add}", '
        'or a pyproject.toml with "generate pyproject"'
    )


# Whether the script has the inline metadata of PEP 723
def _metadata(path: Pyjo.File.object) -> bool:
    try:
        return re.search(r'(?m)^# /// script\r?$', str(path.slurp('UTF-8') or '')) is not None
    except OSError:
        return False


# The key of a file in a ConfigMap, which has no "/", unique among the keys of the other files
def _key(path: str, keys: set[str]) -> str:
    key = re.sub(r'[^-._a-zA-Z0-9]', '-', path.replace('/', '.')).lstrip('.') or 'file'
    unique, n = key, 1
    while unique in keys:
        n += 1
        unique = f'{key}-{n}'
    keys.add(unique)
    return unique


new = Pyjoyment_Command_Author_generate_kubernetes.new
object = Pyjoyment_Command_Author_generate_kubernetes

__DATA__ = r"""
@@ base_kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
labels:
  - pairs:
      app.kubernetes.io/name: <%= name %>
    includeSelectors: true
resources:
  - deployment.yaml
  - service.yaml
patches:
  - path: probes.yaml

@@ base_deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <%= name %>
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: <%= name %>
          image: <%= moniker %>
          imagePullPolicy: IfNotPresent
          env:
            - name: PORT
              value: "<%= port %>"
          ports:
            - name: http
              containerPort: <%= port %>

@@ base_probes
# Written by "generate kubernetes" anew each time, as the application has the plugin Health or not
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <%= name %>
spec:
  template:
    spec:
      containers:
        - name: <%= name %>
          startupProbe:
% if probes:
            httpGet:
              path: <%= probes['livez'] %>
              port: http
% else:
            tcpSocket:
              port: http
% end
            periodSeconds: 1
            failureThreshold: 30
          livenessProbe:
% if probes:
            httpGet:
              path: <%= probes['livez'] %>
              port: http
% else:
            tcpSocket:
              port: http
% end
          readinessProbe:
% if probes:
            httpGet:
              path: <%= probes['readyz'] %>
              port: http
% else:
            tcpSocket:
              port: http
% end
            periodSeconds: 2

@@ base_service
apiVersion: v1
kind: Service
metadata:
  name: <%= name %>
spec:
  ports:
    - name: http
      port: 80
      targetPort: http

@@ prod_kustomization
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../base
patches:
  - path: deployment.yaml
% if image:
images:
  - name: <%= moniker %>
    newName: <%= image %>
% end

@@ prod_deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <%= name %>
spec:
  replicas: 2
  template:
    spec:
      terminationGracePeriodSeconds: <%= delay + (25 if graceful_timeout is None else graceful_timeout) + 5 %>
      containers:
        - name: <%= name %>
          env:
            - name: PYJO_MODE
              value: production
% if graceful_timeout is not None:
            - name: PYJO_GRACEFUL_TIMEOUT
              value: "<%= graceful_timeout %>"
% end
% if delay:
            - name: PYJO_SHUTDOWN_DELAY
              value: "<%= delay %>"
% end

@@ dev_kustomization
# Written by "generate kubernetes" anew each time
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../base
patches:
  - path: deployment.yaml
% if not host_path:
configMapGenerator:
  - name: <%= name %>-files
    files:
% for _, source, _ in files:
      - <%= source %>
% end
% end

@@ dev_deployment
# Written by "generate kubernetes" anew each time
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <%= name %>
spec:
  template:
    spec:
% if not host_path:
      initContainers:
        - name: app
          image: <%= image %>
          command: ["sh", "-c", "cp -RL /files/* /app"]
          volumeMounts:
            - name: files
              mountPath: /files
            - name: app
              mountPath: /app
% end
      containers:
        - name: <%= name %>
          image: <%= image %>
          workingDir: /app
          command: <%= command %>
          env:
            - name: PYJO_MODE
              value: development
            - name: UV_CACHE_DIR
              value: /uv/cache
% if project:
            - name: UV_PROJECT_ENVIRONMENT
              value: /uv/venv
% else:
            - name: VIRTUAL_ENV
              value: /uv/venv
% end
          startupProbe:
            failureThreshold: 300
          volumeMounts:
            - name: app
              mountPath: /app
            - name: uv
              mountPath: /uv
      volumes:
% if host_path:
        - name: app
          hostPath:
            path: <%= host_path %>
            type: Directory
% else:
        - name: files
          configMap:
            name: <%= name %>-files
            items:
% for key, _, path in files:
              - key: <%= key %>
                path: <%= path %>
% end
        - name: app
          emptyDir: {}
% end
        - name: uv
          emptyDir: {}
"""
