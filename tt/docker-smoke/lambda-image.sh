#!/usr/bin/env bash
# A script of generate lite-app that ends with handler = app.start(), in an
# image of "generate dockerfile --target lambda", whose command is the runtime
# of the function itself, run by the emulator of the Runtime API, which the
# image does not have, of the release of RIE_VERSION, as 1.37, or the latest
# one, and invoked with the events of HTTP requests, buffered and streaming.

# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

# The containers of the two invoke modes
extra_cleanup() {
  docker rm -f "${name}-stream" >/dev/null 2>&1 || true
}

# The script, which is the runtime as the main program
python -m Pyjoyment generate lite-app >/dev/null
perl -pi -e 's/^app\.start\(\)$/handler = app.start()/' myapp.py
grep -q '^handler = app.start()$' myapp.py || fail "handler in myapp.py"
python myapp.py generate pyproject >/dev/null
lock
python myapp.py generate dockerfile --target lambda >/dev/null
build_dockerfile

# The emulator for the architecture of Docker
case $(docker info --format '{{.Architecture}}') in
  aarch64 | arm64) suffix=-arm64 ;;
  *) suffix='' ;;
esac
release=${RIE_VERSION:+download/v${RIE_VERSION}}
curl --silent --show-error --fail --location --output "${work}/aws-lambda-rie" \
  "https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/${release:-latest/download}/aws-lambda-rie${suffix}"
chmod 755 "${work}/aws-lambda-rie"

# The command of the image as the bootstrap of the emulator
mapfile -t cmd < <(docker image inspect --format '{{json .Config.Cmd}}' "${name}" | python -c 'import json, sys; print(*json.load(sys.stdin), sep="\n")')
[[ ${cmd[*]} == 'python myapp.py' ]] || fail "command ${cmd[*]}"
ok "command ${cmd[*]}"

for mode in BUFFERED RESPONSE_STREAM; do
  container=${name}
  [[ ${mode} == BUFFERED ]] || container=${name}-stream
  docker run --detach --name "${container}" --publish 127.0.0.1::8080 --env "PYJO_LAMBDA_INVOKE_MODE=${mode}" \
    --volume "${work}/aws-lambda-rie:/aws-lambda-rie:ro" --entrypoint /aws-lambda-rie "${name}" "${cmd[@]}" >/dev/null
  port=$(docker port "${container}" 8080/tcp | perl -ne 'print $1 and last if /:(\d+)$/')

  # The events of the payload formats 2.0, of Function URLs, and 1.0, of REST
  # APIs with a stage
  for event in "${dir}"/events/*.json; do
    if [[ ${mode} == BUFFERED ]]; then
      invoke_event "${port}" "${event}"
    else
      invoke_event "${port}" "${event}" --stream
    fi
  done
done
