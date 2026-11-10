# shellcheck shell=bash
# The steps that the variants of the smoke test share, which a variant
# sources: a temporary project, the wheel of the checkout, the image of
# "generate dockerfile" and its checks, and the TAP of the test, which
# Pyjo.Prove reads.

set -euo pipefail

# The TAP of the test on the standard output of the script, and the output of
# the commands, as of docker build, on its standard error, which Pyjo.Prove
# passes on as it comes
exec 3>&1 1>&2
tests=0

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
dir=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
name=pyjo-smoke-$(basename "$0" .sh)

# The containers, images and networks that a variant adds, which cleanup
# removes too
extra_cleanup() { :; }

cleanup() {
  status=$?
  if [[ ${status} -ne 0 ]] && docker inspect "${name}" >/dev/null 2>&1; then
    echo "--- logs of ${name}"
    docker logs "${name}" 2>&1 || true
  fi
  extra_cleanup
  docker rm -f "${name}" >/dev/null 2>&1 || true
  docker rmi -f "${name}" >/dev/null 2>&1 || true
  rm -rf "${work}"
  echo "1..${tests}" >&3
  exit "${status}"
}
trap cleanup EXIT

ok() {
  echo "ok $((tests += 1)) - $*" >&3
}

fail() {
  echo "not ok $((tests += 1)) - $*" >&3
  exit 1
}

# The modules of the checkout run the generators
export PYTHONPATH=${root}
unset PYJO_EXE PYJO_HOME

# The wheel of the checkout goes into the image, as the version that is tested
# is not on PyPI
uv build --wheel --quiet --out-dir "${work}/wheel" "${root}"
wheel=$(cd "${work}/wheel" && echo *.whl)
sources="[tool.uv.sources]
Pyjoyment = { path = \"${wheel}\" }"

mkdir "${work}/project"
cd "${work}/project"

# The dependencies of the project or of the script with the wheel of the
# checkout, locked
lock() {
  cp "${work}/wheel/${wheel}" .
  if [[ -f pyproject.toml ]]; then
    printf '\n%s\n' "${sources}" >>pyproject.toml
    uv lock --quiet
  else
    uv lock --quiet --script myapp.py
  fi
}

# The image of "generate dockerfile", with the wheel copied with the files of
# the dependencies, the only change of the generated Dockerfile
build_dockerfile() {
  [[ -f .dockerignore ]] || fail ".dockerignore"
  WHEEL=${wheel} perl -pi -e 's{^(COPY (?:pyproject\.toml|myapp\.py)\b.*) \./$}{$1 $ENV{WHEEL} ./}' Dockerfile
  grep -q "^COPY .*${wheel} \./$" Dockerfile || fail "wheel in Dockerfile"
  cat Dockerfile

  docker build --progress plain --tag "${name}" .
}

# The image of "generate dockerfile", with the wheel copied with the files of
# the dependencies, the only change of the generated Dockerfile, which exposes
# its port, serves the pages and stops gracefully on the TERM of docker stop
#
#   smoke_dockerfile [--user USER] [--expose PORT] [--port PORT] [--health PATH] [--compressed PATH] PAGE...
#
#   --expose PORT   the port of the image, of "generate dockerfile --port"
#   --port PORT     the port of PORT of the container, as Knative sets it
#   --health PATH   the path of the HEALTHCHECK of the image, which Docker
#                   reports healthy
#   --compressed PATH
#                   a file whose variants of brotli, zstd and gzip the image
#                   has, of "generate dockerfile --compress"
smoke_dockerfile() {
  local user='' expose=3000 listen=3000 health='' compressed=''
  local -a env=()
  while [[ ${1:-} == --* ]]; do
    case $1 in
      --user) user=$2 ;;
      --health) health=$2 ;;
      --compressed) compressed=$2 ;;
      --expose)
        expose=$2
        listen=$2
        ;;
      --port)
        listen=$2
        env=(--env "PORT=$2")
        ;;
      *) fail "unknown option $1" ;;
    esac
    shift 2
  done

  build_dockerfile
  local exposed
  exposed=$(docker inspect --format '{{range $port, $_ := .Config.ExposedPorts}}{{$port}} {{end}}' "${name}")
  [[ ${exposed} == "${expose}/tcp " ]] || fail "exposed ${exposed}"
  ok "exposed ${expose}"

  docker run --detach --name "${name}" "${env[@]}" --publish "127.0.0.1::${listen}" "${name}" >/dev/null
  local port url
  port=$(docker port "${name}" "${listen}/tcp" | perl -ne 'print $1 and last if /:(\d+)$/')
  url=http://127.0.0.1:${port}

  # The server listens once its workers are started
  for _ in $(seq 120); do
    curl --silent --fail --output /dev/null "${url}/" && break
    sleep 0.5
  done

  local page body
  for page in "$@"; do
    # The body read whole, as grep -q that stops reading it would fail the pipe
    # of curl with pipefail
    body=$(curl --silent --fail "${url}${page}") || fail "GET ${page}"
    grep -q 'Welcome to the Pyjoyment real-time web framework!' <<<"${body}" || fail "GET ${page}"
    ok "GET ${page}"
  done

  if [[ -n ${compressed} ]]; then
    local encoding headers
    for encoding in br zstd gzip; do
      headers=$(curl --silent --fail --header "Accept-Encoding: ${encoding}" --dump-header - --output /dev/null \
        "${url}${compressed}") || fail "GET ${compressed} with ${encoding}"
      grep -qi "^Content-Encoding: ${encoding}" <<<"${headers}" || fail "Content-Encoding ${encoding} of ${compressed}"
      grep -qi '^Vary: Accept-Encoding' <<<"${headers}" || fail "Vary of ${compressed}"
      ok "GET ${compressed} with ${encoding}"
    done
    body=$(curl --silent --fail --header 'Accept-Encoding: gzip' "${url}${compressed}" | gzip -d) ||
      fail "GET ${compressed} decompressed"
    [[ ${body} == "$(<"public${compressed}")" ]] || fail "body of ${compressed}"
    ok "GET ${compressed} decompressed"
  fi

  if [[ -n ${user} ]]; then
    local config
    config=$(docker inspect --format '{{.Config.User}}' "${name}")
    [[ ${config} == "${user}" ]] || fail "user ${config}"
    ok "user ${config}"
  fi

  healthy "${health}"

  stop_gracefully
}

# The HEALTHCHECK of the image requests the path, and Docker reports the
# container healthy, or the image has none
healthy() {
  local health=$1 test status
  test=$(docker inspect --format '{{if .Config.Healthcheck}}{{json .Config.Healthcheck.Test}}{{end}}' "${name}")
  if [[ -z ${health} ]]; then
    [[ -z ${test} ]] || fail "healthcheck ${test}"
    ok "no healthcheck"
    return
  fi
  grep -qF "c.request('GET', '${health}')" <<<"${test}" || fail "healthcheck ${test}"
  for _ in $(seq 60); do
    status=$(docker inspect --format '{{.State.Health.Status}}' "${name}")
    [[ ${status} == healthy ]] && break
    sleep 0.5
  done
  [[ ${status} == healthy ]] || fail "health ${status}"
  ok "healthy with ${health}"
}

# TERM of docker stop is a graceful shutdown, well before the KILL after 10
# seconds
stop_gracefully() {
  local start elapsed code
  start=${SECONDS}
  docker stop --time 10 "${name}" >/dev/null
  elapsed=$((SECONDS - start))
  [[ ${elapsed} -lt 5 ]] || fail "stopped in ${elapsed}s"
  code=$(docker inspect --format '{{.State.ExitCode}}' "${name}")
  [[ ${code} -eq 0 ]] || fail "exit code ${code}"
  ok "stopped gracefully in ${elapsed}s"
}

# The emulator of the Runtime API of AWS Lambda on the port invoked with the
# event of a file, buffered or with --stream
#
#   invoke_event PORT EVENT [--stream]
invoke_event() {
  local test="invoke with ${2##*/}${3:+ streaming}"
  python "${dir}/invoke.py" "${@:3}" "http://127.0.0.1:$1/2015-03-31/functions/function/invocations" "$2" ||
    fail "${test}"
  ok "${test}"
}
