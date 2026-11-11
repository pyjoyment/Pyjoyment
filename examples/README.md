# Examples

Short scripts that show what Pyjoyment does, grouped by the part of it they
use. A script with a `.pl` file next to it is the port of a Mojolicious
script, which shows the same thing in Perl.

## Layout

| Directory        | What it holds                                                                                          |
| ---------------- | ------------------------------------------------------------------------------------------------------ |
| `pyjo/`          | the toolkit: objects, events, URLs, the event loop, and TCP clients and servers on it                  |
| `pyjoyment/`     | applications of the framework, `Pyjoyment.Lite`                                                        |
| `mount/`         | applications of other frameworks, WSGI, ASGI, FastCGI, CGI and AWS Lambda, mounted in `Pyjoyment.Lite` |
| `servers/`       | applications on the servers of Pyjoyment, on ASGI, WSGI and CGI, and on AWS Lambda                     |
| `lambda/`        | an application of `Pyjoyment.Lite` as an event function of AWS Lambda, deployed with OpenTofu          |
| `lambda_stream/` | the same, with the responses that AWS Lambda streams through a Function URL                            |
| `lambda_zip/`    | the same, on a custom runtime with the ZIP files of `generate lambda-zip`                              |
| `ua/`            | the user agent: requests, web scraping, and a server and a user agent in one event loop                |

## Running

Run the scripts from the root of the repository with `uv run`, which runs them
with Pyjoyment of the checkout:

```sh
uv run python examples/pyjo/url.py
uv run python examples/ua/get.py https://github.com
```

An application of `Pyjoyment.Lite` takes a command, as `daemon`, which serves
it on <http://localhost:3000>:

```sh
uv run python examples/pyjoyment/hello.py daemon
```

A script that needs a library which Pyjoyment does not depend on, as the
servers of `hello_world_uvicorn.py` and `hello_world_werkzeug.py` or the
`dnspython` of `resolv_dns.py`, gets it from uv:

```sh
uv run --with uvicorn python examples/servers/hello_world_uvicorn.py
```

The frameworks that the scripts of `mount/` mount, as Flask, Starlette and the
MCP SDK, and Django of the scripts of `servers/`, are in the dependency group
`servers` of the project:

```sh
uv run --group servers python examples/mount/mount_mcp.py daemon
uv run --group servers python examples/servers/django_wsgi.py prefork -c 1 -r 1
```

The application of `aws/` serves a bucket with aiobotocore, the asynchronous AWS
SDK. Its options before the command have the names of the AWS CLI, `--bucket`,
`--profile`, `--region` and `--endpoint-url`, or the environment variables
`S3_BUCKET`, `AWS_PROFILE`, `AWS_REGION` and `AWS_ENDPOINT_URL` in their place:

```sh
uv run --with aiobotocore python examples/aws/s3.py --profile myprofile --bucket mybucket daemon
```

A script that needs a program which Pyjoyment does not run, as php-fpm for
`mount_fastcgi_php.py`, says how to start it in its comment:

```sh
(cd examples/mount && php-fpm -n -y php/php-fpm.conf -F) &
uv run python examples/mount/mount_fastcgi_php.py daemon
```

The application of `lambda/` runs as an event function of AWS Lambda, which its
OpenTofu deploys, with what it mounts, as PHP on php-fpm, as
[`lambda/README.md`](lambda/README.md) says, and the one of `lambda_stream/`
as a function of its own whose responses Lambda streams, as
[`lambda_stream/README.md`](lambda_stream/README.md) says, and the one of
`lambda_zip/` on a custom runtime, with Python in a layer, as
[`lambda_zip/README.md`](lambda_zip/README.md) says. All of them have
Pyjoyment in a layer of its own, of `generate lambda-zip`, which the functions
of the same Python share, or which a layer of Pyjoyment that is published
already replaces.

The tests in [`t/examples/`](../t/examples), in the same groups, check some of
the scripts, and the documentation shows them on its page of examples.
