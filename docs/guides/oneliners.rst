One-liners
==========

Fun and useful one-liners with :mod:`Pyjo`.

This document is a collection of one-liners for the command line, which
fetch web pages and APIs, convert JSON and YAML, look into the manifests of
Kubernetes and run a whole application, each of them a single expression of
Python.

Basics
------

``python -m Pyjo`` runs its code with the functions of :mod:`Pyjo`, the ones
that ``from Pyjo import *`` imports, and prints the value of an expression,
unless it is ``None``. Bytes are printed as they are, and the code is in
single quotes of the shell, so that its strings can be in double quotes.

.. code-block:: console

    $ python -m Pyjo 'x("<p>Hello <b>Pyjo</b>!</p>").at("b").text'
    Pyjo
    $ python -m Pyjo 'c(1, 2, 3).map(lambda n: n * 2).join(", ")'
    2, 4, 6

Code that is not an expression, as several statements separated with ``;``,
runs as it is, and prints only what it prints itself.

.. code-block:: console

    $ python -m Pyjo 'for n in range(3): print(n)'
    0
    1
    2

The arguments after the code are in :data:`sys.argv`, and the code has the
module :mod:`sys` without an import.

.. code-block:: console

    $ python -m Pyjo 'h(sys.argv[1]).code' example.com
    200
    $ python -m Pyjo 'c(*sys.argv[1:]).map(lambda url: f"{h(url).code} {url}").join("\n")' example.com mojolicious.org
    200 example.com
    200 mojolicious.org

The functions that make requests follow ten redirects and detect proxies;
the environment variables that change it are described in :mod:`Pyjo`.

Web pages
---------

:func:`Pyjo.g` makes a ``GET`` request, and the :mod:`Pyjo.DOM` of its
response finds the elements of the page with CSS selectors.

.. code-block:: console

    $ python -m Pyjo 'g("example.com").dom().at("title").text'
    Example Domain
    $ python -m Pyjo 'g("mojolicious.org").dom("a[href]").map(lambda e: e.attr("href")).uniq().join("\n")'

The headers and the status of a response, without its body, come with a
``HEAD`` request of :func:`Pyjo.h`, and :func:`Pyjo.r` dumps a data
structure.

.. code-block:: console

    $ python -m Pyjo 'r(h("example.com").headers.to_dict())'

JSON APIs
---------

``json()`` of a response decodes its JSON, and takes a JSON Pointer for a
value inside it.

.. code-block:: console

    $ python -m Pyjo 'g("https://pypi.org/pypi/Pyjoyment/json").json("/info/requires_python")'
    >=3.12

The other methods of HTTP have their own functions, :func:`Pyjo.p` for
``POST``, :func:`Pyjo.w` for ``PUT``, :func:`Pyjo.t` for ``PATCH`` and
:func:`Pyjo.d` for ``DELETE``, which send a JSON body with ``json``.

.. code-block:: console

    $ python -m Pyjo 'p("https://httpbin.org/post", json={"hello": "world"}).json("/json")'
    {'hello': 'world'}

:func:`Pyjo.y` turns what an API returns into YAML, which is easier to read.

.. code-block:: console

    $ python -m Pyjo 'y(g("https://pypi.org/pypi/Pyjoyment/json").json("/info/project_urls"))'
    Changelog: https://github.com/pyjoyment/Pyjoyment/releases
    Documentation: https://pyjoyment.readthedocs.io/
    Homepage: https://pyjoyment.dev/
    Issues: https://github.com/pyjoyment/Pyjoyment/issues
    Source: https://github.com/pyjoyment/Pyjoyment

Files
-----

:func:`Pyjo.f` is a :mod:`Pyjo.File`, whose ``slurp`` reads a file and
``spew`` writes it. :func:`Pyjo.j` decodes JSON and encodes a data structure,
and :func:`Pyjo.y` loads YAML into a :mod:`Pyjo.Collection` of its documents,
whose ``first()`` is the only one of a configuration file, and dumps data
structures, a document for each.

.. literalinclude:: oneliners/config.yaml
    :language: yaml
    :caption: config.yaml

.. code-block:: console

    $ python -m Pyjo 'y(f("config.yaml").slurp()).first()["hosts"]'
    ['example.com', 'www.example.com']
    $ python -m Pyjo 'j(y(f("config.yaml").slurp()).first())'
    {"name":"myapp","port":"3000","hosts":["example.com","www.example.com"]}

A file converted from YAML to JSON, and back again.

.. code-block:: console

    $ python -m Pyjo 'f("config.json").spew(j(y(f("config.yaml").slurp()).first()))'
    config.json
    $ python -m Pyjo 'y(j(f("config.json").slurp()))'
    name: myapp
    port: '3000'
    hosts:
      - example.com
      - www.example.com

The builder ``z`` of :mod:`Pyjo.JSON.Schema` validates the data of a file,
and prints the JSON Pointers of the values that are not valid.

.. code-block:: console

    $ python -m Pyjo 'z.object(port=z.int(), hosts=z.array(z.string())).validate(y(f("config.yaml").slurp()).first())'
    /port: Expected integer - got string.

Standard input and output
-------------------------

:func:`Pyjo.s` reads the whole standard input, once, as bytes, which
:func:`Pyjo.j` and :func:`Pyjo.y` take with their encoding, with a byte order
mark or in UTF-16 too, as Windows PowerShell writes them, and writes bytes to
the standard output as they are, without a line break.

.. code-block:: console

    $ python -m Pyjo 's(y(j(s())))' < config.json > config.yaml
    $ python -m Pyjo 's(g("https://mojolicious.org/mojo/logo-white.png").body)' > logo-white.png
    $ python -m Pyjo 'f("logo-white.png").slurp()[:8] == b"\x89PNG\r\n\x1a\n"'
    True

What :func:`Pyjo.s` writes is what it returns, which ``python -m Pyjo`` does
not print again, so that the calls nest, and ``fd`` writes to another file
descriptor, as the standard error, which the terminal shows, as ``tee``
does.

.. code-block:: console

    $ python -m Pyjo 's(s(y(j(s())), fd=2))' < config.json > config.yaml
    name: myapp
    port: '3000'
    hosts:
      - example.com
      - www.example.com

PowerShell
----------

PowerShell gives the objects of its pipeline to a program as text, so
``ConvertTo-Json`` makes JSON of them for :func:`Pyjo.j`, and
``ConvertFrom-Json`` makes objects of the JSON of a one-liner again.

.. code-block:: pwsh-session

    PS> [ordered]@{ name = 'myapp'; hosts = @('example.com', 'www.example.com') } | ConvertTo-Json | python -m Pyjo 'y(j(s()))'
    name: myapp
    hosts:
      - example.com
      - www.example.com

    PS> python -m Pyjo 'j(y(f("config.yaml").slurp()).first())' | ConvertFrom-Json | Select-Object -ExpandProperty hosts
    example.com
    www.example.com
    PS> Get-Content config.yaml | python -m Pyjo 'y(s()).first()["hosts"]'
    ['example.com', 'www.example.com']

``Out-File -Encoding unicode``, and ``>`` and ``Out-File`` of Windows
PowerShell 5.1 by default, write UTF-16LE with a byte order mark, which
:func:`Pyjo.f`, :func:`Pyjo.j` and :func:`Pyjo.y` read as it is.

.. code-block:: pwsh-session

    PS> [ordered]@{ name = 'myapp'; port = 3000 } | ConvertTo-Json | Out-File -Encoding unicode app.json
    PS> python -m Pyjo 'j(f("app.json").slurp())["port"]'
    3000

The double quotes inside the code of a one-liner reach the program as they
are with PowerShell 7.3 and newer, and PowerShell 7.4 and newer pass the
bytes of a pipe between programs and of a redirection to a file as they are.
Older versions, as Windows PowerShell 5.1, drop the double quotes unless
they are written as ``\"``, and turn the bytes into strings in between, so a
one-liner there reads and writes the files itself, with :func:`Pyjo.f`.

.. code-block:: pwsh-session

    PS> python -m Pyjo 'f("logo-white.png").spew(g("https://mojolicious.org/mojo/logo-white.png").body)'
    logo-white.png

Kubernetes
----------

The manifests of Kubernetes are YAML, and so is what ``kubectl`` prints with
``-o yaml``.

.. literalinclude:: oneliners/deployment.yaml
    :language: yaml
    :caption: deployment.yaml

.. code-block:: console

    $ python -m Pyjo 'y(f("deployment.yaml").slurp()).first()["spec"]["template"]["spec"]["containers"][0]["image"]'
    ghcr.io/example/myapp:1.0.0

Several statements change a manifest and write it back.

.. code-block:: console

    $ python -m Pyjo 'd = y(f("deployment.yaml").slurp()).first(); d["spec"]["replicas"] = 3; f("deployment.yaml").spew(y(d))'
    $ python -m Pyjo 'y(f("deployment.yaml").slurp()).first()["spec"]["replicas"]'
    3

``kubectl get`` with ``-o yaml`` prints one document, a ``List`` of the
objects in its ``items``, which a one-liner reads from the standard input
with :func:`Pyjo.s`.

.. code-block:: console

    $ kubectl get deployments -A -o yaml | python -m Pyjo 'c(*y(s()).first()["items"]).map(lambda d: d["spec"]["template"]["spec"]["containers"][0]["image"]).uniq().join("\n")'
    ghcr.io/example/myapp:1.0.0
    registry.k8s.io/coredns/coredns:v1.12.0
    $ kubectl get pods -A -o yaml | python -m Pyjo 'c(*y(s()).first()["items"]).grep(lambda p: p["status"]["phase"] != "Running").map(lambda p: p["metadata"]["name"]).join("\n")'
    myapp-7d4b9c8f6d-x2k9p

A single object is the document itself, as a secret, whose values are
Base64, or a ConfigMap, whose value can be YAML again.

.. code-block:: console

    $ kubectl get secret myapp -o yaml | python -m Pyjo 'b(y(s()).first()["data"]["password"]).b64_decode()'
    s3cr3t
    $ kubectl get configmap myapp -o yaml | python -m Pyjo 'y(y(s()).first()["data"]["config.yaml"]).first()["port"]'
    3000

What ``kustomize build`` and ``helm template`` print is a document for each
object, which :func:`Pyjo.y` gives all of them.

.. code-block:: console

    $ kustomize build . | python -m Pyjo 'y(s()).map(lambda d: d["kind"] + "/" + d["metadata"]["name"]).join("\n")'
    Service/myapp
    Deployment/myapp
    $ kustomize build . | python -m Pyjo 'y(*y(s()).grep(lambda d: d["kind"] == "Service"))'
    apiVersion: v1
    kind: Service
    metadata:
      name: myapp
    spec:
      selector:
        app: myapp
      ports:
        - port: 80
          targetPort: 3000

Applications
------------

:func:`Pyjo.a` makes a route of a :mod:`Pyjoyment.Lite` application, whose
``start`` runs its commands, as ``get``, which requests it without a server,
or ``daemon``, which serves it.

.. code-block:: console

    $ python -m Pyjo 'a("/", {"json": {"hello": "world"}}).start()' get /
    {"hello":"world"}

More
----

The other functions, as :func:`Pyjo.l` for URLs, :func:`Pyjo.q` for regular
expressions and :func:`Pyjo.n` for benchmarks, are described in :mod:`Pyjo`.

.. code-block:: console

    $ python -m Pyjo 'l("https://mojolicious.org/perldoc?search=dom").query.param("search")'
    dom
    $ python -m Pyjo 'q(r"\d+").findall("a1b22c333")'
    ['1', '22', '333']
    $ python -m Pyjo 'n(lambda: x("<p>Hello</p>").at("p").text, 1000)'

A script that is read later can use the counterparts of the functions in
their modules, whose names say what they do: :func:`Pyjo.UserAgent.get` and
the other methods of HTTP, whose ``result`` the letters return, as
``Pyjo.UserAgent.get(url).result`` for ``g(url)``, :func:`Pyjo.DOM.new` for
:func:`Pyjo.x`, :func:`Pyjo.JSON.decode_json` and :func:`Pyjo.JSON.encode_json`
for :func:`Pyjo.j`, :func:`Pyjo.YAML.load_all` and :func:`Pyjo.YAML.dump_all`
for :func:`Pyjo.y`, and :func:`Pyjo.File.path` for :func:`Pyjo.f`.

You can continue with :doc:`index` now.
