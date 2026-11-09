#!/usr/bin/env bash
# A script of generate lite-app that ends with handler = app.start(), as an
# event function in the image of AWS Lambda for Python, whose emulator of the
# Runtime API is invoked with the events of HTTP requests.

# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

# The script, whose runtime it detects
python -m Pyjoyment generate lite-app >/dev/null
perl -pi -e 's/^app\.start\(\)$/handler = app.start()/' myapp.py
grep -q '^handler = app.start()$' myapp.py || fail "handler in myapp.py"

cp "${work}/wheel/${wheel}" "${dir}/Dockerfile.lambda" .
docker build --progress plain --file Dockerfile.lambda --build-arg "WHEEL=${wheel}" --tag "${name}" .
docker run --detach --name "${name}" --publish 127.0.0.1::8080 "${name}" >/dev/null
port=$(docker port "${name}" 8080/tcp | perl -ne 'print $1 and last if /:(\d+)$/')

# The events of the payload formats 2.0, of Function URLs, and 1.0, of REST
# APIs with a stage
for event in "${dir}"/events/*.json; do
  invoke_event "${port}" "${event}"
done
