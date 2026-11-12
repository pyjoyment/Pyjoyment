# A streaming event function of AWS Lambda

`function/app.py` is an application of `Pyjoyment.Lite` whose responses AWS
Lambda streams through a Function URL, as they are written, which the OpenTofu
of this directory deploys, with the ZIP files of `generate lambda-zip
--runtime`: the function with `app.py` and `wrapper.py`, with the public layer
of Pyjoyment or the one of its own build, with a Function URL of the invoke
mode `RESPONSE_STREAM`.
`/count` writes a line every half a second, which comes to the client as it is
written.

The runtime of Python of Lambda does not stream, so `wrapper.py`, which
`AWS_LAMBDA_EXEC_WRAPPER` names, runs the runtime client of
`Pyjo.Server.Lambda` in its place, and `PYJO_LAMBDA_INVOKE_MODE` tells the
application the invoke mode of the Function URL, which the function does not
learn from its invocations. Both have to agree with `invoke_mode` of the
Function URL. The runtime puts the layer in the path of Python only for its
own runtime client, so `PYTHONPATH` names the site-packages of the layer for
the one of the wrapper.

The application is the directory `function`, as the generator puts every file
of the current directory into `function.zip`, which would take the state of
OpenTofu too. The inline metadata of the script takes Pyjoyment of the
checkout.

## Running locally

The same script runs as an application of its own:

```sh
uv run python examples/lambda_stream/function/app.py daemon
curl -N http://127.0.0.1:3000/count
```

and as a streaming event function under `Pyjo.App.Lambda`, as its test does:

```sh
uv run python -m Pyjo.Prove -l t/examples/lambda_stream/app.py
```

## Deploying to AWS

The function takes the public layer of Pyjoyment of
[Pyjoyment-Lambda-Layers](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers),
with `function.zip` alone, which `--function-only` writes to `function/dist`,
for the runtime of the variable `runtime`, `python3.15` by default, and the
architecture of the function, `arm64`:

```sh
uv run --directory examples/lambda_stream/function python app.py generate lambda-zip --arch arm64 --runtime python3.15 --function-only
```

OpenTofu 1.13 deploys it with the credentials and the region of the default
chain of AWS, as `AWS_PROFILE` and `AWS_REGION`, and a new build of the same
files changes nothing:

```sh
tofu -chdir=examples/lambda_stream init
tofu -chdir=examples/lambda_stream apply
```

The ARN of the layer of the version of Python of the runtime and of the region
comes from the index of the latest release, `layers.json`, which `data "http"`
reads and `jsondecode` turns into `{layer: {region: arn}}`. The generator tells
the version of Pyjoyment of the dependencies, which the description of the
layer says too: the inline metadata of the script takes Pyjoyment of the
checkout, which can be newer than the one of the latest release.

`-var pyjoyment_version=0.3.0` takes the layer of the latest release of that
version of Pyjoyment, `pyjoyment-0_3_0-python3_15`, for a function of the
checkout of an older version. Its release is the latest one whose tag has the
version and the date, as `0.3.0+2026.11.05`, in the list of the API of GitHub,
which answers 60 requests an hour of an address without a token. The layers of
a version come after its release, so the checkout of a version that is not
released yet takes the layers of its own build.

`-var public_layers=false` takes the layer of the build in the place of the
public one, which the generator writes without `--function-only`:

```sh
uv run --directory examples/lambda_stream/function python app.py generate lambda-zip --arch arm64 --runtime python3.15
tofu -chdir=examples/lambda_stream apply -var public_layers=false
```

`-var pyjoyment_layer=ARN` takes another layer of Pyjoyment that is published
already, for the same Python, in the place of the public one or of
`function/dist/pyjoyment.zip`.

The output `url` is the Function URL, which the test takes in
`TEST_LAMBDA_STREAM_URL`:

```sh
curl -N "$(tofu -chdir=examples/lambda_stream output -raw url)/count"
TEST_LAMBDA_STREAM_URL=$(tofu -chdir=examples/lambda_stream output -raw url) \
  uv run python -m Pyjo.Prove -l t/examples/lambda_stream/app.py
```

The resources go away with:

```sh
tofu -chdir=examples/lambda_stream destroy
```
