# An event function of AWS Lambda

`function/app.py` is an application of `Pyjoyment.Lite` that runs as an event
function of AWS Lambda on the runtime of Python, which the OpenTofu of this
directory deploys, with the ZIP files of `generate lambda-zip --runtime`: the
function with `app.py` and `phpinfo.php`, with the public layer of Pyjoyment or
the one of its own build, with a Function URL, and behind an Application Load
Balancer on request.

The application is the directory `function`, as the generator puts every file
of the current directory into `function.zip`, which would take the state of
OpenTofu too. The inline metadata of the script takes Pyjoyment of the
checkout.

## Running locally

The same script runs as an application of its own:

```sh
uv run python examples/lambda/function/app.py daemon
```

and as an event function, with the events of Lambda, under `Pyjo.App.Lambda`,
as its test does:

```sh
uv run python -m Pyjo.Prove -l t/examples/lambda/app.py
```

## Deploying to AWS

The function takes the public layer of Pyjoyment of
[Pyjoyment-Lambda-Layers](https://github.com/pyjoyment/Pyjoyment-Lambda-Layers),
with `function.zip` alone, which `--function-only` writes to `function/dist`,
for the runtime of the variable `runtime`, `python3.15` by default, and the
architecture of the function, `arm64`:

```sh
uv run --directory examples/lambda/function python app.py generate lambda-zip --arch arm64 --runtime python3.15 --function-only
```

OpenTofu 1.13 deploys it with the credentials and the region of the default
chain of AWS, as `AWS_PROFILE` and `AWS_REGION`, or of the profile of
`-var aws_profile=NAME`, and a new build of the same files changes nothing:

```sh
tofu -chdir=examples/lambda init
tofu -chdir=examples/lambda apply
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
uv run --directory examples/lambda/function python app.py generate lambda-zip --arch arm64 --runtime python3.15
tofu -chdir=examples/lambda apply -var public_layers=false
```

`-var pyjoyment_layer=ARN` takes another layer of Pyjoyment that is published
already, for the same Python, in the place of the public one or of
`function/dist/pyjoyment.zip`.

The output `url` is the Function URL, which the test takes in
`TEST_LAMBDA_URL`:

```sh
TEST_LAMBDA_URL=$(tofu -chdir=examples/lambda output -raw url) \
  uv run python -m Pyjo.Prove -l t/examples/lambda/app.py
```

`-var alb=true` puts the function behind an Application Load Balancer in the
default VPC too, which costs for each hour it runs, where the Function URL
costs nothing while it waits. Its URL is the output `alb_url`, which the test
takes in `TEST_LAMBDA_ALB_URL`:

```sh
tofu -chdir=examples/lambda apply -var alb=true
TEST_LAMBDA_ALB_URL=$(tofu -chdir=examples/lambda output -raw alb_url) \
  uv run python -m Pyjo.Prove -l t/examples/lambda/app.py
```

The resources go away with:

```sh
tofu -chdir=examples/lambda destroy
```

## PHP

The function runs what Pyjoyment mounts, also PHP on php-fpm. The layer of PHP
of [Bref](https://bref.sh) has it, and `app.py` starts it with the execution
environment and serves `phpinfo.php` under `/php` with `Pyjo.App.FastCGI`. The
variable `layers` adds the layer, which is in its default, commented out, or
in a `terraform.tfvars` of this directory, which git ignores:

```hcl
layers = [
  "arn:aws:lambda:eu-central-1:873528684822:layer:arm-php-85:21",
]
```

Locally, `PHP_FPM` names the php-fpm to start:

```sh
PHP_FPM=$(command -v php-fpm) uv run python examples/lambda/function/app.py daemon
```
