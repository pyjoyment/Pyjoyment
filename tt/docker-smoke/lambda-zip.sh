#!/usr/bin/env bash
# A script of generate lite-app that ends with handler = app.start(), in the
# ZIP files of "generate lambda-zip" for the architecture of Docker, extracted
# where Lambda extracts them in the image of the custom runtime provided.al2023,
# the layers of Python and of Pyjoyment in /opt and the function in /var/task,
# whose emulator of the Runtime API runs the bootstrap of the function, invoked
# with the events of HTTP requests, buffered and streaming, and whose Python
# finds the certificates of the system and Pyjoyment of its layer, and in the
# ZIP files of "generate lambda-zip --runtime python3.14" in the image of the
# runtime of Python, whose runtime client puts the same layer in its path, as
# the function has no Pyjoyment of its own.

# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
image=public.ecr.aws/lambda/provided:al2023

# The containers of the two invoke modes and of the runtime of Python
extra_cleanup() {
  docker rm -f "${name}-stream" "${name}-python" >/dev/null 2>&1 || true
}

# The events of the payload formats 2.0, of Function URLs, and 1.0, of REST
# APIs with a stage, buffered or streaming
invoke() {
  local port
  port=$(docker port "$1" 8080/tcp | perl -ne 'print $1 and last if /:(\d+)$/')
  for event in "${dir}"/events/*.json; do
    invoke_event "${port}" "${event}" "${@:2}"
  done
}

# The script, which is the runtime as the main program
python -m Pyjoyment generate lite-app >/dev/null
perl -pi -e 's/^app\.start\(\)$/handler = app.start()/' myapp.py
grep -q '^handler = app.start()$' myapp.py || fail "handler in myapp.py"
python myapp.py generate pyproject >/dev/null
lock

case $(docker info --format '{{.Architecture}}') in
  aarch64 | arm64) arch=arm64 ;;
  *) arch=x86_64 ;;
esac
python myapp.py generate lambda-zip --arch "${arch}"

mkdir "${work}/opt" "${work}/task"
unzip -q dist/python.zip -d "${work}/opt"
unzip -q dist/pyjoyment.zip -d "${work}/opt"
unzip -q dist/function.zip -d "${work}/task"
[[ ! -e ${work}/task/Pyjoyment ]] || fail "Pyjoyment in the function"
[[ -x ${work}/task/bootstrap ]] || fail "bootstrap"
cat "${work}/task/bootstrap"
interpreter=$(perl -ne 'print $1 if m{^exec (/opt/python/bin/\S+) myapp\.py$}' "${work}/task/bootstrap")
[[ -n ${interpreter} && -x ${work}${interpreter} ]] || fail "interpreter of the bootstrap"
ok "bootstrap with ${interpreter}"

for mode in BUFFERED RESPONSE_STREAM; do
  container=${name}
  [[ ${mode} == BUFFERED ]] || container=${name}-stream
  docker run --detach --name "${container}" --publish 127.0.0.1::8080 --env "PYJO_LAMBDA_INVOKE_MODE=${mode}" \
    --volume "${work}/opt:/opt:ro" --volume "${work}/task:/var/task:ro" \
    --entrypoint /usr/local/bin/aws-lambda-rie "${image}" /var/task/bootstrap >/dev/null
  if [[ ${mode} == BUFFERED ]]; then
    invoke "${container}"
  else
    invoke "${container}" --stream
  fi
done

# The OpenSSL of python-build-standalone reads the certificates of /etc/ssl,
# which Amazon Linux links to its own
docker exec "${name}" "${interpreter}" -c \
  'import ssl, sys; sys.exit(not ssl.create_default_context().cert_store_stats()["x509_ca"])' ||
  fail "certificates of the system"
ok "certificates of the system"

# Pyjoyment of the layer, in the site-packages of the Python of the layer
site=/opt/python/lib/${interpreter##*/}/site-packages
docker exec "${name}" "${interpreter}" -c 'import Pyjoyment; print(Pyjoyment.__file__)' |
  grep -qx "${site}/Pyjoyment/__init__.py" || fail "Pyjoyment of the layer"
ok "Pyjoyment of the layer"

# The runtime of Python, with the handler of the script and the layer of
# Pyjoyment in the site-packages of its version, which only its runtime client
# puts in the path, so that the invocations tell that it finds Pyjoyment there
python myapp.py generate lambda-zip --arch "${arch}" --runtime python3.14
[[ ! -e dist/python.zip ]] || fail "no layer of Python"
mkdir -p "${work}/python/opt" "${work}/python/task"
unzip -q dist/pyjoyment.zip -d "${work}/python/opt"
unzip -q dist/function.zip -d "${work}/python/task"
[[ ! -e ${work}/python/task/bootstrap && ! -e ${work}/python/task/Pyjoyment ]] || fail "only the application in the function"
docker run --detach --name "${name}-python" --publish 127.0.0.1::8080 \
  --volume "${work}/python/opt:/opt:ro" --volume "${work}/python/task:/var/task:ro" \
  public.ecr.aws/lambda/python:3.14 myapp.handler >/dev/null
invoke "${name}-python"
