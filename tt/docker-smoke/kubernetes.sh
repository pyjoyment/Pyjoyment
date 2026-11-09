#!/usr/bin/env bash
# A script of generate lite-app, with its plugin Health, in the manifests of
# generate kubernetes, on a cluster of kind of its own: dev with the
# application in a ConfigMap, dev with --host-path and prod on the image of
# generate dockerfile, each in a namespace of its own. The wheel of the
# checkout is larger than a ConfigMap holds, so the script of dev takes it from
# /wheel, which an overlay of the test mounts over the one of dev. kind and
# kubectl come from PATH, and KIND_NODE_IMAGE names the image of the node.

# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

# The directories that the node mounts, at the same paths, for --host-path
work=$(cd "${work}" && pwd -P)
cluster=${name}
export KUBECONFIG=${work}/kubeconfig
kube=(kubectl --context "kind-${cluster}")

extra_cleanup() {
  if [[ ${status} -ne 0 ]] && [[ -f ${KUBECONFIG} ]]; then
    local ns
    for ns in dev host-path prod; do
      echo "--- ${ns}"
      "${kube[@]}" --namespace "${ns}" get all 2>&1 || true
      "${kube[@]}" --namespace "${ns}" logs --all-containers --prefix --selector app.kubernetes.io/name=myapp 2>&1 || true
    done
  fi
  kind delete cluster --name "${cluster}" >/dev/null 2>&1 || true
}

# The application: a page of its own, which a change of the script changes
generate_app() {
  local wheel_path=$1
  python -m Pyjoyment generate lite-app >/dev/null
  METADATA="# /// script
# requires-python = \">=3.12\"
# dependencies = [\"Pyjoyment\"]
#
# [tool.uv.sources]
# Pyjoyment = { path = \"${wheel_path}\" }
# ///" perl -0pi -e 's/\A(#!.*\n)/$1$ENV{METADATA}\n/' myapp.py
  grep -q "^plugin('Health')$" myapp.py || fail "plugin Health"
}

# The page of the application through its Service, requested from its own
# pod, whose image has Python, has the text, after a while for a change
page_has() {
  local ns=$1 text=$2 body=''
  for _ in $(seq 60); do
    body=$("${kube[@]}" --namespace "${ns}" exec deploy/myapp --container myapp -- python -c \
      "import urllib.request; print(urllib.request.urlopen('http://myapp/', timeout=10).read().decode())" \
      2>/dev/null) && grep -qF "${text}" <<<"${body}" && return
    sleep 1
  done
  echo "${body}" >&2
  fail "page of ${ns}: ${text}"
}

rollout() {
  local ns=$1
  "${kube[@]}" --namespace "${ns}" rollout status deploy/myapp --timeout 300s >/dev/null || fail "rollout in ${ns}"
}

welcome='Welcome to the Pyjoyment real-time web framework!'

# The image of prod: generate dockerfile, with the wheel of the checkout in the
# project, as the image installs it
generate_app "${wheel}"
lock
python myapp.py generate dockerfile >/dev/null
build_dockerfile >/dev/null

# The manifests, of a project of the same script that has only the script,
# which takes the wheel from /wheel, as the ConfigMap of dev has the
# application and uv installs its dependencies
mkdir "${work}/dev"
cd "${work}/dev"
generate_app "/wheel/${wheel}"
python myapp.py generate kubernetes --image "${name}" >/dev/null
for file in base/kustomization.yaml base/deployment.yaml base/probes.yaml base/service.yaml prod/kustomization.yaml prod/deployment.yaml; do
  [[ -f kubernetes/${file} ]] || fail "kubernetes/${file}"
done
[[ $(cd kubernetes/dev/files && find . -type f) == ./myapp.py ]] || fail "copy of the application"
grep -q 'exec /uv/venv/bin/python myapp.py daemon"' kubernetes/dev/deployment.yaml || fail "daemon of dev"
ok "generated"

# An overlay of the test over the one of dev, which mounts the wheel in /wheel
overlay() {
  mkdir -p "${work}/$1"
  cat >"${work}/$1/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../dev/kubernetes/dev
patches:
  - path: wheel.yaml
EOF
  cat >"${work}/$1/wheel.yaml" <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
        - name: myapp
          volumeMounts:
            - name: wheel
              mountPath: /wheel
      volumes:
        - name: wheel
          hostPath:
            path: ${work}/wheel
            type: Directory
EOF
}

cat >"${work}/kind.yaml" <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraMounts:
      - hostPath: ${work}
        containerPath: ${work}
EOF
kind create cluster --name "${cluster}" --config "${work}/kind.yaml" ${KIND_NODE_IMAGE:+--image "${KIND_NODE_IMAGE}"} \
  --wait 5m --quiet
kind load docker-image "${name}" --name "${cluster}" >/dev/null
for ns in dev host-path prod; do
  "${kube[@]}" create namespace "${ns}" >/dev/null
done
ok "cluster"

# dev with the application in a ConfigMap, and a change of it in a new one
overlay dev-configmap
"${kube[@]}" --namespace dev apply --kustomize "${work}/dev-configmap" >/dev/null
rollout dev
page_has dev "${welcome}"
ok "dev with a ConfigMap"
perl -pi -e 's/Welcome to the Pyjoyment/Changed: Welcome to the Pyjoyment/' myapp.py
python myapp.py generate kubernetes >/dev/null
"${kube[@]}" --namespace dev apply --kustomize "${work}/dev-configmap" >/dev/null
rollout dev
page_has dev "Changed: ${welcome}"
[[ $("${kube[@]}" --namespace dev get configmap --output name | grep -c myapp-files) -eq 2 ]] || fail "new ConfigMap"
ok "dev with a new ConfigMap"

# dev with --host-path, reloaded when the script changes
python myapp.py generate kubernetes --host-path >/dev/null
[[ ! -e kubernetes/dev/files ]] || fail "no copy of the application"
grep -q 'Pyjo.Server.Reload myapp.py"' kubernetes/dev/deployment.yaml || fail "reload of dev"
overlay dev-host-path
"${kube[@]}" --namespace host-path apply --kustomize "${work}/dev-host-path" >/dev/null
rollout host-path
page_has host-path "Changed: ${welcome}"
ok "dev with --host-path"
perl -pi -e 's/Changed: /Reloaded: /' myapp.py
page_has host-path "Reloaded: ${welcome}"
ok "dev with --host-path reloaded"

# prod, with no failed request while it rolls out again, as the shutdown delay
# of the server keeps a pod serving until the proxies of the cluster know that
# it stops
"${kube[@]}" --namespace prod apply --kustomize kubernetes/prod >/dev/null
rollout prod
[[ $("${kube[@]}" --namespace prod get deploy/myapp --output jsonpath='{.status.readyReplicas}') -eq 2 ]] || fail "replicas"
page_has prod "${welcome}"
ok "prod"
"${kube[@]}" --namespace prod run requests --image "${name}" --image-pull-policy IfNotPresent --restart Never --command -- \
  python -c "
import time, urllib.request
ok = failed = 0
end = time.time() + 30
while time.time() < end:
    try:
        urllib.request.urlopen('http://myapp/', timeout=5).read()
        ok += 1
    except Exception as e:
        failed += 1
        print(e, flush=True)
    time.sleep(0.1)
print(f'ok={ok} failed={failed}')
" >/dev/null
"${kube[@]}" --namespace prod wait --for condition=Ready pod/requests --timeout 60s >/dev/null || fail "requests"
"${kube[@]}" --namespace prod rollout restart deploy/myapp >/dev/null
rollout prod
"${kube[@]}" --namespace prod wait --for jsonpath='{.status.phase}'=Succeeded pod/requests --timeout 60s >/dev/null ||
  fail "requests ended"
result=$("${kube[@]}" --namespace prod logs pod/requests | tail -n 1)
[[ ${result} =~ ^ok=[1-9][0-9]*\ failed=0$ ]] || fail "requests while it rolls out: ${result}"
ok "prod rolled out without a failed request: ${result}"
