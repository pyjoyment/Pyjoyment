---
name: deploy
description: Run and deploy a Pyjoyment application. Use for its servers (daemon, prefork, prethread, the zero downtime of pyjo-hot, pyjo-reload in development), their options and PYJO_* variables, reverse proxies and TLS, graceful stops and the Health plugin for probes, the Cache-Control and the precompressed gzip, brotli and zstd variants of the static files, and the generators of a pyproject.toml, a Dockerfile, the manifests of Kubernetes and the ZIP files of AWS Lambda, and WSGI, ASGI and FastCGI servers in front of it.
---

# Deployment

An application of Pyjoyment serves HTTP and WebSockets with its own servers,
which its commands start, `python app.py daemon` or `python -m MyApp
prefork`. An option of a server has a variable of its own, `PYJO_` and its
name, as `PYJO_WORKERS` for `--workers`, so the environment of a container
configures it without its command line. The generators write the files of a
deployment for the application: `pyproject.toml`, a `Dockerfile`, the
manifests of Kubernetes, and the ZIP files of AWS Lambda.

## The application

```python
# app.py
import os

from Pyjoyment.Lite import *


# The secret of the sessions from the environment of the deployment, not from the code
app.secrets = [os.environ.get('APP_SECRET', 'Change this secret')]

# /livez and /healthz while the server answers, /readyz once the checks pass, for the probes of an orchestrator
ready = {'db': True}
plugin('Health', checks={'db': lambda c: ready['db']})


@get('/')
def index(c):
    c.render(text=f'Hello from {app.mode}')


app.start()
```

## Servers

```sh
pyjo-reload app.py                                 # development, restarts when the files change
python -m MyApp reload                             # the same, as a command, watching the package too
python app.py daemon -l 'http://*:8080'            # one process
python app.py prefork -w 8 -l 'http://*:8080'      # eight worker processes, for code that blocks too
python app.py prethread -w 8                       # eight worker threads, on every core with a free-threaded Python
pyjo-hot app.py                                    # prefork, which HUP replaces with zero downtime
PYJO_MODE=production PYJO_WORKERS=8 PYJO_LISTEN='http://*:8080' python app.py prefork
python app.py prefork -p -l 'http://127.0.0.1:8080'           # behind a reverse proxy, X-Forwarded-For
python app.py daemon -l 'https://*:443?cert=./server.crt&key=./server.key'
```

- `-m production` or `PYJO_MODE=production` hides the details of the
  exception pages, and a plugin of configuration reads `myapp.production.yml`; `PORT` of a platform, as
  Cloud Run or Knative, is the port when `-l` and `PYJO_LISTEN` are not given.
- INT and TERM stop gracefully, waiting for the requests in progress up to
  `--graceful-timeout` (25 seconds), and `--shutdown-delay` (`PYJO_SHUTDOWN_DELAY`)
  keeps serving with a failing `/readyz` before, so that a load balancer moves
  away first; QUIT stops at once, and HUP restarts the workers of `prefork`.
- `-c` limits the connections of a worker, `-c 1` serves one request at a
  time, for an application whose code blocks.

## Containers, Kubernetes and AWS Lambda

```sh
python app.py generate pyproject                   # the project of uv, with the dependencies of the script
python app.py generate dockerfile -p 8080          # Dockerfile and .dockerignore, prefork with a HEALTHCHECK of /livez
python app.py generate kubernetes -i myapp         # kubernetes/base, dev and prod for Kustomize
python app.py generate lambda-zip                  # the ZIP files of a function and of its layers
python app.py generate lambda-zip --function-only  # the function alone, for the public layers
docker build -t myapp . && docker run -p 8080:8080 myapp
kubectl apply -k kubernetes/prod
```

- The `Dockerfile` runs `prefork` on `PORT`, with a `HEALTHCHECK` of
  `/livez`; `--graceful-timeout` and `--user` adjust it, and `--target lambda`
  makes an image of AWS Lambda.
- `kubernetes/dev` runs the files of the project from a ConfigMap on the image
  of uv, `kubernetes/prod` the image of `-i`, with the probes of `/livez` and
  `/readyz` and the graceful stop of the pods.
- On AWS Lambda the script ends with `handler = app.start()`: the runtime of
  Python calls `app.handler`, and a custom runtime runs the script itself.
- The public layers of
  [Pyjoyment-Lambda-Layers](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers),
  as `python3_14-arm64` of Python for `provided.al2023` and
  `pyjoyment-python3_14` of Pyjoyment, also for the runtime `python3.14`, are
  taken by the ARN of a version, which the index of the latest release gives:
  `python -m Pyjo 'g("https://github.com/pyjoyment/Pyjoyment-Lambda-Layers/releases/latest/download/layers.json").json("/pyjoyment-python3_14/eu-central-1")'`.
  `--function-only` tells the version of Pyjoyment of the dependencies, which
  the layer of Pyjoyment is to have.

## Precompressed static files

Static files are served as they are; `renderer.compress` gzips only the
content that the application generates. Compress the static files at the
build, next to the originals, and `Pyjoyment.Static` serves a variant to the
clients whose `Accept-Encoding` takes it, as nginx `gzip_static` would:

```sh
find public -type f -size +1k \( -name '*.css' -o -name '*.js' -o -name '*.svg' \) \
  -exec gzip -k -f -9 -n {} + -exec brotli -k -f -q 11 {} + -exec zstd -q -k -f -19 {} +
python app.py generate dockerfile --compress public   # gzip variants written in the image
python app.py generate dockerfile -a brotli -a zstd -c public   # and brotli and zstd of the packages of Debian
python app.py generate lambda-zip --compress public  # variants in function.zip, with the compressors of the machine
python app.py generate lambda-zip -c public -e br -e gzip   # only the encodings that CloudFront forwards
```

- `app.static.encodings`, `{'br': '.br', 'zstd': '.zst', 'gzip': '.gz'}` by
  default, gives the extensions and the order of preference; `{}` turns it
  off. The variant gets `Content-Encoding`, the `Content-Type` of the file, an
  `ETag` of its own, and every response of the file `Vary: Accept-Encoding`.
- Compress the formats of text: CSS, JavaScript (`.js`, `.mjs`), JSON, source
  maps, SVG, HTML, plain text, CSV, XML, WebAssembly, TTF and OTF fonts.
- Do not compress what is compressed already, whose variant is only larger:
  PNG, JPEG, GIF, WebP and AVIF images, video, audio, WOFF and WOFF2 fonts,
  PDF, and archives (`.zip`, `.gz`, `.br`, `.zst`). Skip files under about a
  kilobyte, and remove a variant that is not smaller than its file.
- `generate dockerfile --compress` writes the variants in the image, of the
  formats of text or of `--compress-pattern`: `.gz` always, `.br` and `.zst`
  when `--apt-package brotli --apt-package zstd` installs the tools, which the
  image of Python lacks; otherwise write them before the build, and the image
  copies them.
- `generate lambda-zip --compress` writes them into `function.zip`: `.gz`
  always, `.zst` with Python 3.14 or the command `zstd`, `.br` with the
  command `brotli` of the machine that builds it.
- `--compress-encoding` (`-e`) of both generators, repeatable, writes only the
  encodings that the clients get, as `br` and `gzip` behind CloudFront, which
  normalizes `Accept-Encoding` to them: a `.zst` there is never served. An
  encoding of the option without its compressor fails the build. The names
  are the ones of `app.static.encodings`, which the application sets to the
  same, as `{'br': '.br', 'gzip': '.gz'}`, to look for no other variant.
- `app.static.immutable`, a regular expression of the paths of names with a
  hash of their content, as `r'^assets/.+\.[0-9a-f]{8,}\.[^/]+$'`, serves
  them with `Cache-Control: public, max-age=31536000, immutable`, and
  `app.static.cache_control`, a string or a function of `(c, rel)`, the other
  files, as `'public, max-age=60'`; without them, browsers revalidate every
  file at every page view.
- A variant older than its file is ignored, so a build that changes a file
  without compressing it again serves the file; keep the mtime of the file
  (`gzip -k`, `brotli -k` and `zstd -k` copy it). A `Range` request gets the
  file.

## WSGI, ASGI and FastCGI servers

```sh
PYJO_WSGI=1 gunicorn app:application               # the script ends with application = app.start()
PYJO_ASGI=1 uvicorn app:application
PYJO_LISTEN='fcgi://127.0.0.1:9000' python app.py daemon    # FastCGI behind nginx or Caddy
```

- Through WSGI the event loop serves one request at a time of each worker of
  the server, and WebSockets need the servers of Pyjoyment or ASGI.

## Mistakes

- `daemon` in production serves with one process, without restarting a
  worker that stops; `prefork` restarts its workers.
- `app.secrets` committed with the code signs the cookies of every
  deployment: take it from the environment or the configuration.
- `/readyz` with the checks of a database in the liveness probe restarts the
  containers when the database is down: liveness is `/livez`.
- A blocking request handler under `daemon` blocks every connection: more
  workers of `prefork`, `-c 1`, or code that does not block.
- The log goes to the standard error, which a container, Kubernetes and AWS
  Lambda collect as it is written; `PYJO_LOG_FORMAT=json` makes each line
  JSON for a collector of logs, and `PYJO_LOG_LEVEL` its level. `print` goes
  to the standard output, which is buffered in blocks there, without a level.

## Documentation

- Cookbook, deployment: https://pyjoyment.readthedocs.io/en/stable/guides/cookbook.html
- Pyjoyment.Plugin.Health: https://pyjoyment.readthedocs.io/en/stable/api/Pyjoyment_Plugin_Health.html
- Pyjo.Server.Prefork: https://pyjoyment.readthedocs.io/en/stable/api/Pyjo_Server_Prefork.html
- generate dockerfile: https://pyjoyment.readthedocs.io/en/stable/api/Pyjoyment_Command_Author_generate_dockerfile.html
- Rendering, precompressed static files: https://pyjoyment.readthedocs.io/en/stable/guides/rendering.html#precompressed-static-files
