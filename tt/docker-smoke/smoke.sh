#!/usr/bin/env bash
# Smoke test of the images of Pyjoyment: runs the script of a variant, which
# generates an application, builds its image with the wheel of the checkout,
# runs it and checks it, under Pyjo.Prove, which reads its TAP and takes the
# options that follow the variant, as its formatters. The only entry point of
# the workflow Docker Smoke Test.
#
# Usage: tt/docker-smoke/smoke.sh app|lite|lite-pep723|lambda|lambda-stream|lambda-image|lambda-zip|fastcgi|kubernetes [OPTION...]
#
#   app           generate app, run as python -m MyApp, with --user app
#   lite          generate lite-app, with generate pyproject
#   lite-pep723   generate lite-app, with the inline metadata of PEP 723
#   lambda        generate lite-app, with handler = app.start(), on AWS Lambda
#   lambda-stream the same, streaming its responses, with the runtime client of
#                 Pyjo.Server.Lambda
#   lambda-image  generate lite-app, in an image of generate dockerfile --target
#                 lambda, as its own runtime, under the emulator of the Runtime
#                 API
#   lambda-zip    generate lite-app, in the ZIP files of generate lambda-zip, on
#                 the custom runtime provided.al2023, under the emulator of the
#                 Runtime API
#   fastcgi       generate lite-app, listening for FastCGI, behind Caddy
#   kubernetes    generate lite-app, in the manifests of generate kubernetes,
#                 dev with a ConfigMap, dev with --host-path and prod, on a
#                 cluster of kind of its own
#
# It needs docker, python and uv on PATH, as "mise exec --" gives them, and
# kind and kubectl for the variant kubernetes.

set -euo pipefail

variant=${1:?Usage: $0 app|lite|lite-pep723|lambda|lambda-stream|lambda-image|lambda-zip|fastcgi|kubernetes}
dir=$(cd "$(dirname "$0")" && pwd)

[[ ${variant} =~ ^[a-z0-9-]+$ && -x ${dir}/${variant}.sh ]] || {
  echo "unknown variant ${variant}" >&2
  exit 1
}

# The path of the script from the root of the checkout, as the reports name it
cd "${dir}/../.."
exec python -m Pyjo.Prove -l -v --ext .sh --exec bash "${@:2}" "tt/docker-smoke/${variant}.sh"
