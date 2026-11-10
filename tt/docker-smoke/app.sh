#!/usr/bin/env bash
# An application of generate app, run as python -m MyApp, with --user app and
# the graceful timeout of the image, which the workers of prefork take, and
# the plugin Health of the application, whose liveness the HEALTHCHECK of the
# image requests, and the variants of --compress, with brotli and zstd of
# --apt-package.

# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

python -m Pyjoyment generate app >/dev/null
cd my_app
grep -q "self.plugin('Health')" MyApp/__init__.py || fail "plugin Health"
lock
# A stylesheet large enough for the variants that the image writes, with brotli
# and zstd of its packages
perl -e 'print "body { color: #333 }\n" x 100' >public/app.css
python -m MyApp generate dockerfile --user app --graceful-timeout 8 \
  --apt-package brotli --apt-package zstd --compress public >/dev/null
smoke_dockerfile --user app --health /livez --compressed /app.css / /index.html

# The workers stopped with the graceful timeout of PYJO_GRACEFUL_TIMEOUT of the
# image, in the logs that are read whole, as grep -q that stops reading them
# would fail the pipe of docker logs with pipefail
logs=$(docker logs "${name}" 2>&1)
grep -q 'gracefully (8 seconds)' <<<"${logs}" || fail "graceful timeout"
ok "graceful timeout of the image"
