#!/usr/bin/env bash
# Cursor start exports do not reach the agent shell, so SSH uses ProxyCommand.
set +x
set -euo pipefail

log() { printf 'cloud-env: %s\n' "$*" >&2; }

redact() {
  sed -E 's/tskey-[^[:space:]]+/[redacted]/g; s/-----BEGIN [^-]+ PRIVATE KEY-----/[redacted]/g'
}

HOST_ALIAS=home-ws01
HOST_FQDN=home-ws01.tail36bc2d.ts.net
SSH_USER=zhanfeng
SSH_KEY_PATH="${HOME}/.ssh/home_ws01"
SSH_CONFIG_PATH="${HOME}/.ssh/config"
SOCKS_ADDR=127.0.0.1
SOCKS_PORT=1055
HTTP_PROXY_PORT=1054
STATE_DIR=/var/lib/tailscale
HOSTNAME_FILE="${HOME}/.local/state/cursor-cloud-env/hostname"
MARKER_BEGIN="# BEGIN cursor-cloud-env"
MARKER_END="# END cursor-cloud-env"
TAILSCALE_TAG=tag:cursorcloud

find_nc() {
  local candidate
  for candidate in /usr/bin/nc.openbsd /bin/nc.openbsd /usr/bin/nc; do
    if [[ -x "$candidate" ]] && "$candidate" -h 2>&1 | grep -q -- '-X'; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  if command -v nc >/dev/null && nc -h 2>&1 | grep -q -- '-X'; then
    command -v nc
    return 0
  fi
  return 1
}

port_open() {
  local port=$1
  python3 - "$port" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
s.settimeout(0.3)
try:
    s.connect(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

userspace_proxies_up() {
  port_open "$HTTP_PROXY_PORT" && port_open "$SOCKS_PORT"
}

tailscaled_args_ok() {
  local args
  args=$(ps -o args= -C tailscaled 2>/dev/null || true)
  [[ "$args" == *"--tun=userspace-networking"* ]] \
    && [[ "$args" == *"--socks5-server="* ]] \
    && [[ "$args" == *"--outbound-http-proxy-listen="* ]]
}

ensure_tailscaled() {
  if pgrep -x tailscaled >/dev/null && tailscaled_args_ok && userspace_proxies_up; then
    return 0
  fi

  if pgrep -x tailscaled >/dev/null; then
    log "stopping a tailscaled that is not in userspace proxy mode"
    sudo pkill -x tailscaled || true
    sleep 0.2
  fi

  sudo mkdir -p "$STATE_DIR" /var/run/tailscale
  sudo setsid tailscaled \
    --tun=userspace-networking \
    --outbound-http-proxy-listen=localhost:${HTTP_PROXY_PORT} \
    --socks5-server=localhost:${SOCKS_PORT} \
    --statedir="$STATE_DIR" \
    >/tmp/tailscaled.log 2>&1 </dev/null &

  local i
  for i in $(seq 1 50); do
    if userspace_proxies_up; then
      return 0
    fi
    sleep 0.1
  done
  log "tailscaled proxies did not listen on ${HTTP_PROXY_PORT}/${SOCKS_PORT}; see /tmp/tailscaled.log"
}

backend_state() {
  sudo tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState",""))' || true
}

ensure_hostname() {
  mkdir -p "$(dirname "$HOSTNAME_FILE")"
  if [[ ! -s "$HOSTNAME_FILE" ]]; then
    python3 -c 'import secrets,string; alphabet=string.ascii_lowercase+string.digits; print("cursor-agent-"+"".join(secrets.choice(alphabet) for _ in range(8)))' >"$HOSTNAME_FILE"
  fi
  tr -d '\n' <"$HOSTNAME_FILE"
}

mint_oauth_authkey() {
  set +x
  python3 - "$TAILSCALE_TAG" <<'PY'
import json, os, sys, urllib.error, urllib.parse, urllib.request

def redact(text):
    import re
    return re.sub(r"tskey-[^\s\"']+", "[redacted]", text)

tag = sys.argv[1]
client_id = os.environ.get("TS_AUTHID", "")
client_secret = os.environ.get("TS_AUTHKEY", "").split("?", 1)[0]
if not client_id or not client_secret:
    sys.exit(1)

try:
    req = urllib.request.Request(
        "https://api.tailscale.com/api/v2/oauth/token",
        data=urllib.parse.urlencode(
            {"client_id": client_id, "client_secret": client_secret}
        ).encode(),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.load(resp).get("access_token", "")
    if not token:
        print("cloud-env: OAuth token response had no access_token", file=sys.stderr)
        sys.exit(1)
    body = json.dumps(
        {
            "capabilities": {
                "devices": {
                    "create": {
                        "reusable": False,
                        "ephemeral": True,
                        "preauthorized": True,
                        "tags": [tag],
                    }
                }
            },
            "expirySeconds": 3600,
            "description": "cursor-cloud-agent",
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.tailscale.com/api/v2/tailnet/-/keys",
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        key = json.load(resp).get("key", "")
    if not key:
        print("cloud-env: auth key response had no key", file=sys.stderr)
        sys.exit(1)
    sys.stdout.write(key)
except urllib.error.HTTPError as e:
    err = e.read().decode("utf-8", "replace")
    print("cloud-env: Tailscale API HTTP %s" % e.code, file=sys.stderr)
    print(redact(err), file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print("cloud-env: failed to mint auth key", file=sys.stderr)
    print(redact(str(e)), file=sys.stderr)
    sys.exit(1)
PY
}

ensure_tailscale_up() {
  set +x
  local state
  state=$(backend_state)
  if [[ "$state" == Running ]]; then
    return 0
  fi
  if [[ -z "${TS_AUTHKEY:-}" ]]; then
    log "TS_AUTHKEY is unset; skip tailscale up (add the OAuth client secret in Cursor Secrets)"
    return 0
  fi
  if [[ "${TS_AUTHKEY}" == tskey-client-* && -z "${TS_AUTHID:-}" ]]; then
    log "TS_AUTHID is unset; skip tailscale up (add the OAuth client ID in Cursor Secrets)"
    return 0
  fi

  export TS_AUTHKEY
  export TS_AUTHID="${TS_AUTHID:-}"
  local hn
  local -a up_args
  hn=$(ensure_hostname)
  up_args=(
    --hostname="$hn"
    --accept-dns=false
    --accept-routes=false
    --reset
  )
  if [[ "${TS_AUTHKEY}" == tskey-client-* ]]; then
    local minted
    minted=$(mint_oauth_authkey) || {
      log "failed to mint an auth key from TS_AUTHID and TS_AUTHKEY"
      return 0
    }
    if [[ -z "$minted" ]]; then
      log "failed to mint an auth key from TS_AUTHID and TS_AUTHKEY"
      return 0
    fi
    export TS_AUTHKEY="$minted"
  fi

  local tmp
  tmp=$(mktemp)
  if ! sudo --preserve-env=TS_AUTHKEY tailscale up "${up_args[@]}" >"$tmp" 2>&1; then
    log "tailscale up failed"
    redact <"$tmp" >&2 || true
  fi
  rm -f "$tmp"
}

write_ssh_key() {
  set +x
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  if [[ -z "${HOME_WS01_SSH_KEY:-}" ]]; then
    log "HOME_WS01_SSH_KEY is unset; skip SSH identity (add it in Cursor Secrets)"
    return 0
  fi
  local tmp old_umask
  tmp=$(mktemp "$HOME/.ssh/home_ws01.XXXXXX")
  old_umask=$(umask)
  umask 077
  printf '%s\n' "$HOME_WS01_SSH_KEY" >"$tmp"
  umask "$old_umask"
  chmod 600 "$tmp"
  mv "$tmp" "$SSH_KEY_PATH"
}

write_ssh_config() {
  local nc_bin
  if ! nc_bin=$(find_nc); then
    log "OpenBSD netcat (nc -X 5) is missing; skip SSH config"
    return 0
  fi
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  local block
  block=$(cat <<EOF
${MARKER_BEGIN}
Host ${HOST_ALIAS} ${HOST_FQDN}
  HostName ${HOST_FQDN}
  HostKeyAlias ${HOST_ALIAS}
  User ${SSH_USER}
  Port 22
  IdentityFile ${SSH_KEY_PATH}
  IdentitiesOnly yes
  PreferredAuthentications publickey
  PasswordAuthentication no
  StrictHostKeyChecking accept-new
  ProxyCommand ${nc_bin} -X 5 -x ${SOCKS_ADDR}:${SOCKS_PORT} %h %p
${MARKER_END}
EOF
)
  if [[ -f "$SSH_CONFIG_PATH" ]] && grep -q "$MARKER_BEGIN" "$SSH_CONFIG_PATH"; then
    local block_file
    block_file=$(mktemp)
    printf '%s\n' "$block" >"$block_file"
    python3 - "$SSH_CONFIG_PATH" "$MARKER_BEGIN" "$MARKER_END" "$block_file" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
begin, end = sys.argv[2], sys.argv[3]
block = pathlib.Path(sys.argv[4]).read_text().rstrip("\n")
text = path.read_text()
start = text.find(begin)
stop = text.find(end)
if start == -1 or stop == -1 or stop < start:
    sys.exit(1)
stop += len(end)
new = text[:start] + block + text[stop:]
path.write_text(new if new.endswith("\n") else new + "\n")
PY
    rm -f "$block_file"
  elif [[ -f "$SSH_CONFIG_PATH" ]]; then
    printf '\n%s\n' "$block" >>"$SSH_CONFIG_PATH"
  else
    printf '%s\n' "$block" >"$SSH_CONFIG_PATH"
  fi
  chmod 600 "$SSH_CONFIG_PATH"
}

ensure_tailscaled || log "ensure_tailscaled failed"
ensure_tailscale_up || log "ensure_tailscale_up failed"
write_ssh_key || log "write_ssh_key failed"
write_ssh_config || log "write_ssh_config failed"
exit 0
