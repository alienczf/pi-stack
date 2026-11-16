#!/usr/bin/env bash
set +x
set -uo pipefail

pass=0
fail=0

ok() { printf 'PASS  %s\n' "$1"; pass=$((pass + 1)); }
bad() { printf 'FAIL  %s\n' "$1"; fail=$((fail + 1)); }

step_tailscaled() {
  if ! pgrep -x tailscaled >/dev/null; then
    bad "tailscaled is not running"
    return
  fi
  local args
  args=$(ps -o args= -C tailscaled 2>/dev/null || true)
  if [[ "$args" != *"--tun=userspace-networking"* ]]; then
    bad "tailscaled is running but not with --tun=userspace-networking"
    return
  fi
  ok "tailscaled is up in userspace mode"
}

step_status() {
  local json state
  json=$(sudo tailscale status --json 2>/dev/null || true)
  if [[ -z "$json" ]]; then
    bad "tailscale status did not return JSON (is tailscaled up?)"
    return
  fi
  state=$(printf '%s' "$json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState",""))' || true)
  if [[ "$state" == Running ]]; then
    ok "tailscale status is connected (BackendState=Running)"
  else
    bad "tailscale status is not connected (BackendState=${state:-unknown}; pending TS_AUTHID or TS_AUTHKEY?)"
  fi
}

step_ssh() {
  if [[ ! -f "${HOME}/.ssh/home_ws01" ]]; then
    bad "ssh zhanfeng@home-ws01 pending secrets (HOME_WS01_SSH_KEY is missing)"
    return
  fi
  local out
  if out=$(ssh -o BatchMode=yes -o ConnectTimeout=10 zhanfeng@home-ws01 'whoami; hostname' 2>/dev/null); then
    ok "ssh zhanfeng@home-ws01 -> $(printf '%s' "$out" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  else
    bad "ssh zhanfeng@home-ws01 'whoami; hostname' failed"
  fi
}

step_tailscaled
step_status
step_ssh

printf '\n%s passed, %s failed\n' "$pass" "$fail"
if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
exit 0
