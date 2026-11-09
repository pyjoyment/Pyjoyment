#!/usr/bin/env bash
# A script of generate lite-app, with the pyproject.toml of generate
# pyproject, in the image of generate dockerfile, which speaks FastCGI to Caddy
# in front of it.

# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
caddy=${name}-caddy

extra_cleanup() {
  if [[ ${status} -ne 0 ]] && docker inspect "${caddy}" >/dev/null 2>&1; then
    echo "--- logs of ${caddy}"
    docker logs "${caddy}" 2>&1 || true
  fi
  docker rm -f "${caddy}" >/dev/null 2>&1 || true
  docker rmi -f "${caddy}" >/dev/null 2>&1 || true
  docker rm -f "${name}" >/dev/null 2>&1 || true
  docker network rm "${name}" >/dev/null 2>&1 || true
}

python -m Pyjoyment generate lite-app >/dev/null
python myapp.py generate pyproject >/dev/null
lock
# No HEALTHCHECK, whose request of HTTP the application, which speaks FastCGI,
# does not answer
python myapp.py generate dockerfile --healthcheck '' >/dev/null
build_dockerfile

# The application listens for FastCGI on the network that it shares with Caddy
docker network create "${name}" >/dev/null
docker run --detach --name "${name}" --network "${name}" --network-alias app \
  --env 'PYJO_LISTEN=fcgi://*:3000' "${name}" >/dev/null

cp "${dir}/Dockerfile.caddy" "${dir}/Caddyfile" "${work}/"
docker build --progress plain --file "${work}/Dockerfile.caddy" --tag "${caddy}" "${work}"
docker run --detach --name "${caddy}" --network "${name}" --publish 127.0.0.1::8080 "${caddy}" >/dev/null
port=$(docker port "${caddy}" 8080/tcp | perl -ne 'print $1 and last if /:(\d+)$/')
url=http://127.0.0.1:${port}

# The application answers once its workers are started
for _ in $(seq 120); do
  curl --silent --fail --output /dev/null "${url}/" && break
  sleep 0.5
done

# The body read whole, as grep -q that stops reading it would fail the pipe of
# curl with pipefail
body=$(curl --silent --fail "${url}/") || fail "GET /"
grep -q 'Welcome to the Pyjoyment real-time web framework!' <<<"${body}" || fail "GET /"
ok "GET /"

headers=$(curl --silent --head "${url}/") || fail "HEAD /"
grep -qi '^Server: Pyjoyment' <<<"${headers}" || fail "HEAD / served by Pyjoyment"
ok "HEAD /"

code=$(curl --silent --output /dev/null --write-out '%{http_code}' "${url}/missing")
[[ ${code} -eq 404 ]] || fail "GET /missing ${code}"
ok "GET /missing 404"

code=$(curl --silent --output /dev/null --write-out '%{http_code}' --data 'name=Pyjoyment' "${url}/")
[[ ${code} -eq 404 ]] || fail "POST / ${code}"
ok "POST / 404"

stop_gracefully
